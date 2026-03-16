# Security Principles and Sources

This document maps the security principles used in this framework to the authoritative standards and guidelines from which they are extracted. For source selection rationale and policy counts, see the README.

---

## Included Sources

### NIST SP 800-218 — Secure Software Development Framework (SSDF)

**Scope:** Lifecycle governance for all software producers and acquirers.
**Extracted policies:** 48 (IDs: SSDF-001 … SSDF-048)
**Coverage in this project:** All SDLC stages — Planning through Maintenance.

Key principle areas:
- Prepare the organization (people, processes, technology)
- Protect software throughout the SDLC
- Produce well-secured software (design, implementation, testing)
- Respond to vulnerabilities post-release

**Mapping to SDLC stages:** Primary enforcement points span Requirements Analysis, Design, Implementation, and Maintenance. Serves as the lifecycle governance backbone for SDLC classification in this project.

---

### NIST AI RMF (AI 100-1) — AI Risk Management Framework

**Scope:** AI lifecycle governance for AI developers, deployers, and operators.
**Extracted policies:** 122 (IDs: RMF-001 … RMF-122)
**Coverage in this project:** AI system governance, accountability, risk identification, and mitigation across the AI system lifecycle.

Key principle areas:
- Govern: organizational roles, policies, and culture for responsible AI
- Map: identify and classify AI risks in context
- Measure: analyze and assess AI risks
- Manage: treat and monitor AI risks

**Mapping to SDLC stages:** Spans Planning (governance setup), Requirements Analysis (risk categorization), Design (risk treatment), and Maintenance (ongoing monitoring). Many administrative policies are categorized as Not Applicable to SDLC.

---

### OWASP ASVS — Application Security Verification Standard

**Scope:** Verifiable security requirements for application developers and testers.
**Extracted policies:** 429 (IDs: ASVS-001 … ASVS-429)
**Coverage in this project:** The largest single source; covers the full spectrum of application security requirements.

Key principle areas:
- Authentication and session management
- Access control
- Input validation and sanitization
- Cryptography
- API and web service security
- Configuration and dependency security
- Logging and monitoring

**Mapping to SDLC stages:** Primarily Implementation and Testing, with significant coverage of Design (security requirements) and Deployment (configuration hardening).

---

### OWASP LLM Top 10

**Scope:** Most critical security risks in LLM-based applications.
**Extracted policies:** 90 (IDs: LLM-001 … LLM-090)
**Coverage in this project:** LLM-specific attack surfaces and mitigations.

Key principle areas:
- Prompt injection (direct and indirect)
- Insecure output handling
- Training data poisoning
- Model denial of service
- Supply chain vulnerabilities
- Sensitive information disclosure
- Insecure plugin design
- Excessive agency and over-reliance
- Misinformation

**Mapping to SDLC stages:** Primarily Design (LLM system architecture) and Implementation (output handling, input sanitization), with Testing and Deployment components.

---

### CWE Top 25 — Most Dangerous Software Weaknesses

**Scope:** Most prevalent and impactful software weakness classes.
**Extracted policies:** 85 (IDs: CWE-001 … CWE-085)
**Coverage in this project:** Vulnerability-class-level constraints for code generation.

Key principle areas:
- Memory safety (buffer overflows, out-of-bounds access)
- Injection (SQL, OS command, XSS)
- Improper access control
- Cryptographic failures
- Insecure deserialization
- Improper input validation

**Mapping to SDLC stages:** Primarily Implementation (code-level constraints) with Architecture and Design scope noted in source references.

---

### OWASP AI Agent Security Cheat Sheet

**Scope:** Security controls specific to autonomous AI agents.
**Extracted policies:** 55 (IDs: AIAS-001 … AIAS-055)
**Coverage in this project:** The primary source for agent-operation-specific security constraints.

Key principle areas:
- Tool security and least privilege
- Input/output validation for agent I/O
- Memory and context isolation
- Multi-agent trust and authentication
- Human oversight and control mechanisms
- Prompt injection defenses in agentic contexts
- Rate limiting and resource controls

**Mapping to SDLC stages:** Primarily Design (agent architecture) and Implementation (tool invocation, memory handling), with Deployment (access controls) and Maintenance (monitoring) components.

---

### Palo Alto GenAI Risk Guide — C-Suite Guide to GenAI Risk Management

**Scope:** Enterprise risk management for GenAI application deployment.
**Extracted policies:** 40 (IDs: PALO-001 … PALO-040)
**Coverage in this project:** Operational and organizational governance policies for GenAI.

Key principle areas:
- Shadow AI discovery and inventory
- Data exposure controls
- Access control for GenAI services
- Network-level visibility and monitoring
- Vendor and third-party risk management
- Incident response for GenAI-related events

**Mapping to SDLC stages:** Primarily Planning and Deployment, with significant Maintenance (monitoring, ongoing risk management) coverage.

---

## Skipped Sources

| Source | Reason |
|--------|--------|
| **CERT Secure Coding Standards** | Language-level rules (C, Java, Python) focused on syntax and memory safety. The relevant weakness classes are captured at higher abstraction in CWE Top 25, avoiding low-level implementation minutiae. |
| **NIST SP 800-53** | Broad federal compliance catalog for information system authorization. Software-development-relevant controls are substantively covered by NIST SSDF at a more actionable abstraction. |
| **OWASP Proactive Controls** | Pedagogical subset of OWASP ASVS. Inclusion would introduce substantial duplication without marginal coverage gains. |
| **SLSA v1.2** | Supply-chain maturity framework. Supply-chain concerns are covered by NIST SSDF (PW.4, RV.1) and OWASP ASVS; SLSA's maturity-level structure does not yield extractable policy statements. |
| **CIS Benchmarks** | Infrastructure and OS hardening baselines governing the runtime environment, not agent behavior or code synthesis. No mapping to SDLC decision points. |
| **MITRE ATLAS** | Adversarial threat taxonomy for ML systems. Describes how attackers exploit AI — a threat catalog without prescriptive behavior constraints; not extractable under the ShieldAgent Stage 1 schema. |

---

## Cross-Reference Matrix

The full cross-reference between policies, sources, and SDLC stages is maintained in the extracted dataset:

- `policy/extracted/combined_policies.json` — all 869 policies with `policy_id`, `source`, and schema fields
- `policy/extracted/combined_policies_sdlc.csv` — all policies with SDLC stage, confidence, rationale, and secondary stages

To query by source or stage, load the CSV directly or use `policy/code/policy_viewer.ipynb`.
