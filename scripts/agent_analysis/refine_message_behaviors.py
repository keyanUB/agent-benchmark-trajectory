#!/usr/bin/env python3
"""Refine broad message tokens in the curated trajectory sequence CSV."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_PATH = Path("data/processed/trajectory_sequences.csv")


CODE_HINT_RE = re.compile(
    r'(^```|"code"\s*:|#include\s+<|\bdef\s+\w+\(|\bclass\s+\w+|\bfunction\s+\w+|\bimport\s+\w+|\bconst\s+\w+|\bpackage\s+main\b)',
    re.IGNORECASE | re.DOTALL,
)


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader), list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def classify_message(event: dict[str, Any]) -> str:
    token = str(event.get("token", ""))
    if not token.startswith("message"):
        return str(event.get("detailed_token") or token)

    preview = str(event.get("preview") or "").strip()
    lower = preview.lower()
    native = str(event.get("native_event_type") or "")
    actor = str(event.get("actor") or "")

    if not preview:
        if native == "llm_call":
            return "message_llm_call"
        return "message_unknown"
    if "task:" in lower and ("you are an expert software developer" in lower or "implementation details" in lower):
        return "message_task_prompt"
    if lower.startswith("**summary**") or "**testing**" in lower or lower.startswith("summary"):
        return "message_summary"
    if lower.startswith("preamble:") or lower.startswith("i’m about to") or lower.startswith("i'm about to") or lower.startswith("i will "):
        return "message_plan_or_preamble"
    if CODE_HINT_RE.search(preview):
        return "message_code_answer"
    if "api_error_status" in lower or "is_error" in lower or token.endswith(":error"):
        return "message_status_or_error"
    if actor == "user":
        return "message_task_prompt"
    return "message_other"


def update_row(row: dict[str, str]) -> dict[str, str]:
    events = json.loads(row.get("event_details_json") or "[]")
    detailed_tokens: list[str] = []
    message_subtypes: list[str] = []
    for event in events:
        token = str(event.get("token") or "")
        detailed = str(event.get("detailed_token") or token)
        if token.startswith("message"):
            detailed = classify_message(event)
            event["message_subtype"] = detailed
            message_subtypes.append(detailed)
        event["detailed_token"] = detailed
        if token:
            detailed_tokens.append(detailed)

    row["event_details_json"] = json.dumps(events, ensure_ascii=False, sort_keys=True)
    row["detailed_behavior_sequence"] = " > ".join(detailed_tokens)
    row["message_sequence"] = " > ".join(message_subtypes)
    row["message_types_called"] = ", ".join(sorted(set(message_subtypes)))
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()

    rows, fieldnames = read_csv(args.path)
    for name in ["message_sequence", "message_types_called"]:
        if name not in fieldnames:
            insert_at = fieldnames.index("tool_calls_json") if "tool_calls_json" in fieldnames else len(fieldnames)
            fieldnames.insert(insert_at, name)

    updated = [update_row(row) for row in rows]
    write_csv(args.path, updated, fieldnames)
    print(f"Refined message behavior tokens in {args.path} ({len(updated)} rows)")


if __name__ == "__main__":
    main()
