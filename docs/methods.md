# Technical Methods

This document records all technical methods used in the agent-secure-behavior project, organized by pipeline stage. Each method section credits its origins and documents design decisions and improvements.

---

## 1. Policy Extraction

### 1.1 Original Method

**Credit:** The policy extraction schema and LLM-based extraction approach are adapted from **ShieldAgent** (Chen, Kang, and Li, ICML 2025; arXiv:2503.22738). ShieldAgent introduces a two-stage pipeline for converting unstructured policy documents into verifiable safety rules for agent governance. Stage 1 of that pipeline — which this project adopts — uses GPT-4o to parse policy documents and extract each policy into four structured fields:

- `definition` — term definitions and boundaries needed to interpret the policy unambiguously
- `scope` — conditions under which the policy applies
- `policy_description` — the exact policy statement (copied verbatim)
- `reference` — source identifiers for traceability

ShieldAgent's Stage 2 further converts these structured policies into formal Linear Temporal Logic (LTL) rules for runtime verification (`r = [𝒫r, Tr, ϕr, tr]`), with iterative verifiability refinement and redundancy pruning. **This project currently implements Stage 1 only.** Stage 2 (formal rule specification) is a planned contribution of Phase 2 (Policy Language), adapted and extended for the software development lifecycle context.

The original project implementation of Stage 1:
1. Loads a source document (PDF, TXT, or CSV) and extracts raw text.
2. Splits text into fixed-size character chunks (60,000 chars, no overlap).
3. Sends each chunk to `gpt-4o-mini` with a prompt instructing extraction of the four ShieldAgent fields.
4. Deduplicates extracted policies by exact string match on `policy_description`.

### 1.2 Updated Method (v2)

The updated implementation retains the ShieldAgent Stage 1 schema and LLM-based extraction approach, with the following methodological refinements:

**Structured output format.** The extraction prompt explicitly requests a JSON object with a `"policies"` key wrapping the array of records: `{"policies": [...]}`. This aligns the prompt with the OpenAI `json_object` response mode, which requires an object at the root level, and ensures deterministic parsing without fallback heuristics.

**Model selection.** The default model is `gpt-5-mini`, chosen for its stronger instruction-following and verbatim copying fidelity compared to smaller models. Authoritative security standards (NIST SP 800-218, OWASP ASVS) have dense, cross-referential, hierarchical structure; a capable model is necessary to extract multi-part requirements accurately and to avoid paraphrasing where verbatim reproduction is required. The `--model` flag allows override for cost-sensitive runs.

**Chunk overlap for contextual continuity.** Security standards are hierarchically organized: a child requirement is only fully interpretable in the context of its parent section heading. The updated chunking strategy carries forward the last `overlap_paragraphs` paragraphs (default: 3) from each chunk as a prefix for the next. This preserves immediate structural context across chunk boundaries without substantially increasing token usage.

**Two-pass deduplication.** Deduplication operates in two sequential passes to handle both exact and near-duplicate policies arising from overlapping source documents:
1. **Normalized exact match** — lowercased, whitespace-collapsed comparison catches trivial duplicates.
2. **Near-duplicate detection** via `difflib.SequenceMatcher` ratio ≥ 0.92 — catches paraphrase duplicates where the same requirement appears with minor wording variation across sources (e.g., the same NIST SP 800-218 requirement extracted from two differently-formatted input files). The threshold of 0.92 is conservative: high enough to merge genuine duplicates, low enough to preserve distinct policies that share common security vocabulary.

**Retained from ShieldAgent Stage 1.** The four-field schema (`definition`, `scope`, `policy_description`, `reference`) is unchanged. The `definition` field is preserved for future manual verification and policy disambiguation. PDF, TXT, and CSV loaders are unchanged. Output format remains a JSON array of policy records.

---

## 2. Lifecycle Classification

*(To be designed — Phase 2)*

The current keyword-regex classifier (`categorize_agent_lifecycle.py`) is not suitable for research-quality classification. The planned replacement will use LLM-based semantic classification integrated into the extraction step or as a dedicated second-pass stage.

---

## 3. Policy Quality Scoring

*(To be designed — Phase 2)*

Each extracted policy will be scored on:
- **Ambiguity:** Is the policy interpretable without additional context?
- **Measurability:** Is the constrained behavior checkable from observable agent state?

---

## 4. Runtime Enforcement Engine

*(To be designed — Phase 3)*
