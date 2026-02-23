# Agent Behavior Security Project

## Research Objective
This project aims to improve the security of LLM-based coding agents by identifying insecure behaviors that arise during autonomous software development and enforcing (programmable) security policies derived from authoritative standards.

Rather than focusing only on code-level vulnerabilities, we model and constrain agent behaviors across the entire lifecycle. (Temporary, needs to be revised)
- Requirement interpretation
- Design decisions
- Code synthesis
- Dependency management
- Configuration generation
- Testing and execution
- Environment setup
- CI/CD modification
- Deployment-related outputs

The goal is twofold:
1. Prevent insecure behaviors
2. Proactively enforce secure engineering practices comparable to those followed by experienced human developers

### Research Questions
RQ1: What insecure/risky behaviors do coding agents exhibit across the software development lifecycle?
RQ2: Can secure software engineering standards be systematically translated into (enforceable/programmable) agent behavior constraints?
RQ3: To what extent does principle-guided governance reduce insecure behaviors in coding agents?

### Core Idea
```
Insecure Coding Behaviors
                ↓
Security Standards (NIST / OWASP / CWE / CERT)
                ↓
Extracted Secure Principles
                ↓
Policy Specification (a new DSL?)
                ↓
Behavioral Enforcement Engine
                ↓
Auditable Agent Decisions
```

## Insecure Behaviors
- Unpinned or unverified dependencies
- Hallucinated packages
- Unsafe default configurations
- Insecure cryptographic choices
- Insecure tool output
- Insufficient input validation and sanitization
- Privilege escalation in configs

## Principal Sources (Under Verifying)
The selection covers: Secure SDLC, Secure coding, System hardening, Dependency management, Deployment security, Access control, Risk management

- [NIST Secure Software Development Framework (SP 800-218)](https://csrc.nist.gov/pubs/sp/800/218/final) &rarr; Lifecycle governance principles
- [CWE Top 25 Most Dangerous Software Weaknesses](https://cwe.mitre.org/top25/index.html) &rarr; Vulnerability identification
- [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/) &rarr; Requirement for authentication, crypto, input validation, logging, etc.
- [CERT Secure Coding Standards](https://wiki.sei.cmu.edu/confluence/spaces/seccode/pages/88042752/SEI+CERT+Coding+Standards) &rarr; Language-aware enforcement
 
- [NIST SP 800-53 — Security and Privacy Controls](https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final) &rarr; Access control, configuration management, system integrity
- [OWASP Proactive Controls](https://owasp.org/projects/spotlight/historical/2021.02.10/) &rarr; Developer security guidance like SCP

- [Supply-chain Levels for Software Artifacts](https://slsa.dev/spec/v1.2/) &rarr; CI/CD configs generation
- [CIS Benchmarks](https://downloads.cisecurity.org/#/?pi_content=91ab0d92a7268333c808284d1f6b464f3c9b71bb57ad44b7b18318fa8568bc49) &rarr; community-driven best practice guidelines (from companies) ([What are CIS Benchmarks?](https://www.ibm.com/think/topics/cis-benchmarks))

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

## Experimental Evaluation
### Agents
**Open-source Agents**
- SWE-agent
- OpenHands
- Aider

**Proprietary Agents**
- Cursor
- CodeX

### Benchmarks
- SusVibes| [Is Vibe Coding Safe? Benchmarking Vulnerability of Agent-Generated Code in Real-World Tasks](https://arxiv.org/abs/2512.03262) | [GitHub](https://github.com/LeiLiLab/susvibes)
- SWEBench | [SWE-bench: Can Language Models Resolve Real-World GitHub Issues?](https://arxiv.org/abs/2310.06770) | [GitHub](https://github.com/SWE-bench/SWE-bench)
- SecCodePLT | [SECODEPLT: A Unified Benchmark for Evaluating the Security Risks and Capabilities of Code Agents](https://arxiv.org/abs/2410.11096) [Dataset](https://huggingface.co/datasets/Virtue-AI-HUB/SecCodePLT)
- Sec-bench | [SEC-bench: Automated Benchmarking of LLM Agents on Real-World Software Security Tasks](https://arxiv.org/abs/2506.11791)| [GitHub](https://github.com/SEC-bench/SEC-bench)
- SecureAgentBench | [SecureAgentBench: Benchmarking Secure Code Generation under Realistic Vulnerability Scenarios](https://arxiv.org/abs/2509.22097) | [GitHub(TBD)](https://github.com/iCSawyer/SecureAgentBench)
- SecRepoBench | [SecRepoBench: Benchmarking Code Agents for Secure Code Completion in Real-World Repositories](https://arxiv.org/pdf/2504.21205) | [GitHub](https://github.com/ai-sec-lab/SecRepoBench)
- CWEval | [CWEval: Outcome-driven Evaluation on Functionality and Security of LLM Code Generation](https://ieeexplore.ieee.org/document/11028476?denied=) | [GitHub](https://github.com/Co1lin/CWEval)
- BaxBench | [BaxBench: Can LLMs Generate Correct and Secure Backends?](https://arxiv.org/abs/2502.11844) | [GitHub](https://github.com/logic-star-ai/baxbench)
- 

### Methods
#### Policy Extraction
Following ShieldAgent's policy extraction method:
```python
SYSTEM_PROMPT = """You are a helpful policy extraction model to identify actionable policies from organizational safety guidelines. Your task is to exhaust all the potential policies from the provided organization handbook which sets restrictions or guidelines for user or entity behaviors in this organization. You will extract specific elements from the given guidelines to produce structured and actionable outputs."""

USER_PROMPT_TEMPLATE = """As a policy extraction model to clean up policies from {organization}, your tasks are:
1. Read and analyze the provided safety policies carefully, section by section.
2. Exhaust all actionable policies that are concrete and explicitly constrain behaviors.
3. For each policy, extract the following four elements:
   1. Definition: Any term definitions, boundaries, or interpretative descriptions for the policy to ensure it can be interpreted without any ambiguity. These definitions should be organized in a list.
   2. Scope: Conditions under which this policy is enforceable (e.g. time period, user group).
   3. Policy Description: The exact description of the policy detailing the restriction or guideline.
   4. Reference: All the referenced sources in the original policy article from which the policy elements were extracted. These sources should be organized piece by piece in a list.

Extraction Guidelines:
• Do not summarize, modify, or simplify any part of the original policy. Copy the exact descriptions.
• Ensure each extracted policy is self-contained and can be fully interpreted by looking at its Definition, Scope, and Policy Description.
• If the Definition or Scope is unclear, leave the value as None.
• Avoid grouping multiple policies into one block. Extract policies as individual pieces of statements.

Provide the output in the following JSON format:
'''json
[
  {{
    "definition": ["Exact term definition or interpretive description."],
    "scope": "Conditions under which the policy is enforceable.",
    "policy_description": "Exact description of the policy.",
    "reference": ["Original source where the elements were extracted."]
  }},
  ...
]
'''

Output Requirements:
- Each policy must focus on explicitly restricting or guiding behaviors.
- Ensure policies are actionable and clear.
- Do not combine unrelated statements into one policy block.
- Return ONLY valid JSON — no markdown fences, no preamble, no explanation.

Here is the policy document text to analyze:

{document_text}"""
```
