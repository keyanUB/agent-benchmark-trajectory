# Agent Behavior Security Project

## Overview
This project studies how to improve the security of LLM-based coding agents by:
1. Identifying insecure behaviors across autonomous software development.
2. Translating authoritative security standards into programmable behavior constraints.

The focus is not only code-level vulnerabilities, but also agent decisions and actions throughout development workflows.

## Research Objective
Build a framework that:
1. Prevents insecure agent behaviors.
2. Enforces secure engineering practices comparable to experienced human developers.

### Security-Relevant Behavior Scope
- Requirement interpretation
- Design decisions
- Code synthesis
- Dependency management
- Configuration generation
- Testing and execution
- Environment setup
- CI/CD modification
- Deployment-related outputs

## Research Questions
- **RQ1:** What insecure or risky behaviors do coding agents exhibit across the software development lifecycle?
- **RQ2:** Can secure software engineering standards be systematically translated into enforceable agent behavior constraints?
- **RQ3:** To what extent does principle-guided governance reduce insecure behaviors in coding agents?

## Core Idea
```text
Insecure Coding Behaviors
                ↓
Security Standards (NIST / OWASP / CWE / CERT)
                ↓
Extracted Secure Principles
                ↓
Policy Specification (DSL candidate)
                ↓
Behavioral Enforcement Engine
                ↓
Auditable Agent Decisions
```

## Insecure Behaviors (Initial)
- Unpinned or unverified dependencies
- Hallucinated packages
- Unsafe default configurations
- Insecure cryptographic choices
- Insecure tool output handling
- Insufficient input validation and sanitization
- Privilege escalation in generated configs

## Standards and References (Under Verification)
Coverage targets: secure SDLC, secure coding, hardening, dependency management, deployment security, access control, risk management.

### Primary Sources
- [NIST Secure Software Development Framework (SP 800-218)](https://csrc.nist.gov/pubs/sp/800/218/final): lifecycle governance principles
- [CWE Top 25 Most Dangerous Software Weaknesses](https://cwe.mitre.org/top25/index.html): vulnerability classes
- [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/): verifiable security requirements
- [CERT Secure Coding Standards](https://wiki.sei.cmu.edu/confluence/spaces/seccode/pages/88042752/SEI+CERT+Coding+Standards): language-aware secure coding guidance
- [OWASP AI Agent Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html)
- [OWASP Top 10 Risk & Mitigations for LLMs and GenAI Apps](policy/LLMAll.pdf)

### Supplementary Sources
- [NIST SP 800-53](https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final): access control, configuration management, integrity
- [OWASP Proactive Controls](https://owasp.org/projects/spotlight/historical/2021.02.10/): secure development controls
- [SLSA v1.2](https://slsa.dev/spec/v1.2/): supply-chain integrity for build/release pipelines
- [CIS Benchmarks](https://downloads.cisecurity.org/#/?pi_content=91ab0d92a7268333c808284d1f6b464f3c9b71bb57ad44b7b18318fa8568bc49): hardening baselines
- [What Are CIS Benchmarks? (IBM)](https://www.ibm.com/think/topics/cis-benchmarks)
- [Palo Alto: C-Suite Guide to GenAI Risk Management](policy/c-suite-guide-to-gen-ai-risk-management.pdf)

## Policy Model

### Example Policy (Sketch)
```yaml
policy_id: DEP_PIN_001
category: dependency-management
description: Dependencies must use exact version pinning
applies_to: install_dependency
rule:
  require_exact_version: true
severity: high
standard_mapping:
  - CWE-1104
  - OWASP-A06
```

### Properties of a "Good" Policy
1. **Low ambiguity**: clear and interpretable.
2. **High measurability**: verifiable and enforceable.

## Measurement Metrics (Draft)
### 1) Consistency Between Declared and Executed Behavior
- **Say-Do Consistency (SDC):**
```math
\text{SDC} = \frac{\text{\# actions consistent with stated plan}}{\text{total actions}}
```
- **Behavioral consistency via KL divergence:**
```math
D_{\mathrm{KL}}\!\left(\pi_{\text{declared}} \,\middle\|\, \pi_{\text{actual}}\right)
```
- TODO: validate and refine the consistency metric proposal.

## Experimental Evaluation

### Agent Set
**Open-source**
- SWE-agent
- OpenHands
- Aider

**Proprietary**
- Cursor
- Codex
- Claude Code

### Benchmark Candidates
- SusVibes: [Paper](https://arxiv.org/abs/2512.03262), [GitHub](https://github.com/LeiLiLab/susvibes)
- SWE-bench: [Paper](https://arxiv.org/abs/2310.06770), [GitHub](https://github.com/SWE-bench/SWE-bench)
- SecCodePLT: [Paper](https://arxiv.org/abs/2410.11096), [Dataset](https://huggingface.co/datasets/Virtue-AI-HUB/SecCodePLT)
- SEC-bench: [Paper](https://arxiv.org/abs/2506.11791), [GitHub](https://github.com/SEC-bench/SEC-bench)
- SecureAgentBench: [Paper](https://arxiv.org/abs/2509.22097), [GitHub (TBD)](https://github.com/iCSawyer/SecureAgentBench)
- SecRepoBench: [Paper](https://arxiv.org/pdf/2504.21205), [GitHub](https://github.com/ai-sec-lab/SecRepoBench)
- CWEval: [Paper](https://ieeexplore.ieee.org/document/11028476?denied=), [GitHub](https://github.com/Co1lin/CWEval)
- BaxBench: [Paper](https://arxiv.org/abs/2502.11844), [GitHub](https://github.com/logic-star-ai/baxbench)

## Lifecycle Models Used in This Project
This project uses two lifecycle views for different analysis layers.

### 1) Agent Operation Lifecycle (Runtime)
Current synthesized view:
1. Perception/Input
2. Memory Retrieval
3. Reasoning/Planning
4. Action/Tool Use
5. Observation
6. Memory Update
7. Evaluation/Reflection
8. Termination

### 2) Software Development Life Cycle (SDLC)
1. Planning
2. Requirements Analysis
3. Design
4. Implementation
5. Testing
6. Deployment
7. Maintenance

## Methods
### Policy Extraction
The extraction workflow is implemented in:
- `policy/code/policy_extractor.py`

It:
1. Loads source documents (`.pdf`, `.txt`, `.csv`).
2. Chunks source text.
3. Calls the OpenAI API for structured policy extraction.
4. Deduplicates and saves extracted policy records.

For the exact extraction prompts and output schema, see the script directly.

## License
This project is licensed under the **Apache License 2.0**. See [LICENSE](LICENSE).
