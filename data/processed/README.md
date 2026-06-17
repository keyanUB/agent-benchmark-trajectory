# Processed Agent Behavior Data

This folder contains the curated, analysis-ready outputs. Bulky intermediate
event dumps were removed because they can be regenerated from the original logs.

Key files:

- `trajectory_sequences.csv`: main per-run trajectory table. Includes raw and
  refined behavior sequences, tool calls, probe details, ordered event details,
  message subtypes, outcome labels, and source-path references.
- `agent_behavior_runs.csv`: compact per-run metadata and evaluation outcome
  fields used by the trajectory/report scripts.
- `agent_logs_inventory.json` and `agent_logs_inventory.md`: raw-bundle
  inventory and benchmark coverage summary.
- `trajectory_profiles.csv`: concentration/diversity metrics by agent,
  language, benchmark, and outcome.
- `trajectory_motifs.csv`: common behavior-sequence motifs.
- `trajectory_transitions.csv`: transition counts/probabilities.
- `trajectory_repeat_profiles.csv`: repeated adjacent behavior blocks.
- `trajectory_similarity.csv`: pairwise trajectory similarity summaries.

Important sequence columns:

- `raw_sequence`: stable coarse labels, kept for backward compatibility.
- `detailed_behavior_sequence`: refined labels, including specific probe and
  message subtypes.
- `probe_sequence`: only refined probe actions in order.
- `message_sequence`: only refined message subtypes in order.
- `event_details_json`: ordered event evidence, including each event's refined
  `detailed_token`.

Regenerable intermediates:

- Full normalized event tables are not kept here. To recreate them, run
  `scripts/agent_analysis/extract_agent_behaviors.py`, which writes to
  `data/intermediate/agent_behaviors/` by default.
