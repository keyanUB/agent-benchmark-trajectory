#!/usr/bin/env python3
"""Generate a deeper behavior analysis report from extracted trajectories."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any


TRAJ_DIR = Path("data/processed")
BEHAVIOR_DIR = Path("data/processed")
OUT = Path("reports/agent_trajectories/deep_behavior_analysis.md")

OUTCOME_ORDER = [
    "func_and_sec_pass",
    "func_only_pass",
    "sec_only_pass",
    "both_fail",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def json_list(value: str) -> list[dict[str, Any]]:
    if not value:
        return []
    return json.loads(value)


def hard_error(event: dict[str, Any]) -> bool:
    """Return true for observed tool/runtime failures, not merely defensive code text."""
    return str(event.get("success")) == "False" or (
        str(event.get("has_error_signal")) == "True"
        and bool(event.get("tool_name"))
        and not str(event.get("token", "")).startswith("message")
    )


def row_metrics(row: dict[str, str]) -> dict[str, Any]:
    events = json_list(row["event_details_json"])
    tokens = [e.get("token", "") for e in events if e.get("token")]
    detailed_tokens = [e.get("detailed_token", e.get("token", "")) for e in events if e.get("token")]
    tools = [e.get("tool_name", "") for e in events if e.get("tool_name")]
    first_error_idx = next((idx for idx, event in enumerate(events) if hard_error(event)), None)
    after_error = events[first_error_idx + 1 :] if first_error_idx is not None else []
    after_tokens = [e.get("token", "") for e in after_error]
    after_detailed_tokens = [e.get("detailed_token", e.get("token", "")) for e in after_error]
    return {
        "len": len(tokens),
        "tool_count": len(tools),
        "has_tool": bool(tools),
        "has_inspect": "inspect_workspace" in tokens,
        "has_read": "read_file" in tokens,
        "has_write": any(token in {"write_file", "edit_file"} for token in tokens),
        "has_execute": any(
            token in {"execute_probe", "test", "install"} or str(token).startswith("probe_")
            for token in detailed_tokens
        ),
        "hard_error": first_error_idx is not None,
        "revised_after_error": any(token in {"write_file", "edit_file"} for token in after_tokens),
        "probed_after_error": any(
            token in {"execute_probe", "test", "install"} or str(token).startswith("probe_")
            for token in after_detailed_tokens
        ),
        "message_after_error": any(str(token).startswith("message") for token in after_tokens),
        "llm_count": sum(1 for token in tokens if str(token).startswith("message")),
        "first": tokens[0] if tokens else "",
        "last": tokens[-1] if tokens else "",
    }


def top_sequences(rows: list[dict[str, str]], limit: int = 3) -> list[tuple[str, int, float]]:
    counts = Counter(row["raw_sequence"] for row in rows)
    total = len(rows) or 1
    return [(sequence, count, count / total) for sequence, count in counts.most_common(limit)]


def top_detailed_sequences(rows: list[dict[str, str]], limit: int = 3) -> list[tuple[str, int, float]]:
    counts = Counter(row.get("detailed_behavior_sequence", row["raw_sequence"]) for row in rows)
    total = len(rows) or 1
    return [(sequence, count, count / total) for sequence, count in counts.most_common(limit)]


def short_sequence(sequence: str, max_tokens: int = 12) -> str:
    tokens = sequence.split(" > ") if sequence else []
    if len(tokens) <= max_tokens:
        return sequence
    return " > ".join(tokens[:max_tokens]) + f" > ... (+{len(tokens) - max_tokens} more)"


def probe_counter(rows: list[dict[str, str]]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for row in rows:
        for token in (row.get("probe_sequence") or "").split(" > "):
            if token:
                counter[token] += 1
    return counter


def probe_summary(rows: list[dict[str, str]], limit: int = 4) -> str:
    counter = probe_counter(rows)
    total = sum(counter.values())
    if total == 0:
        return "none visible"
    return ", ".join(f"{token} {pct(count / total)}" for token, count in counter.most_common(limit))


def message_counter(rows: list[dict[str, str]]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for row in rows:
        for token in (row.get("message_sequence") or "").split(" > "):
            if token:
                counter[token] += 1
    return counter


def agent_trajectory_family(agent: str) -> str:
    families = {
        "codex": "inspect -> probe -> read/finalize; long service loops in baxbench",
        "claude_code": "write first -> compile/run -> final extraction",
        "openhands": "direct generation/retry visible; cweval logs compressed",
        "codex-gpt54": "direct code or short inspect/search -> code",
        "claudecode-opus47": "short message/write -> finish",
        "openhands-gpt54": "read/inspect -> write/edit -> terminal probe -> finish",
    }
    return families.get(agent, "mixed")


def summarize_group(rows: list[dict[str, str]]) -> dict[str, Any]:
    metrics = [row_metrics(row) for row in rows]
    if not rows:
        return {}

    def share(key: str) -> float:
        return sum(1 for item in metrics if item[key]) / len(metrics)

    return {
        "runs": len(rows),
        "median_len": median(item["len"] for item in metrics),
        "tool": share("has_tool"),
        "inspect": share("has_inspect"),
        "read": share("has_read"),
        "write": share("has_write"),
        "execute": share("has_execute"),
        "hard_error": share("hard_error"),
        "revise_after_error": share("revised_after_error"),
        "probe_after_error": share("probed_after_error"),
        "message_after_error": share("message_after_error"),
        "median_llm": median(item["llm_count"] for item in metrics),
    }


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    out = ["| " + " | ".join(headers) + " |"]
    out.append("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        out.append("| " + " | ".join(str(item) for item in row) + " |")
    return "\n".join(out)


def source_path(run_rows: dict[str, dict[str, str]], run_id: str) -> str:
    return run_rows.get(run_id, {}).get("source_path", "")


def sample_for(
    rows: list[dict[str, str]],
    agent: str,
    outcome: str,
    contains: list[str] | None = None,
) -> dict[str, str] | None:
    candidates = [row for row in rows if row["agent"] == agent and row["outcome"] == outcome]
    if contains:
        candidates = [
            row
            for row in candidates
            if all(token in row["raw_sequence"] for token in contains)
        ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda row: (len(row["raw_sequence"]), row["run_id"]))[len(candidates) // 2]


def sample_for_detailed(
    rows: list[dict[str, str]],
    agent: str,
    outcome: str,
    contains: list[str] | None = None,
) -> dict[str, str] | None:
    candidates = [row for row in rows if row["agent"] == agent and row["outcome"] == outcome]
    if contains:
        candidates = [
            row
            for row in candidates
            if all(token in row.get("detailed_behavior_sequence", "") for token in contains)
        ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda row: (len(row.get("detailed_behavior_sequence", "")), row["run_id"]))[
        len(candidates) // 2
    ]


def compact_event_trace(row: dict[str, str], max_events: int = 10) -> list[str]:
    lines: list[str] = []
    for event in json_list(row["event_details_json"])[:max_events]:
        token = event.get("detailed_token") or event.get("token") or event.get("behavior_family") or event.get("native_event_type")
        tool = event.get("tool_name") or "-"
        category = event.get("command_category") or "-"
        preview = (event.get("preview") or "").replace("\n", " ")
        if len(preview) > 150:
            preview = preview[:150] + "..."
        lines.append(f"{event.get('event_index')}: {token} / {tool} / {category} / {preview}")
    return lines


def main() -> None:
    rows = read_csv(TRAJ_DIR / "trajectory_sequences.csv")
    run_rows = {row["run_id"]: row for row in read_csv(BEHAVIOR_DIR / "agent_behavior_runs.csv")}

    by_agent_outcome: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    by_benchmark_agent_outcome: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_agent_outcome[(row["agent"], row["outcome"])].append(row)
        by_benchmark_agent_outcome[(row["benchmark"], row["agent"], row["outcome"])].append(row)

    lines: list[str] = []
    lines.append("# Deep Behavior Analysis")
    lines.append("")
    lines.append(
        "This report analyzes ordered agent trajectories from `trajectory_sequences.csv` and checks representative original logs under the raw benchmark log bundle. "
        "It separates functional/security outcomes where the benchmark provides them. `baxbench` is treated as observed/generated (`present`) because its extracted outcome layer did not map security totals into the same four-way label."
    )
    lines.append(
        "\nNote: sequence labels such as `message:error` can be caused by error words inside generated code or result objects. The `hard error` columns below use stricter tool/runtime signals where possible, so use those columns for recovery analysis."
    )
    lines.append("")
    lines.append("## Main Interpretation")
    lines.append("")
    lines.append(
        "The agents are not following one universal coding trajectory. There are three dominant families: "
        "**inspect/probe/finalize** for Codex on cweval and baxbench, **write/probe/finalize** for Claude Code on cweval, and **single-shot or short editor-terminal loops** for DualGauge agents depending on harness and agent. "
        "Successful secure+functional runs usually include either enough environment probing to avoid interface mistakes or a simple enough task that direct generation is sufficient. Failures often look similar at the coarse tree level, but the intervention point is weaker: the agent validates compilation or a happy-path example while missing the security condition, stops after a direct code message, or hits environment/tool failures without a semantic repair."
    )
    lines.append("")

    lines.append("## Trajectory Pattern Families")
    lines.append("")
    pattern_rows: list[list[Any]] = []
    for agent in sorted({row["agent"] for row in rows}):
        group = [row for row in rows if row["agent"] == agent and row["outcome"] != "missing"]
        if not group:
            continue
        summary = summarize_group(group)
        top = top_detailed_sequences(group, 1)[0]
        pattern_rows.append(
            [
                agent,
                len(group),
                summary["median_len"],
                agent_trajectory_family(agent),
                short_sequence(top[0], 8),
                pct(top[2]),
                pct(summary["inspect"]),
                pct(summary["write"]),
                pct(summary["execute"]),
                probe_summary(group, 3),
            ]
        )
    lines.append(
        md_table(
            [
                "agent",
                "runs",
                "median events",
                "trajectory family",
                "top exact refined pattern",
                "top exact share",
                "inspect",
                "write/edit",
                "probe",
                "main probe types",
            ],
            pattern_rows,
        )
    )
    lines.append("")

    lines.append("## Outcome-Level Behavior Rates")
    lines.append("")
    lines.append(
        "This table keeps only evaluated four-way outcomes. `baxbench` generated/present rows and missing evaluations are omitted here because they are not comparable success/failure labels."
    )
    table_rows: list[list[Any]] = []
    for agent in sorted({row["agent"] for row in rows}):
        for outcome in OUTCOME_ORDER:
            group = by_agent_outcome.get((agent, outcome), [])
            if not group:
                continue
            summary = summarize_group(group)
            table_rows.append(
                [
                    agent,
                    outcome,
                    summary["runs"],
                    summary["median_len"],
                    pct(summary["inspect"]),
                    pct(summary["write"]),
                    pct(summary["execute"]),
                    pct(summary["hard_error"]),
                    pct(summary["revise_after_error"]),
                    pct(summary["probe_after_error"]),
                ]
            )
    lines.append(
        md_table(
            [
                "agent",
                "outcome",
                "runs",
                "median events",
                "inspect",
                "write/edit",
                "execute/test/install",
                "hard error",
                "revise after error",
                "probe after error",
            ],
            table_rows,
        )
    )
    lines.append("")

    lines.append("## Probe Type Breakdown")
    lines.append("")
    lines.append(
        "`probe_sequence` and `probe_actions_json` in `trajectory_sequences.csv` now split the old broad `execute_probe` label into more specific probe types."
    )
    probe_rows: list[list[Any]] = []
    for agent in sorted({row["agent"] for row in rows}):
        group = [row for row in rows if row["agent"] == agent]
        counter: Counter[str] = Counter()
        for row in group:
            for token in (row.get("probe_sequence") or "").split(" > "):
                if token:
                    counter[token] += 1
        total = sum(counter.values()) or 1
        for token, count in counter.most_common(8):
            probe_rows.append([agent, token, count, pct(count / total)])
    lines.append(md_table(["agent", "probe type", "count", "share within agent probes"], probe_rows))
    lines.append("")

    lines.append("## Message Type Breakdown")
    lines.append("")
    lines.append(
        "`message` events are now refined in `detailed_behavior_sequence`, `message_sequence`, and `message_types_called`. "
        "These labels separate invisible LLM calls, task prompts, direct code answers, summaries, planning/preambles, and status/error messages when the log preview makes that visible."
    )
    message_rows: list[list[Any]] = []
    for agent in sorted({row["agent"] for row in rows}):
        group = [row for row in rows if row["agent"] == agent]
        counter = message_counter(group)
        total = sum(counter.values()) or 1
        for token, count in counter.most_common(8):
            message_rows.append([agent, token, count, pct(count / total)])
    lines.append(md_table(["agent", "message subtype", "count", "share within agent messages"], message_rows))
    lines.append("")

    lines.append("## Success vs Failure Patterns")
    lines.append("")
    contrast_rows: list[list[Any]] = []
    for benchmark, agent in sorted({(row["benchmark"], row["agent"]) for row in rows}):
        success_group = by_benchmark_agent_outcome.get((benchmark, agent, "func_and_sec_pass"), [])
        fail_group = by_benchmark_agent_outcome.get((benchmark, agent, "both_fail"), [])
        if not success_group and not fail_group:
            continue
        success_summary = summarize_group(success_group) if success_group else None
        fail_summary = summarize_group(fail_group) if fail_group else None
        success_pattern = short_sequence(top_detailed_sequences(success_group, 1)[0][0], 9) if success_group else "n/a"
        fail_pattern = short_sequence(top_detailed_sequences(fail_group, 1)[0][0], 9) if fail_group else "n/a"
        contrast_rows.append(
            [
                f"{benchmark}/{agent}",
                len(success_group),
                success_summary["median_len"] if success_summary else "n/a",
                success_pattern,
                probe_summary(success_group, 3) if success_group else "n/a",
                len(fail_group),
                fail_summary["median_len"] if fail_summary else "n/a",
                fail_pattern,
                probe_summary(fail_group, 3) if fail_group else "n/a",
            ]
        )
    lines.append(
        md_table(
            [
                "benchmark/agent",
                "secure+functional runs",
                "success median events",
                "common success pattern",
                "success probes",
                "both-fail runs",
                "fail median events",
                "common failure pattern",
                "failure probes",
            ],
            contrast_rows,
        )
    )
    lines.append("")

    lines.append("## Agent-Language Outcome Shape")
    lines.append("")
    language_rows: list[list[Any]] = []
    by_agent_language: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row["outcome"] in OUTCOME_ORDER:
            by_agent_language[(row["agent"], row["language"])].append(row)
    for (agent, language), group in sorted(by_agent_language.items()):
        if len(group) < 20:
            continue
        summary = summarize_group(group)
        outcomes = Counter(row["outcome"] for row in group)
        language_rows.append(
            [
                agent,
                language,
                len(group),
                pct(outcomes["func_and_sec_pass"] / len(group)),
                pct(outcomes["func_only_pass"] / len(group)),
                pct(outcomes["sec_only_pass"] / len(group)),
                pct(outcomes["both_fail"] / len(group)),
                summary["median_len"],
                pct(summary["inspect"]),
                pct(summary["write"]),
                pct(summary["execute"]),
            ]
        )
    lines.append(
        md_table(
            [
                "agent",
                "language",
                "runs",
                "secure+functional",
                "functional-only",
                "security-only",
                "both-fail",
                "median events",
                "inspect",
                "write/edit",
                "execute/test/install",
            ],
            language_rows,
        )
    )
    lines.append("")

    lines.append("## Representative Original-Log Evidence")
    lines.append("")
    lines.append(
        "These examples are intentionally short. They show intervention points without dumping complete code or long terminal sessions. Use `source_path` plus `run_id` for full reconstruction."
    )
    examples = [
        ("Codex cweval secure+functional", sample_for_detailed(rows, "codex", "func_and_sec_pass", ["probe_", "read_file"])),
        ("Codex cweval functional-only", sample_for_detailed(rows, "codex", "func_only_pass", ["inspect_workspace", "probe_"])),
        ("Claude Code cweval secure+functional", sample_for_detailed(rows, "claude_code", "func_and_sec_pass", ["write_file", "probe_"])),
        ("Claude Code cweval both-fail", sample_for_detailed(rows, "claude_code", "both_fail", ["write_file", "probe_"])),
        ("OpenHands cweval both-fail", sample_for(rows, "openhands", "both_fail")),
        ("Codex-GPT54 DualGauge secure+functional", sample_for(rows, "codex-gpt54", "func_and_sec_pass")),
        ("ClaudeCode-Opus47 DualGauge both-fail", sample_for(rows, "claudecode-opus47", "both_fail")),
        ("OpenHands-GPT54 DualGauge secure+functional", sample_for_detailed(rows, "openhands-gpt54", "func_and_sec_pass", ["write_file", "probe_"])),
        ("OpenHands-GPT54 DualGauge both-fail", sample_for_detailed(rows, "openhands-gpt54", "both_fail", ["write_file", "probe_"])),
    ]
    for title, row in examples:
        if not row:
            continue
        lines.append(f"### {title}")
        lines.append(f"- Run: `{row['run_id']}`")
        lines.append(f"- Source log: `{source_path(run_rows, row['run_id'])}`")
        lines.append(f"- Outcome: `{row['outcome']}`")
        lines.append(f"- Refined sequence: `{short_sequence(row.get('detailed_behavior_sequence', row['raw_sequence']), 18)}`")
        if row.get("probe_sequence"):
            lines.append(f"- Probe sequence: `{short_sequence(row['probe_sequence'], 12)}`")
        lines.append("- First events:")
        for event_line in compact_event_trace(row):
            lines.append(f"  - `{event_line}`")
        lines.append("")

    lines.append("## Agent-Specific Interpretation")
    lines.append("")
    lines.append("### codex")
    lines.append(
        "Codex’s reliable pattern is **LLM call -> workspace inspection -> refined probes -> read output/code -> final summary/code extraction**. On cweval, secure+functional runs almost always use probes and usually inspect the workspace first. "
        "The refined probes are mixed: many are `probe_execute_other`, `probe_run_program`, `probe_script_snippet`, and `probe_http_or_network`, with fewer explicit `probe_test` events. This means Codex often validates behavior with custom commands or snippets rather than benchmark-style tests. Failures often still include inspection and probes, so the high-level tree alone cannot explain success. The decisive intervention is whether the probe checks the vulnerability-relevant behavior. Functional-only examples often validate interface/compilation while leaving a security edge case, such as path traversal or cryptographic requirements, under-tested. "
        "On baxbench, Codex has much longer trajectories because it must create an API/service rather than a single function. The original logs show repeated inspect commands, file writes, environment checks, failed local tests caused by missing dependencies, and a final summary explaining what could not be verified."
    )
    lines.append("")
    lines.append("### claude_code")
    lines.append(
        "Claude Code’s cweval pattern is **LLM call -> write file -> compile/run probes -> final extraction**. It reads less than Codex before the first write. This looks like a stronger prior/code-first strategy: the model commits to an initial implementation, then uses Bash to compile or exercise examples. "
        "Its refined probes are mostly `probe_run_program` and `probe_compile_or_build`, so its validation style is strongly compile/run oriented. "
        "Secure+functional success usually happens when the initial implementation already encodes the needed safety rule and the probes catch obvious syntax/interface problems. Both-fail runs are longer and have more write/edit activity, suggesting repair attempts after problems, but those repairs are usually tool-level and local rather than a visible second LLM planning phase. Security-only failures often show many executions without a clear vulnerability-specific revision."
    )
    lines.append("")
    lines.append("### openhands")
    lines.append(
        "The cweval OpenHands logs expose a compressed pattern: **message -> code extraction**, sometimes repeated once after an extraction/runtime failure. Because the non-Codex cweval/OpenHands logs were noted as less reliable, I treat this as a harness/logging observation rather than proof that OpenHands never used tools. The visible intervention point is mostly whether a second generated-code attempt occurs after a failed extraction."
    )
    lines.append("")
    lines.append("### codex-gpt54")
    lines.append(
        "DualGauge codex-gpt54 often appears as either a direct code message or a short inspect/search prefix followed by code. It does not show file writes in the normalized DualGauge logs. When probes appear, they are mostly `probe_execute_other`, `probe_run_program`, or `probe_script_snippet`, but probe volume is low compared with Codex on cweval/baxbench. Secure+functional runs have more inspection than both-fail runs, but many successes are still single-shot. This suggests the benchmark/harness often allows direct solution emission; tool use helps when the task has ambiguous symbols or needs context, but the dominant intervention is still the LLM’s first generated program."
    )
    lines.append("")
    lines.append("### claudecode-opus47")
    lines.append(
        "DualGauge claudecode-opus47 is the most short-horizon agent in the logs. Most runs are **message -> finish** or **write -> message -> finish**, with little visible probing. Secure+functional successes are also short, which means success mostly occurs when one-shot generation is enough. Failures are not visibly rescued by iterative debugging; many failed runs terminate after the same two-step shape."
    )
    lines.append("")
    lines.append("### openhands-gpt54")
    lines.append(
        "DualGauge openhands-gpt54 shows the richest interactive loop: **message -> read/inspect -> write/edit -> terminal probe -> finish**, often with task-tracker or think actions. Its probes are mostly `probe_run_program`, `probe_http_or_network`, and `probe_script_snippet`. Secure+functional runs have higher rates of inspect, write/edit, and probing than both-fail runs. That makes it the clearest case where tool-mediated intervention correlates with better outcomes. Still, failures also often include the same intervention types, so quality of the repair matters more than mere presence of tools."
    )
    lines.append("")

    lines.append("## Language Effects")
    lines.append("")
    lines.append(
        "Language effects are strongest for Codex/cweval+baxbench and weaker for Claude Code/cweval. C/C++ single-file tasks often follow shorter compile/run/read paths. Go, JavaScript, and Python need more framework/runtime probing. Baxbench PHP/Ruby/Rust/Python/JavaScript service tasks have longer trajectories because the agent must infer project shape, create files, handle dependencies, and satisfy an OpenAPI surface. "
        "In DualGauge, language differences are smaller than agent/harness differences because many runs are direct returned-code tasks. Python tends to have slightly better secure+functional rates for codex-gpt54 and openhands-gpt54, but the visible trajectory family remains similar."
    )
    lines.append("")
    lines.append("## Are Procedures Fixed?")
    lines.append("")
    lines.append(
        "The procedures are not fixed. Repeats and retry lengths vary by task and by encountered error. Codex and Claude Code show variable numbers of `execute_probe`, `inspect_workspace`, and `write_file` repeats; OpenHands-GPT54 shows variable read/editor/terminal loops. This does not look like a hardcoded fixed retry cap in the trajectory data. The stable part is the agent-level tendency: Codex inspects/probes, Claude Code writes/probes, ClaudeCode-Opus47 often finishes quickly, and OpenHands-GPT54 loops through editor/terminal actions."
    )
    lines.append("")
    lines.append("## Intervention Points To Study Next")
    lines.append("")
    lines.append("- **First write timing:** write-before-read often means the LLM’s initial plan dominates the solution.")
    lines.append("- **Probe relevance:** successful and failed Codex runs can both compile and run; the question is whether the probe targets the security property.")
    lines.append("- **Error recovery:** distinguish compile/dependency/environment recovery from semantic vulnerability repair.")
    lines.append("- **Second LLM participation:** Codex logs often show a later message after tools, but many are summaries; a stricter classifier should separate summary-only messages from code-revision messages.")
    lines.append("- **Harness shape:** direct-code benchmarks naturally produce shorter trees than service/API benchmarks, so compare agent behavior within each benchmark before comparing across benchmarks.")
    lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
