#!/usr/bin/env python3
"""Build ordered trajectory summaries and prefix trees from behavior events."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_IN = Path("data/intermediate/agent_behaviors")
DEFAULT_OUT = Path("data/processed")

SEQUENCE_FIELDS = [
    "run_id",
    "benchmark",
    "agent",
    "variant",
    "language",
    "task",
    "sample",
    "outcome",
    "repeat_event_count",
    "behavior_sequence",
    "tool_sequence",
    "tools_called",
    "detailed_behavior_sequence",
    "probe_sequence",
    "probe_actions_json",
    "tool_calls_json",
    "event_details_json",
    "raw_sequence",
]

TRANSITION_FIELDS = [
    "group_type",
    "group_value",
    "from_token",
    "to_token",
    "count",
    "probability",
]

MOTIF_FIELDS = [
    "group_type",
    "group_value",
    "sequence",
    "count",
    "share",
    "median_collapsed_len",
    "success_share",
]

PROFILE_FIELDS = [
    "group_type",
    "group_value",
    "run_count",
    "unique_sequences",
    "dominant_sequence",
    "dominant_sequence_count",
    "dominant_sequence_share",
    "avg_collapsed_len",
    "median_collapsed_len",
    "sequence_entropy",
    "success_share",
]

SIMILARITY_FIELDS = [
    "scope",
    "dimension",
    "left",
    "right",
    "cosine_transition_similarity",
    "top_sequence_jaccard",
]

REPEAT_PROFILE_FIELDS = [
    "group_type",
    "group_value",
    "token",
    "repeat_block_count",
    "run_count_with_repeat",
    "min_repeat_len",
    "median_repeat_len",
    "max_repeat_len",
    "unique_repeat_lens",
    "repeat_len_distribution",
    "looks_fixed",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def normalize_lang(lang: str) -> str:
    mapping = {
        "py": "python",
        "Python": "python",
        "js": "javascript",
        "JavaScript": "javascript",
        "go": "go",
        "Go": "go",
        "cpp": "cpp",
        "c": "c",
        "Ruby": "ruby",
        "Rust": "rust",
        "PHP": "php",
    }
    return mapping.get(lang, lang)


def truthy(value: str) -> bool | None:
    if value in {"True", "true", "1"}:
        return True
    if value in {"False", "false", "0"}:
        return False
    return None


def outcome_from_run(run: dict[str, str]) -> str:
    status = run.get("evaluation_status", "")
    if status in {"missing", ""}:
        return status or "unknown"
    fp = truthy(run.get("functional_passed", ""))
    sp = truthy(run.get("security_passed", ""))
    if run.get("functional_total") and run.get("security_total"):
        try:
            ft = int(float(run.get("functional_total", 0)))
            st = int(float(run.get("security_total", 0)))
            fpass = int(float(run.get("functional_passed", 0)))
            spass = int(float(run.get("security_passed", 0))) if run.get("security_passed") not in {"", "True", "False"} else None
            if spass is not None:
                if fpass == ft and spass == st:
                    return "func_and_sec_pass"
                if fpass == ft:
                    return "func_only_pass"
                if spass == st:
                    return "sec_only_pass"
                return "both_fail"
        except ValueError:
            pass
    if fp is True and sp is True:
        return "func_and_sec_pass"
    if fp is True and sp is False:
        return "func_only_pass"
    if fp is False and sp is True:
        return "sec_only_pass"
    if fp is False and sp is False:
        return "both_fail"
    if run.get("gap_present") in {"True", "true", "1"}:
        return "gap_present"
    if status == "success":
        return "evaluated"
    return status


def token_for_event(event: dict[str, str]) -> str:
    family = event.get("behavior_family", "")
    category = event.get("command_category", "")
    native = event.get("native_event_type", "")
    tool = event.get("tool_name", "")
    actor = event.get("actor", "")
    error = event.get("has_error_signal", "") == "True"

    token = ""
    if actor in {"system", "environment"} and family not in {"generated_code", "final_or_result"}:
        return ""
    if native in {"thread.started", "turn.started", "system"}:
        return ""
    if native == "turn.completed":
        return "finish"
    if family == "llm_or_message":
        token = "message"
    elif family == "generated_code":
        token = "generated_code"
    elif family == "final_or_result":
        token = "finish"
    elif family == "error":
        return "" if actor == "system" else "error"
    elif error:
        token = "error"
    elif category in {"inspect_workspace", "inspect_git"}:
        token = "inspect_workspace"
    elif category in {"read_file", "view"}:
        token = "read_file"
    elif category == "search":
        token = "search"
    elif category in {"write_or_edit_file", "create"}:
        token = "write_file"
    elif category in {"str_replace", "insert"}:
        token = "edit_file"
    elif category == "run_tests":
        token = "test"
    elif category == "install_dependency":
        token = "install"
    elif category in {"execute_probe", "network_probe"}:
        token = "execute_probe"
    elif family == "planning":
        token = "plan"
    elif family == "agent_action":
        token = "agent_action"
    elif family == "environment_observation":
        return ""
    elif family in {"file_read", "file_or_search_read"}:
        token = "read_file"
    elif family in {"file_write", "file_write_or_edit"}:
        token = "write_file"
    elif family == "file_edit":
        token = "edit_file"
    elif family == "inspect":
        token = "inspect_workspace"
    elif family == "execute":
        token = "execute_probe"
    else:
        token = tool or native or "other"

    if error and token != "error":
        return f"{token}:error"
    return token


def strip_error_suffix(token: str) -> tuple[str, bool]:
    if token.endswith(":error"):
        return token[: -len(":error")], True
    return token, False


def probe_type_for_event(event: dict[str, str], token: str) -> str:
    """Classify broad probe events into concrete probe/action types."""
    base_token, token_error = strip_error_suffix(token)
    category = event.get("command_category", "")
    if base_token not in {"execute_probe", "test", "install"} and category not in {
        "execute_probe",
        "run_tests",
        "install_dependency",
        "network_probe",
    }:
        return ""
    command = (event.get("command") or "").lower()
    preview = (event.get("preview") or "").lower()
    error_suffix = ":error" if token_error else ""

    if base_token == "test" or category == "run_tests":
        return f"probe_test{error_suffix}"
    if base_token == "install" or category == "install_dependency":
        return f"probe_install_dependency{error_suffix}"
    if category == "network_probe" or any(word in command for word in ["curl ", "wget ", "http "]) or "http://" in command or "https://" in command:
        return f"probe_http_or_network{error_suffix}"
    if any(word in command for word in ["uvicorn", "flask run", "npm start", "rails server", "go run main.go", "python app.py", "node server"]):
        return f"probe_server_run{error_suffix}"
    if any(word in command for word in ["gcc ", "g++ ", "clang ", "clang++ ", "javac ", "cargo build", "go build", "tsc", "mvn package", "gradle build"]):
        return f"probe_compile_or_build{error_suffix}"
    if any(word in command for word in ["pytest", "unittest", "npm test", "npm run test", "cargo test", "go test", "phpunit", "rspec", "jest", "vitest"]):
        return f"probe_test{error_suffix}"
    if "python3 - <<'py'" in command or "python - <<'py'" in command or "python3 - <<\"py\"" in command or "python - <<\"py\"" in command:
        return f"probe_script_snippet{error_suffix}"
    if "node -e" in command or "ruby -e" in command or "php -r" in command:
        return f"probe_script_snippet{error_suffix}"
    if any(word in command for word in ["./solution", "python ", "python3 ", "node ", "ruby ", "php ", "java ", "go run ", "cargo run "]):
        return f"probe_run_program{error_suffix}"
    if category == "execute_probe" or base_token == "execute_probe":
        if "traceback" in preview or "syntaxerror" in preview or "modulenotfounderror" in preview:
            return f"probe_run_program{error_suffix}"
        return f"probe_execute_other{error_suffix}"
    return ""


def detailed_token_for_event(event: dict[str, str], token: str) -> str:
    probe_type = probe_type_for_event(event, token)
    if probe_type:
        return probe_type
    return token


def collapse(tokens: list[str]) -> list[str]:
    out: list[str] = []
    for token in tokens:
        if not out or out[-1] != token:
            out.append(token)
    return out


def repeat_stats(tokens: list[str]) -> dict[str, Any]:
    blocks: list[dict[str, Any]] = []
    if not tokens:
        return {
            "repeat_event_count": 0,
            "repeat_block_count": 0,
            "max_repeat_len": 0,
            "max_repeat_token": "",
            "repeat_blocks": [],
        }
    current = tokens[0]
    length = 1
    for token in tokens[1:] + [None]:
        if token == current:
            length += 1
            continue
        if length > 1:
            blocks.append({"token": current, "length": length, "extra_repeats": length - 1})
        current = token
        length = 1
    max_block = max(blocks, key=lambda b: b["length"], default={"token": "", "length": 0})
    return {
        "repeat_event_count": sum(block["extra_repeats"] for block in blocks),
        "repeat_block_count": len(blocks),
        "max_repeat_len": max_block["length"],
        "max_repeat_token": max_block["token"],
        "repeat_blocks": blocks,
    }


def median(values: list[float]) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    mid = len(values) // 2
    if len(values) % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2


def entropy(counter: Counter[str]) -> float:
    total = sum(counter.values())
    if total <= 0:
        return 0.0
    return -sum((v / total) * math.log2(v / total) for v in counter.values())


def success(outcome: str) -> bool | None:
    if outcome == "func_and_sec_pass":
        return True
    if outcome in {"func_only_pass", "sec_only_pass", "both_fail", "gap_present"}:
        return False
    return None


def safe_name(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text)
    return text.strip("_") or "empty"


def event_detail(event: dict[str, str], token: str, detailed_token: str) -> dict[str, Any]:
    detail: dict[str, Any] = {
        "event_index": int(event.get("event_index") or 0),
        "token": token,
        "detailed_token": detailed_token,
        "native_event_type": event.get("native_event_type", ""),
        "actor": event.get("actor", ""),
        "tool_name": event.get("tool_name", ""),
        "behavior_family": event.get("behavior_family", ""),
        "command_category": event.get("command_category", ""),
        "target_path": event.get("target_path", ""),
        "success": event.get("success", ""),
        "has_error_signal": event.get("has_error_signal", ""),
    }
    command = event.get("command", "")
    preview = event.get("preview", "")
    if command:
        detail["command"] = command
    if preview:
        detail["preview"] = preview
    if event.get("text_sha256"):
        detail["text_sha256"] = event.get("text_sha256")
    return detail


def compact_tool_name(event: dict[str, str]) -> str:
    tool = event.get("tool_name", "")
    native = event.get("native_event_type", "")
    if tool:
        return tool
    if native.startswith("tool_use/"):
        return native.split("/", 1)[1]
    return ""


def tool_call_detail(event: dict[str, str], token: str, detailed_token: str) -> dict[str, Any] | None:
    tool = compact_tool_name(event)
    command = event.get("command", "")
    target = event.get("target_path", "")
    if not tool and not command and not target:
        return None
    detail: dict[str, Any] = {
        "event_index": int(event.get("event_index") or 0),
        "token": token,
        "detailed_token": detailed_token,
        "tool": tool,
        "command_category": event.get("command_category", ""),
        "target_path": target,
        "success": event.get("success", ""),
        "has_error_signal": event.get("has_error_signal", ""),
    }
    if command:
        detail["command"] = command
    return detail


def probe_action_detail(event: dict[str, str], token: str, detailed_token: str) -> dict[str, Any] | None:
    if not detailed_token.startswith("probe_"):
        return None
    detail: dict[str, Any] = {
        "event_index": int(event.get("event_index") or 0),
        "coarse_token": token,
        "probe_type": detailed_token,
        "tool": compact_tool_name(event),
        "command_category": event.get("command_category", ""),
        "target_path": event.get("target_path", ""),
        "success": event.get("success", ""),
        "has_error_signal": event.get("has_error_signal", ""),
    }
    if event.get("command"):
        detail["command"] = event.get("command", "")
    if event.get("preview"):
        detail["preview"] = event.get("preview", "")
    return detail


def load_sequences(events_path: Path, runs_path: Path) -> list[dict[str, Any]]:
    runs = {r["run_id"]: r for r in read_csv(runs_path)}
    events_by_run: dict[str, list[dict[str, str]]] = defaultdict(list)
    for event in read_csv(events_path):
        events_by_run[event["run_id"]].append(event)

    rows: list[dict[str, Any]] = []
    for run_id, run in runs.items():
        events = sorted(events_by_run.get(run_id, []), key=lambda e: int(e.get("event_index") or 0))
        raw: list[str] = []
        detailed_raw: list[str] = []
        probe_tokens: list[str] = []
        behavior_tokens: list[str] = []
        tool_tokens: list[str] = []
        details: list[dict[str, Any]] = []
        tool_calls: list[dict[str, Any]] = []
        probe_actions: list[dict[str, Any]] = []
        for event in events:
            token = token_for_event(event)
            if not token:
                continue
            detailed_token = detailed_token_for_event(event, token)
            raw.append(token)
            detailed_raw.append(detailed_token)
            if detailed_token.startswith("probe_"):
                probe_tokens.append(detailed_token)
            behavior = event.get("behavior_family", "")
            behavior_tokens.append(behavior)
            tool = compact_tool_name(event)
            if tool:
                tool_tokens.append(tool)
            details.append(event_detail(event, token, detailed_token))
            tool_call = tool_call_detail(event, token, detailed_token)
            if tool_call:
                tool_calls.append(tool_call)
            probe_action = probe_action_detail(event, token, detailed_token)
            if probe_action:
                probe_actions.append(probe_action)
        collapsed = collapse(raw)
        repeats = repeat_stats(raw)
        outcome = outcome_from_run(run)
        rows.append(
            {
                "run_id": run_id,
                "benchmark": run.get("benchmark", ""),
                "agent": run.get("agent", ""),
                "variant": run.get("variant", ""),
                "language": normalize_lang(run.get("language", "")),
                "task": run.get("task", ""),
                "sample": run.get("sample", ""),
                "outcome": outcome,
                "event_count": len(events),
                "raw_len": len(raw),
                "collapsed_len": len(collapsed),
                "repeat_event_count": repeats["repeat_event_count"],
                "repeat_block_count": repeats["repeat_block_count"],
                "max_repeat_len": repeats["max_repeat_len"],
                "max_repeat_token": repeats["max_repeat_token"],
                "repeat_blocks_json": json.dumps(repeats["repeat_blocks"], sort_keys=True),
                "behavior_sequence": " > ".join(behavior_tokens),
                "tool_sequence": " > ".join(tool_tokens),
                "tools_called": ", ".join(sorted(set(tool_tokens))),
                "detailed_behavior_sequence": " > ".join(detailed_raw),
                "probe_sequence": " > ".join(probe_tokens),
                "probe_actions_json": json.dumps(probe_actions, ensure_ascii=False, sort_keys=True),
                "tool_calls_json": json.dumps(tool_calls, ensure_ascii=False, sort_keys=True),
                "event_details_json": json.dumps(details, ensure_ascii=False, sort_keys=True),
                "raw_sequence": " > ".join(raw),
                "collapsed_sequence": " > ".join(collapsed),
            }
        )
    return rows


def group_keys(row: dict[str, Any]) -> dict[str, str]:
    return {
        "agent": row["agent"],
        "language": row["language"],
        "benchmark": row["benchmark"],
        "benchmark_agent": f"{row['benchmark']}::{row['agent']}",
        "agent_language": f"{row['agent']}::{row['language']}",
        "benchmark_language": f"{row['benchmark']}::{row['language']}",
        "outcome": row["outcome"],
    }


def transition_rows(seq_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counters: dict[tuple[str, str], Counter[tuple[str, str]]] = defaultdict(Counter)
    from_totals: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for row in seq_rows:
        tokens = row["collapsed_sequence"].split(" > ") if row["collapsed_sequence"] else []
        for group_type, group_value in group_keys(row).items():
            prev = "START"
            for token in tokens:
                counters[(group_type, group_value)][(prev, token)] += 1
                from_totals[(group_type, group_value)][prev] += 1
                prev = token
            counters[(group_type, group_value)][(prev, "END")] += 1
            from_totals[(group_type, group_value)][prev] += 1
    rows: list[dict[str, Any]] = []
    for (group_type, group_value), counter in sorted(counters.items()):
        for (src, dst), count in counter.most_common():
            total = from_totals[(group_type, group_value)][src]
            rows.append(
                {
                    "group_type": group_type,
                    "group_value": group_value,
                    "from_token": src,
                    "to_token": dst,
                    "count": count,
                    "probability": count / total if total else 0,
                }
            )
    return rows


def profile_and_motifs(seq_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in seq_rows:
        for group_type, group_value in group_keys(row).items():
            groups[(group_type, group_value)].append(row)

    profiles: list[dict[str, Any]] = []
    motifs: list[dict[str, Any]] = []
    for (group_type, group_value), rows in sorted(groups.items()):
        seq_counts = Counter(r["collapsed_sequence"] for r in rows)
        lengths = [float(r["collapsed_len"]) for r in rows]
        successes = [success(r["outcome"]) for r in rows]
        known_successes = [s for s in successes if s is not None]
        dominant, dominant_count = seq_counts.most_common(1)[0] if seq_counts else ("", 0)
        profiles.append(
            {
                "group_type": group_type,
                "group_value": group_value,
                "run_count": len(rows),
                "unique_sequences": len(seq_counts),
                "dominant_sequence": dominant,
                "dominant_sequence_count": dominant_count,
                "dominant_sequence_share": dominant_count / len(rows) if rows else 0,
                "avg_collapsed_len": sum(lengths) / len(lengths) if lengths else 0,
                "median_collapsed_len": median(lengths),
                "sequence_entropy": entropy(seq_counts),
                "success_share": (sum(known_successes) / len(known_successes)) if known_successes else "",
            }
        )
        for sequence, count in seq_counts.most_common(20):
            seq_rows_for_sequence = [r for r in rows if r["collapsed_sequence"] == sequence]
            seq_successes = [success(r["outcome"]) for r in seq_rows_for_sequence]
            seq_successes = [s for s in seq_successes if s is not None]
            motifs.append(
                {
                    "group_type": group_type,
                    "group_value": group_value,
                    "sequence": sequence,
                    "count": count,
                    "share": count / len(rows) if rows else 0,
                    "median_collapsed_len": median([float(r["collapsed_len"]) for r in seq_rows_for_sequence]),
                    "success_share": (sum(seq_successes) / len(seq_successes)) if seq_successes else "",
                }
            )
    return profiles, motifs


def repeat_profile_rows(seq_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[tuple[str, int]]] = defaultdict(list)
    runs_with_repeat: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for row in seq_rows:
        try:
            blocks = json.loads(row.get("repeat_blocks_json", "[]"))
        except Exception:
            blocks = []
        for block in blocks:
            token = block.get("token", "")
            length = int(block.get("length", 0))
            if not token or length <= 1:
                continue
            for group_type, group_value in group_keys(row).items():
                key = (group_type, group_value, token)
                groups[key].append((row["run_id"], length))
                runs_with_repeat[key].add(row["run_id"])

    rows: list[dict[str, Any]] = []
    for (group_type, group_value, token), items in sorted(groups.items()):
        lengths = [length for _, length in items]
        dist = Counter(lengths)
        unique_lens = sorted(dist)
        rows.append(
            {
                "group_type": group_type,
                "group_value": group_value,
                "token": token,
                "repeat_block_count": len(items),
                "run_count_with_repeat": len(runs_with_repeat[(group_type, group_value, token)]),
                "min_repeat_len": min(lengths),
                "median_repeat_len": median([float(x) for x in lengths]),
                "max_repeat_len": max(lengths),
                "unique_repeat_lens": ",".join(str(x) for x in unique_lens),
                "repeat_len_distribution": json.dumps(dict(sorted(dist.items())), sort_keys=True),
                "looks_fixed": len(unique_lens) == 1,
            }
        )
    return rows


def transition_vector(rows: list[dict[str, Any]], group_type: str, group_value: str) -> Counter[str]:
    c: Counter[str] = Counter()
    for r in rows:
        if r["group_type"] == group_type and r["group_value"] == group_value:
            c[f"{r['from_token']}->{r['to_token']}"] = int(r["count"])
    return c


def cosine(a: Counter[str], b: Counter[str]) -> float:
    keys = set(a) | set(b)
    dot = sum(a[k] * b[k] for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if not na or not nb:
        return 0.0
    return dot / (na * nb)


def similarity_rows(seq_rows: list[dict[str, Any]], trans_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for scope, dimension in [("all", "agent"), ("all", "language")]:
        values = sorted({r[dimension] for r in seq_rows if r[dimension]})
        top_sets = {}
        vectors = {}
        for value in values:
            top_sets[value] = {r["collapsed_sequence"] for r in seq_rows if r[dimension] == value}
            top_sets[value] = set(list(Counter(r["collapsed_sequence"] for r in seq_rows if r[dimension] == value).keys())[:25])
            vectors[value] = transition_vector(trans_rows, dimension, value)
        for i, left in enumerate(values):
            for right in values[i + 1 :]:
                union = top_sets[left] | top_sets[right]
                inter = top_sets[left] & top_sets[right]
                out.append(
                    {
                        "scope": scope,
                        "dimension": dimension,
                        "left": left,
                        "right": right,
                        "cosine_transition_similarity": cosine(vectors[left], vectors[right]),
                        "top_sequence_jaccard": len(inter) / len(union) if union else 0,
                    }
                )

    # Agent similarities inside each benchmark, which is usually the fairest comparison.
    for benchmark in sorted({r["benchmark"] for r in seq_rows}):
        agents = sorted({r["agent"] for r in seq_rows if r["benchmark"] == benchmark})
        vectors = {
            agent: transition_vector(trans_rows, "benchmark_agent", f"{benchmark}::{agent}")
            for agent in agents
        }
        top_sets = {
            agent: set(seq for seq, _ in Counter(r["collapsed_sequence"] for r in seq_rows if r["benchmark"] == benchmark and r["agent"] == agent).most_common(25))
            for agent in agents
        }
        for i, left in enumerate(agents):
            for right in agents[i + 1 :]:
                union = top_sets[left] | top_sets[right]
                inter = top_sets[left] & top_sets[right]
                out.append(
                    {
                        "scope": benchmark,
                        "dimension": "agent",
                        "left": left,
                        "right": right,
                        "cosine_transition_similarity": cosine(vectors[left], vectors[right]),
                        "top_sequence_jaccard": len(inter) / len(union) if union else 0,
                    }
                )
    return out


def build_prefix_tree(rows: list[dict[str, Any]], max_depth: int = 12) -> dict[str, Any]:
    root: dict[str, Any] = {"count": 0, "success": 0, "children": {}}
    for row in rows:
        tokens = row["collapsed_sequence"].split(" > ") if row["collapsed_sequence"] else []
        node = root
        node["count"] += 1
        if success(row["outcome"]):
            node["success"] += 1
        for token in tokens[:max_depth]:
            node = node["children"].setdefault(token, {"count": 0, "success": 0, "children": {}})
            node["count"] += 1
            if success(row["outcome"]):
                node["success"] += 1
    return root


def prune_tree(node: dict[str, Any], min_count: int = 3, max_children: int = 8) -> dict[str, Any]:
    children = node.get("children", {})
    kept = sorted(children.items(), key=lambda kv: kv[1]["count"], reverse=True)
    pruned = {k: prune_tree(v, min_count, max_children) for k, v in kept[:max_children] if v["count"] >= min_count}
    return {"count": node["count"], "success": node.get("success", 0), "children": pruned}


def tree_to_dot(tree: dict[str, Any], title: str) -> str:
    lines = ["digraph trajectory {", "  rankdir=LR;", "  node [shape=box, fontsize=10];"]
    lines.append(f'  label="{title}";')
    lines.append("  labelloc=t;")
    counter = 0

    def add_node(label: str, node: dict[str, Any]) -> str:
        nonlocal counter
        node_id = f"n{counter}"
        counter += 1
        count = node["count"]
        succ = node.get("success", 0)
        safe_label = label.replace('"', '\\"')
        lines.append(f'  {node_id} [label="{safe_label}\\ncount={count}, success={succ}"];')
        return node_id

    def walk(parent_id: str, node: dict[str, Any]) -> None:
        for token, child in node.get("children", {}).items():
            child_id = add_node(token, child)
            lines.append(f'  {parent_id} -> {child_id} [label="{child["count"]}"];')
            walk(child_id, child)

    root_id = add_node("START", tree)
    walk(root_id, tree)
    lines.append("}")
    return "\n".join(lines) + "\n"


def emit_trees(seq_rows: list[dict[str, Any]], out_dir: Path) -> None:
    tree_dir = out_dir / "trees"
    dot_dir = out_dir / "dot"
    tree_dir.mkdir(parents=True, exist_ok=True)
    dot_dir.mkdir(parents=True, exist_ok=True)

    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in seq_rows:
        for group_type in ["agent", "language", "benchmark_agent", "agent_language"]:
            value = group_keys(row)[group_type]
            if value:
                groups[(group_type, value)].append(row)

    for (group_type, value), rows in sorted(groups.items()):
        if len(rows) < 20:
            continue
        tree = prune_tree(build_prefix_tree(rows), min_count=max(2, len(rows) // 100), max_children=8)
        stem = f"{group_type}__{safe_name(value)}"
        (tree_dir / f"{stem}.json").write_text(json.dumps(tree, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (dot_dir / f"{stem}.dot").write_text(tree_to_dot(tree, f"{group_type}: {value}"), encoding="utf-8")


def emit_html_viewer(out_dir: Path) -> None:
    tree_dir = out_dir / "trees"
    trees: dict[str, Any] = {}
    for path in sorted(tree_dir.glob("*.json")):
        trees[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Agent Trajectory Trees</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8fb;
      --text: #17202a;
      --muted: #667085;
      --line: #c8d0dc;
      --node: #ffffff;
      --accent: #2563eb;
    }}
    body {{
      margin: 0;
      font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 2;
      display: flex;
      gap: 12px;
      align-items: center;
      padding: 14px 18px;
      background: rgba(247, 248, 251, 0.95);
      border-bottom: 1px solid #d8dee9;
      backdrop-filter: blur(8px);
    }}
    h1 {{
      margin: 0 12px 0 0;
      font-size: 18px;
      font-weight: 650;
    }}
    select, input {{
      height: 34px;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      padding: 0 10px;
      background: white;
      color: var(--text);
    }}
    main {{
      padding: 18px;
    }}
    .meta {{
      margin-bottom: 14px;
      color: var(--muted);
    }}
    .tree {{
      overflow: auto;
      padding-bottom: 40px;
    }}
    ul {{
      list-style: none;
      margin: 0 0 0 24px;
      padding: 0;
      border-left: 1px solid var(--line);
    }}
    li {{
      margin: 7px 0;
      padding-left: 14px;
      position: relative;
    }}
    li::before {{
      content: "";
      position: absolute;
      left: 0;
      top: 17px;
      width: 12px;
      border-top: 1px solid var(--line);
    }}
    .node {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      min-height: 28px;
      padding: 4px 8px;
      border: 1px solid #d6dde8;
      border-radius: 6px;
      background: var(--node);
      white-space: nowrap;
      box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
    }}
    .label {{
      font-weight: 600;
    }}
    .count {{
      color: var(--muted);
      font-variant-numeric: tabular-nums;
    }}
    .rate {{
      color: var(--accent);
      font-variant-numeric: tabular-nums;
    }}
  </style>
</head>
<body>
  <header>
    <h1>Trajectory Trees</h1>
    <select id="treeSelect"></select>
    <input id="filter" placeholder="Filter nodes">
  </header>
  <main>
    <div class="meta" id="meta"></div>
    <div class="tree" id="tree"></div>
  </main>
  <script>
    const TREES = {json.dumps(trees, ensure_ascii=False)};
    const select = document.getElementById('treeSelect');
    const filter = document.getElementById('filter');
    const treeEl = document.getElementById('tree');
    const meta = document.getElementById('meta');

    function labelFor(key) {{
      return key.replaceAll('__', ': ').replaceAll('_', ' ');
    }}

    function successRate(node) {{
      if (!node.count) return '';
      return `${{((node.success || 0) / node.count * 100).toFixed(1)}}% success`;
    }}

    function nodeMatches(label, node, query) {{
      if (!query) return true;
      if (label.toLowerCase().includes(query)) return true;
      return Object.entries(node.children || {{}}).some(([childLabel, child]) => nodeMatches(childLabel, child, query));
    }}

    function renderNode(label, node, query) {{
      if (!nodeMatches(label, node, query)) return '';
      const children = Object.entries(node.children || {{}})
        .sort((a, b) => b[1].count - a[1].count)
        .map(([childLabel, child]) => renderNode(childLabel, child, query))
        .filter(Boolean)
        .join('');
      return `<li><span class="node"><span class="label">${{label}}</span><span class="count">n=${{node.count}}</span><span class="rate">${{successRate(node)}}</span></span>${{children ? `<ul>${{children}}</ul>` : ''}}</li>`;
    }}

    function render() {{
      const key = select.value;
      const tree = TREES[key];
      const query = filter.value.trim().toLowerCase();
      meta.textContent = `${{labelFor(key)}} · root count ${{tree.count}} · success count ${{tree.success || 0}}`;
      treeEl.innerHTML = `<ul>${{renderNode('START', tree, query)}}</ul>`;
    }}

    Object.keys(TREES).forEach((key) => {{
      const option = document.createElement('option');
      option.value = key;
      option.textContent = labelFor(key);
      select.appendChild(option);
    }});
    select.value = Object.keys(TREES).find(k => k.startsWith('agent__codex')) || Object.keys(TREES)[0];
    select.addEventListener('change', render);
    filter.addEventListener('input', render);
    render();
  </script>
</body>
</html>
"""
    (out_dir / "trajectory_tree_viewer.html").write_text(html, encoding="utf-8")


def build_markdown(
    seq_rows: list[dict[str, Any]],
    profiles: list[dict[str, Any]],
    motifs: list[dict[str, Any]],
    similarities: list[dict[str, Any]],
    repeat_profiles: list[dict[str, Any]],
) -> str:
    lines = [
        "# Agent Trajectory Trees",
        "",
        f"Built ordered trajectories for `{len(seq_rows)}` runs.",
        "",
        "A trajectory is the collapsed ordered behavior sequence for one task/sample. Consecutive repeated actions are collapsed, so `read_file > read_file > write_file` becomes `read_file > write_file`.",
        "",
        "## Most Concentrated Agent Profiles",
        "",
        "| Agent | Runs | Unique Sequences | Dominant Share | Median Length | Entropy | Dominant Sequence |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    agent_profiles = [p for p in profiles if p["group_type"] == "agent"]
    for p in sorted(agent_profiles, key=lambda r: float(r["dominant_sequence_share"]), reverse=True):
        lines.append(
            f"| {p['group_value']} | {p['run_count']} | {p['unique_sequences']} | "
            f"{float(p['dominant_sequence_share']):.3f} | {float(p['median_collapsed_len']):.1f} | "
            f"{float(p['sequence_entropy']):.2f} | `{p['dominant_sequence']}` |"
        )

    lines.extend(
        [
            "",
            "## Top Motifs By Agent",
            "",
            "| Agent | Share | Count | Median Length | Success Share | Sequence |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for agent in sorted({m["group_value"] for m in motifs if m["group_type"] == "agent"}):
        top = [m for m in motifs if m["group_type"] == "agent" and m["group_value"] == agent][:5]
        for m in top:
            success_share = m["success_share"]
            success_text = "" if success_share == "" else f"{float(success_share):.3f}"
            lines.append(
                f"| {agent} | {float(m['share']):.3f} | {m['count']} | "
                f"{float(m['median_collapsed_len']):.1f} | {success_text} | `{m['sequence']}` |"
            )

    lines.extend(
        [
            "",
            "## Agent Similarity Within Benchmarks",
            "",
            "| Benchmark | Left | Right | Transition Cosine | Top-Sequence Jaccard |",
            "|---|---|---|---:|---:|",
        ]
    )
    bench_sims = [s for s in similarities if s["dimension"] == "agent" and s["scope"] != "all"]
    for s in sorted(bench_sims, key=lambda r: (r["scope"], -float(r["cosine_transition_similarity"]))):
        lines.append(
            f"| {s['scope']} | {s['left']} | {s['right']} | "
            f"{float(s['cosine_transition_similarity']):.3f} | {float(s['top_sequence_jaccard']):.3f} |"
        )

    lines.extend(
        [
            "",
            "## Consecutive Repeats",
            "",
            "| Agent | Runs With Repeats | Median Extra Events | Max Repeat Length | Most Repeated Token |",
            "|---|---:|---:|---:|---|",
        ]
    )
    for agent in sorted({r["agent"] for r in seq_rows}):
        rows = [r for r in seq_rows if r["agent"] == agent]
        with_repeats = [r for r in rows if int(r["repeat_event_count"]) > 0]
        median_extra = median([float(r["repeat_event_count"]) for r in with_repeats])
        max_row = max(rows, key=lambda r: int(r["max_repeat_len"]), default={})
        lines.append(
            f"| {agent} | {len(with_repeats)}/{len(rows)} | {median_extra:.1f} | "
            f"{max_row.get('max_repeat_len', 0)} | {max_row.get('max_repeat_token', '')} |"
        )

    lines.extend(
        [
            "",
            "Top repeated behavior blocks by agent/token:",
            "",
            "| Agent | Token | Blocks | Runs | Repeat Lengths | Looks Fixed |",
            "|---|---|---:|---:|---|---|",
        ]
    )
    agent_repeat_profiles = [r for r in repeat_profiles if r["group_type"] == "agent"]
    for r in sorted(agent_repeat_profiles, key=lambda x: int(x["repeat_block_count"]), reverse=True)[:20]:
        lines.append(
            f"| {r['group_value']} | {r['token']} | {r['repeat_block_count']} | "
            f"{r['run_count_with_repeat']} | `{r['repeat_len_distribution']}` | {r['looks_fixed']} |"
        )

    lines.extend(
        [
            "",
            "## Files",
            "",
            "- `trajectory_sequences.csv`: one ordered behavior sequence per run.",
            "- `trajectory_transitions.csv`: transition counts/probabilities by group.",
            "- `trajectory_motifs.csv`: most common collapsed sequences by group.",
            "- `trajectory_profiles.csv`: diversity/concentration metrics by group.",
            "- `trajectory_repeat_profiles.csv`: repeated consecutive behavior lengths by group/token.",
            "- `trajectory_similarity.csv`: transition-vector and top-sequence similarity.",
            "- `trees/*.json`: pruned prefix trees.",
            "- `dot/*.dot`: Graphviz DOT prefix trees.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_IN)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    in_dir = args.input_dir
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    seq_rows = load_sequences(in_dir / "agent_behavior_events.csv", in_dir / "agent_behavior_runs.csv")
    trans = transition_rows(seq_rows)
    profiles, motifs = profile_and_motifs(seq_rows)
    repeat_profiles = repeat_profile_rows(seq_rows)
    sims = similarity_rows(seq_rows, trans)

    write_csv(out_dir / "trajectory_sequences.csv", seq_rows, SEQUENCE_FIELDS)
    write_csv(out_dir / "trajectory_transitions.csv", trans, TRANSITION_FIELDS)
    write_csv(out_dir / "trajectory_profiles.csv", profiles, PROFILE_FIELDS)
    write_csv(out_dir / "trajectory_motifs.csv", motifs, MOTIF_FIELDS)
    write_csv(out_dir / "trajectory_repeat_profiles.csv", repeat_profiles, REPEAT_PROFILE_FIELDS)
    write_csv(out_dir / "trajectory_similarity.csv", sims, SIMILARITY_FIELDS)
    emit_trees(seq_rows, out_dir)
    emit_html_viewer(out_dir)
    (out_dir / "trajectory_summary.md").write_text(build_markdown(seq_rows, profiles, motifs, sims, repeat_profiles), encoding="utf-8")

    print(f"Wrote {out_dir / 'trajectory_sequences.csv'}")
    print(f"Wrote {out_dir / 'trajectory_transitions.csv'}")
    print(f"Wrote {out_dir / 'trajectory_profiles.csv'}")
    print(f"Wrote {out_dir / 'trajectory_motifs.csv'}")
    print(f"Wrote {out_dir / 'trajectory_repeat_profiles.csv'}")
    print(f"Wrote {out_dir / 'trajectory_similarity.csv'}")
    print(f"Wrote {out_dir / 'trees'} and {out_dir / 'dot'}")
    print(f"Wrote {out_dir / 'trajectory_tree_viewer.html'}")
    print(f"Runs: {len(seq_rows)}")


if __name__ == "__main__":
    main()
