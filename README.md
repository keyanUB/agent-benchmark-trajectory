# Agent Benchmark Trajectory

This repository contains curated trajectory data, reports, and scripts for
analyzing how coding agents behave across benchmark tasks.

The focus is the ordered behavior of agents while generating code: planning,
reading files, writing or editing code, calling tools, probing with tests or
compilation, retrying after errors, and producing final responses. The project
is organized around trajectory comparison across benchmark, agent, language,
tool use, and outcome.

## Contents

```text
data/
  raw/                         # Local-only raw log bundle pointer
  processed/                   # Curated CSVs and inventory summaries
reports/
  agent_trajectories/          # Analysis reports, trajectory viewer, tree data
scripts/
  agent_analysis/              # Parsers, summarizers, refiners, tree renderer
```

Raw benchmark logs are intentionally not checked into this repository. See
`data/raw/README.md` for the expected local raw-log layout.

## Main Artifacts

- `data/processed/trajectory_sequences.csv`: main per-run trajectory table with
  ordered behavior sequences, tool calls, refined message/probe labels, outcome
  fields, and event details.
- `data/processed/agent_behavior_runs.csv`: compact per-run metadata and
  evaluation outcomes.
- `data/processed/agent_logs_inventory.*`: benchmark/agent/language coverage
  inventory.
- `reports/agent_trajectories/deep_behavior_analysis.md`: detailed behavioral
  analysis with success/failure patterns and intervention points.
- `reports/agent_trajectories/figures/common_trees/png/`: rendered common
  trajectory trees by benchmark-agent and agent-language grouping.
- `reports/agent_trajectories/trajectory_tree_viewer.html`: standalone viewer
  for prefix-tree JSON outputs.

## Regenerating Outputs

From the repository root:

```bash
python3 scripts/agent_analysis/inventory_agent_logs.py
python3 scripts/agent_analysis/extract_agent_behaviors.py
python3 scripts/agent_analysis/analyze_agent_trajectories.py
python3 scripts/agent_analysis/refine_message_behaviors.py
python3 scripts/agent_analysis/deep_behavior_analysis.py
python3 scripts/agent_analysis/render_common_trajectory_trees.py
```

The scripts use Python's standard library. Rendering PNG trees also requires
Graphviz's `dot` command.

By default, scripts look for raw logs at:

```text
data/raw/Agent Logs
```

You can override that location with:

```bash
export AGENT_LOGS_ROOT=/path/to/Agent\ Logs
```

## Benchmarks Covered

- `cweval`
- `baxbench`
- `dualgauge`

The processed outputs preserve enough normalized event evidence to inspect
agent trajectory patterns without publishing the raw local run directories.
