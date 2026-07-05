#!/usr/bin/env python3
"""Run Claude Code agents on local BaxBench tasks and record behavior logs."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.baxbench.run_codex_baxbench import DEFAULT_DATASET, build_prompt, load_tasks, select_tasks


DEFAULT_MODEL = "sonnet5"
DEFAULT_OUT = Path("data/raw/baxbench/runs/claude_code") / DEFAULT_MODEL
DEFAULT_VARIANT = "claude-code-cli-agent"


@dataclass
class Paths:
    """Resolved filesystem locations for one Claude Code BaxBench run."""

    root: Path
    workspace: Path
    logs: Path
    steps: Path
    raw_events: Path
    stderr: Path
    final_message: Path
    metadata: Path
    task_record: Path


def now() -> float:
    """Return a floating Unix timestamp for event records."""

    return time.time()


def write_jsonl(path: Path, obj: dict[str, Any]) -> None:
    """Append one JSON object to a UTF-8 JSONL file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")


def clean_slug(value: str) -> str:
    """Make a BaxBench task/env identifier safe for directory names."""

    return "".join(ch if ch.isalnum() or ch in "._=-" else "_" for ch in value)


def make_paths(out_root: Path, variant: str, task: dict[str, Any], sample: str) -> Paths:
    """Derive all output paths for a Claude run from task metadata."""

    root = out_root / variant / clean_slug(task["scenario_id"]) / clean_slug(task["env_id"]) / sample
    return Paths(
        root=root,
        workspace=root / "workspace",
        logs=root / "logs",
        steps=root / "logs" / "steps.jsonl",
        raw_events=root / "logs" / "claude_code_events.jsonl",
        stderr=root / "logs" / "claude_code.stderr.log",
        final_message=root / "final_message.txt",
        metadata=root / "metadata.json",
        task_record=root / "task.json",
    )


def init_run(paths: Paths, task: dict[str, Any], args: argparse.Namespace) -> None:
    """Create or reset the run directory and write reproducibility metadata."""

    if paths.root.exists() and args.force:
        shutil.rmtree(paths.root)
    paths.workspace.mkdir(parents=True, exist_ok=True)
    paths.logs.mkdir(parents=True, exist_ok=True)
    metadata = {
        "agent": "claude_code",
        "model": args.model,
        "variant": args.variant,
        "runner": "claude-code-cli",
        "prompt_mode": args.prompt_mode,
        "task_id": task["task_id"],
        "scenario_id": task["scenario_id"],
        "env_id": task["env_id"],
        "created_at": now(),
    }
    paths.metadata.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    paths.task_record.write_text(json.dumps(task, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    for file_path in (paths.steps, paths.raw_events, paths.stderr, paths.final_message):
        if file_path.exists() and args.force:
            file_path.unlink()


def write_prompt(paths: Paths, task: dict[str, Any], prompt_mode: str) -> str:
    """Persist the exact prompt used for reproducibility."""

    prompt = build_prompt(task, prompt_mode)
    (paths.root / "prompt.txt").write_text(prompt, encoding="utf-8")
    return prompt


def text_from_content(content: Any) -> str:
    """Extract text from Claude stream-json message content blocks."""

    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "\n".join(parts)
    return ""


def normalize_claude_event(event: dict[str, Any]) -> dict[str, Any]:
    """Map one raw Claude Code stream-json event into the shared log envelope."""

    event_type = event.get("type", "claude_event")
    message = event.get("message") if isinstance(event.get("message"), dict) else {}
    subtype = event.get("subtype", "")
    tool_name = event.get("tool_name") or message.get("tool_name") or ""
    command = event.get("command") or ""
    text = event.get("result") or event.get("text") or text_from_content(message.get("content"))

    if event_type == "assistant" or text:
        normalized_type = "llm_call"
    elif event_type in {"tool_use", "tool_result"}:
        normalized_type = f"tool_use/{tool_name or subtype or event_type}"
    else:
        normalized_type = f"claude_code/{event_type}"

    return {
        "type": normalized_type,
        "timestamp": now(),
        "native_event_type": event_type,
        "tool_name": tool_name,
        "input": {"command": command} if command else {},
        "output": {"output": text, "exit_code": event.get("exit_code")},
        "raw_event": event,
    }


def run_task(task: dict[str, Any], args: argparse.Namespace) -> None:
    """Launch Claude Code for one BaxBench task and record every emitted event."""

    paths = make_paths(args.out, args.variant, task, args.sample)
    init_run(paths, task, args)
    prompt = write_prompt(paths, task, args.prompt_mode)

    write_jsonl(
        paths.steps,
        {
            "type": "task.started",
            "timestamp": now(),
            "agent": "claude_code",
            "runner": "claude-code-cli",
            "model": args.model,
            "task_id": task["task_id"],
            "workspace": str(paths.workspace),
        },
    )

    if args.dry_run:
        print(f"[dry-run] claude-code {task['task_id']} -> {paths.root}")
        return

    cmd = [
        args.claude_bin,
        "--print",
        "--output-format",
        "stream-json",
        "--verbose",
        "--model",
        args.model,
        "--permission-mode",
        args.permission_mode,
        "--no-session-persistence",
        "--debug-file",
        str((paths.logs / "claude_code.debug.log").resolve()),
    ]
    if args.bare:
        cmd.append("--bare")
    if args.safe_mode:
        cmd.append("--safe-mode")
    if args.allowed_tools:
        cmd.extend(["--allowedTools", args.allowed_tools])

    write_jsonl(paths.steps, {"type": "agent.command", "timestamp": now(), "command": cmd, "cwd": str(paths.workspace)})
    with subprocess.Popen(
        cmd,
        cwd=paths.workspace,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    ) as proc:
        assert proc.stdin is not None
        assert proc.stdout is not None
        assert proc.stderr is not None
        proc.stdin.write(prompt)
        proc.stdin.close()
        final_text = ""
        for line in proc.stdout:
            line = line.rstrip("\n")
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                event = {"type": "stdout.text", "text": line}
            write_jsonl(paths.raw_events, event)
            write_jsonl(paths.steps, normalize_claude_event(event))
            if isinstance(event, dict) and event.get("type") == "result" and isinstance(event.get("result"), str):
                final_text = event["result"]

        stderr_text = proc.stderr.read()
        return_code = proc.wait()

    if final_text:
        paths.final_message.write_text(final_text, encoding="utf-8")
    if stderr_text:
        paths.stderr.write_text(stderr_text, encoding="utf-8")
    write_jsonl(
        paths.steps,
        {
            "type": "task.completed" if return_code == 0 else "task.failed",
            "timestamp": now(),
            "exit_code": return_code,
            "stderr_path": str(paths.stderr) if stderr_text else "",
            "final_message_path": str(paths.final_message),
        },
    )
    if return_code != 0:
        raise RuntimeError(f"claude run failed for {task['task_id']} with exit code {return_code}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments for task selection and Claude runner behavior."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--model", default=os.environ.get("CLAUDE_MODEL", DEFAULT_MODEL))
    parser.add_argument("--variant", default=DEFAULT_VARIANT)
    parser.add_argument("--sample", default="sample0")
    parser.add_argument("--prompt-mode", choices=["baxbench", "debug-observation"], default="baxbench")
    parser.add_argument("--claude-bin", default=os.environ.get("CLAUDE_BIN", "claude"))
    parser.add_argument("--permission-mode", default="bypassPermissions")
    parser.add_argument("--allowed-tools", default="Bash,Read,Write,Edit,MultiEdit,LS")
    parser.add_argument("--bare", action="store_true")
    parser.add_argument("--no-safe-mode", dest="safe_mode", action="store_false")
    parser.set_defaults(safe_mode=True)
    parser.add_argument("--task-id")
    parser.add_argument("--language")
    parser.add_argument("--framework")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true", help="Remove existing run directory first.")
    parser.add_argument("--dry-run", action="store_true", help="Create run dirs/prompts without API calls.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    """Load tasks, apply filters, and run Claude Code over the selected tasks."""

    args = parse_args(argv)
    if not args.dataset.exists():
        print(f"Dataset not found: {args.dataset}", file=sys.stderr)
        return 2
    if shutil.which(args.claude_bin) is None:
        print(f"Claude CLI not found: {args.claude_bin}", file=sys.stderr)
        return 2

    rows = load_tasks(args.dataset)
    selected = select_tasks(rows, args.task_id, args.limit, args.offset, args.language, args.framework)
    if not selected:
        print("No BaxBench tasks matched the requested filters.", file=sys.stderr)
        return 1

    for task in selected:
        run_task(task, args)
        print(f"wrote {make_paths(args.out, args.variant, task, args.sample).root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
