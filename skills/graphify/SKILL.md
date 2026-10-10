---
name: graphify
description: "Use when mapping or querying code knowledge graphs."
version: 0.1.0
author: Juan Tamez, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [graphify, code-analysis, knowledge-graph, ast]
    related_skills: [repository-knowledge-engineering]
---

# Graphify

Map an authorized codebase into a local, queryable knowledge graph using Graphify-Labs/graphify. This is a Hermes adapter, not a copy of the upstream assistant installer. `/graphify` loads this skill; `graphify` is the installed CLI.

## When to Use

- `/graphify <project>`: build a code-only graph of that project.
- `/graphify query <question>`: query the selected project's existing graph.
- `/graphify explain <symbol>`, `/graphify path <A> <B>`, or `/graphify affected <symbol>`: inspect connections or impact.
- Bare `/graphify`: use the active profile's authorized project workspace, not the profile state directory. If no project can be established, ask for its path.
- Do not substitute this graph for tests, a security audit, runtime evidence, or a full semantic reading of documentation.

## Prerequisites

Python 3.10+ and the official package **graphifyy** (double y); the executable is **graphify**. Resolve the installed binary with `shutil.which` or the native shell lookup; never assume the current project's Python contains its dependencies.

Use `terminal(command="uv tool install graphifyy==0.9.80", timeout=300)` only when the CLI is missing and tool installation is within scope. Do not install another similarly named PyPI package. Validate with `terminal(command="graphify --version", timeout=30)`.

Do **not** run `graphify install --platform hermes`: it creates a profile-local skill that can shadow this canonical shared adapter, and upstream installers may inject instructions or hooks. Hermes automatically registers the shared skill as `/graphify` through `skills.external_dirs`.

## Procedure

1. Resolve the exact authorized project and its instructions. Inspect Git status and existing graph artifacts. Do not scan profile secrets, private session stores, databases, unrelated projects, or a whole home directory. Respect existing ignore files; inspect sensitive source paths before extraction and narrow the source if necessary.
2. Select an output root outside the scanned source: a per-task directory under the active profile's `cache/scratch`, or an ignored output directory outside the selected source subtree. The helper writes `<output-root>/graphify-out`. Use a fresh output root: upstream code-only rebuilding can retain semantic nodes from an existing graph, so an old graph is not proof of a purely local extraction.
3. Build with `terminal(command="python <this-skill-directory>/scripts/build.py <project> --output-root <output-root>", timeout=300)`. The helper runs local AST extraction with two workers and no semantic pass, then clustering with LLM labels disabled. It refuses to overwrite an existing graph output. No model key is needed.
4. Verify `graph.json`, `GRAPH_REPORT.md`, and `graph.html` are nonempty; read schema/version and count `nodes` and `links` (or `edges`) from the final JSON. Inspect an actual node before writing graph filters: schema 1 uses `source_file` and `source_location`, so filtering a guessed `source` field can silently return no results. Count relationship confidence separately. Label these as serialized graph counts: clustering can report fewer edges in its loaded graph, so do not silently substitute console counts or claim every relationship was extracted. Record unsupported-language and zero-symbol coverage separately from successful extraction. For large graphs, distinguish the HTML's aggregated community view from the full JSON graph; a generated HTML file does not prove offline rendering. Empty output is not a successful project map.
Before traversal on a refresh or comparison, compare selected-source hashes with the retained manifests. Reuse an unchanged reference graph rather than rebuilding both projects automatically. Compare against the effective prior snapshot, including its recorded post-refactor deltas; a baseline-only manifest misclassifies your own earlier repairs as intervening changes. Recheck selected hashes after extraction and analysis. If concurrent writers changed inputs, preserve the first graph and take one separate final snapshot when needed; if churn continues, deliver a clearly pinned snapshot instead of chasing an indefinitely moving worktree. Before running affected tests, save hashes of relevant source, tests and dependency manifests; compare them again after the run. Label changed inputs as a mixed-state observation, not qualification of either frozen graph. A later graph rebuild cannot qualify edits made after tests ran. Before writing current-state docs or follow-up tasks, re-read the specific live symbols behind findings: if another writer has already added the fix, queue verification/completion of that implementation rather than duplicate repair work. Keep the pinned finding and later unqualified progress distinct.

5. Use the exact graph path with the commands below. Inspect the query's starting symbols and truncation notice before interpreting its results: fuzzy matching can pull unrelated symbols into traversal. Resolve an exact symbol with `explain`, then use `path` to test the specific connection; narrow or raise the budget only when necessary. Follow graph leads back to the live source before making code claims or edits. `EXTRACTED` is a source relationship; `INFERRED` is derived, not runtime proof. Source line numbers can become stale.
6. When the request includes implementation, use the graph to choose a source-backed behavior or dependency slice, trace its live callers and tests, reproduce the gap, and implement the smallest complete refactor. Rebuild the changed project's graph into a fresh output root after validation; retain the baseline graph and source manifest separately so before/after evidence cannot silently change. Follow `repository-knowledge-engineering` for dirty-worktree snapshot provenance. On continuation, inspect retained receipts and compare selected-source hashes before rebuilding or choosing another slice: unfinished reporting does not mean the delivered code needs reimplementation. Label a refresh that includes intervening worktree changes separately; whole-graph count differences cannot establish attribution to your refactor. Keep prior passing checks bound to their recorded source snapshot, and run fresh affected checks for the current state. Do not substitute graph generation or a refactor plan for authorized implementation, or present one bounded slice as whole-project parity.
7. When documentation and backlog maintenance are requested, load `repo-docs` and update the affected design/verification owners plus the complete open task bodies. Rendering a goal-coverage table alone does not make follow-ups actionable: name the implementation or harness, observable acceptance, exclusions and dependencies, while preserving existing task IDs and milestone focus. Keep widget-remount or fresh-provider-scope evidence separate from native process-relaunch acceptance, because mocked storage does not qualify persistence across real app processes.
8. Report to the user in ordinary language: what was mapped or asked, what the graph actually returned, and any coverage gap. Keep graph path, source revision, tool version, commands and exit results in the durable receipt. Give the absolute artifact root and distinguish the full JSON from an aggregated HTML view. Do not claim the adapter improves model behavior without a separate evaluation.

## Quick Reference

Use these through `terminal`, quoting each argument; do not pass user text through a shell unescaped.

- `graphify query "<question>" --graph <graph.json> --budget 2000`
- `graphify explain "<symbol>" --graph <graph.json>`
- `graphify path "<A>" "<B>" --graph <graph.json>`
- `graphify affected "<symbol>" --graph <graph.json> --depth 2`
- `graphify god-nodes --graph <graph.json> --top 10 --json`

The `query` command is graph traversal, not an LLM answer. Translate its evidence into a source-backed explanation; do not invent a connection when no match exists. For Flutter, resolve the widget and its State class separately before testing a provider path: the indexed reference may originate from `_WidgetState`, not the widget declaration. Confirm the actual caller in source even when an exact graph path exists.

## Boundaries and Pitfalls

- Check each language extractor before describing coverage as AST or semantic analysis. In 0.9.80, Dart extraction is regex-based; Riverpod references can be indexed while local import paths or scoped methods remain incomplete. A missing graph path is not proof that the source dependency is absent. Verify the live import/call and use an exact provider/symbol path where available.
- Docs, PDFs, images, video, semantic extraction and community labeling may invoke paid or remote backends. They are **not** enabled by this adapter; obtain explicit scope/cost/data approval before using them. No credentials are copied between profiles.
- Treat a graph refresh/recomparison as analysis-only unless implementation is also requested. If focused tests reveal stale controls or wording, report the reproduced mismatch and next repair slice without changing assertions or product code. Change docs, TODO or the goal ledger only when documentation/backlog maintenance is explicitly requested; preserve active task ownership and do not close implementation from graph evidence. A background failure notification supplies evidence, not authorization to expand scope. Run only checks that answer the comparison. After the final report, start no additional application suite unless a new user instruction explicitly requests it; never describe an assistant-initiated suite as “requested.” When repairs are authorized, follow `test-driven-development` to replace obsolete expectations with behavior checks rather than deleting assertions to get green.
- Do not add Git hooks, watchers, MCP servers, global graph merging, scheduled jobs, hosted uploads, or always-on instruction injection as part of a graph request.
- Graph and HTML artifacts can contain sensitive source names and snippets. Keep them local and out of Git; ask before external delivery. Browser visualization is not guaranteed to work offline; inspect upstream HTML dependencies when offline rendering matters.
- This helper is tested against 0.9.80. Recheck actual help and provenance before upgrading. Unsupported optional grammars and missing clustering dependencies must be reported, not hidden by fabricated output.
- Fresh sessions discover new skills. Telegram's finite menu requires explicit priority and bot-menu publication if `/graphify` must be listed; typed command resolution and menu registration are separate checks. Preserve other priorities and do not restart healthy workers just to refresh a menu.

## Verification

Run `terminal(command="python <this-skill-directory>/scripts/test_build.py", timeout=60)` and the shared repository's `make test`. Exercise the installed CLI on a small isolated two-file fixture, then run `query`, `explain`, and `path` against its real graph. Report focused Graphify checks separately from shared-library checks: a failure in another skill does not erase successful graph extraction, and a successful graph build does not make the broader suite green. Name the failing suite and leave unrelated repairs outside the graph request. Verify fresh profile-scoped skill resolution; bot-menu readback is required for a live-menu claim. Tests prove the adapter contract and tested CLI behavior, not arbitrary language coverage or live model adoption.

See [upstream provenance](references/upstream.md) for the reviewed source and installation boundary. Follow [the shared contract](../shared/COMMON-CONTRACT.md).
