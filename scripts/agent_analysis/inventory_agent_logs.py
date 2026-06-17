#!/usr/bin/env python3
"""Inventory benchmark agent logs and evaluation results.
Outputs:
  data/processed/agent_logs_inventory.json
  data/processed/agent_logs_inventory.md
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path(os.environ.get("AGENT_LOGS_ROOT", "data/raw/Agent Logs"))
DEFAULT_OUT = Path("data/processed")


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root))


def count_lines(path: Path) -> int:
    with path.open(encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


def scan_cweval(root: Path) -> dict[str, Any]:
    base = root / "cweval"
    result: dict[str, Any] = {"path": rel(base, root), "runs": []}
    if not base.exists():
        return result

    for agent_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        for variant_dir in sorted(p for p in agent_dir.iterdir() if p.is_dir()):
            summary_path = variant_dir / "summary.json"
            res_all_path = variant_dir / "res_all.json"
            res_path = variant_dir / "generated_0" / "res.json"
            step_files = sorted((variant_dir / "agent_logs").glob("*/*/*/logs/steps.jsonl"))
            suite_counts = Counter()
            lang_counts = Counter()
            step_line_total = 0
            for step_file in step_files:
                parts = step_file.relative_to(variant_dir / "agent_logs").parts
                if len(parts) >= 3:
                    suite_counts[parts[0]] += 1
                    lang_counts[parts[1]] += 1
                step_line_total += count_lines(step_file)

            summary = load_json(summary_path) if summary_path.exists() else {}
            result["runs"].append(
                {
                    "agent": agent_dir.name,
                    "variant": variant_dir.name,
                    "model": summary.get("model"),
                    "summary": summary,
                    "generation_logs": {
                        "count": len(step_files),
                        "steps_jsonl_lines": step_line_total,
                        "by_suite": dict(sorted(suite_counts.items())),
                        "by_language": dict(sorted(lang_counts.items())),
                        "root": rel(variant_dir / "agent_logs", root),
                    },
                    "evaluation_results": {
                        "summary_json": rel(summary_path, root) if summary_path.exists() else None,
                        "res_all_json": rel(res_all_path, root) if res_all_path.exists() else None,
                        "generated_0_res_json": rel(res_path, root) if res_path.exists() else None,
                    },
                }
            )
    return result


def scan_baxbench(root: Path) -> dict[str, Any]:
    base = root / "baxbench"
    result: dict[str, Any] = {"path": rel(base, root), "runs": []}
    if not base.exists():
        return result

    run_root = base / "codex" / "scp_owasp"
    summary_path = run_root / "summary.json"
    summary = load_json(summary_path) if summary_path.exists() else {}
    sample_dirs = sorted(p.parent for p in run_root.glob("codex/*/*/temp0.2-openapi-scp/sample*/test_results.json"))
    tasks = Counter()
    frameworks = Counter()
    totals = Counter()
    step_files = []
    func_logs = []
    sec_logs = []
    for sample_dir in sample_dirs:
        rel_parts = sample_dir.relative_to(run_root / "codex").parts
        if len(rel_parts) >= 4:
            tasks[rel_parts[0]] += 1
            frameworks[rel_parts[1]] += 1
        test_result = load_json(sample_dir / "test_results.json")
        totals["functional_passed"] += int(test_result.get("num_passed_ft", 0))
        totals["functional_total"] += int(test_result.get("num_total_ft", 0))
        totals["security_total"] += int(test_result.get("num_total_st", 0))
        totals["functional_exceptions"] += int(test_result.get("num_ft_exceptions", 0))
        totals["security_exceptions"] += int(test_result.get("num_st_exceptions", 0))
        if "num_passed_st" in test_result:
            totals["security_passed"] += int(test_result.get("num_passed_st", 0))
        step_path = sample_dir / "logs" / "steps.jsonl"
        if step_path.exists():
            step_files.append(step_path)
        func_logs.extend(sample_dir.glob("func_test_*.log"))
        sec_logs.extend(sample_dir.glob("sec_test_*.log"))

    result["runs"].append(
        {
            "agent": "codex",
            "variant": "scp_owasp",
            "model": summary.get("model"),
            "summary": summary,
            "sample_count": len(sample_dirs),
            "task_count": len(tasks),
            "framework_count": len(frameworks),
            "tasks": dict(sorted(tasks.items())),
            "frameworks": dict(sorted(frameworks.items())),
            "generation_logs": {
                "count": len(step_files),
                "steps_jsonl_lines": sum(count_lines(p) for p in step_files),
                "root": rel(run_root / "codex", root),
            },
            "evaluation_results": {
                "summary_json": rel(summary_path, root) if summary_path.exists() else None,
                "test_results_json_count": len(sample_dirs),
                "func_test_log_count": len(func_logs),
                "sec_test_log_count": len(sec_logs),
                "aggregate_test_counts": dict(sorted(totals.items())),
            },
        }
    )
    return result


def scan_dualgauge(root: Path) -> dict[str, Any]:
    base = root / "dualgauge"
    result: dict[str, Any] = {"path": rel(base, root), "runs": []}
    if not base.exists():
        return result

    eval_root = base / "evaluation_results"
    for lang_dir in sorted(p for p in eval_root.iterdir() if p.is_dir()):
        for agent_dir in sorted(p for p in lang_dir.iterdir() if p.is_dir()):
            generated_root = base / "generated_samples" / lang_dir.name / agent_dir.name
            execution_root = base / "execution_results" / lang_dir.name / agent_dir.name
            summaries = sorted(agent_dir.glob("*/sample_*/summary.json"))
            debug_files = sorted(agent_dir.glob("*/sample_*/debug.json"))
            result_files = sorted(execution_root.glob("*/sample_*/result.json"))
            event_files = sorted(generated_root.glob("*/raw_outputs/*_events.jsonl"))
            task_ids = {p.relative_to(agent_dir).parts[0] for p in summaries}

            aggregate = Counter()
            status_counts = Counter()
            for summary_path in summaries:
                summary = load_json(summary_path)
                status_counts[str(summary.get("status", "unknown"))] += 1
                aggregate["gap_present"] += int(bool(summary.get("gap_present")))
                for category, data in summary.get("categories", {}).items():
                    key = category.lower().replace(" ", "_")
                    aggregate[f"{key}_passed"] += int(data.get("passed_test_cases", 0))
                    aggregate[f"{key}_total"] += int(data.get("total_test_cases", 0))

            result["runs"].append(
                {
                    "language": lang_dir.name,
                    "agent": agent_dir.name,
                    "task_count": len(task_ids),
                    "sample_summary_count": len(summaries),
                    "status_counts": dict(sorted(status_counts.items())),
                    "aggregate_evaluation": dict(sorted(aggregate.items())),
                    "generation_logs": {
                        "event_jsonl_count": len(event_files),
                        "event_jsonl_lines": sum(count_lines(p) for p in event_files),
                        "root": rel(generated_root, root),
                    },
                    "evaluation_results": {
                        "summary_json_count": len(summaries),
                        "debug_json_count": len(debug_files),
                        "root": rel(agent_dir, root),
                    },
                    "execution_results": {
                        "result_json_count": len(result_files),
                        "root": rel(execution_root, root),
                    },
                }
            )
    return result


def build_markdown(inventory: dict[str, Any], source_root: Path) -> str:
    lines = [
        "# Agent Logs Inventory",
        "",
        f"Source root: `{source_root}`",
        "",
        "Notes:",
        "- cweval and baxbench non-Codex generation logs may not reflect later pipeline fixes; Codex is the reliable reference for those two benchmarks.",
        "- baxbench only contains Codex `scp_owasp`; base and zero-shot logs are absent from this bundle.",
        "- cweval OpenHands used `gpt-5-nano`; Codex used `gpt-5.1-codex-mini`; Claude Code used Haiku 4.5.",
        "",
        "## cweval",
        "",
        "| Agent | Variant | Model | Summary success/total | Step logs | Step lines | Suites | Languages | Result files |",
        "|---|---:|---|---:|---:|---:|---|---|---|",
    ]
    for run in inventory["cweval"]["runs"]:
        summary = run["summary"]
        suites = ", ".join(f"{k}:{v}" for k, v in run["generation_logs"]["by_suite"].items())
        langs = ", ".join(f"{k}:{v}" for k, v in run["generation_logs"]["by_language"].items())
        result_files = ", ".join(k for k, v in run["evaluation_results"].items() if v)
        lines.append(
            f"| {run['agent']} | {run['variant']} | {run.get('model') or ''} | "
            f"{summary.get('success', '')}/{summary.get('total', '')} | "
            f"{run['generation_logs']['count']} | {run['generation_logs']['steps_jsonl_lines']} | "
            f"{suites} | {langs} | {result_files} |"
        )

    lines.extend(
        [
            "",
            "## baxbench",
            "",
            "| Agent | Variant | Model | Summary success/total | Samples | Tasks | Frameworks | Step logs | Test result files | Test count aggregate |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for run in inventory["baxbench"]["runs"]:
        summary = run["summary"]
        agg = run["evaluation_results"]["aggregate_test_counts"]
        agg_text = ", ".join(f"{k}:{v}" for k, v in agg.items())
        lines.append(
            f"| {run['agent']} | {run['variant']} | {run.get('model') or ''} | "
            f"{summary.get('success', '')}/{summary.get('total', '')} | "
            f"{run['sample_count']} | {run['task_count']} | {run['framework_count']} | "
            f"{run['generation_logs']['count']} | {run['evaluation_results']['test_results_json_count']} | {agg_text} |"
        )

    lines.extend(
        [
            "",
            "## dualgauge",
            "",
            "| Language | Agent | Tasks | Sample summaries | Event logs | Execution results | Gap present | Security pass/total | Functional pass/total |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for run in inventory["dualgauge"]["runs"]:
        agg = run["aggregate_evaluation"]
        lines.append(
            f"| {run['language']} | {run['agent']} | {run['task_count']} | "
            f"{run['sample_summary_count']} | {run['generation_logs']['event_jsonl_count']} | "
            f"{run['execution_results']['result_json_count']} | {agg.get('gap_present', 0)} | "
            f"{agg.get('security_passed', 0)}/{agg.get('security_total', 0)} | "
            f"{agg.get('functional_correctness_passed', 0)}/{agg.get('functional_correctness_total', 0)} |"
        )

    lines.extend(
        [
            "",
            "## Canonical Path Patterns",
            "",
            "- cweval generation logs: `cweval/<agent>/<variant>/agent_logs/{core,lang}/<lang>/<cwe_task>/logs/steps.jsonl`",
            "- cweval evaluation results: `summary.json`, `res_all.json`, `generated_0/res.json`",
            "- baxbench generation logs: `baxbench/codex/scp_owasp/codex/<Task>/<Lang-Framework>/temp0.2-openapi-scp/sample0/logs/steps.jsonl`",
            "- baxbench evaluation results: `test_results.json`, plus optional `func_test_*.log` and `sec_test_*.log` files",
            "- dualgauge generation logs: `dualgauge/generated_samples/<lang>/<agent>/<task#>/raw_outputs/<id>_sample_<n>_events.jsonl`",
            "- dualgauge evaluation results: `dualgauge/evaluation_results/<lang>/<agent>/<task#>/sample_<n>/summary.json` and `debug.json`",
            "- dualgauge intermediate execution results: `dualgauge/execution_results/<lang>/<agent>/<task#>/sample_<n>/result.json`",
            "",
            "The companion JSON file contains exact roots and per-run artifact counts.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    inventory = {
        "source_root": str(root),
        "cweval": scan_cweval(root),
        "baxbench": scan_baxbench(root),
        "dualgauge": scan_dualgauge(root),
    }

    json_path = out_dir / "agent_logs_inventory.json"
    md_path = out_dir / "agent_logs_inventory.md"
    json_path.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(build_markdown(inventory, root), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
