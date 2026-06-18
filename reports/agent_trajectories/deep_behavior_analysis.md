# Agent Trajectories → Ideas for Designing Coding-Agent Benchmarks

CWEval, BaxBench, and DualGauge were built to grade an **artifact** (does the generated code contain a CWE). But a coding agent does not emit code in one shot — it runs a **process**: inspect → write → probe → recover → finalize. This report distills what the trajectories in `trajectory_sequences.csv` reveal about that process, and turns each observation into a design lever for a benchmark aimed at *agents* rather than base models.

Findings use the 1,854 full-observability runs (cleaned dataset; see footnote).

## Agent snapshot

| agent | benchmark | strategy | probes? | what predicts its success |
|---|---|---|---|---|
| codex | cweval + baxbench | explore-first, longest (med 15) | 94% | probe *relevance* (hidden — see F2) |
| claude_code | cweval | code-first, then run/compile | 99% | probe *relevance* (hidden) |
| openhands-gpt54 | dualgauge | plan + read/write/probe loop | 35% | depth of engagement (probe 71% vs 29%) |

All three agents are *active* (they use tools); they differ in strategy, not in whether they engage.

## Findings and what each implies for benchmark design

**F1 — Agents have a stable playbook but a task-adaptive trajectory.**
Each agent's *strategy* is fixed (codex always explores, claude_code always writes-then-probes, openhands-gpt54 always loops), yet exact sequences and lengths vary with the task (codex's top exact pattern recurs ~1% of the time; claude_code ~3%).
→ **Design implication:** grade the *trajectory*, not only the final artifact. An artifact-only score is blind to the dimension that distinguishes a careful agent from a lucky one. The benchmark needs a per-step record and behavior-level metrics as first-class outputs.

**F2 — Success and failure trajectories look identical at the coarse level.**
claude_code and codex probe in ~99%/94% of runs; their passing and failing runs share the same shape and the same probe *mix* — failures are just longer (claude_code median 11 vs 8). What separates them is whether a probe actually exercises the security property, which the coarse trajectory cannot show.
→ **Design implication:** the benchmark must make *probe relevance* measurable, not probe presence. Build tasks where the security condition can only be confirmed by a security-specific check (e.g. the exploit input), and score whether the agent ran it — not merely that it "tested something."

**F3 — Engagement depth, not presence, tracks success — and priors confound it.**
openhands-gpt54 succeeds when it engages deeply (probe 71% vs 29%, write 67% vs 40%, inspect 84% vs 60% in success vs failure) but also fails with shallow loops. And on simple tasks an agent can produce secure code from base-model priors without reading anything, so "engagement" and "competence" get conflated.
→ **Design implication:** make context-gathering *necessary* by putting the security-relevant requirement where the agent must read it — repo-specific and unguessable from priors. This forces real engagement and factors out base-model knowledge, so the benchmark measures the *agent*, not the underlying model.

**F4 — Observability is fragile (a lesson from preparing this data).**
Whole agents had to be discarded for unusable logs: one agent's cweval export recorded zero tool events (only the LLM message and final code), and two DualGauge agents had incomplete/incorrect event logs. 164 further runs had corrupted JSON. Meanwhile the same agent family was fully observable under a different harness — so the gap is the logging path, not the agent.
→ **Design implication:** a coding-agent benchmark must define and enforce a **standard trajectory log schema** across agents and harnesses. Without it, trajectory metrics are silently incomparable, and "the agent did nothing" is indistinguishable from "we failed to record it." Logging is part of the benchmark, not an afterthought.

**F5 — Task type, not the agent or language, dominates trajectory shape.**
codex's behavior swings enormously (write/edit 6%→93%) — but that tracks single-function (cweval) vs service-building (baxbench), not the agent. Its apparent "language effect" is really this benchmark confound; within one task type it is stable. Language only tunes branch *intensity* (claude_code inspects more for C/C++), not the tree.
→ **Design implication:** control task type as an explicit axis and compare agents within it. A benchmark that mixes single-function and service tasks will attribute harness effects to agents. Language can be a secondary variable, not a primary one.

**F6 — Error recovery is task-triggered and shallow.**
Recovery after a real runtime error happens ~45–64% of the time for the active agents, and even then is often compile/dependency repair rather than a semantic security fix.
→ **Design implication:** add a **staged-feedback** task mode (start from a failing security test, or inject feedback mid-run) to measure semantic recovery — a dimension single-turn benchmarks cannot test at all.

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

*Data: cleaned `trajectory_sequences.csv` (1,863 verified runs across claude_code, codex, openhands-gpt54; 1,854 with observable trajectories). Removed during preparation: codex-gpt54 and claudecode-opus47 (incomplete/incorrect logs), openhands cweval (tool steps never logged), and 164 runs with corrupted JSON. A few codex runs remain `outcome_only` and are excluded from behavior figures. `hard error` = runtime error on a tool/probe event, excluding `:error` result-object artifacts. `codex` exotic-language rows are baxbench service tasks, hence the task-type confound noted in F5.*
