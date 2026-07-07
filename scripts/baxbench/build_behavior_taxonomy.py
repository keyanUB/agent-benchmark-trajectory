#!/usr/bin/env python3
"""Build a two-axis behavior taxonomy from BaxBench Codex trajectories.

The taxonomy separates:
  1. primary process labels: what the agent is doing
  2. secondary attribute labels: what the behavior is about

This avoids treating security, dependency, and environment context as duplicate
process steps. Those concepts are orthogonal attributes that can attach to
inspection, implementation writing, refinement, verification, diagnosis, or
adaptation events.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path("data/raw/baxbench/runs/codex/gpt-5.4-mini/codex-cli-agent")
DEFAULT_SAMPLE = "sample_batch50"
DEFAULT_OUT = Path("reports/baxbench_behavior_taxonomy_20260705")

INCLUDED_TOOLS = {"agent_message", "command_execution", "file_change"}
INCLUDED_TASK_TYPES = {"task.started", "task.completed"}


@dataclass(frozen=True)
class LabelDef:
    """Codebook entry with criteria needed for human review."""

    label: str
    definition: str
    include: str
    exclude: str


PRIMARY_CODEBOOK: list[LabelDef] = [
    LabelDef(
        "orientation",
        "The agent establishes task/workspace context before implementation.",
        "Initial context checks, scaffold checks, prompt-to-workspace framing.",
        "Concrete file/tool inspection commands, which are inspection.",
    ),
    LabelDef(
        "inspection",
        "The agent gathers information from files, tools, commands, or the local environment.",
        "Workspace reads, source reads, git status, toolchain discovery, package-cache checks.",
        "Strategic change after a constraint, which is adaptation.",
    ),
    LabelDef(
        "planning",
        "The agent states or selects an implementation strategy.",
        "Messages describing intended architecture, file layout, endpoint design, or next coding step.",
        "Final summaries and factual command output.",
    ),
    LabelDef(
        "implementation_writing",
        "The agent creates, updates, or deletes source/configuration artifacts.",
        "File-change events that add, update, or delete implementation artifacts.",
        "Later correctness repairs explicitly triggered by review or failure, which are refinement.",
    ),
    LabelDef(
        "refinement",
        "The agent revises code after initial construction for correctness or robustness.",
        "Fixes to validation, status codes, edge cases, persistence, routes, build errors, or tests.",
        "First-pass implementation writing.",
    ),
    LabelDef(
        "verification_static",
        "The agent runs formatting, lint, syntax, or source-level checks.",
        "gofmt, py_compile, syntax-only compilers, tsc --noEmit, source-level checks.",
        "Full project builds, tests, and live service probes.",
    ),
    LabelDef(
        "verification_build",
        "The agent builds or compiles the generated project.",
        "go build, cargo build, npm run build, tsc project build, javac/gcc/g++ project checks.",
        "Unit tests and live HTTP probes.",
    ),
    LabelDef(
        "verification_test",
        "The agent runs an automated test suite or local test command.",
        "pytest, unittest, go test, npm test, jest, vitest, rails test, rspec, phpunit.",
        "Build-only commands and manual curl probes.",
    ),
    LabelDef(
        "verification_runtime",
        "The agent starts or probes live runtime behavior.",
        "Server startup, curl/http requests, runserver, port binding, endpoint smoke tests.",
        "Static checks and non-running builds.",
    ),
    LabelDef(
        "failure_observation_diagnosis",
        "The agent observes, records, or explains an error, failed command, or mismatch.",
        "Failed verification, missing-tool output, traceback/error output, explanatory diagnosis messages.",
        "Successful verification and ordinary implementation work.",
    ),
    LabelDef(
        "adaptation",
        "The agent changes strategy in response to constraints or failed assumptions.",
        "Fallback to standard library, local compatibility layers, dependency replacement, cache relocation.",
        "Minor code fixes that do not alter strategy.",
    ),
    LabelDef(
        "final_reporting",
        "The agent summarizes completed work, validation, artifacts, or residual limitations.",
        "Final assistant message and task.completed records.",
        "Interim progress messages.",
    ),
]


ATTRIBUTE_CODEBOOK: list[LabelDef] = [
    LabelDef(
        "defensive_coding",
        "The behavior concerns security- or robustness-relevant implementation choices.",
        "Input validation, path normalization, SQL parameterization, escaping, size limits, secret handling.",
        "Generic implementation work without defensive relevance.",
    ),
    LabelDef(
        "dependency_related",
        "The behavior concerns package, framework, compiler, module, or runtime dependencies.",
        "Dependency discovery, module-cache checks, missing framework diagnosis, package fallback.",
        "General workspace inspection unrelated to dependencies.",
    ),
    LabelDef(
        "environment_or_sandbox_constraint",
        "The behavior concerns constraints imposed by the local environment or sandbox.",
        "Blocked network, missing binaries, permission errors, unwritable caches, bind/socket denial.",
        "Ordinary application bugs not caused by the environment.",
    ),
    LabelDef(
        "runtime_service_constraint",
        "The behavior concerns live service startup, HTTP probing, process lifetime, or port binding.",
        "curl probes, runserver behavior, socket bind failures, background process checks.",
        "Static compilation and unit tests.",
    ),
]


PRIMARY_PRIORITY = [
    "final_reporting",
    "adaptation",
    "failure_observation_diagnosis",
    "verification_runtime",
    "verification_test",
    "verification_build",
    "verification_static",
    "refinement",
    "implementation_writing",
    "planning",
    "inspection",
    "orientation",
]

ERROR_RE = re.compile(
    r"\b(error|exception|traceback|failed|failure|not found|no such|missing|permission denied|"
    r"operation not permitted|cannot|unavailable|blocked|denied|module not found|command not found)\b",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    """Parse CLI options for reproducible reruns."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--sample", default=DEFAULT_SAMPLE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load JSONL records, skipping malformed lines defensively."""

    events: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def infer_task_meta(path: Path, root: Path, sample: str) -> dict[str, str]:
    """Infer suite/framework/run identifiers from a BaxBench output path."""

    rel = path.relative_to(root)
    suite = rel.parts[0] if len(rel.parts) > 0 else ""
    framework = rel.parts[1] if len(rel.parts) > 1 else ""
    return {"suite": suite, "framework": framework, "sample": sample, "run_id": f"{suite}/{framework}/{sample}"}


def event_text(event: dict[str, Any]) -> str:
    """Extract the evidence text used by deterministic rules."""

    chunks: list[str] = []
    output = event.get("output")
    if isinstance(output, dict):
        chunks.append(str(output.get("output") or ""))
        exit_code = output.get("exit_code")
        if exit_code not in (None, 0):
            chunks.append(f"exit_code={exit_code}")
    input_obj = event.get("input")
    if isinstance(input_obj, dict):
        chunks.append(str(input_obj.get("command") or ""))
    for change in event.get("changes") or []:
        if isinstance(change, dict):
            chunks.append(f"{change.get('kind', '')} {change.get('path', '')}")
    return "\n".join(c for c in chunks if c)


def command_process(command: str) -> str:
    """Map command text to a primary process label."""

    c = command.lower()
    if not c:
        return ""
    if re.search(r"\b(gofmt|py_compile|tsc --noemit|syntax-only|php -l|ruby -c|node --check|node -c)\b", c):
        return "verification_static"
    if re.search(r"\b(go build|cargo build|npm run build|tsc\b|javac|g\+\+|gcc)\b", c):
        return "verification_build"
    if re.search(r"\b(go test|pytest|unittest|npm test|jest|vitest|rails test|rspec|phpunit)\b", c):
        return "verification_test"
    if re.search(r"\b(curl|wget|http://|runserver|listenandserve|npm run start|go run|./myapp|rails server)\b", c):
        return "verification_runtime"
    if re.search(r"\b(go mod|npm install|npm ci|go get|pip install|bundle install|composer install|cargo fetch)\b", c):
        return "adaptation"
    if re.search(r"\b(ls|find|pwd|rg --files|git status|git diff|sed -n|cat |head|tail|nl -ba|command -v|go env|go version|go list|node --version|npm --version|python3|php|ruby|which|lsof)\b", c):
        return "inspection"
    if re.search(r"\b(mkdir|chmod|printf)\b", c):
        return "implementation_writing"
    return ""


def is_included_event(event: dict[str, Any]) -> bool:
    """Select completed behavior-bearing events as annotation units."""

    if event.get("type") in INCLUDED_TASK_TYPES:
        return True
    if (event.get("tool_name") or "") not in INCLUDED_TOOLS:
        return False
    return event.get("native_event_type") == "item.completed"


def choose_primary(candidates: set[str]) -> str:
    """Select one process label by analytic priority."""

    for label in PRIMARY_PRIORITY:
        if label in candidates:
            return label
    return ""


def label_event(event: dict[str, Any]) -> tuple[str, list[str], str, bool]:
    """Assign one primary process and zero or more secondary attributes."""

    text = event_text(event)
    lower = text.lower()
    tool = event.get("tool_name") or ""
    event_type = event.get("type") or ""
    output = event.get("output") if isinstance(event.get("output"), dict) else {}
    exit_code = output.get("exit_code")

    command = ""
    if isinstance(event.get("input"), dict):
        command = str(event["input"].get("command") or "")

    processes: set[str] = set()
    attributes: set[str] = set()
    command_label = command_process(command)
    if command_label:
        processes.add(command_label)

    command_failed = exit_code not in (None, 0)
    substantive_failure = bool(ERROR_RE.search(text))
    if command_failed and command_label in {
        "adaptation",
        "verification_static",
        "verification_build",
        "verification_test",
        "verification_runtime",
    }:
        substantive_failure = True

    if event_type == "task.started":
        processes.add("orientation")
    if event_type == "task.completed":
        processes.add("final_reporting")
    if tool == "file_change":
        if re.search(r"\b(fix|tighten|normalize|validate|correct|rollback|status|edge|bug|update)\b", lower):
            processes.add("refinement")
        else:
            processes.add("implementation_writing")
    if tool == "agent_message":
        if re.search(r"\b(checking|inspect|confirmed|workspace|layout|scaffold|existing)\b", lower):
            processes.add("orientation")
        if re.search(r"\b(next|plan|shape|strategy|implementation|creating|adding|writing|wire|bootstrap|endpoint will)\b", lower):
            processes.add("planning")
        if re.search(r"\b(fix|tighten|tightening|correct|remaining|gap|bug|mismatch|edge|status code|updated|hardening|type-safety|less brittle)\b", lower):
            processes.add("refinement")
        if re.search(r"\b(verify|test|build|compile|smoke|runserver|startup|passes|validating|syntax check|syntax-level|quick pass|runtime check|request-path check)\b", lower):
            processes.add("verification_build")
        if re.search(r"\b(fallback|switch|switched|workaround|compatibility layer|degrade|stdlib|self-contained|redirecting|pivot)\b", lower):
            processes.add("adaptation")
        if re.search(r"\b(implemented|created/modified|validation:|verification:|files:)\b", lower):
            processes.add("final_reporting")

    if substantive_failure:
        processes.add("failure_observation_diagnosis")

    if re.search(r"\b(input validation|validate|validation|normalize|path normalization|escape|escaping|sql|parameter|secret|size limit|maxbytes|readheader|csrf|safe|unreadable|permission issue)\b", lower):
        attributes.add("defensive_coding")
    if re.search(r"\b(dependency|module|package|install|cache|framework import|npm|go mod|not installed|not available|command -v|go env|go list)\b", lower):
        attributes.add("dependency_related")
    if re.search(r"\b(sandbox|network|blocked|missing|unavailable|not installed|permission|operation not permitted|no such host|command not found|module not found|bind|socket|cache)\b", lower):
        attributes.add("environment_or_sandbox_constraint")
    if re.search(r"\b(curl|http://|runserver|listen|startup|port|bind|socket|background process|live request|smoke check|runtime probe)\b", lower):
        attributes.add("runtime_service_constraint")

    return choose_primary(processes), sorted(attributes), command_label, substantive_failure


def collect_labeled_events(root: Path, sample: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Read all trajectories and return event-level and run-level records."""

    event_rows: list[dict[str, Any]] = []
    run_rows: list[dict[str, Any]] = []
    paths = sorted(root.glob(f"*/*/{sample}/logs/steps.jsonl"))
    for path in paths:
        meta = infer_task_meta(path, root, sample)
        events = read_jsonl(path)
        process_counter: Counter[str] = Counter()
        attribute_counter: Counter[str] = Counter()
        observed_event_count = 0
        analyzed_event_count = 0
        excluded_non_substantive_events = 0
        failed_events = 0
        sequence: list[str] = []
        for raw_index, event in enumerate(events):
            if not is_included_event(event):
                continue
            observed_event_count += 1
            process, attributes, command_label, failed = label_event(event)
            if not process:
                excluded_non_substantive_events += 1
                continue
            analyzed_event_count += 1
            failed_events += int(failed)
            process_counter[process] += 1
            attribute_counter.update(attributes)
            sequence.append(process)
            preview = event_text(event).replace("\r", "").replace("\n", "\\n")[:500]
            event_rows.append(
                {
                    **meta,
                    "raw_event_index": raw_index,
                    "analysis_event_index": analyzed_event_count,
                    "timestamp": event.get("timestamp", ""),
                    "event_type": event.get("type", ""),
                    "native_event_type": event.get("native_event_type", ""),
                    "tool_name": event.get("tool_name", ""),
                    "command_process_hint": command_label,
                    "failed_or_error_signal": str(failed).lower(),
                    "primary_process": process,
                    "secondary_attributes": "|".join(attributes),
                    "preview": preview,
                }
            )

        final_path = path.parent.parent / "final_message.txt"
        run_rows.append(
            {
                **meta,
                "steps_path": str(path),
                "final_message_present": str(final_path.exists()).lower(),
                "observed_event_count": observed_event_count,
                "analyzed_event_count": analyzed_event_count,
                "excluded_non_substantive_events": excluded_non_substantive_events,
                "failed_or_error_events": failed_events,
                "process_counts_json": json.dumps(dict(sorted(process_counter.items())), sort_keys=True),
                "attribute_counts_json": json.dumps(dict(sorted(attribute_counter.items())), sort_keys=True),
                "primary_process_sequence": " > ".join(sequence),
            }
        )
    return event_rows, run_rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write a list of dictionaries as CSV with stable columns."""

    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def summarize(event_rows: list[dict[str, Any]], run_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute aggregate process counts, attribute counts, and process transitions."""

    process_counts: Counter[str] = Counter()
    attribute_counts: Counter[str] = Counter()
    suite_process_counts: dict[str, Counter[str]] = defaultdict(Counter)
    suite_attribute_counts: dict[str, Counter[str]] = defaultdict(Counter)
    transitions: Counter[tuple[str, str]] = Counter()
    by_run: dict[str, list[str]] = defaultdict(list)

    for row in event_rows:
        process = row["primary_process"]
        process_counts[process] += 1
        suite_process_counts[row["suite"]][process] += 1
        by_run[row["run_id"]].append(process)
        attrs = [a for a in row["secondary_attributes"].split("|") if a]
        attribute_counts.update(attrs)
        suite_attribute_counts[row["suite"]].update(attrs)

    for seq in by_run.values():
        for left, right in zip(seq, seq[1:]):
            transitions[(left, right)] += 1

    return {
        "run_count": len(run_rows),
        "event_count": len(event_rows),
        "observed_behavior_event_count": sum(int(row["observed_event_count"]) for row in run_rows),
        "excluded_non_substantive_event_count": sum(int(row["excluded_non_substantive_events"]) for row in run_rows),
        "primary_process_counts": dict(process_counts.most_common()),
        "secondary_attribute_counts": dict(attribute_counts.most_common()),
        "suite_process_counts": {suite: dict(counter.most_common()) for suite, counter in sorted(suite_process_counts.items())},
        "suite_attribute_counts": {suite: dict(counter.most_common()) for suite, counter in sorted(suite_attribute_counts.items())},
        "top_process_transitions": [
            {"from": left, "to": right, "count": count}
            for (left, right), count in transitions.most_common(30)
        ],
    }


def write_codebook(path: Path) -> None:
    """Write the machine-readable two-axis codebook."""

    payload = {
        "unit_of_analysis": {
            "primary": "completed event in logs/steps.jsonl with tool_name in agent_message, command_execution, file_change, plus task.started/task.completed",
            "excluded": "thread/turn bookkeeping events and tool_start events to avoid double-counting started/completed pairs",
            "taxonomy_shape": "two_axis",
            "primary_process_rule": "exactly one primary process label per included event, selected by deterministic analytic priority",
            "secondary_attribute_rule": "zero or more orthogonal attributes may attach to any primary process label",
        },
        "primary_process_labels": [entry.__dict__ for entry in PRIMARY_CODEBOOK],
        "secondary_attribute_labels": [entry.__dict__ for entry in ATTRIBUTE_CODEBOOK],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")


def markdown_table(rows: list[list[Any]], headers: list[str]) -> str:
    """Render a compact Markdown table."""

    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(out)


def write_report(path: Path, summary: dict[str, Any], root: Path, sample: str) -> None:
    """Write the academic-method report with the revised two-axis taxonomy."""

    process_table = markdown_table(
        [[k, v] for k, v in list(summary["primary_process_counts"].items())],
        ["primary process", "event count"],
    )
    attribute_table = markdown_table(
        [[k, v] for k, v in list(summary["secondary_attribute_counts"].items())],
        ["secondary attribute", "event count"],
    )
    transition_table = markdown_table(
        [[t["from"], t["to"], t["count"]] for t in summary["top_process_transitions"][:12]],
        ["from", "to", "count"],
    )
    suite_rows = []
    for suite, counts in summary["suite_process_counts"].items():
        top = ", ".join(f"{label}={count}" for label, count in list(counts.items())[:5])
        suite_rows.append([suite, top])
    suite_table = markdown_table(suite_rows, ["suite", "top primary processes"])

    text = f"""# BaxBench Agent Coding Behavior Taxonomy

Generated: {datetime.now(timezone.utc).isoformat()}

## Research Objective

This artifact builds a first-pass taxonomy of coding-agent behaviors from the
current Codex BaxBench trajectories. The descriptive research questions are:

1. What observable behavior types appear during agent coding tasks?
2. How often do these behavior types occur across the current BaxBench sample?
3. What common behavior transitions characterize the coding process?
4. Which behaviors reflect environment constraints and adaptive workarounds?

## Data

- Source root: `{root}`
- Sample name: `{sample}`
- Runs analyzed: {summary["run_count"]}
- Observed behavior-bearing events before substantive filtering: {summary["observed_behavior_event_count"]}
- Analyzed substantive behavior events: {summary["event_count"]}
- Excluded non-substantive residual events: {summary["excluded_non_substantive_event_count"]}
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

{process_table}

### Secondary Attribute Counts

{attribute_table}

### Common Primary-Process Transitions

{transition_table}

### Suite-Level Primary Processes

{suite_table}

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
"""
    path.write_text(text, encoding="utf-8")


def write_readme(path: Path, summary: dict[str, Any], root: Path, sample: str) -> None:
    """Write concise usage notes for the generated taxonomy artifact directory."""

    text = f"""# BaxBench Behavior Taxonomy Artifact

This directory contains a generated taxonomy analysis of agent coding behavior
from BaxBench trajectories.

## Scope

- Source root: `{root}`
- Sample name: `{sample}`
- Runs analyzed: {summary["run_count"]}
- Observed behavior-bearing events before substantive filtering: {summary["observed_behavior_event_count"]}
- Analyzed substantive behavior events: {summary["event_count"]}
- Excluded non-substantive residual events: {summary["excluded_non_substantive_event_count"]}

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
"""
    path.write_text(text, encoding="utf-8")


def main() -> None:
    """Run the full taxonomy artifact generation pipeline."""

    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    event_rows, run_rows = collect_labeled_events(args.root, args.sample)
    summary = summarize(event_rows, run_rows)

    write_codebook(args.out / "codebook.json")
    write_csv(args.out / "labeled_events.csv", event_rows)
    write_csv(args.out / "run_summaries.csv", run_rows)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    write_report(args.out / "report.md", summary, args.root, args.sample)
    write_readme(args.out / "README.md", summary, args.root, args.sample)
    print(f"wrote {args.out}")
    print(f"runs={summary['run_count']} events={summary['event_count']}")


if __name__ == "__main__":
    main()
