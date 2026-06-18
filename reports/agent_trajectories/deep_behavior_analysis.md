# Agent Trajectories → Ideas for Designing Coding-Agent Benchmarks

CWEval, BaxBench, and DualGauge were built to grade an **artifact** (does the generated code contain a CWE). But a coding agent does not emit code in one shot — it runs a **process**: inspect → write → probe → recover → finalize. This report distills what the trajectories in `trajectory_sequences.csv` reveal about that process, and turns each observation into a design lever for a benchmark aimed at *agents* rather than base models.

Findings use the 3,696 full-observability runs (the cleaned dataset; see footnote).

## Agent snapshot

| agent | benchmark | strategy | probes? | what predicts its success |
|---|---|---|---|---|
| codex | cweval+baxbench | explore-first, longest (med 15) | 94% | probe *relevance* (hidden — see F2) |
| claude_code | cweval | code-first, then run/compile | 99% | probe *relevance* (hidden) |
| openhands-gpt54 | dualgauge | plan + read/write/probe loop | 35% | tool engagement (probe 71% vs 29%) |
| codex-gpt54 | dualgauge | peek-then-answer | 5% | whether it inspects at all (78% vs 37%) |
| claudecode-opus47 | dualgauge | pure one-shot (med 2) | 1% | being able to one-shot it |
| openhands | cweval | **not observable** | — | (logs lost; outcomes only) |

## Findings and what each implies for benchmark design

**F1 — Agents have a stable playbook but a task-adaptive trajectory.**
Each agent's *strategy* is fixed (codex always explores, claude_code always writes-then-probes), yet exact sequences and lengths vary with the task (codex's top exact pattern recurs ~1% of the time; claude_code ~3%).
→ **Design implication:** grade the *trajectory*, not only the final artifact. An artifact-only score is blind to the dimension that distinguishes a careful agent from a lucky one. The benchmark needs a per-step record and behavior-level metrics as first-class outputs.

**F2 — For strong agents, success and failure look identical at the coarse level.**
claude_code and codex probe in ~99%/94% of runs; their passing and failing runs share the same shape and the same probe *mix* — failures are just longer (claude_code median 11 vs 8). What separates them is whether a probe actually exercises the security property, which the coarse trajectory cannot show.
→ **Design implication:** the benchmark must make *probe relevance* measurable, not probe presence. Build tasks where the security condition can only be confirmed by a security-specific check (e.g. the exploit input), and score whether the agent ran it — not merely that it "tested something."

**F3 — For one-shot agents, the only visible success signal is engaging at all.**
codex-gpt54 inspects 78% of the time in successes vs 37% in failures; its failures collapse to single-event blurts (median length 1). opus47 inverts this — its successes are *pure* one-shots and tool use mostly marks an already-failing run.
→ **Design implication:** make context-gathering *necessary*, not optional. Put the security-relevant requirement somewhere the agent must read it (repo-specific, unguessable from priors), so "did it engage" becomes "did it succeed." This is also the cleanest way to separate genuine agent competence from base-model priors.

**F4 — Observability is broken and non-uniform.**
openhands (cweval) logged zero tool events — only the LLM message and final code survived export — while the same agent family under DualGauge is fully observable. 164 other runs had corrupted event logs.
→ **Design implication:** a coding-agent benchmark must define and enforce a **standard trajectory log schema** across agents and harnesses. Without it, trajectory metrics are silently incomparable, and "the agent did nothing" is indistinguishable from "we failed to record it." Logging is part of the benchmark, not an afterthought.

**F5 — Task type, not the agent or language, dominates trajectory shape.**
codex's behavior swings enormously (write/edit 6%→93%) — but that tracks single-function (cweval) vs service-building (baxbench), not the agent. Its apparent "language effect" is really this benchmark confound; within one task type it is stable. Language only tunes branch *intensity* (claude_code inspects more for C/C++), not the tree.
→ **Design implication:** control task type as an explicit axis and compare agents within it. A benchmark that mixes single-function and service tasks will attribute harness effects to agents. Language can be a secondary variable, not a primary one.

**F6 — Error recovery is task-triggered and shallow.**
Recovery after a real runtime error happens ~45–64% of the time for the active agents and ~0% for the one-shot agents; even when present it is often compile/dependency repair, not a semantic security fix.
→ **Design implication:** add a **staged-feedback** task mode (start from a failing security test, or inject feedback mid-run) to measure semantic recovery — a dimension current one-shot benchmarks cannot test at all.

## Design blueprint (the levers, in one place)

A coding-agent security benchmark should:

1. **Score the trajectory, not just the artifact** (F1) — leaderboard for outcome, behavioral profile for process.
2. **Force and measure security-relevant probing** (F2) — tasks whose security is confirmable only by a specific check.
3. **Make repo-specific context necessary** (F3) — requirements planted in the workspace, unguessable from priors, so engagement is required and base-model priors are factored out.
4. **Standardize trajectory logging** (F4) — a fixed event schema enforced across agents/harnesses.
5. **Control task type explicitly** (F5) — single-function vs service as a first-class axis; language secondary.
6. **Include staged recovery** (F6) — failing-test starts / mid-run feedback to test semantic repair.

The throughline: existing benchmarks ask *"is the final code secure?"*; a coding-agent benchmark should ask *"did the agent's process make the code trustworthy — and can we see it do so?"*

---

*Data: cleaned `trajectory_sequences.csv` (4,062 verified runs; 3,696 with observable trajectories). `openhands` cweval and a few codex runs are `outcome_only` (tool steps not logged) and excluded from behavior figures. `hard error` = runtime error on a tool/probe event, excluding `:error` result-object artifacts. `codex` exotic-language rows are baxbench service tasks, hence the task-type confound noted in F5.*
