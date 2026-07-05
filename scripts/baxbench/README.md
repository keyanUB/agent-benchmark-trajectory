# BaxBench Agent Runners

## Codex Agent Runner

The default runner launches the real Codex CLI agent through:

```text
codex exec --json
```

This is preferred for trajectory collection because Codex itself performs the
planning, file edits, shell commands, and final response. The script preserves
the raw Codex JSONL stream and also writes a normalized `steps.jsonl`.

The default prompt mode is `baxbench`. It uses only task/environment content
reconstructed from the BaxBench dataset and does not ask the agent to expose
behavior, use tools, run probes, or inspect potential CWEs.

Run one BaxBench task in dry-run mode:

```bash
python3 scripts/baxbench/run_codex_baxbench.py \
  --task-id Calculator-Python-Flask \
  --dry-run \
  --force
```

Run one task with Codex CLI:

```bash
python3 scripts/baxbench/run_codex_baxbench.py \
  --model gpt-5.4-mini \
  --task-id Calculator-Python-Flask \
  --force
```

Run a small batch:

```bash
python3 scripts/baxbench/run_codex_baxbench.py \
  --model gpt-5.4-mini \
  --language Python \
  --framework Flask \
  --limit 5
```

Outputs are written under:

```text
data/raw/baxbench/runs/codex/gpt-5.4-mini/codex-cli-agent/<scenario>/<env>/sample0/
  prompt.txt
  task.json
  metadata.json
  final_message.txt
  workspace/
  logs/codex_cli_events.jsonl
  logs/codex_cli.stderr.log
  logs/steps.jsonl
```

`codex_cli_events.jsonl` is the raw `codex exec --json` stream. `steps.jsonl`
keeps the raw event under `raw_event` and copies known command/message fields
to stable top-level fields for trajectory extraction.

There is an explicit fallback runner:

```bash
python3 scripts/baxbench/run_codex_baxbench.py \
  --runner responses-api \
  --model gpt-5.4-mini \
  --task-id Calculator-Python-Flask
```

Use that only when Codex CLI is unavailable. It is a small custom tool loop, not
the primary Codex agent runner.

For debugging the logging pipeline only, there is a non-neutral prompt mode:

```bash
python3 scripts/baxbench/run_codex_baxbench.py \
  --prompt-mode debug-observation \
  --task-id Calculator-Python-Flask
```

Do not use `debug-observation` for normal behavior observation.

## Claude Code Agent Runner

Run one task with Claude Code CLI:

```bash
python3 scripts/baxbench/run_claude_baxbench.py \
  --model sonnet5 \
  --task-id Calculator-Python-Flask \
  --force
```

Outputs are written under:

```text
data/raw/baxbench/runs/claude_code/sonnet5/claude-code-cli-agent/<scenario>/<env>/sample0/
  prompt.txt
  task.json
  metadata.json
  final_message.txt
  workspace/
  logs/claude_code_events.jsonl
  logs/claude_code.stderr.log
  logs/steps.jsonl
```

The Claude runner also defaults to neutral `--prompt-mode baxbench`.
