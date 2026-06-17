# Raw Agent Logs

The original benchmark logs and evaluation results are intentionally not checked
into this repository because the raw bundle is large and may contain local
runtime metadata.

To regenerate processed artifacts, place or symlink the raw bundle here:

```text
data/raw/Agent Logs
```

Alternatively set:

```bash
export AGENT_LOGS_ROOT=/path/to/Agent\ Logs
```

Important subtrees:

- `cweval/`: generation logs and evaluation results for Codex, Claude Code, and OpenHands.
- `baxbench/`: Codex `scp_owasp` generation logs and test results.
- `dualgauge/`: generated samples, execution results, and evaluation summaries.

The processed files in `data/processed/` include source-path references back into
this raw-data root, so full trajectories can be reconstructed from the original
logs when needed.
