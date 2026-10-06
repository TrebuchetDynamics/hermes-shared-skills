---
name: repo-issue-audit
description: "Audit a repo for issues without modifying it."
version: 1.0.0
author: Hermes Curator
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [audit, code-review, verification, guards, static-analysis, evidence]
---

# Read-only repository issue audit

When asked to "find issues", audit a repo, or produce a problem report, the deliverable is an **evidence-tiered report** — not a wave of observations from reading source. The order below is what keeps false positives out of the report; skipping a step is how they get in.

## When to Use

Load this for any "find issues / audit / what's wrong with this repo" request where the user did not ask for a fix. It governs how the audit is produced and how findings are tiered. Repo-specific maps and guard inventories belong in that repo's own skill; this one is the procedure.

## Procedure

### 1. Establish the working-tree baseline first

Run `git status --porcelain` and `git log --oneline -5` **before** anything else.

- Uncommitted changes mean every later result describes a tree nobody reviewed. Say so up front.
- **A guard reporting PASS on a dirty tree may be validating a modified version of itself.** Check whether any file under `tools/check-*`, `scripts/check-*`, or a task-runner target is itself modified, and report that explicitly rather than presenting the pass as clean.
- Pre-existing changes you did not make are not yours to fix, revert, or commit. Report them; do not touch them.

### 2. Run the repo's own guards — don't substitute your own analysis

Mature repos already encode their invariants as deterministic, read-only checks. Discover them from the task runner instead of guessing:

- `package.json` `scripts` (a `preflight` script is often a chain — read it, don't assume)
- `Makefile` targets (a `preflight-fast` / `check-*` recipe lists the exact battery)
- `scripts/check*`, `tools/check-*`, `tools/check_*`

Run each one and capture its **real exit status plus its own summary line**. Prefer the individual checks over the umbrella target: the umbrella usually also builds and runs tests, is slow, and can be OOM-killed on a loaded host, which tells you nothing about the guards.

Run nothing that deploys, restarts services, installs packages, or touches hardware unless the request explicitly authorizes it.

### 3. State the verification gap explicitly

The guard layer is **not** the build layer. If you did not run build / typecheck / unit / e2e, or a toolchain is missing, list them under a "not verified" tier. A report that shows only green guards silently implies coverage it does not have.

### 4. Layer heuristics on top, each labelled with the method that produced it

Coverage gaps, size hotspots, orphan files, marker hygiene. For every finding, name the heuristic — so the reader can judge it, and so a later session can re-run it.

### 5. Close by naming what the method cannot find

Guards and structural scans find shape and drift, not logic bugs (off-by-one, wrong constant, protocol violation, race). Say so plainly instead of implying full coverage.

## Pitfalls

- **Validate a coverage heuristic against a module you know is tested before publishing any gap list.** Test layouts vary *within* one repo: co-located `foo.test.ts`, `src/**/__tests__/`, and a separate top-level `test/` tree all coexist. A scan rooted at the source directory finds zero tests that live beside it. One wrong assumption produced ~260 phantom "untested" files in a single pass.
- **A component's own doc about its test convention can be stale — read the tree, not the doc.** When doc and tree disagree, the tree is the finding (report the drift), and the tree is what your heuristic must match.
- **Import-orphan heuristics need language exclusions.** Entry points (`cmd/*/main`, `main.go`, `main.py`, `__main__.py`) and package initialisers (`__init__.py`, `mod.rs`) have no importers by design and dominate a naive orphan list.
- **Marker greps (`TODO|FIXME|HACK|XXX`) need comment-context filtering in any bilingual codebase.** They collide with ordinary content — an i18n table's Spanish "TODO" (= all), `/dev/bus/usb/XXX/YYY` path examples. Filter to comment context before counting, and expect the real count to be small in a disciplined repo.
- **Size hotspots are a smell, not a finding.** Separate generated and content files (translation tables, data blobs, long test suites) from hand-written logic before ranking, or the top of the list is always noise.
- **Never let a heuristic's output straight into the report.** Spot-check the top few entries by hand first. This is the step that catches every pitfall above.

## Report shape

Keep the tiers visibly separate — never blend "the check passed" with "I inferred this":

1. Guards run — which, and their real status (`repo-guards-green` is a legitimate and useful headline).
2. Not verified — build/test/toolchains you could not exercise.
3. Working-tree state — uncommitted changes, and whether any guard is among them.
4. Heuristic findings — each labelled with its method.
5. Limits — what this method cannot see, and the one or two findings worth acting on first.

Lead with the actionable items and offer next steps; do not fix anything unless asked.

## Worked example

Project-specific worked examples (exact guard command lists, coverage-scan recipes) belong in that project's own codebase-map skill, not here.
