#!/usr/bin/env python3
"""
observe_agent_openhands.py  —  Layers 1–3 Behavioral Recorder for OpenHands

Records the complete behavioral trace of an OpenHands coding agent session
for later analysis.  Supports running the same BaxBench tasks across multiple
LLMs to compare behavioral differences.

Input: Pre-prepared JSONL prompt files (prompts_none.jsonl, prompts_generic.jsonl,
       prompts_specific.jsonl) where each line is a JSON object with task_id,
       scenario_id, env_id, safety_prompt, and prompt fields.

Output layout
─────────────
  behaviors/openhands_run/<dataset>/
  └── <safety_prompt>_<task_id>_<model_short>_<YYYYMMDD_HHMMSS>/
      ├── task_info.json              # Task metadata (task_id, scenario_id, etc.)
      ├── prompt.txt                  # Exact prompt sent to the agent
      ├── run_meta.json               # Timing, cost, model, environment
      ├── events_live.jsonl           # Timestamped event log from callback
      ├── trajectory/                 # OpenHands persisted event files
      │   ├── base_state.json
      │   └── events/
      │       └── event-00000-xxx.json ...
      ├── workspace_diff.patch        # git diff of agent output
      └── workspace/                  # Agent's working directory

Usage
─────
    # Run first 5 tasks from prompts_none.jsonl with GPT-5 mini
    python observe_agent_openhands.py --prompts prompts_none.jsonl -n 5 --model openai/gpt-5-mini

    # Run all tasks from prompts_specific.jsonl with Claude
    python observe_agent_openhands.py --prompts prompts_specific.jsonl --model anthropic/claude-sonnet-4-6

    # Run first 3 tasks across all conditions (custom dataset name)
    for f in prompts_none.jsonl prompts_generic.jsonl prompts_specific.jsonl; do
        python observe_agent_openhands.py --prompts $f -n 3 --model openai/gpt-5-mini --dataset baxbench
    done

Requirements
────────────
    pip install openhands-sdk openhands-tools
    Appropriate API key set in environment:
      ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, etc.
"""

import argparse
import json
import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from pydantic import SecretStr

from openhands.sdk import LLM, Agent, Conversation, Tool, LocalWorkspace
from openhands.tools.terminal import TerminalTool
from openhands.tools.file_editor import FileEditorTool

# ── Defaults ──────────────────────────────────────────────────────────────────
BEHAVIORS_DIR        = Path(__file__).parent.parent
DEFAULT_MODEL        = "openai/gpt-5-mini"
DEFAULT_MAX_ITER     = 50
DEFAULT_DATASET      = "baxbench"
# ─────────────────────────────────────────────────────────────────────────────


# ═══════════════════════════════════════════════════════════════════════════════
#  LOAD TASKS FROM JSONL
# ═══════════════════════════════════════════════════════════════════════════════

def load_tasks(prompts_path: Path, n: int | None = None) -> list[dict]:
    """Load tasks from a JSONL file. Each line is a JSON object with
    task_id, scenario_id, env_id, safety_prompt, prompt fields."""
    tasks = []
    with open(prompts_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            tasks.append(json.loads(line))
    if n is not None:
        tasks = tasks[:n]
    return tasks


# ═══════════════════════════════════════════════════════════════════════════════
#  LAYER 3 — LIVE OBSERVATION CALLBACK
# ═══════════════════════════════════════════════════════════════════════════════

def make_event_callback(log_path: Path):
    """
    Returns a callback that OpenHands calls for every event.
    Writes each event to a timestamped JSONL file and prints live progress.
    """
    log_file = open(log_path, "w", encoding="utf-8")
    event_count = [0]

    def callback(event):
        received_at = datetime.now().isoformat()
        event_count[0] += 1

        # Serialize event
        try:
            if hasattr(event, "model_dump"):
                event_dict = event.model_dump()
            elif hasattr(event, "to_dict"):
                event_dict = event.to_dict()
            elif hasattr(event, "__dict__"):
                event_dict = {k: v for k, v in event.__dict__.items() if not k.startswith("_")}
            else:
                event_dict = {"raw": str(event)}
        except Exception:
            event_dict = {"raw": str(event)}

        event_dict["_received_at"] = received_at
        event_dict["_seq"] = event_count[0]

        try:
            log_file.write(json.dumps(event_dict, default=str, ensure_ascii=False) + "\n")
            log_file.flush()
        except Exception:
            pass

        _live_print(event, event_count[0], received_at)

    def close():
        log_file.close()

    callback.close = close
    callback.event_count = event_count
    return callback


def _live_print(event, seq: int, ts: str):
    """Compact one-liner per event for live observation."""
    ts_short = ts[11:23]
    event_type = type(event).__name__

    detail = ""
    if hasattr(event, "tool_call_metadata") and event.tool_call_metadata:
        tool_name = getattr(event.tool_call_metadata, "function_name", "?")
        detail = f"tool={tool_name}"
    elif hasattr(event, "command") and event.command:
        detail = f"cmd={str(event.command)[:60].replace(chr(10), '\\n')}"
    elif hasattr(event, "path") and event.path:
        detail = f"path={event.path}"
    elif hasattr(event, "content") and event.content:
        detail = f"content={str(event.content)[:60].replace(chr(10), '\\n')}"
    elif hasattr(event, "message") and event.message:
        detail = f"msg={str(event.message)[:60].replace(chr(10), '\\n')}"

    print(f"  {ts_short}  [{seq:03d}] {event_type:<30} {detail}", flush=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  WORKSPACE GIT DIFF
# ═══════════════════════════════════════════════════════════════════════════════

def _init_workspace_git(workspace: Path) -> bool:
    try:
        subprocess.run(["git", "init"], cwd=workspace, capture_output=True, text=True, check=True)
        subprocess.run(["git", "config", "user.email", "observer@research"], cwd=workspace, capture_output=True, text=True, check=True)
        subprocess.run(["git", "config", "user.name", "Observer"], cwd=workspace, capture_output=True, text=True, check=True)
        subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=workspace, capture_output=True, text=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("[warn] git not available — workspace diffing disabled")
        return False


def _capture_workspace_diff(workspace: Path, run_dir: Path):
    try:
        subprocess.run(["git", "add", "-A"], cwd=workspace, capture_output=True, text=True)
        diff = subprocess.run(["git", "diff", "--cached"], cwd=workspace, capture_output=True, text=True)
        if diff.stdout.strip():
            (run_dir / "workspace_diff.patch").write_text(diff.stdout, encoding="utf-8")
            stat = subprocess.run(["git", "diff", "--cached", "--stat"], cwd=workspace, capture_output=True, text=True)
            print(f"[observe] workspace_diff.patch saved")
            if stat.stdout.strip():
                print(f"          {stat.stdout.strip().splitlines()[-1]}")
        subprocess.run(["git", "commit", "-m", "agent output"], cwd=workspace, capture_output=True, text=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass


# ═══════════════════════════════════════════════════════════════════════════════
#  ENVIRONMENT & API KEY
# ═══════════════════════════════════════════════════════════════════════════════

def _collect_environment_info() -> dict:
    info = {
        "os": platform.platform(),
        "python": platform.python_version(),
    }
    try:
        import openhands
        info["openhands_sdk"] = getattr(openhands, "__version__", "unknown")
    except Exception:
        info["openhands_sdk"] = "unknown"
    try:
        result = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=5)
        info["git"] = result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        info["git"] = "(not found)"
    return info


def _resolve_api_key(model: str) -> str | None:
    provider = model.split("/")[0].lower() if "/" in model else ""
    key_map = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai":    "OPENAI_API_KEY",
        "gemini":    "GEMINI_API_KEY",
        "google":    "GEMINI_API_KEY",
        "deepseek":  "DEEPSEEK_API_KEY",
        "mistral":   "MISTRAL_API_KEY",
    }
    env_var = key_map.get(provider)
    if env_var:
        return os.environ.get(env_var)
    return os.environ.get("LLM_API_KEY")


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _write_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def _list_workspace_files(workspace: Path) -> list[dict]:
    files = []
    for p in sorted(workspace.rglob("*")):
        if p.is_file() and ".git" not in p.parts:
            files.append({
                "path": str(p.relative_to(workspace)),
                "size_bytes": p.stat().st_size,
            })
    return files


def _model_short_name(model: str) -> str:
    return model.split("/")[-1] if "/" in model else model


# ═══════════════════════════════════════════════════════════════════════════════
#  RUN ONE TASK
# ═══════════════════════════════════════════════════════════════════════════════

def run_one_task(
    task: dict,
    model: str,
    api_key: str,
    max_iterations: int,
    env_info: dict,
    task_index: int,
    runs_dir: Path,
) -> dict:
    """Run a single task and return the run_meta dict."""

    task_id = task["task_id"]
    safety = task.get("safety_prompt", "unknown")
    prompt = task["prompt"]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_short = _model_short_name(model)
    run_dir = runs_dir / f"{safety}_{task_id}_{model_short}_{timestamp}"
    workspace = run_dir / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    persistence_dir = run_dir / "trajectory"
    persistence_dir.mkdir(parents=True, exist_ok=True)

    # Save task info and prompt
    _write_json(run_dir / "task_info.json", {
        "task_id": task_id,
        "scenario_id": task.get("scenario_id"),
        "env_id": task.get("env_id"),
        "spec_type": task.get("spec_type"),
        "safety_prompt": safety,
    })
    (run_dir / "prompt.txt").write_text(prompt, encoding="utf-8")

    print(f"\n{'═' * 66}")
    print(f"  TASK {task_index + 1}: {task_id}")
    print(f"  condition    : {safety}")
    print(f"  model        : {model}")
    print(f"  max_iter     : {max_iterations}")
    print(f"  workspace    : {workspace}")
    print(f"{'═' * 66}\n")

    # Prepare workspace git
    has_git = _init_workspace_git(workspace)

    # Set up agent
    llm = LLM(model=model, api_key=SecretStr(api_key))
    agent = Agent(
        llm=llm,
        tools=[
            Tool(name=TerminalTool.name),
            Tool(name=FileEditorTool.name),
        ],
    )

    # Event callback
    cb = make_event_callback(run_dir / "events_live.jsonl")

    # Run
    start_wall = datetime.now()
    error_msg = None

    conversation = None
    try:
        conversation = Conversation(
            agent=agent,
            workspace=LocalWorkspace(working_dir=workspace),
            persistence_dir=str(persistence_dir),
            callbacks=[cb],
            max_iteration_per_run=max_iterations,
        )
        conversation.send_message(prompt)
        conversation.run()
    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        print(f"\n[error] Agent failed: {error_msg}", file=sys.stderr)
    finally:
        if conversation is not None:
            conversation.close()

    end_wall = datetime.now()
    wall_seconds = round((end_wall - start_wall).total_seconds(), 2)
    cb.close()

    # Post-run
    if has_git:
        _capture_workspace_diff(workspace, run_dir)

    llm_cost = None
    try:
        llm_cost = llm.metrics.accumulated_cost
    except Exception:
        pass

    agent_files = _list_workspace_files(workspace)

    run_meta = {
        "task_id":          task_id,
        "task_index":       task_index,
        "safety_prompt":    safety,
        "model":            model,
        "max_iterations":   max_iterations,
        "timestamp":        timestamp,
        "workspace":        str(workspace),
        "wall_seconds":     wall_seconds,
        "start_time":       start_wall.isoformat(),
        "end_time":         end_wall.isoformat(),
        "event_count":      cb.event_count[0],
        "llm_cost_usd":     llm_cost,
        "error":            error_msg,
        "agent_files":      agent_files,
        "environment":      env_info,
        "output_files": {
            "events_live":       "events_live.jsonl",
            "trajectory":        "trajectory/",
            "workspace_diff":    "workspace_diff.patch",
        },
    }
    _write_json(run_dir / "run_meta.json", run_meta)

    # Summary
    print(f"\n  ── Task Complete ──")
    print(f"  task        : {task_id} ({safety})")
    print(f"  wall clock  : {wall_seconds}s")
    print(f"  events      : {cb.event_count[0]}")
    if llm_cost is not None:
        print(f"  cost (USD)  : ${llm_cost:.4f}")
    if error_msg:
        print(f"  error       : {error_msg}")
    if agent_files:
        print(f"  files       : {len(agent_files)}")
        for f_info in agent_files[:5]:
            print(f"    {f_info['path']:<40} ({f_info['size_bytes']:,} bytes)")
        if len(agent_files) > 5:
            print(f"    ... and {len(agent_files) - 5} more")
    print(f"  outputs     → {run_dir}")

    return run_meta


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--prompts", required=True,
        help="Path to JSONL prompt file (e.g. prompts_none.jsonl)",
    )
    parser.add_argument(
        "-n", type=int, default=None,
        help="Run only the first N tasks (default: all)",
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        help=f"LiteLLM model string (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--max-iterations", type=int, default=DEFAULT_MAX_ITER,
        help=f"Max agent iterations per task (default: {DEFAULT_MAX_ITER})",
    )
    parser.add_argument(
        "--dataset", default=DEFAULT_DATASET,
        help=f"Dataset name used as output subdirectory (default: {DEFAULT_DATASET})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # ── 1. Resolve API key ────────────────────────────────────────────────────
    api_key = _resolve_api_key(args.model)
    if not api_key:
        print(f"[error] No API key found for model {args.model}.", file=sys.stderr)
        return 1

    # ── 2. Environment info ───────────────────────────────────────────────────
    env_info = _collect_environment_info()
    print(f"[observe] Environment: Python {env_info['python']}, "
          f"SDK {env_info['openhands_sdk']}")

    # ── 3. Load tasks ─────────────────────────────────────────────────────────
    prompts_path = Path(args.prompts)
    if not prompts_path.exists():
        print(f"[error] Prompts file not found: {prompts_path}", file=sys.stderr)
        return 1

    tasks = load_tasks(prompts_path, args.n)
    runs_dir = BEHAVIORS_DIR / "openhands_run" / args.dataset
    print(f"[observe] Loaded {len(tasks)} tasks from {prompts_path.name}")
    print(f"[observe] Model: {args.model}")
    print(f"[observe] Dataset: {args.dataset}")
    print(f"[observe] Safety condition: {tasks[0].get('safety_prompt', '?') if tasks else '?'}")
    print(f"[observe] Output dir: {runs_dir}")

    runs_dir.mkdir(parents=True, exist_ok=True)

    # ── 4. Run all tasks ──────────────────────────────────────────────────────
    results = []
    for i, task in enumerate(tasks):
        meta = run_one_task(
            task=task,
            model=args.model,
            api_key=api_key,
            max_iterations=args.max_iterations,
            env_info=env_info,
            task_index=i,
            runs_dir=runs_dir,
        )
        results.append(meta)

    # ── 5. Final summary ──────────────────────────────────────────────────────
    print(f"\n{'═' * 66}")
    print(f"  ALL TASKS COMPLETE")
    print(f"{'═' * 66}")
    print(f"  tasks run   : {len(results)}")
    print(f"  model       : {args.model}")
    print(f"  condition   : {tasks[0].get('safety_prompt', '?') if tasks else '?'}")

    total_wall = sum(r["wall_seconds"] for r in results)
    total_cost = sum(r["llm_cost_usd"] or 0 for r in results)
    total_events = sum(r["event_count"] for r in results)
    errors = sum(1 for r in results if r["error"])

    print(f"  total time  : {total_wall:.1f}s")
    print(f"  total cost  : ${total_cost:.4f}")
    print(f"  total events: {total_events}")
    if errors:
        print(f"  errors      : {errors}")
    print(f"  output dir  : {runs_dir}")
    print(f"{'═' * 66}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
