"""
deduplicate_policies.py — Remove near-duplicate policies across all sources.

Algorithm
---------
1. Load all policies from combined_policies_sdlc.csv.
2. Normalize each policy_description: lowercase + collapse whitespace.
3. Compare every pair (i, j) where i < j using difflib.SequenceMatcher.
   If the ratio exceeds THRESHOLD (0.92), policy j is flagged as a duplicate
   of policy i. Policy i (the earlier occurrence in file order) is kept.
   Once a policy is flagged as a duplicate it is not used as a canonical
   reference for further comparisons — only non-duplicate policies seed new
   duplicate groups.
4. Write a markdown report (duplicates_report.md) listing each duplicate
   group with full policy details and similarity scores.
5. Write a deduplicated copy to combined_policies_sdlc_deduped.csv.
   Original files are not modified.

Threshold justification
-----------------------
0.92 is the same threshold used in the extraction pipeline. At this level,
SequenceMatcher only matches policies whose normalized text is nearly
identical — differing by minor wording variation or punctuation. Semantically
related but distinctly worded policies score below this threshold and are
retained.

Comparison is done regardless of source or SDLC stage, so cross-source
near-duplicates (the same requirement extracted from two different standards)
are also caught.
"""

import csv
import re
from difflib import SequenceMatcher
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

THRESHOLD = 0.92
BASE = Path(__file__).parent
SDLC_CSV = BASE / "combined_policies_sdlc.csv"
REPORT_MD = BASE / "duplicates_report.md"
DEDUPED_CSV = BASE / "combined_policies_sdlc_deduped.csv"

# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

with open(SDLC_CSV, encoding="utf-8", newline="") as f:
    rows = list(csv.DictReader(f))

fieldnames = list(rows[0].keys())


# ---------------------------------------------------------------------------
# Normalize
# ---------------------------------------------------------------------------

def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


normalized = [normalize(r["policy_description"]) for r in rows]

# ---------------------------------------------------------------------------
# Pairwise duplicate detection
# ---------------------------------------------------------------------------
# duplicate_of[j] = i  means row j is a duplicate of row i (i < j)
# Only non-duplicate rows act as canonical references.

duplicate_of: dict[int, int] = {}

for i in range(len(rows)):
    if i in duplicate_of:
        continue  # i is itself a duplicate; skip as reference
    for j in range(i + 1, len(rows)):
        if j in duplicate_of:
            continue  # already flagged
        ratio = SequenceMatcher(None, normalized[i], normalized[j]).ratio()
        if ratio > THRESHOLD:
            duplicate_of[j] = i

# ---------------------------------------------------------------------------
# Build duplicate groups for the report
# ---------------------------------------------------------------------------
# group_for[i] = list of (j, ratio) that are duplicates of i

from collections import defaultdict
groups: dict[int, list[tuple[int, float]]] = defaultdict(list)
for j, i in duplicate_of.items():
    ratio = SequenceMatcher(None, normalized[i], normalized[j]).ratio()
    groups[i].append((j, ratio))

# ---------------------------------------------------------------------------
# Write markdown report
# ---------------------------------------------------------------------------

lines = [
    "# Duplicate Policy Report",
    "",
    f"Threshold: `SequenceMatcher ratio > {THRESHOLD}`  ",
    f"Total policies compared: {len(rows)}  ",
    f"Duplicate groups found: {len(groups)}  ",
    f"Policies removed: {len(duplicate_of)}  ",
    "",
    "---",
    "",
]

for canonical_idx, dups in sorted(groups.items()):
    canon = rows[canonical_idx]
    lines += [
        f"## Group — kept: `{canon['policy_id']}`",
        "",
        f"**Canonical** `{canon['policy_id']}` | source: `{canon['source']}` | "
        f"sdlc_stage: `{canon['sdlc_stage']}`  ",
        f"> {canon['policy_description']}",
        "",
    ]
    for dup_idx, ratio in sorted(dups, key=lambda x: -x[1]):
        dup = rows[dup_idx]
        lines += [
            f"**Duplicate** `{dup['policy_id']}` | source: `{dup['source']}` | "
            f"sdlc_stage: `{dup['sdlc_stage']}` | similarity: `{ratio:.4f}`  ",
            f"> {dup['policy_description']}",
            "",
        ]
    lines.append("---")
    lines.append("")

with open(REPORT_MD, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

# ---------------------------------------------------------------------------
# Write deduplicated CSV (original files are not modified)
# ---------------------------------------------------------------------------

dup_ids = {rows[j]["policy_id"] for j in duplicate_of}

filtered_rows = [r for r in rows if r["policy_id"] not in dup_ids]
with open(DEDUPED_CSV, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(filtered_rows)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

print(f"Policies before:  {len(rows)}")
print(f"Duplicates found: {len(duplicate_of)}")
print(f"Policies after:   {len(filtered_rows)}")
print(f"Duplicate groups: {len(groups)}")
print()
print(f"Report:      {REPORT_MD}")
print(f"Deduped CSV: {DEDUPED_CSV}")
print(f"Original CSV unchanged.")
