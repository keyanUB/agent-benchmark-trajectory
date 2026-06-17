# Agent Logs Inventory

Source root: `<RAW_AGENT_LOGS>`

Notes:
- cweval and baxbench non-Codex generation logs may not reflect later pipeline fixes; Codex is the reliable reference for those two benchmarks.
- baxbench only contains Codex `scp_owasp`; base and zero-shot logs are absent from this bundle.
- cweval OpenHands used `gpt-5-nano`; Codex used `gpt-5.1-codex-mini`; Claude Code used Haiku 4.5.

## cweval

| Agent | Variant | Model | Summary success/total | Step logs | Step lines | Suites | Languages | Result files |
|---|---:|---|---:|---:|---:|---|---|---|
| claude_code | base | anthropic:claude-haiku-4-5-20251001 | 25/119 | 119 | 1349 | core:108, lang:11 | c:31, cpp:21, go:19, js:23, py:25 | summary_json, res_all_json, generated_0_res_json |
| claude_code | scp_owasp |  | 0/119 | 119 | 1291 | core:108, lang:11 | c:31, cpp:21, go:19, js:23, py:25 | summary_json, res_all_json, generated_0_res_json |
| claude_code | zs |  | 0/119 | 119 | 1312 | core:108, lang:11 | c:31, cpp:21, go:19, js:23, py:25 | summary_json, res_all_json, generated_0_res_json |
| codex | base | openai:gpt-5.1-codex-mini | 3/119 | 119 | 1368 | core:108, lang:11 | c:31, cpp:21, go:19, js:23, py:25 | summary_json, res_all_json, generated_0_res_json |
| codex | scp_owasp | openai:gpt-5.1-codex-mini | 4/119 | 119 | 1356 | core:108, lang:11 | c:31, cpp:21, go:19, js:23, py:25 | summary_json, res_all_json, generated_0_res_json |
| codex | zs | openai:gpt-5.1-codex-mini | 7/119 | 119 | 1476 | core:108, lang:11 | c:31, cpp:21, go:19, js:23, py:25 | summary_json, res_all_json, generated_0_res_json |
| openhands | base |  | 0/119 | 119 | 482 | core:108, lang:11 | c:31, cpp:21, go:19, js:23, py:25 | summary_json, res_all_json, generated_0_res_json |
| openhands | scp_owasp |  | 0/119 | 119 | 724 | core:108, lang:11 | c:31, cpp:21, go:19, js:23, py:25 | summary_json, res_all_json, generated_0_res_json |
| openhands | zs |  | 0/119 | 119 | 714 | core:108, lang:11 | c:31, cpp:21, go:19, js:23, py:25 | summary_json, res_all_json, generated_0_res_json |

## baxbench

| Agent | Variant | Model | Summary success/total | Samples | Tasks | Frameworks | Step logs | Test result files | Test count aggregate |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| codex | scp_owasp | openai:gpt-5.1-codex-mini | 2/392 | 392 | 28 | 14 | 392 | 392 | functional_exceptions:121, functional_passed:279, functional_total:476, security_exceptions:410, security_total:987 |

## dualgauge

| Language | Agent | Tasks | Sample summaries | Event logs | Execution results | Gap present | Security pass/total | Functional pass/total |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| cpp | claudecode-opus47 | 305 | 305 | 307 | 305 | 2 | 1126/1859 | 344/1897 |
| cpp | codex-gpt54 | 305 | 305 | 307 | 305 | 12 | 1465/1859 | 643/1897 |
| cpp | openhands-gpt54 | 302 | 302 | 307 | 302 | 14 | 1189/1817 | 583/1877 |
| javascript | claudecode-opus47 | 301 | 301 | 307 | 301 | 0 | 1142/1842 | 400/1879 |
| javascript | codex-gpt54 | 303 | 303 | 307 | 303 | 3 | 1456/1847 | 866/1884 |
| javascript | openhands-gpt54 | 302 | 302 | 307 | 302 | 3 | 1176/1851 | 759/1885 |
| python | claudecode-opus47 | 304 | 304 | 307 | 304 | 0 | 1011/1853 | 824/1893 |
| python | codex-gpt54 | 304 | 304 | 307 | 304 | 0 | 1475/1853 | 1385/1893 |
| python | openhands-gpt54 | 304 | 304 | 307 | 304 | 7 | 1187/1853 | 967/1893 |

## Canonical Path Patterns

- cweval generation logs: `cweval/<agent>/<variant>/agent_logs/{core,lang}/<lang>/<cwe_task>/logs/steps.jsonl`
- cweval evaluation results: `summary.json`, `res_all.json`, `generated_0/res.json`
- baxbench generation logs: `baxbench/codex/scp_owasp/codex/<Task>/<Lang-Framework>/temp0.2-openapi-scp/sample0/logs/steps.jsonl`
- baxbench evaluation results: `test_results.json`, plus optional `func_test_*.log` and `sec_test_*.log` files
- dualgauge generation logs: `dualgauge/generated_samples/<lang>/<agent>/<task#>/raw_outputs/<id>_sample_<n>_events.jsonl`
- dualgauge evaluation results: `dualgauge/evaluation_results/<lang>/<agent>/<task#>/sample_<n>/summary.json` and `debug.json`
- dualgauge intermediate execution results: `dualgauge/execution_results/<lang>/<agent>/<task#>/sample_<n>/result.json`

The companion JSON file contains exact roots and per-run artifact counts.
