#!/usr/bin/env python3
"""
Categorize all policies in combined_policies.json by SDLC stage.
Uses the prompts defined in policy_categorizer.md.
Output: policy/extracted/combined_policies_sdlc.csv

Usage:
    python categorize_sdlc.py
    ANTHROPIC_API_KEY must be set in environment.
"""

import csv
import json
import os
import sys
from collections import Counter
from pathlib import Path

import anthropic

EXTRACTED = Path("../extracted")
INPUT     = EXTRACTED / "combined_policies.json"
OUT_CSV   = EXTRACTED / "combined_policies_sdlc.csv"

MODEL = "claude-opus-4-6"

SYSTEM_PROMPT = """\
You are an expert in secure software development lifecycle (SDLC) frameworks, such as NIST SSDF. \
Your task is to analyze organizational security policies and accurately categorize each one into \
its primary SDLC stage.

SDLC STAGES
The following are the lifecycle stages used for categorization:
1. Planning
2. Requirements Analysis
3. Design
4. Implementation
5. Testing
6. Deployment
7. Maintenance
8. Not Applicable — use this when the policy is administrative, procedural, or meta-level \
(e.g., framework versioning, licensing, organizational governance) and does not govern any \
software development activity.

INSTRUCTIONS
For each policy provided:
1. Read the policy_description and scope carefully.
2. Identify the primary SDLC stage it governs — the stage where the policy has its greatest \
enforcement or impact.
3. If the policy clearly spans multiple stages, assign it to the stage where it is first enforced \
or has the most critical application.
4. If the policy is administrative or meta-level and does not apply to any software development \
activity, assign "Not Applicable".
5. Output your response strictly in the JSON format specified below.

OUTPUT FORMAT
Return a JSON object with a single key "categorizations" containing an array. Each object must contain:
- policy_id: the identifier provided with the policy
- stage: the assigned SDLC stage (must exactly match one of the stage names provided above)
- confidence: your confidence in this categorization — "high", "medium", or "low"
- rationale: a 1-2 sentence explanation of why this stage was chosen
- secondary_stages: an array of any other stages this policy is relevant to (can be empty)

EXAMPLE OUTPUT
{
  "categorizations": [
    {
      "policy_id": "ASVS-042",
      "stage": "Implementation",
      "confidence": "high",
      "rationale": "This policy mandates the use of SAST tools during code writing and pre-commit checks, making Implementation its primary enforcement point.",
      "secondary_stages": ["Testing"]
    },
    {
      "policy_id": "RMF-001",
      "stage": "Not Applicable",
      "confidence": "high",
      "rationale": "This policy describes NIST's internal review schedule for the framework itself and does not govern any software development activity.",
      "secondary_stages": []
    }
  ]
}

HANDLING AMBIGUITY
- If a policy is too vague to categorize with confidence, set confidence to "low" and explain \
the ambiguity in rationale.
- Do not invent or infer policy intent beyond what is written.
- Do not create new stage names — only use the stages listed above.\
"""


def build_user_message(policies: list[dict]) -> str:
    slim = [
        {
            "policy_id":          p["policy_id"],
            "policy_description": p["policy_description"],
            "scope":              p.get("scope"),
        }
        for p in policies
    ]
    return (
        "Please categorize all policies in the following JSON. "
        "Each policy object contains a policy_id, policy_description, and scope. "
        "Return one categorization entry per policy, in the same order as the input.\n\n"
        + json.dumps(slim, ensure_ascii=False)
    )


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY not set.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    policies = json.loads(INPUT.read_text(encoding="utf-8"))
    print(f"[Input] {len(policies)} policies loaded from {INPUT}")

    user_message = build_user_message(policies)
    print(f"[Request] Sending {len(user_message):,} chars to {MODEL}...")

    response = client.messages.create(
        model=MODEL,
        max_tokens=8096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text.strip()

    # Strip accidental markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    parsed = json.loads(raw)

    if "categorizations" not in parsed:
        print(f"[ERROR] Missing 'categorizations' key. Keys found: {list(parsed.keys())}")
        sys.exit(1)

    cats: list[dict] = parsed["categorizations"]
    print(f"[Response] Received {len(cats)} categorizations.")

    cat_map = {c["policy_id"]: c for c in cats}

    # Merge and write CSV
    fields = [
        "policy_id", "source", "sdlc_stage", "sdlc_confidence",
        "sdlc_secondary_stages", "sdlc_rationale",
        "scope", "policy_description", "reference",
    ]
    rows = []
    missing = []

    for p in policies:
        pid = p["policy_id"]
        c = cat_map.get(pid)
        if not c:
            missing.append(pid)
            continue
        rows.append({
            "policy_id":              pid,
            "source":                 p.get("source", ""),
            "sdlc_stage":             c["stage"],
            "sdlc_confidence":        c["confidence"],
            "sdlc_secondary_stages":  "; ".join(c.get("secondary_stages", [])),
            "sdlc_rationale":         c["rationale"],
            "scope":                  p.get("scope", "") or "",
            "policy_description":     p["policy_description"],
            "reference":              "; ".join(
                p["reference"] if isinstance(p.get("reference"), list)
                else [str(p.get("reference", ""))]
            ),
        })

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[Output] Saved {len(rows)} rows → {OUT_CSV}")

    if missing:
        print(f"[WARNING] {len(missing)} policies with no categorization: {missing[:10]}")

    # Statistics
    stage_counts = Counter(r["sdlc_stage"] for r in rows)
    conf_counts  = Counter(r["sdlc_confidence"] for r in rows)
    src_stage    = {}
    for r in rows:
        src_stage.setdefault(r["source"], Counter())[r["sdlc_stage"]] += 1

    print("\n=== SDLC Stage Distribution ===")
    for stage, n in sorted(stage_counts.items(), key=lambda x: -x[1]):
        bar = "█" * (n // 10)
        print(f"  {stage:<25} {n:3d}  ({100 * n / len(rows):5.1f}%)  {bar}")

    print("\n=== Confidence ===")
    for conf, n in sorted(conf_counts.items()):
        print(f"  {conf:<10} {n:3d}  ({100 * n / len(rows):.1f}%)")

    print("\n=== Stage breakdown per source ===")
    for src, counts in sorted(src_stage.items()):
        top = counts.most_common(3)
        top_str = ", ".join(f"{s}:{n}" for s, n in top)
        print(f"  {src:<30} {top_str}")

    print(f"\nTotal categorized: {len(rows)}")


if __name__ == "__main__":
    main()
