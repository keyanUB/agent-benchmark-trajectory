# BaxBench Behavior Taxonomy Artifact

This directory contains a generated taxonomy analysis of agent coding behavior
from BaxBench trajectories.

## Scope

- Source root: `data/raw/baxbench/runs/codex/gpt-5.4-mini/codex-cli-agent`
- Sample name: `sample_batch50`
- Runs analyzed: 90
- Observed behavior-bearing events before substantive filtering: 2131
- Analyzed substantive behavior events: 2052
- Excluded non-substantive residual events: 79

## Files

- `report.md`: research-method report and first-pass findings.
- `codebook.json`: formal two-axis taxonomy definitions.
- `labeled_events.csv`: event-level labels for analyzed substantive events.
- `run_summaries.csv`: per-run behavior counts and exclusion counts.
- `summary.json`: aggregate counts and transition statistics.

## Taxonomy Shape

Each analyzed event receives exactly one primary process label and zero or more
secondary attribute labels. Primary labels describe what the agent is doing in
the coding workflow. Secondary attributes describe cross-cutting concerns such
as defensive coding, dependency handling, sandbox constraints, or runtime
service constraints.

## Non-Substantive Residual Events

Some events pass the structural event filter but do not contain enough evidence
for a substantive coding-behavior label. These include generic progress
messages, bookkeeping-like command outputs, and weak-evidence fragments that
would otherwise require a forced or misleading category.

Those events are excluded as non-substantive residual events. They are counted
in `summary.json` and in each row of `run_summaries.csv` as
`excluded_non_substantive_events`, but they are omitted from
`labeled_events.csv` and from transition counts.
