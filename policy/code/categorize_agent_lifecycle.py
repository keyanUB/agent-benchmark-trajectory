#!/usr/bin/env python3
"""Categorize policy rows by agent operation lifecycle stage.

Input CSV columns expected:
- source_file, definition, scope, policy_description, reference

Output CSV adds:
- agent_stage_primary
- agent_stage_secondary
- agent_stage_reason
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path

STAGES = [
    "Perception/Input",
    "Memory Retrieval",
    "Reasoning/Planning",
    "Action/Tool Use",
    "Observation",
    "Memory Update",
    "Evaluation/Reflection",
    "Termination",
]

# Ordered by precision (specific first).
PATTERNS: dict[str, list[str]] = {
    "Perception/Input": [
        r"\bprompt injection\b",
        r"\buntrusted input\b",
        r"\buser input\b",
        r"\binput validation\b",
        r"\bsanitiz(?:e|ation|ing)\b",
        r"\bencoding\b",
        r"\bquery string\b",
        r"\brequest parameters?\b",
        r"\burl\b",
        r"\bfile upload\b",
        r"\binjection\b",
        r"\bprompt\b",
    ],
    "Memory Retrieval": [
        r"\bretriev(?:e|al)\b",
        r"\bknowledge base\b",
        r"\bvector(?: store)?\b",
        r"\bembedding\b",
        r"\bcontext( window)?\b",
        r"\bsource control metadata\b",
    ],
    "Reasoning/Planning": [
        r"\bthreat modeling\b",
        r"\brisk modeling\b",
        r"\battack surface\b",
        r"\bsecurity requirements?\b",
        r"\bdesign requirements?\b",
        r"\barchitecture\b",
        r"\bdesign review\b",
        r"\bdecision\b",
        r"\bpolicy\b",
        r"\bplan(?:ning)?\b",
    ],
    "Action/Tool Use": [
        r"\bextension(s)?\b",
        r"\bdownstream systems?\b",
        r"\boperating system calls?\b",
        r"\bshell command\b",
        r"\bexecute|execution\b",
        r"\bimplement\b",
        r"\bconfigure|configuration\b",
        r"\bdeploy(?:ment)?\b",
        r"\baccess controls?\b",
        r"\bauthorization\b",
        r"\brate-?limit(?:ing)?\b",
        r"\bguardrails?\b",
        r"\bpermissions?\b",
        r"\btoken(s)?\b",
        r"\bTLS|DTLS|WSS\b",
    ],
    "Observation": [
        r"\blog(?:ging)?\b",
        r"\bmonitor(?:ing)?\b",
        r"\baudit(?:ing)?\b",
        r"\btelemetry\b",
        r"\bdetect(?:ion)?\b",
        r"\balert(?:ing)?\b",
        r"\bvisibility\b",
    ],
    "Memory Update": [
        r"\bartifact data\b",
        r"\bretention\b",
        r"\bprovenance data\b",
        r"\brecords?\b",
        r"\bdocument(?:ed|ation)\b",
        r"\bmaintain\b",
        r"\bmetadata\b",
        r"\bshare provenance\b",
    ],
    "Evaluation/Reflection": [
        r"\bverif(?:y|ication)\b",
        r"\btest(?:ing)?\b",
        r"\bSAST|DAST|penetration\b",
        r"\bassess(?:ment)?\b",
        r"\breview\b",
        r"\banaly(?:ze|sis)\b",
        r"\bcompliance\b",
        r"\bvulnerabilit(?:y|ies)\b",
        r"\broot cause\b",
        r"\bexercise(s)?\b",
    ],
    "Termination": [
        r"\bsession termination\b",
        r"\blogout\b",
        r"\bexpiration\b",
        r"\brevok(?:e|ation)\b",
        r"\bdisallow any further use\b",
        r"\bdecommission\b",
    ],
}

DEFAULT_STAGE = "Action/Tool Use"


def rank_stages(text: str) -> tuple[str, list[str], str]:
    scores: dict[str, int] = defaultdict(int)
    hits: dict[str, list[str]] = defaultdict(list)

    for stage, patterns in PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, flags=re.IGNORECASE):
                scores[stage] += 1
                hits[stage].append(pattern)

    if not scores:
        return (
            DEFAULT_STAGE,
            [],
            "No strong agent-lifecycle cues; defaulted to concrete action/tool execution.",
        )

    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], STAGES.index(kv[0])))
    primary = ranked[0][0]

    secondary: list[str] = []
    for stage, score in ranked[1:]:
        if score >= max(1, ranked[0][1] - 1):
            secondary.append(stage)
        if len(secondary) == 2:
            break

    primary_hits = ", ".join(hits[primary][:3])
    reason = f"Primary cues: {primary_hits}."
    return primary, secondary, reason


def main() -> None:
    parser = argparse.ArgumentParser(description="Categorize policies by agent operation lifecycle stages.")
    parser.add_argument("--input", default="policy/code/combined_policies.csv", help="Input CSV path")
    parser.add_argument(
        "--output",
        default="policy/code/combined_policies_agent_lifecycle.csv",
        help="Output CSV path",
    )
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)

    with in_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    extra_fields = ["agent_stage_primary", "agent_stage_secondary", "agent_stage_reason"]
    out_fields = fieldnames + extra_fields

    for row in rows:
        text = " ".join(
            [
                row.get("definition", "") or "",
                row.get("scope", "") or "",
                row.get("policy_description", "") or "",
                row.get("reference", "") or "",
            ]
        )
        primary, secondary, reason = rank_stages(text)
        row["agent_stage_primary"] = primary
        row["agent_stage_secondary"] = "; ".join(secondary)
        row["agent_stage_reason"] = reason

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
