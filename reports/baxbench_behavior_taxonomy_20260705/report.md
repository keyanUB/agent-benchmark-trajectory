# BaxBench Agent Coding Behavior Taxonomy

Generated: 2026-07-07T22:26:50.026066+00:00

## Research Objective

This artifact builds a first-pass taxonomy of coding-agent behaviors from the
current Codex BaxBench trajectories. The descriptive research questions are:

1. What observable behavior types appear during agent coding tasks?
2. How often do these behavior types occur across the current BaxBench sample?
3. What common behavior transitions characterize the coding process?
4. Which behaviors reflect environment constraints and adaptive workarounds?

## Data

- Source root: `data/raw/baxbench/runs/codex/gpt-5.4-mini/codex-cli-agent`
- Sample name: `sample_batch50`
- Runs analyzed: 90
- Observed behavior-bearing events before substantive filtering: 2131
- Analyzed substantive behavior events: 2052
- Excluded non-substantive residual events: 79
- Agent/model family: Codex CLI trajectories using `gpt-5.4-mini`

The analysis uses `logs/steps.jsonl` from each run. Raw files are not edited.

## Revised Taxonomy Design

The taxonomy is now explicitly two-axis:

1. **Primary process label**: exactly one label describing what the agent is
   doing in the coding workflow.
2. **Secondary attribute labels**: zero or more orthogonal tags describing what
   the behavior concerns, such as defensive coding, dependency issues, sandbox
   constraints, or runtime-service constraints.

This design avoids double-counting concepts such as security behavior or
dependency handling as process steps. For example, a path-normalization edit is
primary process `refinement` with secondary attribute `defensive_coding`; a
Django fallback is primary process `adaptation` with secondary attributes
`dependency_related` and `environment_or_sandbox_constraint`.

## Answer to Research Question 1

**RQ1: What observable behavior types appear during agent coding tasks?**

At the primary-process level, the current BaxBench trajectories show twelve
observable behavior types:

1. **Orientation**: establishes task/workspace context.
2. **Inspection**: gathers information from files, commands, tools, or the
   local environment.
3. **Planning**: states or selects an implementation strategy.
4. **Implementation writing**: creates, updates, or deletes implementation
   artifacts.
5. **Refinement**: revises generated code for correctness, robustness, or
   edge cases.
6. **Static verification**: runs formatting, syntax, lint, or source-level
   checks.
7. **Build verification**: builds or compiles the generated project.
8. **Test verification**: runs automated tests or local test commands.
9. **Runtime verification**: starts services or probes live endpoint behavior.
10. **Failure observation/diagnosis**: observes or explains failed commands,
    errors, missing tools, or mismatches.
11. **Adaptation**: changes strategy in response to constraints or failed
    assumptions.
12. **Final reporting**: summarizes completed artifacts, validation steps, and
    residual limitations.

At the secondary-attribute level, four cross-cutting themes appear:

1. **Defensive coding**: validation, normalization, escaping, parameterization,
   size limits, and secret/permission-aware handling.
2. **Dependency related**: package, framework, compiler, module, or runtime
   availability and replacement.
3. **Environment or sandbox constraint**: network, permission, missing binary,
   cache, or socket-binding constraints.
4. **Runtime service constraint**: live service startup, HTTP probing, port
   binding, and process lifetime issues.

Thus, the agent's process is best characterized as an
inspect-plan-write-verify-repair-adapt workflow with cross-cutting defensive,
dependency, environment, and runtime-service concerns.

## Annotation Protocol

Primary unit of analysis: a completed behavior-bearing event in `steps.jsonl`.
Included units are completed `agent_message`, `command_execution`, and
`file_change` events, plus `task.started` and `task.completed`. Thread/turn
bookkeeping and `tool_start` records are excluded to avoid double-counting.

Events that pass this structural filter but do not contain enough substantive
evidence for a primary process label are excluded from the analysis as
`non_substantive_residual` events. This avoids forcing ambiguous bookkeeping,
generic progress, or weak-evidence messages into a misleading category. The
excluded count is reported above and in `summary.json`.

The full formal codebook is available in `codebook.json`.

## Empirical Summary

### Primary Process Counts

| primary process | event count |
| --- | --- |
| inspection | 416 |
| failure_observation_diagnosis | 355 |
| verification_build | 260 |
| refinement | 238 |
| implementation_writing | 158 |
| orientation | 148 |
| final_reporting | 146 |
| planning | 135 |
| adaptation | 95 |
| verification_static | 90 |
| verification_test | 9 |
| verification_runtime | 2 |

### Secondary Attribute Counts

| secondary attribute | event count |
| --- | --- |
| dependency_related | 426 |
| environment_or_sandbox_constraint | 277 |
| runtime_service_constraint | 217 |
| defensive_coding | 202 |

### Common Primary-Process Transitions

| from | to | count |
| --- | --- | --- |
| inspection | inspection | 162 |
| failure_observation_diagnosis | failure_observation_diagnosis | 105 |
| inspection | planning | 78 |
| verification_build | failure_observation_diagnosis | 70 |
| refinement | refinement | 66 |
| failure_observation_diagnosis | refinement | 65 |
| verification_build | inspection | 61 |
| final_reporting | final_reporting | 56 |
| planning | implementation_writing | 51 |
| refinement | failure_observation_diagnosis | 51 |
| implementation_writing | verification_build | 50 |
| failure_observation_diagnosis | verification_build | 49 |

### Suite-Level Primary Processes

| suite | top primary processes |
| --- | --- |
| Calculator | inspection=57, failure_observation_diagnosis=40, refinement=34, verification_build=34, orientation=25 |
| ClickCount | inspection=54, failure_observation_diagnosis=51, refinement=46, verification_build=37, final_reporting=26 |
| Compiler | failure_observation_diagnosis=119, inspection=81, verification_build=72, refinement=53, adaptation=36 |
| CreditCardService | inspection=67, implementation_writing=47, failure_observation_diagnosis=47, verification_build=36, refinement=32 |
| FileSearch | inspection=48, verification_build=28, orientation=26, refinement=25, failure_observation_diagnosis=25 |
| Forum | inspection=86, failure_observation_diagnosis=55, verification_build=40, refinement=39, orientation=23 |
| FrameExtract | inspection=23, failure_observation_diagnosis=18, verification_build=13, refinement=9, orientation=8 |

## Interpretation

The revised taxonomy indicates that agent coding behavior is not reducible to
implementation writing. The most frequent process behaviors are inspection,
failure observation/diagnosis, build verification, refinement, implementation
writing, and orientation. Security-relevant behavior appears primarily as a
cross-cutting attribute, not as a standalone workflow stage.

From a computer-security research perspective, this is important: defensive
behavior should be analyzed by where it occurs in the workflow. Defensive
planning, defensive implementation writing, defensive refinement, and defensive
verification represent different kinds of agent competence.

## Academic Rigor Assessment

This directory is suitable as a reproducible first-pass taxonomy artifact, but
it is not yet a finalized academic coding study. The deterministic labels make
the pipeline auditable and repeatable, but final publication-quality claims
should add human annotation.

Recommended next validation steps:

1. Stratify 15-20% of runs by suite and framework.
2. Have two annotators independently label the selected events using
   `codebook.json`.
3. Compute Cohen's kappa or Krippendorff's alpha separately for primary process
   labels and secondary attributes.
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

- `codebook.json`: formal two-axis taxonomy definitions and unit rules.
- `labeled_events.csv`: event-level process labels, attributes, and evidence previews.
- `run_summaries.csv`: one row per BaxBench run with process and attribute counts.
- `summary.json`: aggregate counts and process transitions.
- `README.md`: artifact usage notes and the non-substantive exclusion rule.
- `report.md`: this report.
