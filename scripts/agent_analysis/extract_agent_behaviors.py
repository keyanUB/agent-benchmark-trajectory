#!/usr/bin/env python3
"""Extract normalized coding-agent behavior events from benchmark logs.

The extractor creates two analysis-friendly layers:
  1. event rows: one normalized row per observed LLM/tool/action/result event
  2. run rows: one summary row per benchmark task/sample trajectory

It intentionally stores previews and hashes for large text/code payloads instead
of copying full generated code into the derived files.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


DEFAULT_ROOT = Path(os.environ.get("AGENT_LOGS_ROOT", "data/raw/Agent Logs"))
DEFAULT_OUT = Path("data/intermediate/agent_behaviors")
PREVIEW_LIMIT = 500


EVENT_FIELDS = [
    "run_id",
    "event_index",
    "benchmark",
    "agent",
    "model",
    "variant",
    "language",
    "task",
    "sample",
    "suite",
    "framework",
    "source_path",
    "timestamp",
    "native_event_type",
    "actor",
    "tool_name",
    "behavior_family",
    "command_category",
    "command",
    "target_path",
    "success",
    "has_error_signal",
    "text_len",
    "text_sha256",
    "preview",
]

RUN_FIELDS = [
    "run_id",
    "benchmark",
    "agent",
    "model",
    "variant",
    "language",
    "task",
    "sample",
    "suite",
    "framework",
    "source_path",
    "event_count",
    "llm_events",
    "tool_events",
    "command_events",
    "file_read_events",
    "file_write_events",
    "file_edit_events",
    "test_events",
    "install_events",
    "search_events",
    "error_events",
    "final_answer_events",
    "first_agent_action",
    "category_counts",
    "tool_counts",
    "duration_seconds",
    "functional_passed",
    "functional_total",
    "security_passed",
    "security_total",
    "gap_present",
    "evaluation_status",
]


ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
ERROR_RE = re.compile(
    r"\b(error|exception|traceback|failed|failure|not found|command not found|module_not_found|module not found|syntaxerror|typeerror|valueerror)\b",
    re.IGNORECASE,
)


@dataclass
class RunState:
    meta: dict[str, Any]
    counters: Counter[str] = field(default_factory=Counter)
    tool_counts: Counter[str] = field(default_factory=Counter)
    category_counts: Counter[str] = field(default_factory=Counter)
    timestamps: list[float] = field(default_factory=list)
    first_agent_action: str = ""
    outcomes: dict[str, Any] = field(default_factory=dict)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def safe_json(line: str) -> Any | None:
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def stable_hash(text: str) -> str:
    if not isinstance(text, str):
        text = json.dumps(text, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def preview(text: Any, limit: int = PREVIEW_LIMIT) -> str:
    if text is None:
        return ""
    if not isinstance(text, str):
        text = json.dumps(text, ensure_ascii=False, sort_keys=True)
    text = strip_ansi(text).replace("\r", "")
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"


def text_len(text: Any) -> int:
    if text is None:
        return 0
    if not isinstance(text, str):
        text = json.dumps(text, ensure_ascii=False, sort_keys=True)
    return len(text)


def detect_error(text: Any, success: bool | None = None) -> bool:
    if success is False:
        return True
    if text is None:
        return False
    if not isinstance(text, str):
        text = json.dumps(text, ensure_ascii=False, sort_keys=True)
    return bool(ERROR_RE.search(strip_ansi(text)))


def classify_command(command: str) -> str:
    c = command.lower().strip()
    if not c:
        return ""
    if re.search(r"(write_text|cat\s*>|tee |apply_patch|sed -i|perl -pi|touch |mkdir |cp |mv )", c):
        return "write_or_edit_file"
    if re.search(r"\b(pwd|ls|find|tree|du|wc)\b", c):
        return "inspect_workspace"
    if re.search(r"\b(rg|grep|ag|ack)\b", c):
        return "search"
    if re.search(r"\b(cat|sed -n|head|tail|less|more|python3? -m json\.tool)\b", c):
        return "read_file"
    if re.search(r"\b(pytest|unittest|npm test|npm run test|cargo test|go test|mvn test|gradle test|rails test|rspec|jest|vitest|phpunit)\b", c):
        return "run_tests"
    if re.search(r"\b(pip install|npm install|yarn add|pnpm install|bundle install|cargo add|go get|composer install|gem install)\b", c):
        return "install_dependency"
    if re.search(r"\b(git status|git diff|git show|git log)\b", c):
        return "inspect_git"
    if re.search(r"\b(git add|git commit|git push|git checkout|git switch)\b", c):
        return "git_mutation"
    if re.search(r"\b(curl|wget|httpie|nc |netcat)\b", c):
        return "network_probe"
    if re.search(r"\b(node|python3?|ruby|go run|cargo run|php|java|javac|gcc|g\+\+)\b", c):
        return "execute_probe"
    return "other_command"


def family_from_tool(tool_name: str, native_type: str = "", command_category: str = "") -> str:
    tool = (tool_name or "").lower()
    native = (native_type or "").lower()
    if native == "done" or tool == "code_extraction":
        return "generated_code"
    if native.startswith("messageevent"):
        return "llm_or_message"
    if native.startswith("actionevent"):
        return "agent_action"
    if native.startswith("observationevent"):
        return "environment_observation"
    if "llm" in native or native in {"assistant", "agent_message", "message"} or native.startswith("assistant.text"):
        return "llm_or_message"
    if "error" in native:
        return "error"
    if tool in {"text", "messageaction"}:
        return "llm_or_message"
    if "think" in tool or "tasktracker" in tool or tool == "todo_list":
        return "planning"
    if "finish" in tool:
        return "final_or_result"
    if tool in {"write"}:
        return "file_write"
    if tool in {"edit", "notebookedit"}:
        return "file_edit"
    if tool in {"read", "glob", "grep"}:
        return "file_or_search_read"
    if "fileeditor" in tool:
        if command_category in {"view", "read_file", "inspect_workspace"}:
            return "file_read"
        if command_category in {"create", "write_or_edit_file"}:
            return "file_write"
        return "file_edit"
    if "terminal" in tool or tool in {"bash", "command_execution"}:
        if command_category == "run_tests":
            return "test"
        if command_category == "install_dependency":
            return "install"
        if command_category in {"inspect_workspace", "read_file", "inspect_git", "search"}:
            return "inspect"
        if command_category == "write_or_edit_file":
            return "file_write_or_edit"
        return "execute"
    if native == "result":
        return "final_or_result"
    return "other"


def split_shell_command(command: str) -> str:
    # Keep the command intact for traceability, but remove common shell wrapper noise.
    m = re.match(r"^/bin/(?:bash|zsh) -lc ['\"](?P<body>.*)['\"]$", command, re.DOTALL)
    return m.group("body") if m else command


def target_from_text(data: dict[str, Any], command: str = "") -> str:
    for key in ("file_path", "filePath", "path", "source", "target_file"):
        value = data.get(key)
        if isinstance(value, str):
            return value
    m = re.search(r"Path\(['\"]([^'\"]+)['\"]\)\.write_text", command)
    if m:
        return m.group(1)
    m = re.search(r">\s*([A-Za-z0-9_./-]+\.[A-Za-z0-9_]+)", command)
    if m:
        return m.group(1)
    return ""


def emit_event(
    events: list[dict[str, Any]],
    run: RunState,
    native_event_type: str,
    actor: str = "",
    tool_name: str = "",
    command: str = "",
    command_category: str = "",
    target_path: str = "",
    timestamp: Any = "",
    success: bool | None = None,
    text: Any = "",
) -> None:
    command = split_shell_command(command)
    if command and not command_category:
        command_category = classify_command(command)
    behavior_family = family_from_tool(tool_name, native_event_type, command_category)
    has_error = detect_error(text or command, success)
    text = "" if text is None else text
    row = {
        **{k: run.meta.get(k, "") for k in [
            "run_id",
            "benchmark",
            "agent",
            "model",
            "variant",
            "language",
            "task",
            "sample",
            "suite",
            "framework",
            "source_path",
        ]},
        "event_index": len(events) + 1,
        "timestamp": timestamp or "",
        "native_event_type": native_event_type,
        "actor": actor,
        "tool_name": tool_name,
        "behavior_family": behavior_family,
        "command_category": command_category,
        "command": command,
        "target_path": target_path,
        "success": "" if success is None else success,
        "has_error_signal": has_error,
        "text_len": text_len(text),
        "text_sha256": stable_hash(text) if text_len(text) else "",
        "preview": preview(text),
    }
    events.append(row)

    run.counters["event_count"] += 1
    if behavior_family == "llm_or_message":
        run.counters["llm_events"] += 1
    if tool_name:
        run.counters["tool_events"] += 1
        run.tool_counts[tool_name] += 1
    if command:
        run.counters["command_events"] += 1
    if command_category:
        run.category_counts[command_category] += 1
    if behavior_family in {"file_read", "file_or_search_read"} or command_category == "read_file":
        run.counters["file_read_events"] += 1
    if behavior_family in {"file_write", "file_write_or_edit"}:
        run.counters["file_write_events"] += 1
    if behavior_family == "file_edit":
        run.counters["file_edit_events"] += 1
    if behavior_family == "test" or command_category == "run_tests":
        run.counters["test_events"] += 1
    if behavior_family == "install":
        run.counters["install_events"] += 1
    if command_category == "search":
        run.counters["search_events"] += 1
    if has_error:
        run.counters["error_events"] += 1
    if behavior_family == "final_or_result" or native_event_type in {"result", "turn.completed"}:
        run.counters["final_answer_events"] += 1
    if not run.first_agent_action and actor in {"agent", "assistant"} and behavior_family not in {"llm_or_message", "error"}:
        run.first_agent_action = command_category or tool_name or behavior_family
    if isinstance(timestamp, (int, float)):
        run.timestamps.append(float(timestamp))


def cweval_outcomes(run_dir: Path) -> dict[tuple[str, str, str], dict[str, Any]]:
    path = run_dir / "generated_0" / "res.json"
    if not path.exists():
        return {}
    data = load_json(path)
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    for result_path, result in data.items():
        parts = Path(result_path).parts
        for i, part in enumerate(parts):
            if part in {"core", "lang"} and i + 2 < len(parts):
                suite, language = part, parts[i + 1]
                task = parts[i + 2].removesuffix("_test.py")
                out[(suite, language, task)] = result
                if task.endswith(f"_{language}"):
                    out[(suite, language, task[: -(len(language) + 1)])] = result
                break
    return out


def parse_steps_jsonl(path: Path, run: RunState) -> tuple[list[dict[str, Any]], RunState]:
    events: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            obj = safe_json(line)
            if not isinstance(obj, dict):
                continue
            typ = obj.get("type", "")
            timestamp = obj.get("timestamp", "")
            if typ == "llm_call":
                model = obj.get("input", {}).get("model")
                if model and not run.meta.get("model"):
                    run.meta["model"] = model
                emit_event(
                    events,
                    run,
                    native_event_type="llm_call",
                    actor="assistant",
                    tool_name="",
                    timestamp=timestamp,
                    text=obj.get("output", {}).get("text") or obj.get("reasoning") or "",
                )
            elif typ.startswith("tool_use/"):
                tool = typ.split("/", 1)[1]
                command = obj.get("input", {}).get("command", "")
                output = obj.get("output", {}).get("output", "")
                emit_event(
                    events,
                    run,
                    native_event_type=typ,
                    actor="agent",
                    tool_name=tool,
                    command=command,
                    target_path=target_from_text({}, command),
                    timestamp=timestamp,
                    success=not detect_error(output),
                    text=output,
                )
            else:
                tool_name = "code_extraction" if typ == "done" else ""
                emit_event(events, run, native_event_type=typ, actor="system", tool_name=tool_name, timestamp=timestamp, text=obj)
    return events, run


def parse_jsonl_objects(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            obj = safe_json(line.strip())
            if isinstance(obj, dict):
                yield obj


def parse_openhands_objects(path: Path) -> Iterable[dict[str, Any]]:
    text = strip_ansi(path.read_text(encoding="utf-8", errors="replace"))
    marker = "--JSON Event--"
    start = 0
    while True:
        idx = text.find(marker, start)
        if idx == -1:
            break
        brace = text.find("{", idx)
        if brace == -1:
            break
        depth = 0
        in_string = False
        escape = False
        for pos in range(brace, len(text)):
            ch = text[pos]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
            else:
                if ch == '"':
                    in_string = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        raw = text[brace : pos + 1]
                        obj = safe_json(raw)
                        if isinstance(obj, dict):
                            yield obj
                        start = pos + 1
                        break
        else:
            break


def parse_dualgauge_event_file(path: Path, run: RunState) -> tuple[list[dict[str, Any]], RunState]:
    events: list[dict[str, Any]] = []
    objects = list(parse_jsonl_objects(path))
    if not objects and "openhands" in run.meta.get("agent", ""):
        objects = list(parse_openhands_objects(path))

    pending_codex: dict[str, dict[str, Any]] = {}
    for obj in objects:
        typ = obj.get("type") or obj.get("kind") or ""
        timestamp = obj.get("timestamp", "")
        if typ == "thread.started":
            emit_event(events, run, "thread.started", actor="system", text=obj)
        elif typ == "turn.started":
            emit_event(events, run, "turn.started", actor="system", text="")
        elif typ == "error":
            emit_event(events, run, "error", actor="system", text=obj.get("message") or obj, success=False)
        elif typ in {"item.started", "item.completed"}:
            item = obj.get("item", {})
            item_type = item.get("type", "")
            item_id = item.get("id", "")
            if typ == "item.started":
                pending_codex[item_id] = item
                continue
            if item_type == "command_execution":
                command = item.get("command", "")
                output = item.get("aggregated_output", "")
                success = item.get("exit_code") in (0, None)
                emit_event(
                    events,
                    run,
                    "item.completed",
                    actor="agent",
                    tool_name="command_execution",
                    command=command,
                    timestamp=timestamp,
                    success=success,
                    text=output,
                )
            elif item_type == "agent_message":
                emit_event(events, run, "agent_message", actor="assistant", text=item.get("text", ""))
            else:
                emit_event(events, run, "item.completed", actor="agent", tool_name=item_type, text=item)
        elif typ == "turn.completed":
            emit_event(events, run, "turn.completed", actor="system", text=obj.get("usage", {}))
        elif typ == "system":
            model = obj.get("model")
            if model and not run.meta.get("model"):
                run.meta["model"] = model
            emit_event(events, run, "system", actor="system", text=obj)
        elif typ == "assistant":
            message = obj.get("message", {})
            model = message.get("model")
            if model and not run.meta.get("model"):
                run.meta["model"] = model
            content = message.get("content", [])
            if not content:
                emit_event(events, run, "assistant", actor="assistant", text=message)
            for block in content:
                btype = block.get("type", "")
                if btype == "tool_use":
                    tool_name = block.get("name", "")
                    inp = block.get("input", {})
                    command = inp.get("command", "") if isinstance(inp, dict) else ""
                    command_category = classify_command(command) if command else ""
                    if tool_name.lower() in {"write", "edit"}:
                        command_category = "write_or_edit_file"
                    elif tool_name.lower() in {"read"}:
                        command_category = "read_file"
                    elif tool_name.lower() in {"grep", "glob"}:
                        command_category = "search"
                    emit_event(
                        events,
                        run,
                        "assistant.tool_use",
                        actor="assistant",
                        tool_name=tool_name,
                        command=command,
                        command_category=command_category,
                        target_path=target_from_text(inp if isinstance(inp, dict) else {}, command),
                        text=inp,
                    )
                elif btype == "text":
                    emit_event(events, run, "assistant.text", actor="assistant", text=block.get("text", ""))
                elif btype == "thinking":
                    run.counters["thinking_events"] += 1
        elif typ == "user":
            result = obj.get("tool_use_result")
            if isinstance(result, dict):
                success = not bool(result.get("error"))
                emit_event(
                    events,
                    run,
                    "tool_result",
                    actor="environment",
                    tool_name=result.get("type", "tool_result"),
                    target_path=result.get("filePath", ""),
                    success=success,
                    text=result,
                )
        elif typ == "stream_event":
            # The assistant/user records carry the usable semantic information;
            # stream deltas are intentionally skipped to avoid duplicate rows.
            continue
        elif typ == "result":
            emit_event(events, run, "result", actor="system", success=obj.get("subtype") == "success", text=obj)
        elif typ in {"ActionEvent", "ObservationEvent", "MessageEvent"}:
            source = obj.get("source", "")
            action = obj.get("action", {}) or {}
            observation = obj.get("observation", {}) or {}
            payload = action or observation or obj.get("llm_message") or obj.get("message") or obj
            tool_name = payload.get("kind", "") if isinstance(payload, dict) else ""
            command = payload.get("command", "") if isinstance(payload, dict) else ""
            command_category = classify_command(command)
            if tool_name == "FileEditorAction" or tool_name == "FileEditorObservation":
                command_category = command or command_category
            emit_event(
                events,
                run,
                typ,
                actor=source,
                tool_name=tool_name,
                command=command,
                command_category=command_category,
                target_path=target_from_text(payload if isinstance(payload, dict) else {}, command),
                success=None if typ == "ActionEvent" else not detect_error(payload),
                text=payload,
            )
        else:
            emit_event(events, run, typ or "unknown", actor=obj.get("source", ""), text=obj)
    return events, run


def run_summary(run: RunState) -> dict[str, Any]:
    duration = ""
    if len(run.timestamps) >= 2:
        duration = max(run.timestamps) - min(run.timestamps)
    row = {field: run.meta.get(field, "") for field in RUN_FIELDS}
    for key in [
        "event_count",
        "llm_events",
        "tool_events",
        "command_events",
        "file_read_events",
        "file_write_events",
        "file_edit_events",
        "test_events",
        "install_events",
        "search_events",
        "error_events",
        "final_answer_events",
    ]:
        row[key] = run.counters.get(key, 0)
    row["first_agent_action"] = run.first_agent_action
    row["category_counts"] = json.dumps(dict(sorted(run.category_counts.items())), sort_keys=True)
    row["tool_counts"] = json.dumps(dict(sorted(run.tool_counts.items())), sort_keys=True)
    row["duration_seconds"] = duration
    row.update({k: run.outcomes.get(k, "") for k in [
        "functional_passed",
        "functional_total",
        "security_passed",
        "security_total",
        "gap_present",
        "evaluation_status",
    ]})
    return row


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def scan_cweval(root: Path) -> Iterable[tuple[Path, RunState]]:
    base = root / "cweval"
    for agent_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        for variant_dir in sorted(p for p in agent_dir.iterdir() if p.is_dir()):
            summary = load_json(variant_dir / "summary.json") if (variant_dir / "summary.json").exists() else {}
            outcomes = cweval_outcomes(variant_dir)
            for step_path in sorted((variant_dir / "agent_logs").glob("*/*/*/logs/steps.jsonl")):
                parts = step_path.relative_to(variant_dir / "agent_logs").parts
                suite, language, task = parts[0], parts[1], parts[2]
                run_id = f"cweval:{agent_dir.name}:{variant_dir.name}:{suite}:{language}:{task}"
                outcome = outcomes.get((suite, language, task), {})
                state = RunState(
                    meta={
                        "run_id": run_id,
                        "benchmark": "cweval",
                        "agent": agent_dir.name,
                        "model": summary.get("model", ""),
                        "variant": variant_dir.name,
                        "language": language,
                        "task": task,
                        "sample": "generated_0",
                        "suite": suite,
                        "framework": "",
                        "source_path": str(step_path.relative_to(root)),
                    },
                    outcomes={
                        "functional_passed": outcome.get("functional", ""),
                        "functional_total": 1 if "functional" in outcome else "",
                        "security_passed": outcome.get("secure", ""),
                        "security_total": 1 if "secure" in outcome else "",
                        "evaluation_status": "present" if outcome else "missing",
                    },
                )
                yield step_path, state


def scan_baxbench(root: Path) -> Iterable[tuple[Path, RunState]]:
    run_root = root / "baxbench" / "codex" / "scp_owasp"
    summary = load_json(run_root / "summary.json") if (run_root / "summary.json").exists() else {}
    for step_path in sorted(run_root.glob("codex/*/*/temp0.2-openapi-scp/sample*/logs/steps.jsonl")):
        sample_dir = step_path.parents[1]
        parts = sample_dir.relative_to(run_root / "codex").parts
        task, framework, temp, sample = parts[0], parts[1], parts[2], parts[3]
        lang = framework.split("-", 1)[0]
        test_result = load_json(sample_dir / "test_results.json") if (sample_dir / "test_results.json").exists() else {}
        run_id = f"baxbench:codex:scp_owasp:{task}:{framework}:{sample}"
        state = RunState(
            meta={
                "run_id": run_id,
                "benchmark": "baxbench",
                "agent": "codex",
                "model": summary.get("model", ""),
                "variant": "scp_owasp",
                "language": lang,
                "task": task,
                "sample": sample,
                "suite": "",
                "framework": framework,
                "source_path": str(step_path.relative_to(root)),
            },
            outcomes={
                "functional_passed": test_result.get("num_passed_ft", ""),
                "functional_total": test_result.get("num_total_ft", ""),
                "security_passed": test_result.get("num_passed_st", ""),
                "security_total": test_result.get("num_total_st", ""),
                "evaluation_status": "present" if test_result else "missing",
            },
        )
        yield step_path, state


def scan_dualgauge(root: Path) -> Iterable[tuple[Path, RunState]]:
    gen_root = root / "dualgauge" / "generated_samples"
    for event_path in sorted(gen_root.glob("*/*/*/raw_outputs/*_events.jsonl")):
        parts = event_path.relative_to(gen_root).parts
        language, agent, task = parts[0], parts[1], parts[2]
        sample_match = re.search(r"_sample_(\d+)_events\.jsonl$", event_path.name)
        sample = f"sample_{sample_match.group(1)}" if sample_match else "sample_0"
        summary_path = root / "dualgauge" / "evaluation_results" / language / agent / task / sample / "summary.json"
        summary = load_json(summary_path) if summary_path.exists() else {}
        cats = summary.get("categories", {})
        sec = cats.get("Security", {})
        func = cats.get("Functional Correctness", {})
        run_id = f"dualgauge:{language}:{agent}:{task}:{sample}"
        state = RunState(
            meta={
                "run_id": run_id,
                "benchmark": "dualgauge",
                "agent": agent,
                "model": summary.get("llm_name", agent),
                "variant": "",
                "language": language,
                "task": task,
                "sample": sample,
                "suite": "",
                "framework": "",
                "source_path": str(event_path.relative_to(root)),
            },
            outcomes={
                "functional_passed": func.get("passed_test_cases", ""),
                "functional_total": func.get("total_test_cases", ""),
                "security_passed": sec.get("passed_test_cases", ""),
                "security_total": sec.get("total_test_cases", ""),
                "gap_present": summary.get("gap_present", ""),
                "evaluation_status": summary.get("status", "missing" if not summary else ""),
            },
        )
        yield event_path, state


def build_markdown(run_rows: list[dict[str, Any]], event_rows: list[dict[str, Any]], source_root: Path) -> str:
    by_benchmark = Counter(r["benchmark"] for r in run_rows)
    by_agent = Counter(r["agent"] for r in run_rows)
    by_lang = Counter(r["language"] for r in run_rows if r["language"])

    def table(counter: Counter[str]) -> list[str]:
        return [f"| {k} | {v} |" for k, v in sorted(counter.items())]

    fam = Counter(r["behavior_family"] for r in event_rows)
    cats = Counter(r["command_category"] for r in event_rows if r["command_category"])

    lines = [
        "# Agent Behavior Extraction",
        "",
        f"Source root: `{source_root}`",
        "",
        f"Extracted `{len(event_rows)}` normalized events across `{len(run_rows)}` task/sample trajectories.",
        "",
        "## Runs by benchmark",
        "",
        "| Benchmark | Runs |",
        "|---|---:|",
        *table(by_benchmark),
        "",
        "## Runs by agent",
        "",
        "| Agent | Runs |",
        "|---|---:|",
        *table(by_agent),
        "",
        "## Runs by language",
        "",
        "| Language | Runs |",
        "|---|---:|",
        *table(by_lang),
        "",
        "## Behavior families",
        "",
        "| Family | Count |",
        "|---|---:|",
        *table(fam),
        "",
        "## Command categories",
        "",
        "| Category | Count |",
        "|---|---:|",
        *table(cats),
        "",
        "## Output files",
        "",
        "- `agent_behavior_events.jsonl`: full normalized event rows with previews/hashes.",
        "- `agent_behavior_events.csv`: tabular event view for spreadsheet/dataframe use.",
        "- `agent_behavior_runs.csv`: one row per trajectory with behavior counts and evaluation outcomes.",
        "",
        "Schema highlights: `behavior_family` is the coarse action family, `command_category` is the shell/action subclass, and native tool names are preserved in `tool_name`.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    all_events: list[dict[str, Any]] = []
    run_rows: list[dict[str, Any]] = []

    scanners = [
        (scan_cweval, parse_steps_jsonl),
        (scan_baxbench, parse_steps_jsonl),
        (scan_dualgauge, parse_dualgauge_event_file),
    ]
    for scanner, parser_fn in scanners:
        for path, state in scanner(root):
            events, state = parser_fn(path, state)
            all_events.extend(events)
            run_rows.append(run_summary(state))

    jsonl_path = out_dir / "agent_behavior_events.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for row in all_events:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    write_csv(out_dir / "agent_behavior_events.csv", all_events, EVENT_FIELDS)
    write_csv(out_dir / "agent_behavior_runs.csv", run_rows, RUN_FIELDS)
    (out_dir / "agent_behavior_summary.md").write_text(build_markdown(run_rows, all_events, root), encoding="utf-8")

    print(f"Wrote {jsonl_path}")
    print(f"Wrote {out_dir / 'agent_behavior_events.csv'}")
    print(f"Wrote {out_dir / 'agent_behavior_runs.csv'}")
    print(f"Wrote {out_dir / 'agent_behavior_summary.md'}")
    print(f"Events: {len(all_events)}")
    print(f"Runs: {len(run_rows)}")


if __name__ == "__main__":
    main()
