# Securing the AI Developer: Behavioral Governance for LLM Coding Agents

> *AI coding agents write code, install packages, modify configs, and deploy systems — often without a human in the loop. What happens when they make insecure decisions?*

This project builds a principled framework for identifying, measuring, and constraining insecure behaviors in LLM-based coding agents — not just at the code level, but across the full arc of autonomous software development.

---

## The Problem

Modern coding agents are capable of completing end-to-end development tasks: interpreting requirements, designing systems, writing and testing code, managing dependencies, and configuring deployments. But capability without constraint is a liability.

Current evaluations focus on *functional* correctness. Security is an afterthought — if considered at all. This project asks a harder question:

**Do coding agents behave securely?**

Not just "does the code compile?" but: Does the agent pin its dependencies? Avoid weak cryptography? Refuse to escalate privileges? Validate inputs at trust boundaries? Handle tool outputs safely?

---

## Research Questions

| | Question |
|---|---|
| **RQ1** | What insecure or risky behaviors do coding agents exhibit across the software development lifecycle? |
| **RQ2** | Can established security standards be systematically translated into enforceable agent behavior policies? |
| **RQ3** | To what extent does principle-guided governance reduce insecure behaviors in practice? |

---

## The Framework

```
Observed Agent Behaviors
         ↓
Threat Modeling & Behavior Taxonomy
         ↓
Security Standards  ──→  Policy Extraction
(NIST / OWASP / CWE)          ↓
                      Behavior Policy Corpus (869 policies)
                              ↓
                      Enforcement Engine
                              ↓
                      Auditable Agent Decisions
```

The core insight: security standards like OWASP ASVS and NIST SSDF already encode what *humans* should do. We translate that into what *agents* must do.

---

## Behavior Scope

Insecure agent behavior occurs at every stage of development — not just in the final code. This project covers:

| SDLC Phase | Example Agent Behaviors |
|---|---|
| Requirements & Design | Misinterpreting trust boundaries, over-privileged designs |
| Code Synthesis | Weak crypto, missing input validation, injection-prone patterns |
| Dependency Management | Unpinned versions, hallucinated packages, unverified sources |
| Configuration | Hardcoded secrets, unsafe defaults, excessive permissions |
| Testing & Execution | Skipping security tests, ignoring sanitization |
| CI/CD & Deployment | Modifying pipelines, exposing secrets in build logs |

---

## Policy Corpus

869 behavior policies extracted from seven authoritative sources:

| Source | Policies | Focus |
|--------|----------|-------|
| [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/) | 429 | Application security verification |
| [NIST AI RMF (AI 100-1)](https://airc.nist.gov/Home) | 122 | AI risk management |
| [OWASP LLM Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/) | 90 | LLM-specific vulnerabilities |
| [CWE Top 25](https://cwe.mitre.org/top25/index.html) | 85 | Software weakness enumeration |
| [OWASP AI Agent Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html) | 55 | Agent-specific controls |
| [NIST SP 800-218 (SSDF)](https://csrc.nist.gov/pubs/sp/800/218/final) | 48 | Secure development framework |
| [Palo Alto GenAI Risk Guide](https://www.paloaltonetworks.com/blog/2024/02/c-suite-guide-to-gen-ai-risk-management/) | 40 | GenAI risk management |
| **Total** | **869** | |

For source selection rationale, see [docs/principles-sources.md](docs/principles-sources.md).

### Policy Format

Each policy is machine-readable and maps directly to security standards:

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

A well-formed policy is **unambiguous** (clear enough to evaluate) and **measurable** (verifiable against agent actions).

### SDLC Stage Distribution

Each policy is classified to its primary enforcement stage in the software development lifecycle using LLM-based semantic classification (Claude Opus 4.6), with a confidence rating and rationale. Cross-stage policies carry a secondary stage field.

| SDLC Stage | Policies | % | Primary Sources |
|---|---|---|---|
| Implementation | 515 | 59.3% | OWASP ASVS, CWE Top 25, OWASP LLM Top 10 |
| Design | 76 | 8.7% | OWASP ASVS, OWASP AI Agent Security |
| Maintenance | 74 | 8.5% | Palo Alto GenAI Risk, NIST AI RMF |
| Planning | 71 | 8.2% | NIST AI RMF, NIST SP 800-218 |
| Requirements Analysis | 44 | 5.1% | OWASP ASVS, NIST SP 800-218 |
| Testing | 36 | 4.1% | OWASP ASVS |
| Deployment | 32 | 3.7% | OWASP ASVS, CWE Top 25 |
| Not Applicable | 21 | 2.4% | CWE Top 25, NIST AI RMF |
| **Actionable Total** | **848** | | |

Implementation dominates (59.3%) because four of seven sources are code-centric by design. The remaining three sources (NIST AI RMF, NIST SSDF, Palo Alto) spread coverage across Planning, Maintenance, and the full lifecycle.

**Classification confidence:**

| Confidence | Count | % |
|---|---|---|
| High | 797 | 91.7% |
| Medium | 67 | 7.7% |
| Low | 5 | 0.6% |

The 91.7% high-confidence rate validates that the 7-stage taxonomy maps cleanly onto existing standards. Medium-confidence cases arise from genuinely cross-stage policies — for example, "least privilege" is both an architectural design decision and a deployment-time enforcement point. The 21 Not Applicable entries (category definitions, administrative meta-policies) are retained for traceability but excluded from all enforcement and evaluation.

**Known coverage gaps:** Testing (4.1%) and Deployment (3.7%) are thin — security testing requirements are largely embedded within ASVS verification levels rather than stated as standalone policies, and CIS Benchmarks (the primary Deployment-hardening source) was intentionally excluded. For full categorization details, see [docs/sdlc-categorization-summary.md](docs/sdlc-categorization-summary.md).

---

## Measurement

### Say-Do Consistency (SDC)
Does the agent do what it says it will do?

$$\text{SDC} = \frac{\text{\# actions consistent with stated plan}}{\text{total actions}}$$

### Behavioral Divergence
How far does actual behavior drift from declared behavior?

$$D_{\mathrm{KL}}\!\left(\pi_{\text{declared}} \,\middle\|\, \pi_{\text{actual}}\right)$$

---

## Experimental Setup

### Agents Under Study

| Type | Agents |
|------|--------|
| Open-source | SWE-agent, OpenHands, Aider |
| Proprietary | Cursor, Codex, Claude Code |

### Benchmarks

| Benchmark | Focus |
|-----------|-------|
| [SusVibes](https://arxiv.org/abs/2512.03262) | Suspicious agent behavior |
| [SWE-bench](https://arxiv.org/abs/2310.06770) | Software engineering tasks |
| [SecCodePLT](https://arxiv.org/abs/2410.11096) | Secure code generation |
| [SEC-bench](https://arxiv.org/abs/2506.11791) | Security-focused tasks |
| [SecureAgentBench](https://arxiv.org/abs/2509.22097) | Agent security |
| [SecRepoBench](https://arxiv.org/pdf/2504.21205) | Secure repo-level tasks |
| [CWEval](https://ieeexplore.ieee.org/document/11028476?denied=) | CWE-grounded evaluation |
| [BaxBench](https://arxiv.org/abs/2502.11844) | Backend security |

---

## Implementation

Policy extraction is implemented in `policy/code/policy_extractor.py`:

1. Load source documents (`.pdf`, `.txt`, `.csv`)
2. Chunk and embed source text
3. Extract structured policies via LLM
4. Deduplicate and store policy records

---

## Repository Structure

```
├── docs/
│   ├── principles-sources.md     # Policy source rationale
│   ├── related-works.md          # Literature and prior work
│   ├── methods.md                # Methodology details
│   └── sdlc-categorization-summary.md
├── policy/
│   └── code/policy_extractor.py  # Policy extraction pipeline
├── research_proposal.docx        # Full research proposal
└── requirements.txt
```

---

## License

Apache License 2.0. See [LICENSE](LICENSE).
