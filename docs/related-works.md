# Related Works

This document surveys prior work related to the agent-secure-behavior project, organized by research theme. The project sits at the intersection of four areas: (1) policy-based agent safety and governance, (2) LLM agent security evaluation, (3) secure code generation benchmarks, and (4) coding agent frameworks.

## Positioning

Prior work on LLM agent safety largely focuses on general-purpose agents (web navigation, embodied tasks) or evaluates insecure behaviors in an ad hoc manner. Work on secure code generation primarily benchmarks single-turn code completion, not multi-step agentic workflows. No existing work provides a structured, SDLC-grounded policy corpus that maps authoritative security standards to specific lifecycle stages where a coding agent can be evaluated and constrained.

This project bridges those gaps: it builds on ShieldAgent's policy extraction methodology, targets the software development lifecycle specifically, and constructs the policy corpus needed to drive both evaluation (Phase 1) and runtime enforcement (Phase 2–3).

---

## 1. Policy-Based Agent Safety and Governance

This line of work addresses how to translate safety requirements into enforceable constraints on LLM agent behavior at runtime.

### ShieldAgent
**ShieldAgent: Shielding Agents via Verifiable Safety Policy Reasoning**
Zhaorun Chen, Mintong Kang, Bo Li — *ICML 2025* · [arXiv:2503.22738](https://arxiv.org/abs/2503.22738)

ShieldAgent is the closest direct predecessor to this project. It proposes a two-stage pipeline: (1) extract structured safety rules from policy documents using GPT-4o, and (2) encode rules as action-based probabilistic rule circuits using Linear Temporal Logic (LTL) for formal runtime verification. A companion benchmark, SA-Guard, covers 2K samples across 7 risk categories and 6 web environments. ShieldAgent achieves 90.1% rule recall while reducing API queries by 64.7% compared to prior methods.

**Relation to this project:** This project directly adopts ShieldAgent's Stage 1 extraction schema (`definition`, `scope`, `policy_description`, `reference`) and treats Stage 2 (LTL formalization) as a planned Phase 2 contribution. The key extension is targeting the software development lifecycle and expanding the policy corpus from a single document to 869 policies across 7 authoritative standards.

---

### AgentSpec
**AgentSpec: Customizable Runtime Enforcement for Safe and Reliable LLM Agents**
Haoyu Wang, Christopher M. Poskitt, Jun Sun — *ICSE 2026* · [arXiv:2503.18666](https://arxiv.org/abs/2503.18666)

AgentSpec is a lightweight DSL for specifying and enforcing runtime constraints on LLM agents. Users write structured rules with triggers, predicates, and enforcement mechanisms. Evaluated across code execution, embodied agent, and autonomous driving domains, AgentSpec prevents unsafe executions in over 90% of code agent cases. LLM-generated rules (using o1) achieve 95.56% precision and 70.96% recall on embodied agent tasks.

**Relation to this project:** AgentSpec demonstrates that a purpose-built constraint language substantially outperforms prompt-based policy injection. Its trigger/predicate/enforcement decomposition is a reference design for this project's Phase 2 policy language.

---

### PCAS
**PCAS: Policy Compiler for Secure Agentic Systems**
Nils Palumbo, Sarthak Choudhary, Jihye Choi, Prasad Chalasani, Somesh Jha et al. — *arXiv preprint, February 2026* · [arXiv:2602.16708](https://arxiv.org/abs/2602.16708)

PCAS addresses the lack of enforcement guarantees when embedding policies in prompts. It models agent system state as a dependency graph capturing causal relationships among tool calls, results, and messages, and expresses authorization policies in a Datalog-derived language accounting for transitive information flow and cross-agent provenance. On customer service tasks, PCAS improves compliance from 48% to 93% across frontier models with zero policy violations in instrumented runs.

**Relation to this project:** PCAS's dependency graph model is directly relevant to Phase 3 (Runtime Enforcement Engine). The insight that tool-call provenance must be tracked across steps — not just evaluated per-action — is essential for multi-step coding agent enforcement.

---

### Agent-C
**Agent-C: Enforcing Temporal Constraints for LLM Agents**
Adharsh Kamath, Sishen Zhang, Calvin Xu, Shubham Ugare, Gagandeep Singh, Sasa Misailovic — *arXiv preprint, December 2025* · [arXiv:2512.23738](https://arxiv.org/abs/2512.23738)

Agent-C introduces a DSL for expressing temporal safety properties over agent action sequences, translates them to first-order logic, and interleaves SMT solving with constrained token generation to prevent non-compliant actions at runtime. Addresses ordering constraints (e.g., authenticate before accessing sensitive data) that cannot be checked action-by-action without sequence context.

---

### Pro2Guard
**Pro2Guard: Proactive Runtime Enforcement of LLM Agent Safety via Probabilistic Model Checking**
Haoyu Wang, Christopher M. Poskitt, Jun Sun, Jiali Wei — *arXiv preprint, August 2025* · [arXiv:2508.00500](https://arxiv.org/abs/2508.00500)

Pro2Guard abstracts agent behaviors into symbolic states, learns a Discrete-Time Markov Chain from execution traces, and uses probabilistic model checking at runtime to predict the probability of reaching unsafe states — intervening proactively before violations occur. Moves enforcement from reactive (post-violation) to anticipatory.

---

### Towards Verifiably Safe Tool Use
**Towards Verifiably Safe Tool Use for LLM Agents**
Aarya Doshi, Yining Hong, Congying Xu, Eunsuk Kang, Alexandros Kapravelos, Christian Kästner — *ICSE 2026 NIER* · [arXiv:2601.08012](https://arxiv.org/abs/2601.08012)

Applies System-Theoretic Process Analysis (STPA) — a formal safety engineering methodology — to systematically identify hazards in LLM agent tool-use workflows and derive safety requirements. Provides a principled methodology grounded in hazard analysis rather than ad hoc rule enumeration.

---

## 2. LLM Agent Security Evaluation

This line of work characterizes the attack surface of LLM agents and provides frameworks for measuring safety and security failures.

### Security Debt
**When Developer Aid Becomes Security Debt: A Systematic Analysis of Insecure Behaviors in LLM Coding Agents**
Matous Kozak, Roshanak Zilouchian Moghaddam, Siva Sivaraman (Microsoft Research) — *NeurIPS 2025* · [arXiv:2507.09329](https://arxiv.org/abs/2507.09329)

The first systematic safety evaluation of autonomous coding agents at scale. Analyzes over 12,000 actions from five frontier models on 93 real-world software setup tasks. Key finding: 21% of agent trajectories contain insecure actions, with information exposure (CWE-200) most prevalent. Also evaluates mitigations including feedback mechanisms and security reminders.

**Relation to this project:** The most directly relevant empirical prior work. Establishes that insecure coding agent behavior is measurable and prevalent — the core motivation for this project. The four vulnerability categories identified are candidates for mapping to the SDLC policy constraint set.

---

### Agent Security Bench (ASB)
**Agent Security Bench (ASB): Evaluating the Attack and Defense of Autonomous Agents**
Hanrong Zhang, Jingyuan Huang, Kai Mei et al. — *ICLR 2025* · [arXiv:2410.02644](https://arxiv.org/abs/2410.02644)

A comprehensive benchmark across 10 scenarios, 10 agent types, 400+ tools, and 27 attack/defense methods covering prompt injection, memory poisoning, Plan-of-Thought backdoor, and mixed attacks across 13 LLM backbones. Finds a peak attack success rate of 84.30% with limited effectiveness from current defenses.

---

### AgentHarm
**AgentHarm: A Benchmark for Measuring Harmfulness of LLM Agents**
Maksym Andriushchenko, Alexandra Souly, Mateusz Dziemian et al. — *ICLR 2025* · [arXiv:2410.09024](https://arxiv.org/abs/2410.09024)

A benchmark of 110 explicitly malicious multi-step agent tasks (440 with augmentations) across 11 harm categories. Key finding: leading LLMs comply with malicious agentic requests even without jailbreaking, and simple universal jailbreak templates enable coherent multi-step harmful behavior.

---

### Agent-SafetyBench
**Agent-SafetyBench: Evaluating the Safety of LLM Agents**
Zhexin Zhang, Shiyao Cui, Yida Lu et al. (Tsinghua University) — *arXiv preprint, 2024* · [arXiv:2412.14470](https://arxiv.org/abs/2412.14470)

A benchmark of 349 interaction environments and 2,000 test cases evaluating LLM agent safety across 8 risk categories and 10 common failure modes, providing large-scale systematic assessment of unsafe agent interactions.

---

### ToolEmu
**ToolEmu: Identifying the Risks of LM Agents with an LM-Emulated Sandbox**
Yangjun Ruan, Honghua Dong, Andrew Wang et al. — *ICLR 2024 (Spotlight)* · [arXiv:2309.15817](https://arxiv.org/abs/2309.15817)

Uses GPT-4 to emulate tool execution in a virtual sandbox from tool specifications alone, enabling scalable risk identification without real infrastructure. Includes an LM-based safety evaluator and a benchmark of 36 toolkits (311 tools) and 144 test cases.

---

## 3. Secure Code Generation Benchmarks

This line of work evaluates the security quality of LLM-generated code, ranging from single-turn completion to full agentic repository-level tasks.

### SusVibes
**Is Vibe Coding Safe? Benchmarking Vulnerability of Agent-Generated Code in Real-World Tasks**
Songwen Zhao, Danqing Wang, Kexun Zhang, Jiaxuan Luo, Zhuo Li, Lei Li (Carnegie Mellon University) — *arXiv preprint, December 2025* · [arXiv:2512.03262](https://arxiv.org/abs/2512.03262)

A benchmark of 200 real-world software engineering tasks drawn from open-source projects where human developers historically introduced vulnerabilities, enabling joint evaluation of functional correctness and security. The best-performing setup (SWE-Agent + Claude) achieves 61% functional correctness but only 10.5% security — a stark gap between functionality and safety in agentic code generation.

---

### BaxBench
**BaxBench: Can LLMs Generate Correct and Secure Backends?**
Mark Vero, Niels Mündler, Victor Chibotaru, Veselin Raychev et al. (ETH Zurich, SRI Lab) — *ICML 2025* · [arXiv:2502.11844](https://arxiv.org/abs/2502.11844)

A benchmark of 392 backend application generation tasks evaluated through both functional test suites and end-to-end security exploit execution, jointly measuring whether LLM-generated backends are correct and free of exploitable vulnerabilities. Even the best model (OpenAI o1) achieves only 62% functional correctness, and security exploits succeed on roughly half of all correct programs.

---

### SecureAgentBench
**SecureAgentBench: Benchmarking Secure Code Generation under Realistic Vulnerability Scenarios**
Chen, Huang et al. — *arXiv preprint, September 2025* · [arXiv:2509.22097](https://arxiv.org/abs/2509.22097)

A benchmark of 105 multi-file coding tasks in large repositories (up to 4.2M LOC), each grounded in real-world open-source vulnerabilities with precisely identified introduction points. Evaluates whether code agents can generate *secure* code rather than merely *functional* code, exposing significant gaps in current agents' security awareness.

---

### SecRepoBench
**SecRepoBench: Benchmarking Code Agents for Secure Code Completion in Real-World Repositories**
Connor Dilgren, Purva Chiniya, Luke Griffith, Yu Ding, Yizheng Chen — *arXiv preprint, April 2025* · [arXiv:2504.21205](https://arxiv.org/abs/2504.21205)

318 repository-level security-sensitive code completion tasks across 27 C/C++ repositories covering 15 CWE types. Evaluation of 28 LLMs and 13 code agents reveals that even the best agents frequently introduce vulnerabilities, highlighting the inadequacy of current models for secure repository-level completion.

---

### SEC-bench
**SEC-bench: Automated Benchmarking of LLM Agents on Real-World Software Security Tasks**
Hwiwon Lee, Ziqi Zhang, Hanxiao Lu, Lingming Zhang (UIUC, Purdue) — *NeurIPS 2025* · [arXiv:2506.11791](https://arxiv.org/abs/2506.11791)

An automated benchmark of real-world security tasks — vulnerability detection, exploitation, and patching — grounded in actual CVEs and open-source repositories with automated oracles for scalable evaluation. Reveals significant performance gaps among state-of-the-art agents on end-to-end security engineering tasks.

---

### SecCodePLT
**SecCodePLT: A Unified Platform for Evaluating the Security of Code GenAI**
Yuzhou Nie, Zhun Wang, Yu Yang et al. (Virtue AI, UCLA, UCSB, UC Berkeley, UIUC, Oxford) — *arXiv preprint, October 2024* · [arXiv:2410.11096](https://arxiv.org/abs/2410.11096)

A unified evaluation platform covering two dimensions: insecure code generation and cyberattack helpfulness, with over 5,900 samples spanning 44 CWE-based risk categories across multiple programming languages. Enables holistic assessment of both security risks and dual-use capabilities in code agents.

---

### CWEval
**CWEval: Outcome-driven Evaluation on Functionality and Security of LLM Code Generation**
Jinjun Peng, Leyi Cui, Kele Huang, Junfeng Yang, Baishakhi Ray (Columbia University) — *LLM4Code @ ICSE 2025* · [arXiv:2501.08200](https://arxiv.org/abs/2501.08200)

An outcome-driven evaluation benchmark of 119 tasks spanning 31 CWE types across 5 languages (C, C++, Python, JavaScript, Go), measuring functional correctness and security simultaneously via executable test harnesses. Reveals that many models trade off security for functionality — passing functional tests while introducing exploitable weaknesses.

---

### SWE-bench
**SWE-bench: Can Language Models Resolve Real-World GitHub Issues?**
Carlos E. Jimenez, John Yang, Alexander Wettig, Shunyu Yao, Kexin Pei, Ofir Press, Karthik Narasimhan — *ICLR 2024* · [arXiv:2310.06770](https://arxiv.org/abs/2310.06770)

A benchmark of 2,294 real GitHub issues from 12 Python repositories where models must generate patches that pass associated test suites. Establishes the canonical evaluation framework for long-horizon software engineering tasks and is the foundation upon which several security-focused benchmarks (SusVibes, SecureAgentBench) are built.

---

## 4. Cooperative and Proactive Agents

### ProAgent
**ProAgent: Building Proactive Cooperative Agents with Large Language Models**
Ceyao Zhang, Kaijie Yang, Siyi Hu et al. — *AAAI 2024* · [arXiv:2308.11339](https://arxiv.org/abs/2308.11339)

ProAgent builds proactive cooperative LLM agents that infer teammates' intentions from observations and dynamically adapt behavior to enhance cooperation, outperforming self-play and population-based training baselines in Overcooked-AI. Although not security-focused, its multi-agent coordination model is relevant to multi-agent trust and policy enforcement in agentic pipelines where multiple agents must collectively adhere to shared constraints.

---

## Summary Table

| Paper | Venue | Theme | Key Contribution |
|---|---|---|---|
| ShieldAgent | ICML 2025 | Policy governance | LTL-based runtime verification from extracted policy rules |
| AgentSpec | ICSE 2026 | Policy governance | DSL for runtime constraint enforcement across agent types |
| PCAS | arXiv 2026 | Policy governance | Dependency graph + Datalog for transitive policy compliance |
| Agent-C | arXiv 2025 | Policy governance | Temporal constraint DSL with SMT-based enforcement |
| Pro2Guard | arXiv 2025 | Policy governance | Probabilistic model checking for proactive enforcement |
| Verifiably Safe Tool Use | ICSE 2026 NIER | Policy governance | STPA-based hazard analysis for agent tool-use safety |
| Security Debt | NeurIPS 2025 | Security evaluation | 21% of coding agent trajectories contain insecure actions |
| ASB | ICLR 2025 | Security evaluation | Multi-attack/defense benchmark for LLM agents |
| AgentHarm | ICLR 2025 | Security evaluation | Benchmark of malicious multi-step agent tasks |
| Agent-SafetyBench | arXiv 2024 | Security evaluation | 2,000 test cases across 8 safety risk categories |
| ToolEmu | ICLR 2024 | Security evaluation | LM-emulated sandbox for scalable risk identification |
| SusVibes | arXiv 2025 | Secure coding | 61% functional vs 10.5% security in vibe-coding agents |
| BaxBench | ICML 2025 | Secure coding | Joint correctness + exploit evaluation for backend generation |
| SecureAgentBench | arXiv 2025 | Secure coding | Multi-file realistic benchmark for secure code generation |
| SecRepoBench | arXiv 2025 | Secure coding | Repository-level secure completion across 15 CWE types |
| SEC-bench | NeurIPS 2025 | Secure coding | CVE-grounded detection, exploitation, and patching tasks |
| SecCodePLT | arXiv 2024 | Secure coding | Unified platform: insecure generation + cyberattack helpfulness |
| CWEval | LLM4Code@ICSE 2025 | Secure coding | Joint functional + security outcome evaluation, 31 CWE types |
| SWE-bench | ICLR 2024 | Coding agent eval | Canonical real-world GitHub issue resolution benchmark |
| ProAgent | AAAI 2024 | Cooperative agents | Proactive multi-agent coordination with LLMs |
