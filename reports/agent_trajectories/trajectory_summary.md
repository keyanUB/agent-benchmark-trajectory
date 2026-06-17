# Agent Trajectory Trees

Built ordered trajectories for `4226` runs.

A trajectory is the collapsed ordered behavior sequence for one task/sample. Consecutive repeated actions are collapsed, so `read_file > read_file > write_file` becomes `read_file > write_file`.

## Most Concentrated Agent Profiles

| Agent | Runs | Unique Sequences | Dominant Share | Median Length | Entropy | Dominant Sequence |
|---|---:|---:|---:|---:|---:|---|
| openhands | 357 | 3 | 0.451 | 4.0 | 1.52 | `message > generated_code:error > message > generated_code:error` |
| claudecode-opus47 | 921 | 55 | 0.269 | 2.0 | 3.15 | `message:error > finish:error` |
| codex-gpt54 | 921 | 242 | 0.198 | 3.0 | 5.55 | `message:error` |
| claude_code | 357 | 153 | 0.148 | 5.0 | 5.73 | `message > write_file > execute_probe > generated_code` |
| openhands-gpt54 | 921 | 475 | 0.139 | 6.0 | 7.39 | `message` |
| codex | 749 | 521 | 0.041 | 9.0 | 8.47 | `message > inspect_workspace > execute_probe > read_file > message > generated_code` |

## Top Motifs By Agent

| Agent | Share | Count | Median Length | Success Share | Sequence |
|---|---:|---:|---:|---:|---|
| claude_code | 0.148 | 53 | 4.0 | 0.943 | `message > write_file > execute_probe > generated_code` |
| claude_code | 0.129 | 46 | 5.0 | 0.891 | `message > error > execute_probe > read_file > generated_code:error` |
| claude_code | 0.101 | 36 | 5.0 | 0.917 | `message > write_file > execute_probe > read_file > generated_code` |
| claude_code | 0.067 | 24 | 4.0 | 0.917 | `message > error > execute_probe > generated_code:error` |
| claude_code | 0.025 | 9 | 7.0 | 0.889 | `message > write_file > execute_probe > install > execute_probe > read_file > generated_code` |
| claudecode-opus47 | 0.269 | 248 | 2.0 | 0.078 | `message:error > finish:error` |
| claudecode-opus47 | 0.231 | 213 | 2.0 | 0.033 | `message > finish` |
| claudecode-opus47 | 0.183 | 169 | 3.0 | 0.000 | `error > message:error > finish:error` |
| claudecode-opus47 | 0.110 | 101 | 3.0 | 0.000 | `error > message > finish` |
| claudecode-opus47 | 0.062 | 57 | 3.0 | 0.000 | `write_file > message > finish` |
| codex | 0.041 | 31 | 6.0 | 0.839 | `message > inspect_workspace > execute_probe > read_file > message > generated_code` |
| codex | 0.024 | 18 | 6.0 | 1.000 | `message > inspect_workspace > execute_probe > error > message > generated_code:error` |
| codex | 0.020 | 15 | 5.0 | 0.933 | `message > execute_probe > read_file > message > generated_code` |
| codex | 0.017 | 13 | 7.0 | 0.769 | `message > inspect_workspace > read_file > execute_probe > read_file > message > generated_code` |
| codex | 0.017 | 13 | 7.0 | 1.000 | `message > inspect_workspace > error > execute_probe > read_file > message > generated_code` |
| codex-gpt54 | 0.198 | 182 | 1.0 | 0.101 | `message:error` |
| codex-gpt54 | 0.197 | 181 | 1.0 | 0.050 | `message` |
| codex-gpt54 | 0.041 | 38 | 3.0 | 0.162 | `inspect_workspace > error > message:error` |
| codex-gpt54 | 0.040 | 37 | 3.0 | 0.162 | `search > error > message:error` |
| codex-gpt54 | 0.040 | 37 | 4.0 | 0.270 | `inspect_workspace > search > error > message:error` |
| openhands | 0.451 | 161 | 4.0 | 0.288 | `message > generated_code:error > message > generated_code:error` |
| openhands | 0.333 | 119 | 2.0 | 0.466 | `message > generated_code:error` |
| openhands | 0.216 | 77 | 4.0 | 0.465 | `message > generated_code:error > message > generated_code` |
| openhands-gpt54 | 0.139 | 128 | 1.0 | 0.024 | `message` |
| openhands-gpt54 | 0.084 | 77 | 1.0 | 0.000 | `message:error` |
| openhands-gpt54 | 0.034 | 31 | 2.0 | 0.032 | `message > message:error` |
| openhands-gpt54 | 0.023 | 21 | 6.0 | 0.143 | `message:error > read_file > inspect_workspace > error > write_file > error` |
| openhands-gpt54 | 0.018 | 17 | 7.0 | 0.176 | `message:error > read_file > inspect_workspace > error > write_file > execute_probe > error` |

## Agent Similarity Within Benchmarks

| Benchmark | Left | Right | Transition Cosine | Top-Sequence Jaccard |
|---|---|---|---:|---:|
| cweval | claude_code | codex | 0.677 | 0.000 |
| cweval | codex | openhands | 0.524 | 0.000 |
| cweval | claude_code | openhands | 0.395 | 0.000 |
| dualgauge | codex-gpt54 | openhands-gpt54 | 0.350 | 0.042 |
| dualgauge | claudecode-opus47 | openhands-gpt54 | 0.164 | 0.000 |
| dualgauge | claudecode-opus47 | codex-gpt54 | 0.160 | 0.000 |

## Consecutive Repeats

| Agent | Runs With Repeats | Median Extra Events | Max Repeat Length | Most Repeated Token |
|---|---:|---:|---:|---|
| claude_code | 303/357 | 3.0 | 13 | execute_probe |
| claudecode-opus47 | 5/921 | 1.0 | 4 | inspect_workspace |
| codex | 698/749 | 6.0 | 17 | write_file |
| codex-gpt54 | 411/921 | 2.0 | 15 | web_search |
| openhands | 0/357 | 0.0 | 0 |  |
| openhands-gpt54 | 822/921 | 1.0 | 11 | read_file |

Top repeated behavior blocks by agent/token:

| Agent | Token | Blocks | Runs | Repeat Lengths | Looks Fixed |
|---|---|---:|---:|---|---|
| codex | execute_probe | 891 | 429 | `{"2": 462, "3": 217, "4": 104, "5": 56, "6": 20, "7": 17, "8": 5, "9": 6, "10": 2, "11": 1, "13": 1}` | False |
| codex | inspect_workspace | 799 | 640 | `{"2": 192, "3": 142, "4": 238, "5": 133, "6": 51, "7": 19, "8": 10, "9": 8, "10": 3, "11": 3}` | False |
| openhands-gpt54 | read_file | 585 | 492 | `{"2": 534, "3": 34, "4": 9, "5": 6, "7": 1, "11": 1}` | False |
| codex-gpt54 | error | 366 | 343 | `{"2": 197, "3": 110, "4": 39, "5": 13, "6": 5, "7": 2}` | False |
| codex | error | 339 | 244 | `{"2": 214, "3": 74, "4": 23, "5": 15, "6": 8, "7": 3, "8": 2}` | False |
| openhands-gpt54 | agent_action | 320 | 208 | `{"2": 252, "3": 47, "4": 18, "5": 1, "6": 2}` | False |
| claude_code | execute_probe | 301 | 224 | `{"2": 106, "3": 69, "4": 41, "5": 28, "6": 20, "7": 17, "8": 9, "9": 4, "10": 2, "11": 1, "12": 2, "13": 2}` | False |
| openhands-gpt54 | error | 264 | 216 | `{"2": 196, "3": 55, "4": 10, "5": 3}` | False |
| codex | write_file | 221 | 169 | `{"2": 112, "3": 43, "4": 22, "5": 12, "6": 5, "7": 5, "8": 3, "9": 6, "10": 2, "11": 2, "12": 1, "13": 1, "14": 4, "15": 1, "17": 2}` | False |
| codex | read_file | 198 | 123 | `{"2": 119, "3": 50, "4": 19, "5": 5, "6": 4, "11": 1}` | False |
| openhands-gpt54 | write_file | 155 | 135 | `{"2": 121, "3": 28, "4": 5, "5": 1}` | False |
| openhands-gpt54 | message | 128 | 128 | `{"2": 128}` | True |
| openhands-gpt54 | inspect_workspace | 89 | 80 | `{"2": 79, "3": 10}` | False |
| openhands-gpt54 | message:error | 77 | 77 | `{"2": 77}` | True |
| codex-gpt54 | inspect_workspace | 75 | 70 | `{"2": 65, "3": 8, "4": 1, "9": 1}` | False |
| claude_code | inspect_workspace | 59 | 36 | `{"2": 44, "3": 13, "4": 2}` | False |
| claude_code | read_file | 58 | 50 | `{"2": 40, "3": 15, "4": 2, "6": 1}` | False |
| codex-gpt54 | search | 52 | 51 | `{"2": 42, "3": 10}` | False |
| openhands-gpt54 | edit_file | 44 | 40 | `{"2": 25, "3": 11, "4": 4, "5": 3, "6": 1}` | False |
| claude_code | error | 39 | 33 | `{"2": 33, "3": 5, "4": 1}` | False |

## Files

- `trajectory_sequences.csv`: one ordered behavior sequence per run.
- `trajectory_transitions.csv`: transition counts/probabilities by group.
- `trajectory_motifs.csv`: most common collapsed sequences by group.
- `trajectory_profiles.csv`: diversity/concentration metrics by group.
- `trajectory_repeat_profiles.csv`: repeated consecutive behavior lengths by group/token.
- `trajectory_similarity.csv`: transition-vector and top-sequence similarity.
- `trees/*.json`: pruned prefix trees.
- `dot/*.dot`: Graphviz DOT prefix trees.
