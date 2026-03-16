# Policy Dataset: SDLC Stage Categorization

**Project:** Agent Secure Behavior
**Date:** March 2026
**Dataset:** 869 policies extracted from 7 authoritative security standards
**Method:** LLM-based semantic classification (Claude Opus 4.6) — each policy assigned to its primary SDLC enforcement stage with confidence rating and rationale

---

## Key Results

- **869 policies** extracted and categorized across 7 SDLC stages
- **Implementation dominates** (59.3%) — consistent with the code-centric nature of most source standards
- **91.7% high-confidence** assignments — the stage structure maps cleanly onto existing security standards
- **Identified coverage gaps** in Testing (4.1%) and Deployment (3.7%) stages — informing future source selection
- **21 non-actionable entries** (2.4%) filtered out as Not Applicable — mostly category definitions and administrative meta-policies

---

## 1. SDLC Stage Distribution

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
| **Total** | **869** | **100%** | |

The **Implementation-heavy distribution** (59.3%) reflects the composition of the source corpus: four of seven sources are primarily code-level standards (OWASP ASVS, CWE Top 25, OWASP LLM Top 10, OWASP AI Agent Security). The remaining three sources (NIST AI RMF, NIST SP 800-218, Palo Alto) provide the policy spread across Planning, Maintenance, and the full SDLC.

---

## 2. Per-Source Stage Profile

| Source | Total | Top Stage (%) | 2nd Stage (%) | 3rd Stage (%) |
|---|---|---|---|---|
| OWASP ASVS | 429 | Implementation (81%) | Design (7%) | Requirements Analysis (5%) |
| NIST AI RMF | 122 | Planning (38%) | Maintenance (21%) | Not Applicable (17%) |
| OWASP LLM Top 10 | 90 | Implementation (62%) | Design (16%) | Maintenance (9%) |
| CWE Top 25 | 85 | Implementation (66%) | Design (14%) | Deployment (9%) |
| OWASP AI Agent Security | 55 | Implementation (62%) | Design (22%) | Deployment (7%) |
| NIST SP 800-218 (SSDF) | 48 | Implementation (27%) | Planning (19%) | Maintenance (15%) |
| Palo Alto GenAI Risk | 40 | Maintenance (63%) | Planning (24%) | Deployment (8%) |

Each source has a distinct stage profile that reflects its purpose:

- **OWASP ASVS** is narrowly focused on Implementation (81%) — it is a code-level verification checklist by design.
- **NIST AI RMF** is the most broadly distributed source and the only one where Planning is the top stage — its governance framing spans the full AI system lifecycle.
- **NIST SP 800-218 (SSDF)** is the most balanced source across all 7 SDLC stages, making it the backbone for lifecycle coverage in this dataset.
- **Palo Alto GenAI Risk** is the only source where Maintenance leads (63%), reflecting its operational focus on monitoring, discovery, and incident response for deployed GenAI systems.

---

## 3. Categorization Quality

### Confidence Distribution

| Confidence | Count | % | Interpretation |
|---|---|---|---|
| High | 797 | 91.7% | Clear primary stage, minimal ambiguity |
| Medium | 67 | 7.7% | Genuine cross-stage policies; judgment required |
| Low | 5 | 0.6% | Abstract principles or informational notes |

The high proportion of high-confidence assignments (91.7%) validates that the 7-stage SDLC taxonomy maps well onto existing security standards — most policies have a natural home in one stage.

### Medium Confidence — Cross-Stage Policies

Medium confidence arises when a policy is both a design-time principle and an operational enforcement point. Three representative cases:

**CWE-026** — *Deployment (secondary: Design)*
> "Run your code using the lowest privileges that are required to accomplish the necessary tasks."

Least privilege is simultaneously an architectural design decision and a runtime/OS configuration. The primary stage (Deployment) reflects where enforcement happens; Design is secondary because the principle should be established at architecture time.

**ASVS-085** — *Deployment (secondary: Implementation)*
> "Verify that the application's top-level domain is added to the public HSTS preload list."

A deployment-time operational action with an implementation prerequisite — HSTS headers must be correctly implemented before preload registration is meaningful. The stage ordering depends on which activity is considered primary.

**ASVS-252** — *Planning (secondary: Maintenance)*
> "Verify that a cryptographic inventory is maintained with a documented plan that outlines the migration path to new cryptographic standards such as post-quantum cryptography."

Defining the migration plan is a planning activity; executing and maintaining the inventory is ongoing maintenance. The policy conflates both lifecycle activities in a single statement.

### Low Confidence — Abstract or Weakly Prescriptive Policies

Low confidence arises from policies that are section-level principles, informational notes, or recommendations rather than requirements.

**ASVS-172** — *Requirements Analysis*
> "V7 Session Management: Sessions are unique to each individual and cannot be guessed or shared."

A section header / principle statement, not an actionable requirement. It defines *what* the requirement means rather than *where* it is enforced — too abstract for confident stage assignment.

**ASVS-391** — *Implementation*
> "MAC-then-encrypt is still allowed for compatibility with legacy applications. It is used in TLS v1.2 with old cipher suites."

A descriptive compatibility note. It neither mandates nor prohibits the pattern, and has no clear enforcement point.

**ASVS-414** — *Implementation*
> "A password strength meter should be provided to help users set a stronger password."

The use of "should" (recommendation) rather than "must" (requirement) makes this weakly prescriptive. Whether it constitutes an enforceable policy depends on the application's risk tier.

---

## 4. Coverage Gaps

The stage distribution reveals structural gaps that inform next steps:

| Stage | Count | Gap Assessment |
|---|---|---|
| Testing | 36 (4.1%) | Security testing requirements are largely embedded within ASVS verification levels rather than stated as standalone policies. A dedicated testing-policy extraction may improve coverage. |
| Deployment | 32 (3.7%) | Configuration hardening is partially covered by ASVS but CIS Benchmarks (excluded from current corpus) is the primary source for this stage. An acknowledged trade-off in source selection. |
| Requirements Analysis | 44 (5.1%) | Many ASVS "documentation" requirements were classified here. Coverage is thin relative to the importance of this stage in secure SDLC. |

---

## 5. Implications for Next Steps

**Policy constraint set for evaluation.** The 848 actionable policies (869 minus 21 Not Applicable) form the constraint corpus for Phase 2. The 515 Implementation-stage policies are the immediate priority for agent code generation evaluation, as this is where coding agents operate most directly.

**Multi-stage policy handling.** 67 medium-confidence policies span two stages. The `sdlc_secondary_stages` field in the dataset enables queries that include cross-stage coverage — important for policies like least privilege that must be enforced at both design and deployment time.

**Source gaps to revisit.** If evaluation reveals insufficient Testing or Deployment coverage, targeted addition of OWASP Testing Guide (for Testing) or CIS Benchmarks (for Deployment) would directly address the identified gaps without substantially increasing corpus size.

**Not Applicable entries.** The 21 Not Applicable policies are retained in the dataset for traceability but should be excluded from all enforcement, coverage, and evaluation analyses.

---

*Full dataset: `policy/extracted/combined_policies_sdlc.csv` — 869 rows, fields: policy_id, source, sdlc_stage, sdlc_confidence, sdlc_secondary_stages, sdlc_rationale, scope, policy_description, reference*
