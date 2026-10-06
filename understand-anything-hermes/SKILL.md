---
name: understand-anything-hermes
description: "Install and run Understand-Anything in a Hermes profile."
version: 1.0.0
author: Hermes fleet agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [understand-anything, knowledge-graph, codebase-analysis, hermes-profile, skills]
---

# Understand-Anything on Hermes

`Egonex-AI/Understand-Anything` (MIT, v2.9.7 as of 2026-10) is a multi-agent pipeline + dashboard that turns a repo into an interactive knowledge graph. It ships skills for many agents, **Hermes included**, but the bundled `install.sh hermes` targets `$HOME/.hermes/skills` — the *default profile*, not the active one.

## When to Use

Load this when installing, rebuilding, or debugging the Understand-Anything toolchain in a Hermes profile, or when a task needs the codebase knowledge graph regenerated or queried.

## Install (profile-scoped — do this, not `install.sh`)

The installer only knows the default profile. For any other profile, link manually:

```bash
UA=<path to your Understand-Anything clone>   # e.g. ~/git/Understand-Anything
ln -sfn "$UA/understand-anything-plugin/skills" "$HERMES_HOME/skills/understand-anything"
ln -sfn "$UA/understand-anything-plugin" "$HOME/.understand-anything-plugin"   # plugin root the SKILL.md searches for
```

`$HERMES_HOME` is the active profile dir (e.g. `~/.hermes/profiles/<name>`) — never hardcode `~/.hermes`. Hermes discovers skills **through** the folder symlink: after linking, `skill_view(name='understand-dashboard')` resolves. The in-session skill list is snapshotted at session start, so a fresh session shows them in the index.

Build the engine (required — every pipeline script imports `packages/core/dist`):

```bash
export PATH="$HOME/.hermes/tools/node-26.7.0-linux-x64/bin:$PATH"   # node 26 present; pnpm is NOT
npm install -g pnpm                                                 # → 12.x, works
cd "$UA/understand-anything-plugin"
pnpm install --frozen-lockfile
pnpm --filter @understand-anything/core build
pnpm --filter @understand-anything/skill build          # optional: /understand-chat etc.
pnpm --filter @understand-anything/dashboard build      # optional: dashboard UI
```

Skills provided: `understand`, `understand-chat`, `understand-dashboard`, `understand-diff`, `understand-domain`, `understand-explain`, `understand-figma`, `understand-knowledge`, `understand-onboard`.

## Running the pipeline from Hermes

The skills are written for Claude Code tool names (Task/Read/Write/Bash). Hermes has no `/understand` slash command — **load the skill and execute its phases yourself** with `terminal`, `read_file`, `write_file`, and `delegate_task` for file-analyzer batches.

Scripts live at `$PLUGIN_ROOT/skills/understand/*.mjs|*.py` and run standalone:

```bash
SD="$UA/understand-anything-plugin/skills/understand"
node "$SD/scan-project.mjs" <projectRoot> <out.json> [--exclude <globs>] [--exclude-analysis-data]
node "$SD/extract-import-map.mjs" <in.json> <out.json>      # {projectRoot, files[]} -> {importMap}
node "$SD/extract-structure.mjs" <in.json> <out.json>        # {projectRoot, batchFiles[]} -> functions/classes/exports
node "$SD/compute-batches.mjs" <projectRoot>                 # -> .ua/intermediate/batches.json
python "$SD/merge-batch-graphs.py" <projectRoot>             # -> assembled-graph.json
node "$SD/build-fingerprints.mjs" <in.json>
```

`scan-project.mjs --help` does **not** exist; unknown options exit 1. Usage is `<projectRoot> <outputPath> [flags]`. Same for `generate-ignore.mjs` — a stray `--help` creates a literal `--help/.ua/` directory in the cwd.

## Pitfalls found the hard way

- **`scan-result.json` carries no `importMap` in this build**, even though `SKILL.md` says it does. Run `extract-import-map.mjs` separately; without it the graph has `contains` edges only (no cross-file structure).
- **`compute-batches.mjs` emits up to 25 files per batch**; small/orphan batches get merged. Gate check: >100 files is "scope it down" territory in the source skill.
- **Fusing batches is legal** but each fused dispatch must still write `batch-<batchIndex>.json` (or `-part-<k>`) per *original* index — the merge regex `batch-(\d+)(?:-part-(\d+))?` silently drops any other name, losing every node in that file.
- **`extract-structure.mjs` omits `functions`/`classes` keys when empty** — normalise to `[]` before feeding `GraphBuilder.addFileWithAnalysis`, which iterates them unguarded. Reconstruct `lineRange` as `[startLine, endLine]`.
- **`GraphBuilder` emits function/class nodes with empty `tags`**, and `detectLayers()` only assigns `type:"file"` nodes. Both trip UA's own schema validation — backfill tags and add an "Unassigned" layer for leftover config/document/service nodes.
- **Validate before writing.** `validateGraph()` drops dangling edges; write first and the file on disk keeps them.
- A deterministic no-LLM graph is entirely buildable (`GraphBuilder` + `detectLayers` + `generateHeuristicTour`) — the right checkpoint before committing to a 100+-subagent LLM pass.

## Cost shape

Phase 2 dispatches one file-analyzer subagent **per batch** (≤25 files). For example, a 3,565-file repo after exclusions → 183 batches → 183 LLM dispatches. Treat a full semantic pass as a multi-hour, high-token job and get explicit user consent for scope first; the deterministic structural pass costs nothing and gives a complete map in ~15 s.

A deterministic structural-graph builder is worth keeping per project (in that project's scratch or tools), adapted to its paths.
