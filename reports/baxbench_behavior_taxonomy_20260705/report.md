# BaxBench Agent Coding Behavior Taxonomy

Generated: 2026-07-05T21:23:19.976216+00:00

## Research Objective

This artifact builds a first-pass taxonomy of coding-agent behaviors from the
current Codex BaxBench trajectories. The descriptive research questions are:

1. What observable behavior types appear during agent code-generation tasks?
2. How often do these behavior types occur across the current BaxBench sample?
3. What common behavior transitions characterize the coding process?
4. Which behaviors reflect environment constraints and adaptive workarounds?

## Data

- Source root: `data/raw/baxbench/runs/codex/gpt-5.4-mini/codex-cli-agent`
- Sample name: `sample_batch50`
- Runs analyzed: 80
- Included behavior events: 1929
- Agent/model family: Codex CLI trajectories using `gpt-5.4-mini`

The analysis uses `logs/steps.jsonl` from each run. Raw files are not edited.

## Annotation Protocol

Primary unit of analysis: a completed behavior-bearing event in `steps.jsonl`.
Included units are completed `agent_message`, `command_execution`, and
`file_change` events, plus `task.started` and `task.completed`. Thread/turn
bookkeeping and `tool_start` records are excluded to avoid double-counting.

The taxonomy is multi-label. A single event may represent, for example,
`failure_diagnosis`, `environment_constraint`, and `dependency_handling`.
The full label set is stored in `labeled_events.csv`; `primary_label` is only a
convenience column for sequence analysis.

## Codebook

The full formal codebook is available in `codebook.json`. It includes label
definitions, inclusion criteria, and exclusion criteria.

## Empirical Summary

### Most Frequent Labels

| behavior label | event count |
| --- | --- |
| task_orientation | 420 |
| workspace_inspection | 405 |
| security_safety | 365 |
| failure_diagnosis | 353 |
| verification_build | 323 |
| implementation_planning | 317 |
| code_generation | 300 |
| code_refinement | 223 |
| environment_constraint | 176 |
| toolchain_dependency_inspection | 161 |
| dependency_handling | 145 |
| final_reporting | 131 |
| other_observed_behavior | 110 |
| adaptation_workaround | 80 |
| verification_test | 18 |

### Common Label Transitions

| from | to | count |
| --- | --- | --- |
| workspace_inspection | workspace_inspection | 97 |
| failure_diagnosis | failure_diagnosis | 90 |
| final_reporting | final_reporting | 51 |
| code_refinement | failure_diagnosis | 47 |
| verification_build | failure_diagnosis | 47 |
| failure_diagnosis | code_refinement | 44 |
| workspace_inspection | security_safety | 41 |
| code_generation | code_generation | 38 |
| verification_build | workspace_inspection | 36 |
| task_orientation | verification_build | 32 |
| task_orientation | workspace_inspection | 31 |
| other_observed_behavior | failure_diagnosis | 30 |

### Suite-Level Patterns

| suite | top labels |
| --- | --- |
| Calculator | task_orientation=74, workspace_inspection=56, security_safety=49, implementation_planning=48, verification_build=46 |
| ClickCount | task_orientation=68, security_safety=67, workspace_inspection=66, implementation_planning=61, failure_diagnosis=60 |
| Compiler | failure_diagnosis=125, workspace_inspection=105, verification_build=92, task_orientation=86, implementation_planning=77 |
| CreditCardService | task_orientation=74, workspace_inspection=72, security_safety=72, code_generation=71, failure_diagnosis=54 |
| FileSearch | task_orientation=65, workspace_inspection=53, security_safety=45, implementation_planning=39, code_generation=34 |
| Forum | security_safety=56, task_orientation=53, workspace_inspection=53, verification_build=50, failure_diagnosis=42 |

## Interpretation

The current runs show a repeatable coding-agent workflow:

1. orient to the task and workspace;
2. inspect environment and framework availability;
3. generate service files;
4. refine correctness and safety behavior;
5. verify through builds, tests, or runtime probes;
6. diagnose failures;
7. adapt around missing dependencies, network limits, or sandbox limits;
8. report final artifacts and residual validation limits.

The strongest empirical signal in this batch is that environment adaptation is
not incidental. Missing frameworks, blocked network dependency resolution,
socket binding restrictions, unavailable binaries, and cache-permission issues
frequently shaped the resulting behavior sequence.

## Academic Rigor Assessment

This directory is suitable as a reproducible first-pass taxonomy artifact, but
it is not yet a finalized academic coding study. The deterministic labels make
the pipeline auditable and repeatable, but final publication-quality claims
should add human annotation.

Recommended next validation steps:

1. Stratify 15-20% of runs by suite and framework.
2. Have two annotators independently label the selected events using
   `codebook.json`.
3. Compute Cohen's kappa or Krippendorff's alpha for each label.
4. Adjudicate disagreements and revise the codebook once.
5. Freeze the codebook, then re-label all trajectories.
6. Link behavior patterns to artifact outcomes such as build success, runtime
   success, functional correctness, and security properties.

## Validity Threats

- Construct validity: deterministic text rules approximate behavior but may
  miss implicit intent.
- Internal validity: some behaviors are caused by local environment constraints,
  not only by the agent's coding strategy.
- External validity: all analyzed trajectories are from one agent/model family
  and one benchmark sample.
- Reliability: inter-annotator agreement has not yet been measured.
- Outcome validity: this report describes behavior frequency and sequence, but
  does not independently judge final code correctness/security.

## Generated Files

- `codebook.json`: formal taxonomy definitions and unit rules.
- `labeled_events.csv`: event-level labels with evidence previews.
- `run_summaries.csv`: one row per BaxBench run with label counts and sequence.
- `summary.json`: aggregate counts and transitions.
- `report.md`: this report.
