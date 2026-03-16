#!/usr/bin/env python3
"""
Adds a stable `policy_id` field to each extracted policy JSON file,
then regenerates combined_policies.json with IDs included.

ID format: <SOURCE_CODE>-<zero-padded-3-digit-seq>
Example:   ASVS-001, RMF-042, CWE-007
"""

import json
from pathlib import Path

EXTRACTED_DIR = Path("../extracted")
COMBINED_OUT  = EXTRACTED_DIR / "combined_policies.json"

SOURCE_CODES = {
    "OWASP_ASVS":              "ASVS",
    "OWASP_LLM_Top10":         "LLM",
    "OWASP_AI_Agent_Security": "AIAS",
    "CWE_Top25":               "CWE",
    "NIST_SP800218":           "SSDF",
    "NIST_AI_RMF":             "RMF",
    "PaloAlto_GenAI_Risk":     "PALO",
}

def add_ids():
    source_files = sorted(
        f for f in EXTRACTED_DIR.glob("*.json")
        if f.name != "combined_policies.json"
    )

    all_policies = []

    for fp in source_files:
        code = SOURCE_CODES.get(fp.stem, fp.stem.upper()[:6])
        policies = json.loads(fp.read_text(encoding="utf-8"))

        for i, policy in enumerate(policies, 1):
            policy["policy_id"] = f"{code}-{i:03d}"

        fp.write_text(json.dumps(policies, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  {fp.name}: {len(policies)} IDs added ({code}-001 … {code}-{len(policies):03d})")

        for p in policies:
            p_with_source = {"policy_id": p["policy_id"], "source": fp.stem, **p}
            all_policies.append(p_with_source)

    COMBINED_OUT.write_text(
        json.dumps(all_policies, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nCombined: {len(all_policies)} policies → {COMBINED_OUT}")

if __name__ == "__main__":
    add_ids()
