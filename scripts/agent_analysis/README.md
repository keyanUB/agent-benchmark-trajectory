# Agent Analysis Scripts

Scripts for converting raw benchmark logs into trajectory data and reports.

Recommended workflow from the repository root:

```bash
python3 scripts/agent_analysis/inventory_agent_logs.py
python3 scripts/agent_analysis/extract_agent_behaviors.py
python3 scripts/agent_analysis/analyze_agent_trajectories.py
python3 scripts/agent_analysis/refine_message_behaviors.py
python3 scripts/agent_analysis/deep_behavior_analysis.py
python3 scripts/agent_analysis/render_common_trajectory_trees.py
```

Default paths:

- Raw logs: `AGENT_LOGS_ROOT`, defaulting to `data/raw/Agent Logs`
- Intermediate normalized events: `data/intermediate/agent_behaviors/`
- Curated processed outputs: `data/processed/`
- Human-facing reports: `reports/agent_trajectories/`
- Rendered common trajectory trees:
  `reports/agent_trajectories/figures/common_trees/`

The intermediate event tables can be large. They are treated as regenerable
scratch outputs rather than curated project artifacts.
