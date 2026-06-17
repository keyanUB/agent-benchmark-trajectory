# Agent Trajectory Reports

This folder contains the human-facing trajectory analysis artifacts.

Key files:

- `deep_behavior_analysis.md`: main report with agent trajectory families,
  refined probe/message categories, success/failure contrasts, language
  comparisons, and representative original-log evidence.
- `trajectory_summary.md`: compact automated summary of trajectory motifs,
  similarities, and repeats.
- `trajectory_tree_viewer.html`: standalone interactive viewer for trajectory
  prefix trees.
- `figures/common_trees/png/*.png`: rendered common trajectory trees for each
  benchmark-agent and agent-language group with enough runs.
- `figures/common_trees/dot/*.dot`: DOT source files for those rendered trees.
- `figures/common_trees/manifest.json`: index of rendered tree images and their
  grouping metadata.
- `trees/common_trees/*.json`: prefix-tree data for the same rendered groups.

Older top-level-only generated tree pictures were removed. Re-run
`scripts/agent_analysis/render_common_trajectory_trees.py` to recreate the
current common tree figures from `data/processed/trajectory_sequences.csv`.
