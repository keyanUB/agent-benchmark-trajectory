#!/usr/bin/env python3
"""
Policy Extraction Script
Reads a PDF, TXT, or CSV document and uses GPT-4o-mini to extract structured policies.

Usage:
    python policy_extractor.py --input <path_to_file> --org <organization_name> [--output <output_json>]

Supported input formats:
    .pdf  — text extracted page-by-page via pdfplumber
    .txt  — read as-is (UTF-8, with Latin-1 fallback)
    .csv  — each row serialised as  "col1: val | col2: val | ..."  lines

Requirements:
    pip install openai pdfplumber tqdm
"""

import argparse
import csv
import json
import os
import sys
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("Installing pdfplumber...")
    os.system("pip install pdfplumber --break-system-packages -q")
    import pdfplumber

try:
    from openai import OpenAI
except ImportError:
    print("Installing openai...")
    os.system("pip install openai --break-system-packages -q")
    from openai import OpenAI

try:
    from tqdm import tqdm
except ImportError:
    # Fallback if tqdm not available
    def tqdm(iterable, **kwargs):
        return iterable


# ── Prompts ──────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a helpful policy extraction model to identify actionable policies from organizational safety guidelines. Your task is to exhaust all the potential policies from the provided organization handbook which sets restrictions or guidelines for user or entity behaviors in this organization. You will extract specific elements from the given guidelines to produce structured and actionable outputs."""

USER_PROMPT_TEMPLATE = """As a policy extraction model to clean up policies from {organization}, your tasks are:
1. Read and analyze the provided safety policies carefully, section by section.
2. Exhaust all actionable policies that are concrete and explicitly constrain behaviors.
3. For each policy, extract the following four elements:
   1. Definition: Any term definitions, boundaries, or interpretative descriptions for the policy to ensure it can be interpreted without any ambiguity. These definitions should be organized in a list.
   2. Scope: Conditions under which this policy is enforceable (e.g. time period, user group).
   3. Policy Description: The exact description of the policy detailing the restriction or guideline.
   4. Reference: All the referenced sources in the original policy article from which the policy elements were extracted. These sources should be organized piece by piece in a list.

Extraction Guidelines:
• Do not summarize, modify, or simplify any part of the original policy. Copy the exact descriptions.
• Ensure each extracted policy is self-contained and can be fully interpreted by looking at its Definition, Scope, and Policy Description.
• If the Definition or Scope is unclear, leave the value as None.
• Avoid grouping multiple policies into one block. Extract policies as individual pieces of statements.

Provide the output in the following JSON format:
```json
[
  {{
    "definition": ["Exact term definition or interpretive description."],
    "scope": "Conditions under which the policy is enforceable.",
    "policy_description": "Exact description of the policy.",
    "reference": ["Original source where the elements were extracted."]
  }},
  ...
]
```

Output Requirements:
- Each policy must focus on explicitly restricting or guiding behaviors.
- Ensure policies are actionable and clear.
- Do not combine unrelated statements into one policy block.
- Return ONLY valid JSON — no markdown fences, no preamble, no explanation.

Here is the policy document text to analyze:

{document_text}"""


# ── Document Loaders ─────────────────────────────────────────────────────────

def load_pdf(path: str) -> str:
    """Extract all text from a PDF file using pdfplumber."""
    text_parts = []
    with pdfplumber.open(path) as pdf:
        total = len(pdf.pages)
        print(f"[PDF] Extracting text from {total} pages...")
        for i, page in enumerate(tqdm(pdf.pages, desc="Reading pages", unit="page")):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(f"[Page {i + 1}]\n{page_text}")
    return "\n\n".join(text_parts)


def load_txt(path: str) -> str:
    """Read a plain-text file, falling back to Latin-1 if UTF-8 fails."""
    for encoding in ("utf-8", "latin-1"):
        try:
            with open(path, "r", encoding=encoding) as f:
                text = f.read()
            print(f"[TXT] Read {len(text):,} characters (encoding: {encoding}).")
            return text
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not decode {path} as UTF-8 or Latin-1.")


def load_csv(path: str, delimiter: str = ",") -> str:
    """
    Convert a CSV file to a readable text block.
    Each row becomes a line of  "Column: value | Column: value"  pairs,
    preceded by a row-number marker so the model can reference specific rows.
    """
    rows_text = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        # Sniff delimiter if auto-detection is needed
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel  # fallback
        reader = csv.DictReader(f, dialect=dialect)
        headers = reader.fieldnames or []
        print(f"[CSV] Columns: {headers}")
        for i, row in enumerate(reader, 1):
            pairs = " | ".join(f"{k}: {v}" for k, v in row.items() if v not in (None, ""))
            rows_text.append(f"[Row {i}] {pairs}")
    text = "\n".join(rows_text)
    print(f"[CSV] Converted {len(rows_text):,} rows to {len(text):,} characters.")
    return text


# Supported extensions → loader functions
LOADERS = {
    ".pdf": load_pdf,
    ".txt": load_txt,
    ".csv": load_csv,
}


def load_document(path: str) -> str:
    """Dispatch to the correct loader based on file extension."""
    ext = Path(path).suffix.lower()
    if ext not in LOADERS:
        raise ValueError(
            f"Unsupported file type '{ext}'. "
            f"Supported types: {', '.join(LOADERS)}"
        )
    return LOADERS[ext](path)


# ── Chunking ──────────────────────────────────────────────────────────────────

def chunk_text(text: str, max_chars: int = 60_000) -> list[str]:
    """
    Split text into chunks that fit within the model's context.
    Tries to split on double-newlines to preserve paragraph boundaries.
    """
    if len(text) <= max_chars:
        return [text]

    chunks = []
    current = []
    current_len = 0

    paragraphs = text.split("\n\n")
    for para in paragraphs:
        if current_len + len(para) + 2 > max_chars and current:
            chunks.append("\n\n".join(current))
            current = [para]
            current_len = len(para)
        else:
            current.append(para)
            current_len += len(para) + 2

    if current:
        chunks.append("\n\n".join(current))

    return chunks


# ── OpenAI Call ───────────────────────────────────────────────────────────────

def extract_policies_from_chunk(
    client: OpenAI,
    chunk: str,
    organization: str,
    model: str = "gpt-4o-mini",
) -> list[dict]:
    """Call the OpenAI API for a single text chunk and return parsed policies."""
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
        temperature=0,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content.strip()

    # Strip accidental markdown fences (```json ... ```)
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    parsed = json.loads(raw)

    # Model returned a top-level error key -- surface the message clearly
    if isinstance(parsed, dict) and "error" in parsed:
        raise ValueError(f"Model returned an error: {parsed['error']}")

    # Happy path: bare list
    if isinstance(parsed, list):
        return parsed

    # Model wrapped the array in a dict key (e.g. {"policies": [...]})
    for v in parsed.values():
        if isinstance(v, list):
            return v

    raise ValueError(f"Unexpected JSON structure from model: {list(parsed.keys())}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Extract structured policies from a document (PDF, TXT, or CSV) "
            "using GPT-4o-mini."
        )
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to the input file (.pdf, .txt, or .csv).",
    )
    parser.add_argument(
        "--org",
        default="the organization",
        help="Name of the organization (e.g. 'NIST', 'GitLab'). Default: 'the organization'.",
    )
    parser.add_argument(
        "--output",
        default="policies.json",
        help="Path for the output JSON file. Default: policies.json",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="OpenAI model to use. Default: gpt-4o-mini",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="OpenAI API key. Falls back to OPENAI_API_KEY env var.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=60_000,
        help="Max characters per chunk sent to the model. Default: 60000",
    )
    args = parser.parse_args()

    # Validate input path and extension
    input_path = Path(args.input)
    if not input_path.is_file():
        print(f"[ERROR] File not found: {args.input}")
        sys.exit(1)

    ext = input_path.suffix.lower()
    if ext not in LOADERS:
        print(f"[ERROR] Unsupported file type '{ext}'. Supported: {', '.join(LOADERS)}")
        sys.exit(1)

    # Set up OpenAI client
    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print(
            "[ERROR] No OpenAI API key found. "
            "Set OPENAI_API_KEY env var or pass --api-key."
        )
        sys.exit(1)
    client = OpenAI(api_key=api_key)

    # Load document text via the appropriate loader
    full_text = load_document(args.input)
    print(f"[Input] Total characters loaded: {len(full_text):,}")

    # Chunk
    chunks = chunk_text(full_text, max_chars=args.chunk_size)
    print(f"[Chunks] Split into {len(chunks)} chunk(s) for processing.")

    # Extract policies chunk by chunk
    all_policies: list[dict] = []
    for idx, chunk in enumerate(chunks, 1):
        print(f"\n[Model] Processing chunk {idx}/{len(chunks)} ({len(chunk):,} chars)...")
        try:
            policies = extract_policies_from_chunk(
                client=client,
                chunk=chunk,
                organization=args.org,
                model=args.model,
            )
            print(f"  → Extracted {len(policies)} policies from chunk {idx}.")
            all_policies.extend(policies)
        except Exception as e:
            print(f"  [WARNING] Failed to process chunk {idx}: {e}")
            print(f"  [DEBUG]   Check your API key, model name, and quota. Use --model gpt-4o-mini")

    # Deduplicate by policy_description (simple exact-match dedup)
    seen = set()
    unique_policies = []
    for p in all_policies:
        key = p.get("policy_description", "")
        if key not in seen:
            seen.add(key)
            unique_policies.append(p)

    print(f"\n[Result] Total unique policies extracted: {len(unique_policies)}")

    # Save output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(unique_policies, f, indent=2, ensure_ascii=False)

    print(f"[Output] Saved to: {output_path.resolve()}")

    # Print a preview of the first policy
    if unique_policies:
        print("\n── First Extracted Policy (preview) ──")
        print(json.dumps(unique_policies[0], indent=2))


if __name__ == "__main__":
    main()