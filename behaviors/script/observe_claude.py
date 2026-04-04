#!/usr/bin/env python3
"""
observe_claude.py  —  Layers 1–3 Behavioral Recorder for Claude Code

Records the complete, unmodified behavioral trace of a Claude Code coding
session for later analysis.  This script is a *recorder*, not an analyzer —
it captures everything and saves it faithfully.  Behavioral coding and phase
segmentation (Layer 4) belong in a separate analysis script that reads
these logs after the fact.

Architecture
────────────
  Layer 1  Raw event capture      stream-json stdout  → raw_stream.jsonl
                                  stderr (--verbose)  → stderr.txt
                                  wall-clock stamps   → timestamped_events.jsonl

  Layer 2  Session transcript     Internal JSONL      → session_transcript.jsonl
           backup                 (copied from ~/.claude/projects/…
                                   after the run, in case stdout drops events)

  Layer 3  Live observation       Real-time terminal   (prints to console
           during the run         while recording)

  Layer 4  (separate script)      Reads the above logs and applies a
                                  behavioral coding scheme.

Output layout
─────────────
  behaviors/runs/
  └── baxbench_<task_id>_<YYYYMMDD_HHMMSS>/
      ├── task_info.json              # Task metadata from the prompts file
      ├── prompt.txt                  # Exact prompt sent to the agent
      ├── raw_stream.jsonl            # Verbatim stdout (stream-json events)
      ├── timestamped_events.jsonl    # Each event + _received_at wall clock
      ├── stderr.txt                  # Claude CLI stderr (--verbose output)
      ├── session_transcript.jsonl    # Internal JSONL from ~/.claude/projects/
      ├── generated_code.<ext>        # Code extracted from <CODE>…</CODE> tags
      ├── run_meta.json               # Run metadata, timing, environment info
      ├── workspace_diff.patch        # git diff of everything agent wrote via tools
      └── workspace/                  # Agent's working directory (tool-use files)

Usage
─────
    python observe_claude.py --prompts-file datasets/prompts_none.jsonl
    python observe_claude.py --prompts-file datasets/prompts_none.jsonl --task-index 3
    python observe_claude.py --prompts-file datasets/prompts_none.jsonl --max-turns 50

Requirements
────────────
    ANTHROPIC_API_KEY must be set (or `claude` authenticated via OAuth)
    `claude` CLI must be on PATH
    `git` on PATH (optional — used for workspace diffing)
"""

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

# ── Defaults ──────────────────────────────────────────────────────────────────
_PROJECT_ROOT     = Path(__file__).parent.parent.parent  # behaviors/script/ → project root
DEFAULT_PROMPTS   = _PROJECT_ROOT / "datasets" / "baxbench" / "prompts_none.jsonl"
_RUNS_BASE        = Path(__file__).parent.parent / "runs"  # behaviors/runs/<dataset>/
MODEL             = "claude-sonnet-4-6"
DEFAULT_MAX_TURNS = 25   # Single-file BaxBench tasks usually finish in 5–15
                         # turns; 25 gives headroom without risking runaway.
# ─────────────────────────────────────────────────────────────────────────────


# ═══════════════════════════════════════════════════════════════════════════════
#  LAYER 1 — RAW EVENT CAPTURE
# ═══════════════════════════════════════════════════════════════════════════════

def _stream_reader(
    stream,
    raw_log_path: Path,
    ts_log_path: Path,
    event_counter: dict,
    lock: threading.Lock,
):
    """
    Background thread: reads stdout line-by-line and writes two files.

      raw_log_path   — verbatim line from the CLI (byte-identical replay)
      ts_log_path    — same JSON + "_received_at" wall-clock field

    Also maintains event_counter (a shared dict) for the final summary
    and drives the Layer 3 live console output.
    """
    with (
        open(raw_log_path, "w", encoding="utf-8") as raw_f,
        open(ts_log_path, "w", encoding="utf-8") as ts_f,
    ):
        for raw_line in stream:
            received_at = datetime.now().isoformat()
            line = raw_line.rstrip("\n")
            if not line:
                continue

            # ── Raw log (verbatim) ────────────────────────────────────────
            raw_f.write(line + "\n")
            raw_f.flush()

            # ── Parse ─────────────────────────────────────────────────────
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                event = {"type": "raw_text", "content": line}

            # ── Timestamped log ───────────────────────────────────────────
            event["_received_at"] = received_at
            ts_f.write(json.dumps(event, ensure_ascii=False) + "\n")
            ts_f.flush()

            # ── Counting ──────────────────────────────────────────────────
            etype = event.get("type", "unknown")
            with lock:
                event_counter["total"] = event_counter.get("total", 0) + 1
                event_counter[etype] = event_counter.get(etype, 0) + 1

            # ── Layer 3: live console ─────────────────────────────────────
            _live_print(event)


def _stderr_reader(stream, stderr_path: Path, lock: threading.Lock, stderr_lines: list):
    """
    Background thread: captures stderr line-by-line with timestamps.
    --verbose output goes to stderr: context-building info, tool execution
    pipeline details, and retry notices.
    """
    with open(stderr_path, "w", encoding="utf-8") as f:
        for raw_line in stream:
            received_at = datetime.now().isoformat()
            line = raw_line.rstrip("\n")
            if not line:
                continue
            stamped = f"[{received_at}] {line}"
            f.write(stamped + "\n")
            f.flush()
            with lock:
                stderr_lines.append(stamped)


# ═══════════════════════════════════════════════════════════════════════════════
#  LAYER 3 — LIVE OBSERVATION (console output while recording)
# ═══════════════════════════════════════════════════════════════════════════════

def _live_print(event: dict):
    """
    Print a compact one-liner per interesting event so the researcher can
    watch the session in real time.
    """
    etype = event.get("type", "?")
    ts = event.get("_received_at", "")[11:23]  # HH:MM:SS.mmm

    if etype == "system":
        subtype = event.get("subtype", "")
        if subtype == "init":
            sid = event.get("session_id", "?")[:12]
            n_tools = len(event.get("tools", []))
            print(f"  {ts}  [init]       session={sid}…  tools={n_tools}", flush=True)
        else:
            print(f"  {ts}  [system]     {subtype}", flush=True)

    elif etype == "assistant":
        msg = event.get("message", {})
        for block in msg.get("content", []):
            btype = block.get("type", "")
            if btype == "tool_use":
                name = block.get("name", "?")
                inp = block.get("input", {})
                if isinstance(inp, dict):
                    preview_key = next(
                        (k for k in ("command", "file_path", "content",
                                     "pattern", "query")
                         if k in inp),
                        None,
                    )
                    if preview_key:
                        val = str(inp[preview_key])[:60].replace("\n", "\\n")
                        print(f"  {ts}  [tool_use]   {name}  {preview_key}={val}",
                              flush=True)
                    else:
                        print(f"  {ts}  [tool_use]   {name}", flush=True)
                else:
                    print(f"  {ts}  [tool_use]   {name}", flush=True)

            elif btype == "thinking":
                text = (block.get("thinking") or "")[:70].replace("\n", " ")
                print(f"  {ts}  [thinking]   {text}…", flush=True)

            elif btype == "text":
                text = (block.get("text") or "").strip()[:70].replace("\n", " ")
                if text:
                    print(f"  {ts}  [text]       {text}…", flush=True)

    elif etype == "user":
        msg = event.get("message", {})
        for block in msg.get("content", []):
            if block.get("type") == "tool_result":
                tuid = (block.get("tool_use_id") or "")[:12]
                is_err = block.get("is_error", False)
                tag = "tool_ERR" if is_err else "tool_res"
                print(f"  {ts}  [{tag}]  id={tuid}…", flush=True)

    elif etype == "result":
        cost = event.get("total_cost_usd")
        cost_s = f"  cost=${cost:.4f}" if cost is not None else ""
        sub = event.get("subtype", "?")
        print(f"  {ts}  [result]     subtype={sub}{cost_s}", flush=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  LAYER 2 — SESSION TRANSCRIPT BACKUP
# ═══════════════════════════════════════════════════════════════════════════════

def _copy_session_transcript(run_dir: Path, session_id: str | None,
                             run_start: datetime):
    """
    After the run, copy the internal session JSONL from
    ~/.claude/projects/<hash>/<session_id>.jsonl

    This is a backup in case stdout stream-json drops tail events.
    The internal JSONL always has the complete trace.
    """
    claude_projects = Path.home() / ".claude" / "projects"
    if not claude_projects.exists():
        print("[layer2] ~/.claude/projects/ not found — skipping transcript backup")
        return

    candidates = list(claude_projects.rglob("*.jsonl"))
    if not candidates:
        print("[layer2] No session JSONL files found — skipping transcript backup")
        return

    # Prefer exact session_id match in filename
    matched = None
    if session_id:
        for c in candidates:
            if session_id in c.stem:
                matched = c
                break

    # Fallback: most recently modified .jsonl touched during this run
    # (time-bounded to avoid grabbing a file from a previous run)
    if not matched:
        run_start_ts = run_start.timestamp()
        recent = [
            c for c in candidates
            if c.stat().st_mtime >= run_start_ts - 5  # 5s grace for clock skew
        ]
        if recent:
            recent.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            matched = recent[0]
        else:
            print("[layer2] No JSONL modified during this run — skipping transcript backup")
            return

    dest = run_dir / "session_transcript.jsonl"
    try:
        shutil.copy2(matched, dest)
        size_kb = dest.stat().st_size / 1024
        print(f"[layer2] Session transcript backed up ({size_kb:.1f} KB)")
        print(f"         source: {matched}")
    except Exception as e:
        print(f"[layer2] Failed to copy transcript: {e}")


def _extract_session_id(ts_log_path: Path) -> str | None:
    """Read the init event from timestamped_events.jsonl to get session_id."""
    try:
        with open(ts_log_path, "r", encoding="utf-8") as f:
            for line in f:
                event = json.loads(line)
                if (event.get("type") == "system"
                        and event.get("subtype") == "init"):
                    return event.get("session_id")
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  GENERATED CODE EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════════

# env_id format: "<Language>-<Framework>"  (e.g. "Python-FastAPI", "Go-Fiber")
_LANG_TO_FILENAME = {
    "python":     "app.py",
    "javascript": "app.js",
    "typescript": "app.ts",
    "go":         "main.go",
    "rust":       "main.rs",
    "java":       "App.java",
    "ruby":       "app.rb",
    "php":        "app.php",
}

def _infer_filename(task: dict) -> str:
    """Derive the output filename from env_id (e.g. 'Python-FastAPI' → 'app.py')."""
    env_id = task.get("env_id") or task.get("task_id") or ""
    lang   = env_id.split("-")[0].lower()
    return _LANG_TO_FILENAME.get(lang, "generated_code.txt")

def _extract_generated_code(raw_log: Path, run_dir: Path,
                            workspace: Path, task: dict) -> list[str]:
    """
    Parse raw_stream.jsonl for assistant text blocks, then extract code from
    <CODE>…</CODE> tags (the format used by the BaxBench prompts).
    Code is written into workspace/ so it lives alongside any tool-written files.

    For single-file responses:
        <CODE> … </CODE>
        → workspace/<code_filename>  (e.g. workspace/app.py)

    For multi-file responses:
        <FILEPATH> path/to/file </FILEPATH>
        <CODE> … </CODE>
        → workspace/<filename> for each block

    Returns a list of paths written (relative to run_dir).
    """
    # ── Collect all assistant text across events ──────────────────────────────
    # Events are streamed; the last complete assistant text block is the final
    # response. We take the longest text block to avoid truncated partials.
    text_blocks: list[str] = []
    try:
        with open(raw_log, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") != "assistant":
                    continue
                for block in event.get("message", {}).get("content", []):
                    if block.get("type") == "text":
                        text = block.get("text", "").strip()
                        if text:
                            text_blocks.append(text)
    except FileNotFoundError:
        return []

    if not text_blocks:
        return []

    # Use the longest text block (most complete streaming snapshot)
    full_text = max(text_blocks, key=len)

    # ── Try multi-file pattern first: <FILEPATH>…</FILEPATH><CODE>…</CODE> ───
    filepath_pattern = re.compile(
        r"<FILEPATH>\s*(.+?)\s*</FILEPATH>\s*<CODE>(.*?)</CODE>",
        re.DOTALL | re.IGNORECASE,
    )
    multi_matches = filepath_pattern.findall(full_text)

    written: list[str] = []

    if multi_matches:
        for filepath, code in multi_matches:
            dest = workspace / Path(filepath.strip()).name  # flatten to filename only
            dest.write_text(code.strip(), encoding="utf-8")
            written.append(str(dest.relative_to(run_dir)))
        return written

    # ── Single-file pattern: <CODE>…</CODE> ──────────────────────────────────
    code_pattern = re.compile(r"<CODE>(.*?)</CODE>", re.DOTALL | re.IGNORECASE)
    match = code_pattern.search(full_text)

    if match:
        code     = match.group(1).strip()
        filename = task.get("code_filename") or _infer_filename(task)
        dest     = workspace / filename
        dest.write_text(code, encoding="utf-8")
        written.append(str(dest.relative_to(run_dir)))
        return written

    # ── No tags found — save raw response as fallback ─────────────────────────
    dest = workspace / "generated_code.txt"
    dest.write_text(full_text, encoding="utf-8")
    written.append(str(dest.relative_to(run_dir)))
    return written


# ═══════════════════════════════════════════════════════════════════════════════
#  WORKSPACE GIT DIFF
# ═══════════════════════════════════════════════════════════════════════════════

def _init_workspace_git(workspace: Path) -> bool:
    """
    Initialize a git repo in the workspace so we can produce a clean diff
    of everything the agent wrote via tools.  Returns True if git is available.
    """
    try:
        subprocess.run(
            ["git", "init"], cwd=workspace,
            capture_output=True, text=True, check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "observer@research"],
            cwd=workspace, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Observer"],
            cwd=workspace, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "init (empty workspace)"],
            cwd=workspace, capture_output=True, text=True, check=True,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("[warn] git not available — workspace diffing disabled")
        return False


def _capture_workspace_diff(workspace: Path, run_dir: Path):
    """Stage all files and save the full diff as a .patch file."""
    try:
        subprocess.run(
            ["git", "add", "-A"], cwd=workspace,
            capture_output=True, text=True,
        )
        diff = subprocess.run(
            ["git", "diff", "--cached"],
            cwd=workspace, capture_output=True, text=True,
        )
        if diff.stdout.strip():
            (run_dir / "workspace_diff.patch").write_text(
                diff.stdout, encoding="utf-8",
            )
            stat = subprocess.run(
                ["git", "diff", "--cached", "--stat"],
                cwd=workspace, capture_output=True, text=True,
            )
            print(f"[observe] workspace_diff.patch saved")
            if stat.stdout.strip():
                print(f"          {stat.stdout.strip().splitlines()[-1]}")
        subprocess.run(
            ["git", "commit", "-m", "agent output"],
            cwd=workspace, capture_output=True, text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass


# ═══════════════════════════════════════════════════════════════════════════════
#  ENVIRONMENT INFO (for reproducibility)
# ═══════════════════════════════════════════════════════════════════════════════

def _collect_environment_info() -> dict:
    """Capture tool versions so runs are reproducible."""
    info = {
        "os":     platform.platform(),
        "python": platform.python_version(),
    }
    for name, cmd in [("claude_cli", ["claude", "--version"]),
                      ("git",        ["git", "--version"])]:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            info[name] = r.stdout.strip() or r.stderr.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            info[name] = "(not found)"
    return info


# ═══════════════════════════════════════════════════════════════════════════════
#  AGENT RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

def run_agent(prompt: str, workspace: Path, run_dir: Path, max_turns: int) -> dict:
    """
    Launch `claude` CLI in stream-json mode, capture stdout + stderr in
    background threads, and return run metadata.

    Flags used:
      --print                       Non-interactive (run and exit)
      --output-format stream-json   One JSON event per line on stdout
      --verbose                     Detailed stderr: context building,
                                    tool execution pipeline, retries
      --model <model>               Pin model
      --max-turns <n>               Safety limit on agentic turns
      --dangerously-skip-permissions  Auto-approve all tool calls (required
                                      for unattended execution)
    """
    raw_log_path = run_dir / "raw_stream.jsonl"
    ts_log_path  = run_dir / "timestamped_events.jsonl"
    stderr_path  = run_dir / "stderr.txt"

    cmd = [
        "claude",
        "--print",
        "--output-format", "stream-json",
        "--verbose",
        "--model", MODEL,
        "--max-turns", str(max_turns),
        "--dangerously-skip-permissions",
    ]

    print(f"\n{'═' * 66}")
    print(f"  STARTING CLAUDE CODE")
    print(f"  model     : {MODEL}")
    print(f"  max_turns : {max_turns}")
    print(f"  workspace : {workspace}")
    print(f"  command   : {' '.join(cmd)}")
    print(f"{'═' * 66}\n")

    event_counter: dict = {}
    stderr_lines:  list = []
    lock = threading.Lock()
    start_wall = datetime.now()

    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(workspace),
        env={**os.environ},
    )

    stdout_thread = threading.Thread(
        target=_stream_reader,
        args=(process.stdout, raw_log_path, ts_log_path, event_counter, lock),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_stderr_reader,
        args=(process.stderr, stderr_path, lock, stderr_lines),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()

    try:
        process.stdin.write(prompt)
        process.stdin.close()
    except BrokenPipeError:
        pass

    stdout_thread.join()
    stderr_thread.join()
    process.wait()

    end_wall = datetime.now()
    session_id = _extract_session_id(ts_log_path)

    return {
        "exit_code":     process.returncode,
        "event_counter": dict(event_counter),
        "wall_seconds":  round((end_wall - start_wall).total_seconds(), 2),
        "start_time":    start_wall.isoformat(),
        "end_time":      end_wall.isoformat(),
        "session_id":    session_id,
        "stderr_lines":  len(stderr_lines),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _write_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _count_tool_uses(raw_log: Path) -> int:
    """Count unique tool_use blocks in raw_stream.jsonl without full extraction."""
    seen = set()
    try:
        with open(raw_log, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") != "assistant":
                    continue
                for block in event.get("message", {}).get("content", []):
                    if block.get("type") == "tool_use" and block.get("id"):
                        seen.add(block["id"])
    except FileNotFoundError:
        pass
    return len(seen)


def _list_workspace_files(workspace: Path) -> list[dict]:
    """List all non-git files in workspace with sizes."""
    return [
        {"path": str(p.relative_to(workspace)), "size_bytes": p.stat().st_size}
        for p in sorted(workspace.rglob("*"))
        if p.is_file() and ".git" not in p.parts
    ]


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--prompts-file", default=str(DEFAULT_PROMPTS),
        help="Path to JSONL prompts file (default: datasets/prompts_none.jsonl)",
    )
    parser.add_argument(
        "--task-index", type=int, default=0,
        help="Row index in the prompts file (default: 0)",
    )
    parser.add_argument(
        "--max-turns", type=int, default=DEFAULT_MAX_TURNS,
        help=f"Max agentic turns (default: {DEFAULT_MAX_TURNS})",
    )
    return parser.parse_args()


def _load_task(path: Path, index: int) -> tuple[dict, str]:
    """
    Load one record from a JSONL prompts file.
    Returns (task_info dict, prompt string).
    The prompt field is removed from task_info and returned separately.
    """
    with open(path, "r", encoding="utf-8") as f:
        lines = [l for l in f if l.strip()]
    if index >= len(lines):
        raise IndexError(
            f"task-index {index} out of range (file has {len(lines)} records)"
        )
    record = json.loads(lines[index])
    prompt = record.pop("prompt")
    # "response" field (present in prompts_specific.jsonl) is a reference answer —
    # keep it in task_info for evaluation but never send it to the agent.
    record.pop("response", None)
    return record, prompt


def main() -> int:
    args = parse_args()

    # ── 1. Pre-flight ─────────────────────────────────────────────────────────
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("[warn] ANTHROPIC_API_KEY not set; proceeding (OAuth may work)")

    prompts_path = Path(args.prompts_file)
    if not prompts_path.exists():
        print(f"[error] Prompts file not found: {prompts_path}", file=sys.stderr)
        return 1

    # ── 2. Environment info ───────────────────────────────────────────────────
    env_info = _collect_environment_info()
    print(f"[observe] Environment: Python {env_info['python']}, "
          f"CLI {env_info['claude_cli']}, OS {env_info['os']}")

    # ── 3. Load task ──────────────────────────────────────────────────────────
    print(f"[observe] Loading prompts: {prompts_path}")
    try:
        task, prompt = _load_task(prompts_path, args.task_index)
    except IndexError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 1

    print(f"[observe] Task #{args.task_index}: {task['task_id']}")
    if task.get("env_framework"):
        print(f"          framework : {task['env_framework']}")
    if task.get("safety_prompt"):
        print(f"          safety    : {task['safety_prompt']}")

    # ── 4. Create run directory ───────────────────────────────────────────────
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")  # kept for run_meta only
    dataset_name   = prompts_path.parent.name          # e.g. datasets/baxbench/ → "baxbench"
    safety_variant = task.get("safety_prompt", "none") # "none" | "generic" | "specific"
    run_dir        = _RUNS_BASE / dataset_name / safety_variant / task['task_id']
    workspace = run_dir / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    _write_json(run_dir / "task_info.json", task)
    (run_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    print(f"[observe] Run directory: {run_dir}")
    print(f"[observe] Prompt: {len(prompt)} chars")

    # ── 5. Prepare workspace ──────────────────────────────────────────────────
    has_git = _init_workspace_git(workspace)

    # ── 6. Run the agent (Layers 1 + 3) ──────────────────────────────────────
    result = run_agent(prompt, workspace, run_dir, args.max_turns)

    # ── 7. Post-run captures ──────────────────────────────────────────────────
    if has_git:
        _capture_workspace_diff(workspace, run_dir)

    # Layer 2: back up internal session transcript
    _copy_session_transcript(run_dir, result["session_id"],
                             datetime.fromisoformat(result["start_time"]))

    # Extract generated code from <CODE>…</CODE> tags in the agent's response
    generated = _extract_generated_code(run_dir / "raw_stream.jsonl", run_dir, workspace, task)
    if generated:
        print(f"[observe] Generated code → {', '.join(generated)}")

    # ── 8. Write run metadata ─────────────────────────────────────────────────
    tool_use_count = _count_tool_uses(run_dir / "raw_stream.jsonl")
    agent_files    = _list_workspace_files(workspace)

    run_meta = {
        "task_id":        task["task_id"],
        "task_index":     args.task_index,
        "dataset":        dataset_name,
        "safety_variant": safety_variant,
        "prompts_file":   str(prompts_path),
        "model":          MODEL,
        "max_turns":      args.max_turns,
        "timestamp":      timestamp,
        "workspace":      str(workspace),
        "exit_code":      result["exit_code"],
        "session_id":     result["session_id"],
        "wall_seconds":   result["wall_seconds"],
        "start_time":     result["start_time"],
        "end_time":       result["end_time"],
        "event_counts":   result["event_counter"],
        "tool_use_count": tool_use_count,
        "stderr_lines":   result["stderr_lines"],
        "generated_files": generated,
        "agent_files":    agent_files,
        "environment":    env_info,
        "cli_flags": [
            "--print", "--output-format", "stream-json", "--verbose",
            "--model", MODEL, "--max-turns", str(args.max_turns),
            "--dangerously-skip-permissions",
        ],
    }
    _write_json(run_dir / "run_meta.json", run_meta)

    # ── 9. Print summary ──────────────────────────────────────────────────────
    print(f"\n{'═' * 66}")
    print(f"  RUN COMPLETE")
    print(f"{'═' * 66}")
    print(f"  task        : {task['task_id']}")
    print(f"  exit code   : {result['exit_code']}")
    print(f"  wall clock  : {result['wall_seconds']}s")
    print(f"  session_id  : {result['session_id'] or '(not found)'}")

    ec = result["event_counter"]
    print(f"\n  events captured:")
    print(f"    total           : {ec.get('total', 0)}")
    for etype in ("system", "assistant", "user", "result", "raw_text"):
        if ec.get(etype):
            print(f"    {etype:<16}: {ec[etype]}")
    print(f"    stderr lines    : {result['stderr_lines']}")

    if generated:
        print(f"\n  generated code:")
        for g in generated:
            size = (run_dir / g).stat().st_size
            print(f"    {g:<44} ({size:,} bytes)")

    if agent_files:
        print(f"\n  workspace files (via tools):")
        for fi in agent_files:
            print(f"    {fi['path']:<44} ({fi['size_bytes']:,} bytes)")

    print(f"\n  all outputs → {run_dir}")
    print(f"{'═' * 66}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
