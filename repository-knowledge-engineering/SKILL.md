---
name: repository-knowledge-engineering
description: "Use when building durable source-backed repo expertise."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [codebase, knowledge-graph, architecture, source-evidence]
---

# Repository Knowledge Engineering

## When to Use

Use for deeply learning a repository, producing a code knowledge graph, or maintaining reusable project expertise. This is executable source analysis, not a LOC report or plan-only orientation.

## Always-on rules

- Exercise the user's named analysis engine; cloning it or reading its README alone does not satisfy a request to use it.
- Separate structural indexing, semantic understanding, runtime verification, and scientific clearance. A large graph proves none of the latter by itself.
- For requests to find issues, pair the named engine's scoped extraction with focused behavioral counterexamples and positive controls; graph counts and repeated historical suspicions are not a bug-audit deliverable. Label each finding reproduced, source-only, or unresolved, and lead the final report with severity, impact and evidence rather than indexing statistics.
- Retain source-cited references in the active profile's durable workspace; keep procedural lessons in skills rather than dumping repository facts into global memory.
- Report artifacts, verified coverage, and gaps concisely. Do not claim complete expertise when only selected subsystems received semantic review.

## Procedure

1. **Define scope and deliverables.** Identify repository, desired depth, named tool, read-only boundary, and outputs: graph, subsystem explanations, reading index, risk/unknowns map, and receipt. Read applicable instructions and relevant manifests before interpreting architecture.
2. **Pin source.** Record HEAD, dirty paths, and submodule gitlinks. Prefer a non-Git `git archive` snapshot when writers are active. Label separately inspected dirty files rather than blending them into pinned evidence. A gitlink does not mean dependency source was analyzed.
3. **Filter before reading content.** Enumerate tracked paths and explicitly allow source, tests, manifests, policy, and docs. Exclude credentials, protected datasets, raw evidence, run artifacts, and caches. Save selected/excluded counts and paths. Audit suffix filtering for essential JSON manifests, schemas, and contract fixtures so the whitelist does not accidentally omit the project's defining inputs.
4. **Inspect and exercise the engine.** Read its actual layout, manifests, parser contracts, and schema. Build only required components in an isolated workspace. For Understand-Anything, follow [the extraction recipe](references/knowledge-graph-extraction.md). Do not enable commit hooks, automatic updates, main-checkout graph redirects, or external source uploads merely to index code.
5. **Extract deterministic evidence.** Run native scanner, resolved imports, and structural extraction; retain raw outputs. Account for every input as analyzed, unsupported/skipped, or unreadable. Investigate unreadable paths rather than relabeling them unsupported.
6. **Review subsystem semantics.** Trace entrypoints through transformations, storage, serving/consumption, error paths, tests, and release gates. Delegate only disjoint read-only scopes and require source citations and exact artifact paths. Resolve dated documentation conflicts against live implementation and binding policy; record contradictions rather than adopting convenient stale claims. For issue-finding requests, follow [the behavioral audit recipe](references/behavioral-audits.md): revalidate retained suspicions against the pinned source, execute safe counterexamples with controls, and preserve actual test receipts before declaring a bug confirmed.
7. **Assemble conservatively.** Use parser-derived declarations and resolved import edges. Include declaration location in symbol IDs because repeated names can denote different scopes. Preserve method names as partial evidence when ranges are absent; never fabricate ranges or connect dynamic calls by name similarity. Mark structural-only summaries explicitly.
8. **Validate and verify.** Use the engine schema validator, inspect its warnings, and independently check unique IDs, ranges, endpoints, layer membership, and coverage totals. Read back delegated reports and spot-check material claims against source before marking semantic review complete. Schema validity is not behavioral accuracy.
9. **Persist and refresh.** Keep source/tool revisions, scope, graph, raw extraction, evidence index, reviewed references, and receipt together. Use durable tool paths or provide reacquisition/build steps because scratch paths expire. Recheck relevant source changes before reusing retained knowledge.

## Completion boundary

Report extraction and semantic-review coverage separately. Pending background reviews stay pending; finish independent work and end the turn for result delivery rather than polling or declaring completion. Runtime readiness requires separately authorized runtime evidence.

## Adjacent skills

Use `codebase-inspection` for language/LOC metrics and guided-onboarding skills for contributor reading plans. Their reconnaissance overlaps, but neither substitutes for the executable graph and retained evidence in this workflow.
