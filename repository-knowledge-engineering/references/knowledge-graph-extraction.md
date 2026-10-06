# Understand-Anything deterministic extraction

This recipe covers the engine components exercised successfully. The complete semantic-agent pipeline and interactive dashboard are separate deliverables.

## Acquire and inspect

Clone `https://github.com/Egonex-AI/Understand-Anything.git` into an isolated tool workspace and record its commit. Read root and plugin manifests. Source lives under `understand-anything-plugin/`; assuming top-level `packages/core/` mislocates the engine.

Inspect `skills/understand/SKILL.md`, `agents/file-analyzer.md`, and core `src/types.ts`/`src/schema.ts` beneath the plugin root. Do not use the global plugin installer when only local extraction is required, because it can modify other agent installations.

## Build

Run from the tool root:

```sh
npm exec --yes --package=pnpm@10 -- pnpm install --frozen-lockfile --ignore-scripts
npm exec --yes --package=pnpm@10 -- pnpm --filter @understand-anything/core build
```

Check current dependency advisories before installation and inspect the actual package-manager version executed: the repository's `packageManager` field can select its pinned release despite the launcher version. Suppress unrelated install lifecycle scripts, then explicitly build core. Do not silently replace frozen-lockfile failure with unpinned resolution.

Set `TOOL_ROOT` to the clone, `SOURCE_ROOT` to the allowed pinned snapshot, and `OUT` to a new profile-owned output directory. Preserve source-relative paths.

## Scan

```sh
node "$TOOL_ROOT/understand-anything-plugin/skills/understand/scan-project.mjs" \
  "$SOURCE_ROOT" "$OUT/scan-result.json" --exclude-analysis-data
```

An archive export is not a checkout, so recursive-walk fallback is expected. Prefer an allowed-file snapshot: recursive scans do not inherit checkout ignore protection. Reconcile the scanner list against snapshot inventory because the engine applies additional default exclusions.

## Resolve imports and extract

Write input JSON using native file tools. Copy the scanner's actual file objects unchanged; each includes `path`, `language`, `sizeLines`, and `fileCategory`.

- `import-input.json`: `{ "projectRoot": "<SOURCE_ROOT>", "files": [<scanner file objects>] }`
- `structure-input.json`: `{ "projectRoot": "<SOURCE_ROOT>", "batchFiles": [<scanner file objects>], "batchImportData": {} }`

These illustrate shapes, not valid literal JSON; populate real arrays. For semantic batches, supply the actual resolved per-batch imports.

```sh
node "$TOOL_ROOT/understand-anything-plugin/skills/understand/extract-import-map.mjs" \
  "$OUT/import-input.json" "$OUT/import-map.json"
node "$TOOL_ROOT/understand-anything-plugin/skills/understand/extract-structure.mjs" \
  "$OUT/structure-input.json" "$OUT/structure.json"
```

Require successful exits, nonempty outputs, `scriptCompleted`, and reconciled file coverage. Inspect `filesSkipped`, `filesUnreadable`, and per-stage outcomes independently. A language can produce call-site records while declaration arrays remain empty; overall success does not establish complete symbol coverage.

## Assemble and validate

Built core exports `GraphBuilder` and `validateGraph` from `packages/core/dist/index.js`. Follow the types at the pinned revision. Check `validateGraph(graph).success` and inspect its reported issues, then independently validate uniqueness and edge endpoints.

Keep four coverage claims separate:

- File coverage: every scanner file is represented or accounted for.
- Symbol coverage: declarations come from parser evidence and valid ranges.
- Import coverage: resolved map edges have existing endpoints.
- Semantic coverage: behavioral explanations come from actual subsystem source review.

Tag structural-only summaries. Use declaration locations to distinguish repeated names. Retain unresolved calls and method-name lists in raw evidence rather than guessing relationships; names alone do not justify method-range nodes.

Save source/tool revisions, scope, scanner/parser/import counts, skipped/unreadable paths, graph totals, validation issues, duplicate IDs, dangling edges, and limitations in the receipt. Do not describe the full semantic pipeline as complete when only deterministic extraction ran.
