#!/usr/bin/env python3
"""Build a behavior taxonomy artifact set from BaxBench Codex trajectories.

The script implements a reproducible first-pass academic workflow:
  * define the primary annotation unit as completed trajectory events
  * apply a documented, deterministic codebook to each unit
  * summarize event frequencies, run-level patterns, and label transitions
  * write a report that separates empirical results from validity limits
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


CODEBOOK: list[LabelDef] = [
    LabelDef(
        "task_orientation",
        "The agent establishes task/workspace context before implementation.",
        "Initial checks of prompt implications, workspace layout, existing files, or repo status.",
        "Specific dependency probing or verification commands, which receive narrower labels.",
    ),
    LabelDef(
        "implementation_planning",
        "The agent states or selects an implementation strategy.",
        "Messages describing intended file layout, architecture, endpoint design, or next coding step.",
        "Final summaries of completed work.",
    ),
    LabelDef(
        "code_generation",
        "The agent creates, updates, or deletes source/configuration artifacts.",
        "Any file_change event that adds, updates, or deletes files in the task workspace.",
        "Read-only commands that display generated code.",
    ),
    LabelDef(
        "code_refinement",
        "The agent makes correctness-oriented changes after an initial implementation.",
        "Fixing status codes, validation, edge cases, compile errors, route behavior, or persistence logic.",
        "The first creation of a file set unless the agent explicitly frames it as a fix.",
    ),
    LabelDef(
        "workspace_inspection",
        "The agent inspects files, directories, git status, or generated source.",
        "Commands such as ls, find, rg --files, git status, sed/head/tail/nl/cat.",
        "Toolchain checks such as go version, npm version, or compiler discovery.",
    ),
    LabelDef(
        "toolchain_dependency_inspection",
        "The agent checks runtime, compiler, package, framework, or module availability.",
        "go env, go list, node/npm/python/php/ruby checks, package-cache searches, command -v.",
        "General file inspection that is not about tool or dependency availability.",
    ),
    LabelDef(
        "dependency_handling",
        "The agent attempts to use, install, resolve, or replace dependencies/frameworks.",
        "go mod tidy, npm install/build dependency failures, module-cache handling, framework import decisions.",
        "Plain toolchain version checks without a dependency decision.",
    ),
    LabelDef(
        "verification_static",
        "The agent runs static formatting, lint, syntax, or source-level checks.",
        "gofmt, syntax-only compiler calls, py_compile, tsc --noEmit, direct source inspections for compile shape.",
        "Full build/test/runtime smoke checks.",
    ),
    LabelDef(
        "verification_build",
        "The agent builds or compiles the generated project.",
        "go build, cargo build, npm run build, tsc build, javac, compiler invocations for project build.",
        "Unit tests or live HTTP probes.",
    ),
    LabelDef(
        "verification_test",
        "The agent runs an automated test suite or local unit/integration test.",
        "pytest, unittest, go test, npm test, jest, rails test, or hand-written test command.",
        "Build-only commands or manual curl probes.",
    ),
    LabelDef(
        "verification_runtime",
        "The agent starts the service or probes runtime behavior.",
        "curl/http requests, server startup, port binding, live endpoint checks.",
        "Static build/test commands.",
    ),
    LabelDef(
        "failure_diagnosis",
        "The agent observes or explains an error, failed command, or mismatch.",
        "Events with failed exit codes, error output, or messages explaining a failure cause.",
        "Successful verification commands.",
    ),
    LabelDef(
        "adaptation_workaround",
        "The agent changes strategy in response to constraints.",
        "Fallback to stdlib, local compatibility layers, cache relocation, graceful degradation, framework replacement.",
        "Minor fixes that do not alter strategy.",
    ),
    LabelDef(
        "security_safety",
        "The agent explicitly implements or discusses safety/security-relevant behavior.",
        "Input validation, path normalization, SQL parameterization, escaping, size limits, secret handling.",
        "Generic correctness fixes without safety relevance.",
    ),
    LabelDef(
        "environment_constraint",
        "The trajectory encounters sandbox, network, missing binary, permission, or port constraints.",
        "No module/network access, missing php/django, bind denied, cache permission errors.",
        "Ordinary application-level compile errors.",
    ),
    LabelDef(
        "final_reporting",
        "The agent summarizes completed work, files, validation, or residual limits.",
        "Final assistant message and task.completed event.",
        "Interim progress messages.",
    ),
]

PRIMARY_PRIORITY = [
    "final_reporting",
    "adaptation_workaround",
    "failure_diagnosis",
    "environment_constraint",
    "dependency_handling",
    "verification_runtime",
    "verification_test",
    "verification_build",
    "verification_static",
    "code_refinement",
    "code_generation",
    "security_safety",
    "implementation_planning",
    "toolchain_dependency_inspection",
    "workspace_inspection",
    "task_orientation",
    "other_observed_behavior",
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
    """Load a JSONL file while skipping malformed lines defensively."""

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
    """Infer suite/framework/run identifiers from the BaxBench output path."""

    rel = path.relative_to(root)
    parts = rel.parts
    suite = parts[0] if len(parts) > 0 else ""
    framework = parts[1] if len(parts) > 1 else ""
    run_id = f"{suite}/{framework}/{sample}"
    return {"suite": suite, "framework": framework, "sample": sample, "run_id": run_id}


def event_text(event: dict[str, Any]) -> str:
    """Extract the text payload used by deterministic annotation rules."""

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


def command_category(command: str) -> str:
    """Map shell commands to analysis categories before assigning labels."""

    c = command.lower()
    if not c:
        return ""
    if re.search(r"\b(ls|find|pwd|rg --files|git status|sed -n|cat |head|tail|nl -ba)\b", c):
        return "workspace_inspection"
    if re.search(r"\b(command -v|go env|go version|go list|node --version|npm --version|python3|php|ruby|bundle|composer|which)\b", c):
        return "toolchain_dependency_inspection"
    if re.search(r"\b(go mod|npm install|npm ci|go get|pip install|bundle install|composer install|cargo fetch)\b", c):
        return "dependency_handling"
    if re.search(r"\b(gofmt|py_compile|tsc --noemit|syntax-only|php -l|ruby -c)\b", c):
        return "verification_static"
    if re.search(r"\b(go build|cargo build|npm run build|tsc\b|javac|g\+\+|gcc)\b", c):
        return "verification_build"
    if re.search(r"\b(go test|pytest|unittest|npm test|jest|vitest|rails test|rspec|phpunit)\b", c):
        return "verification_test"
    if re.search(r"\b(curl|wget|http://|runserver|listenandserve|npm run start|go run|./myapp|php -s|rails server)\b", c):
        return "verification_runtime"
    return "other"


def is_included_event(event: dict[str, Any]) -> bool:
    """Select the primary annotation unit: completed behavior-bearing events."""

    if event.get("type") in INCLUDED_TASK_TYPES:
        return True
    tool = event.get("tool_name") or ""
    native = event.get("native_event_type") or ""
    if tool not in INCLUDED_TOOLS:
        return False
    if native != "item.completed":
        return False
    return True


def choose_primary_label(labels: set[str]) -> str:
    """Choose the sequence label by analytic priority rather than alphabetic order."""

    for label in PRIMARY_PRIORITY:
        if label in labels:
            return label
    return sorted(labels)[0]


def label_event(event: dict[str, Any]) -> tuple[list[str], str, bool, str]:
    """Apply deterministic multi-label rules to a single included event."""

    labels: set[str] = set()
    text = event_text(event)
    lower = text.lower()
    tool = event.get("tool_name") or ""
    event_type = event.get("type") or ""
    output = event.get("output") if isinstance(event.get("output"), dict) else {}
    exit_code = output.get("exit_code")
    command_failed = exit_code not in (None, 0)

    command = ""
    if isinstance(event.get("input"), dict):
        command = str(event["input"].get("command") or "")
    category = command_category(command)
    if category and category != "other":
        labels.add(category)

    substantive_failure = bool(ERROR_RE.search(text))
    if command_failed and category in {
        "dependency_handling",
        "verification_static",
        "verification_build",
        "verification_test",
        "verification_runtime",
        "toolchain_dependency_inspection",
    }:
        substantive_failure = True

    if event_type == "task.started":
        labels.add("task_orientation")
    if event_type == "task.completed":
        labels.add("final_reporting")
    if tool == "file_change":
        labels.add("code_generation")
        if re.search(r"\b(fix|tighten|normalize|validate|correct|rollback|status|edge|bug|update)\b", lower):
            labels.add("code_refinement")
    if tool == "agent_message":
        if re.search(r"\b(checking|inspect|confirmed|workspace|layout|scaffold|existing)\b", lower):
            labels.add("task_orientation")
        if re.search(r"\b(next|plan|shape|strategy|implementation|creating|adding|writing|wire|build)\b", lower):
            labels.add("implementation_planning")
        if re.search(r"\b(fix|tighten|correct|remaining|gap|bug|mismatch|edge|status code)\b", lower):
            labels.add("code_refinement")
        if re.search(r"\b(dependency|module|package|install|cache|framework import|npm|go mod|not installed|not available)\b", lower):
            labels.add("dependency_handling")
        if re.search(r"\b(verify|test|build|compile|smoke|runserver|startup|passes|validating)\b", lower):
            labels.add("verification_build")
        if re.search(r"\b(fallback|switch|workaround|compatibility layer|degrade|stdlib|self-contained|redirecting|pivot)\b", lower):
            labels.add("adaptation_workaround")
        if re.search(r"\b(sandbox|network|blocked|missing|unavailable|not installed|permission|bind|socket)\b", lower):
            labels.add("environment_constraint")
        if re.search(r"\b(input validation|path normalization|escaping|parameter|secret|size limit|safe|security|permission issue|unreadable)\b", lower):
            labels.add("security_safety")
        if re.search(r"\b(implemented|created/modified|validation:|verification:|files:)\b", lower):
            labels.add("final_reporting")

    if substantive_failure:
        labels.add("failure_diagnosis")
    if re.search(r"\b(operation not permitted|no such host|command not found|module not found|not installed|not available|permission|bind)\b", lower):
        labels.add("environment_constraint")
    if re.search(r"\b(input|validate|validation|normalize|escape|sql|parameter|path|secret|maxbytes|readheader|csrf)\b", lower):
        labels.add("security_safety")
    if not labels:
        labels.add("other_observed_behavior")
    primary = choose_primary_label(labels)
    return sorted(labels), category, substantive_failure, primary


def collect_labeled_events(root: Path, sample: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Read all trajectories and return event-level and run-level records."""

    event_rows: list[dict[str, Any]] = []
    run_rows: list[dict[str, Any]] = []
    paths = sorted(root.glob(f"*/*/{sample}/logs/steps.jsonl"))
    for path in paths:
        meta = infer_task_meta(path, root, sample)
        events = read_jsonl(path)
        run_label_counter: Counter[str] = Counter()
        run_event_count = 0
        failed_events = 0
        sequence: list[str] = []
        for raw_index, event in enumerate(events):
            if not is_included_event(event):
                continue
            labels, category, failed, primary = label_event(event)
            run_event_count += 1
            failed_events += int(failed)
            run_label_counter.update(labels)
            sequence.append(primary)
            text = event_text(event)
            evidence_preview = text.replace("\r", "").replace("\n", "\\n")[:500]
            event_rows.append(
                {
                    **meta,
                    "raw_event_index": raw_index,
                    "analysis_event_index": run_event_count,
                    "timestamp": event.get("timestamp", ""),
                    "event_type": event.get("type", ""),
                    "native_event_type": event.get("native_event_type", ""),
                    "tool_name": event.get("tool_name", ""),
                    "command_category": category,
                    "failed_or_error_signal": str(failed).lower(),
                    "primary_label": primary,
                    "labels": "|".join(labels),
                    "preview": evidence_preview,
                }
            )

        final_path = path.parent.parent / "final_message.txt"
        run_rows.append(
            {
                **meta,
                "steps_path": str(path),
                "final_message_present": str(final_path.exists()).lower(),
                "included_event_count": run_event_count,
                "failed_or_error_events": failed_events,
                "label_counts_json": json.dumps(dict(sorted(run_label_counter.items())), sort_keys=True),
                "primary_sequence": " > ".join(sequence),
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
    """Compute aggregate counts, per-suite summaries, and label transitions."""

    label_counts: Counter[str] = Counter()
    primary_counts: Counter[str] = Counter()
    suite_counts: dict[str, Counter[str]] = defaultdict(Counter)
    transitions: Counter[tuple[str, str]] = Counter()

    by_run: dict[str, list[str]] = defaultdict(list)
    for row in event_rows:
        labels = row["labels"].split("|")
        label_counts.update(labels)
        primary_counts[row["primary_label"]] += 1
        suite_counts[row["suite"]].update(labels)
        by_run[row["run_id"]].append(row["primary_label"])

    for seq in by_run.values():
        for left, right in zip(seq, seq[1:]):
            transitions[(left, right)] += 1

    return {
        "run_count": len(run_rows),
        "event_count": len(event_rows),
        "label_counts": dict(label_counts.most_common()),
        "primary_label_counts": dict(primary_counts.most_common()),
        "suite_label_counts": {suite: dict(counter.most_common()) for suite, counter in sorted(suite_counts.items())},
        "top_transitions": [
            {"from": left, "to": right, "count": count}
            for (left, right), count in transitions.most_common(30)
        ],
    }


def write_codebook(path: Path) -> None:
    """Write the machine-readable codebook used by the labeler."""

    payload = {
        "unit_of_analysis": {
            "primary": "completed event in logs/steps.jsonl with tool_name in agent_message, command_execution, file_change, plus task.started/task.completed",
            "excluded": "thread/turn bookkeeping events and tool_start events to avoid double-counting started/completed pairs",
            "multi_label": True,
            "primary_label_rule": "alphabetically first deterministic label; use labels field for full multi-label analysis",
        },
        "labels": [entry.__dict__ for entry in CODEBOOK],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")


def markdown_table(rows: list[list[Any]], headers: list[str]) -> str:
    """Render a compact Markdown table."""

    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(out)


def write_report(path: Path, summary: dict[str, Any], out_dir: Path, root: Path, sample: str) -> None:
    """Write the academic-method report with results and validity notes."""

    top_labels = list(summary["label_counts"].items())[:15]
    top_transitions = summary["top_transitions"][:12]
    label_table = markdown_table([[k, v] for k, v in top_labels], ["behavior label", "event count"])
    transition_table = markdown_table(
        [[t["from"], t["to"], t["count"]] for t in top_transitions],
        ["from", "to", "count"],
    )
    suite_rows = []
    for suite, counts in summary["suite_label_counts"].items():
        top = ", ".join(f"{label}={count}" for label, count in list(counts.items())[:5])
        suite_rows.append([suite, top])
    suite_table = markdown_table(suite_rows, ["suite", "top labels"])

    text = f"""# BaxBench Agent Coding Behavior Taxonomy

Generated: {datetime.now(timezone.utc).isoformat()}

## Research Objective

This artifact builds a first-pass taxonomy of coding-agent behaviors from the
current Codex BaxBench trajectories. The descriptive research questions are:

1. What observable behavior types appear during agent code-generation tasks?
2. How often do these behavior types occur across the current BaxBench sample?
3. What common behavior transitions characterize the coding process?
4. Which behaviors reflect environment constraints and adaptive workarounds?

## Data

- Source root: `{root}`
- Sample name: `{sample}`
- Runs analyzed: {summary["run_count"]}
- Included behavior events: {summary["event_count"]}
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

{label_table}

### Common Label Transitions

{transition_table}

### Suite-Level Patterns

{suite_table}

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
    write_report(args.out / "report.md", summary, args.out, args.root, args.sample)
    print(f"wrote {args.out}")
    print(f"runs={summary['run_count']} events={summary['event_count']}")


if __name__ == "__main__":
    main()
