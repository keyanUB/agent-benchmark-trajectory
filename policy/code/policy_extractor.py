#!/usr/bin/env python3
"""
Policy Extraction Script (v2)
Reads a PDF, TXT, or CSV document and uses an OpenAI model to extract structured policies.

Extraction schema (definition, scope, policy_description, reference) is adapted from
ShieldAgent Stage 1 (Chen, Kang, Li — ICML 2025; arXiv:2503.22738).
See docs/methods.md §1 for full credit and design rationale.

Usage:
    python policy_extractor.py --input <path> --org <name> [--output <file.json>]

Supported input formats:
    .pdf  — text extracted page-by-page via pdfplumber
    .txt  — read as-is (UTF-8, with Latin-1 fallback)
    .csv  — each row serialised as "col1: val | col2: val | ..." lines

Requirements:
    pip install openai pdfplumber tqdm

Updates in v2 (see docs/methods.md §1.2):
    - Structured output prompt requests {"policies": [...]} object for reliable json_object parsing
    - Default model gpt-5-mini for higher verbatim extraction fidelity on dense security standards
    - Chunk overlap (last N paragraphs carried forward) preserves section heading context
    - Two-pass deduplication: normalized exact-match + SequenceMatcher near-duplicate detection
"""

import argparse
import csv
import json
import os
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    os.system("pip install pdfplumber --break-system-packages -q")
    import pdfplumber

try:
    from openai import OpenAI
except ImportError:
    os.system("pip install openai --break-system-packages -q")
    from openai import OpenAI

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):
        return iterable


# ── Prompts ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You are a security policy extraction model. Your task is to identify every "
    "actionable policy from a provided security standard or guideline document. "
    "You extract structured records that can later be used to govern software agent behavior."
)

USER_PROMPT_TEMPLATE = """\
Extract all actionable security policies from the following excerpt of the {organization} document.

For each policy, extract exactly these four fields:
  1. definition  — Any term definitions, boundaries, or interpretive descriptions needed to
                   understand the policy unambiguously. Provide as a list of strings.
                   If none are needed, use an empty list.
  2. scope       — The conditions under which this policy applies (user group, system type,
                   lifecycle phase, etc.). Use null if not specified.
  3. policy_description — The exact policy statement as written in the source. Do NOT
                          paraphrase, summarize, or simplify. Copy the original wording.
  4. reference   — All source identifiers cited in or near this policy (section numbers,
                   standard IDs, version numbers). Provide as a list of strings.

Extraction rules:
- Extract every distinct actionable policy. Do not skip policies to save space.
- Each policy record must be self-contained: a reader should be able to understand and
  apply the policy using only its four fields.
- Do not merge multiple policies into one record.
- Do not invent or infer policies not explicitly stated in the text.

Return a JSON object in exactly this format:
{{
  "policies": [
    {{
      "definition": ["..."],
      "scope": "...",
      "policy_description": "...",
      "reference": ["..."]
    }}
  ]
}}

Document excerpt:
{document_text}"""


# ── Document Loaders ──────────────────────────────────────────────────────────

def load_pdf(path: str) -> str:
    text_parts = []
    with pdfplumber.open(path) as pdf:
        print(f"[PDF] Extracting text from {len(pdf.pages)} pages...")
        for i, page in enumerate(tqdm(pdf.pages, desc="Reading pages", unit="page")):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(f"[Page {i + 1}]\n{page_text}")
    return "\n\n".join(text_parts)


def load_txt(path: str) -> str:
    for encoding in ("utf-8", "latin-1"):
        try:
            with open(path, "r", encoding=encoding) as f:
                text = f.read()
            print(f"[TXT] Read {len(text):,} characters (encoding: {encoding}).")
            return text
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not decode {path} as UTF-8 or Latin-1.")


def load_csv(path: str) -> str:
    rows_text = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(f, dialect=dialect)
        print(f"[CSV] Columns: {reader.fieldnames}")
        for i, row in enumerate(reader, 1):
            pairs = " | ".join(f"{k}: {v}" for k, v in row.items() if v not in (None, ""))
            rows_text.append(f"[Row {i}] {pairs}")
    text = "\n".join(rows_text)
    print(f"[CSV] Converted {len(rows_text):,} rows ({len(text):,} chars).")
    return text


LOADERS = {".pdf": load_pdf, ".txt": load_txt, ".csv": load_csv}


def load_document(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext not in LOADERS:
        raise ValueError(f"Unsupported file type '{ext}'. Supported: {', '.join(LOADERS)}")
    return LOADERS[ext](path)


# ── Chunking with overlap ─────────────────────────────────────────────────────

def chunk_text(text: str, max_chars: int = 60_000, overlap_paragraphs: int = 3) -> list[str]:
    """
    Split text into chunks fitting within max_chars.
    Carries the last `overlap_paragraphs` paragraphs of each chunk forward as
    a prefix for the next, preserving section heading context across boundaries.
    """
    paragraphs = text.split("\n\n")

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para) + 2  # +2 for the "\n\n" separator
        if current_len + para_len > max_chars and current:
            chunks.append("\n\n".join(current))
            # Carry forward the last N paragraphs as overlap
            overlap = current[-overlap_paragraphs:] if len(current) >= overlap_paragraphs else current[:]
            current = overlap + [para]
            current_len = sum(len(p) + 2 for p in current)
        else:
            current.append(para)
            current_len += para_len

    if current:
        chunks.append("\n\n".join(current))

    return chunks


# ── OpenAI Extraction ─────────────────────────────────────────────────────────

def extract_policies_from_chunk(
    client: OpenAI,
    chunk: str,
    organization: str,
    model: str,
) -> list[dict]:
    """Send one chunk to the model and return the list of extracted policy dicts."""
    user_prompt = USER_PROMPT_TEMPLATE.format(
        organization=organization,
        document_text=chunk,
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content.strip()
    parsed = json.loads(raw)

    if "policies" not in parsed:
        raise ValueError(f"Model response missing 'policies' key. Keys found: {list(parsed.keys())}")

    policies = parsed["policies"]
    if not isinstance(policies, list):
        raise ValueError(f"'policies' value is not a list: {type(policies)}")

    return policies


# ── Deduplication ─────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Lowercase and collapse whitespace for comparison."""
    return re.sub(r"\s+", " ", text.lower().strip())


def deduplicate(policies: list[dict], similarity_threshold: float = 0.92) -> list[dict]:
    """
    Two-pass deduplication (see docs/methods.md §1.2, Fix 4):
      Pass 1 — exact match on normalized policy_description.
      Pass 2 — near-duplicate detection via SequenceMatcher ratio >= threshold.
    Returns deduplicated list preserving first-seen order.
    """
    accepted: list[dict] = []
    accepted_normalized: list[str] = []

    for policy in policies:
        desc = policy.get("policy_description", "")
        norm = _normalize(desc)

        # Pass 1: exact match
        if norm in accepted_normalized:
            continue

        # Pass 2: near-duplicate
        is_near_dup = any(
            SequenceMatcher(None, norm, existing).ratio() >= similarity_threshold
            for existing in accepted_normalized
        )
        if is_near_dup:
            continue

        accepted.append(policy)
        accepted_normalized.append(norm)

    return accepted


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Extract structured security policies from a document (PDF, TXT, CSV)."
    )
    parser.add_argument("--input", required=True, help="Path to input file (.pdf, .txt, .csv).")
    parser.add_argument("--org", default="the organization",
                        help="Organization or standard name (e.g. 'NIST', 'OWASP').")
    parser.add_argument("--output", default="policies.json",
                        help="Output JSON file path. Default: policies.json")
    parser.add_argument("--model", default="gpt-5-mini",
                        help="OpenAI model. Default: gpt-5-mini")
    parser.add_argument("--api-key", default=None,
                        help="OpenAI API key. Falls back to OPENAI_API_KEY env var.")
    parser.add_argument("--chunk-size", type=int, default=60_000,
                        help="Max characters per chunk. Default: 60000")
    parser.add_argument("--overlap-paragraphs", type=int, default=3,
                        help="Paragraphs carried forward as overlap between chunks. Default: 3")
    parser.add_argument("--similarity-threshold", type=float, default=0.92,
                        help="SequenceMatcher ratio for near-duplicate detection. Default: 0.92")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_file():
        print(f"[ERROR] File not found: {args.input}")
        sys.exit(1)
    if input_path.suffix.lower() not in LOADERS:
        print(f"[ERROR] Unsupported file type. Supported: {', '.join(LOADERS)}")
        sys.exit(1)

    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("[ERROR] No OpenAI API key. Set OPENAI_API_KEY or pass --api-key.")
        sys.exit(1)
    client = OpenAI(api_key=api_key)

    full_text = load_document(args.input)
    print(f"[Input] {len(full_text):,} characters loaded.")

    chunks = chunk_text(full_text, max_chars=args.chunk_size,
                        overlap_paragraphs=args.overlap_paragraphs)
    print(f"[Chunks] {len(chunks)} chunk(s) (overlap: {args.overlap_paragraphs} paragraphs).")

    all_policies: list[dict] = []
    for idx, chunk in enumerate(chunks, 1):
        print(f"\n[Model] Chunk {idx}/{len(chunks)} ({len(chunk):,} chars) → {args.model}...")
        try:
            policies = extract_policies_from_chunk(client, chunk, args.org, args.model)
            print(f"  Extracted {len(policies)} policies.")
            all_policies.extend(policies)
        except Exception as e:
            print(f"  [WARNING] Chunk {idx} failed: {e}")

    before = len(all_policies)
    unique_policies = deduplicate(all_policies, args.similarity_threshold)
    after = len(unique_policies)
    print(f"\n[Dedup] {before} raw → {after} unique ({before - after} removed, "
          f"threshold={args.similarity_threshold}).")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(unique_policies, f, indent=2, ensure_ascii=False)
    print(f"[Output] Saved to: {output_path.resolve()}")

    if unique_policies:
        print("\n── First policy (preview) ──")
        print(json.dumps(unique_policies[0], indent=2))


if __name__ == "__main__":
    main()
