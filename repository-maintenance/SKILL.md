---
name: repository-maintenance
description: Sync repositories and submodules to upstream main.
version: 0.1.0
author: Hermes
license: MIT
metadata:
  hermes:
    tags: [Git, Repositories, Submodules, Upstream]
---

# Repository Maintenance

Synchronize a repository or a superproject and its declared submodules to their upstream `main` branches. This workflow does not assume that dirty work may be discarded, nor that a changed submodule pointer may be committed or pushed without permission.

## When to Use

- “Update all repos,” “use main branches,” or “make every repo upstream-current.”
- “Clean local changes” when the user explicitly authorizes discarding them.
- A project root declares Git submodules and the user includes them in scope.

## Prerequisites

- A target repository or project root; resolve what “all” means before broadening to unrelated sibling repositories.
- A configured remote for each repository. Never assume the remote is named `origin` until inspected.
- Verify that the selected remote URL is the canonical upstream repository, not merely a fork named `origin`; compare it with `.gitmodules` and, when available, verify GitHub identity with `gh api repos/OWNER/REPO --jq '[.full_name, .fork, (.parent.full_name // "-")]'`. If it is a fork or ambiguous, report it and do not claim the repository is upstream-current.
- Treat commit, pull/merge, and push as separate permissions: a request to commit and pull does not authorize pushing; a preference for upstream repositories identifies canonical remotes, not permission to publish. A bare “Approved” authorizes only the concrete operation proposed immediately before it; if the preceding message only reports status or leaves multiple risk levels open, ask which action is approved. Never infer deployment from approval of a code fix. Require explicit user direction before discarding local changes or publishing to a shared upstream branch. A scoped “commit and push all” instruction authorizes delivery only in the named workspace; still inspect each diff and run relevant checks before staging.

## How to Run

Use `read_file` to inspect project guidance and `terminal` to run Git commands in the confirmed project root. Use `clarify` if the requested scope or destructive/publishing choice is unclear. Do not use credentials from chat or expose them in output.

## Quick Reference

- `git status --short --branch`
- `git remote -v`
- `git branch -vv`
- `git submodule status`
- `git fetch <remote>`
- `git merge-base --is-ancestor main <remote>/main`
- `git switch main`
- `git merge --ff-only <remote>/main`
- `git reset --hard <remote>/main` (only after explicit discard authorization)
- `git clean -fd` (only after explicit discard authorization; removes untracked non-ignored files)

## Procedure

1. **Resolve scope.** Confirm the named repository/project. If “all” could mean a larger workspace, ask. Include every initialized and declared submodule when the user says “inside this project and its submodules.”
2. **Read guidance.** Inspect root `AGENTS.md`, README, `.gitmodules`, and nested repo instructions before changing checkouts. Respect stated branch policies; a tag-pinned submodule is not implicitly a request to move to `main`.
3. **Inventory each repository.** Record remote URLs, active branch or detached HEAD, upstream tracking and ahead/behind state, and dirty paths. Inspect the actual diff for every dirty checkout and submodule separately; superproject status does not show submodule file changes. Identify uninitialized submodules.
4. **Fetch before comparing.** Fetch each repository’s configured remote, then compare local `main` with that remote’s `main`. Use `git rev-list --left-right --count HEAD...<remote>/main` (first count is local-only commits; second is remote-only commits) and `git diff --name-status HEAD..<remote>/main` to list incoming paths. Confirm both refs exist and whether local `main` is a fast-forward ancestor. Inspect incoming changed paths before integrating when any local checkout is dirty; do not mistake a locally-ahead diff for remote incoming changes.
5. **Update every in-scope checkout.** For a project-wide “pull/update all” request, explicitly pull each initialized repository—superproject and every declared submodule—rather than assuming the parent pull updates child checkouts; Git may fetch submodule objects recursively without advancing each child branch. Switch only to an existing `main` branch when requested; fast-forward with `git merge --ff-only <remote>/main` when ancestry permits. If dirty files do not overlap incoming changes, Git may preserve them through the fast-forward; verify their diffs afterward. If paths overlap, Git refuses, or safety is uncertain, preserve the work and stop rather than stashing, resetting, or forcing a merge. For detached HEAD, advance the existing `main` ref only after confirming ancestry; attach it only if the working tree is preserved. Never rewrite or delete unrelated branches to make status look clean. Report any declared but uninitialized repository instead of silently counting it as pulled.
6. **Handle and deliver dirty work deliberately.** Treat a no-local-changes requirement separately from permission to publish: if a task would create dirty state and current delivery authorization does not cover those exact changes, ask before editing. Do not assume a completed commit/push request carries into a later task. Never assume local edits can be discarded or committed merely because the user says “all repos.” If the user explicitly authorizes committing/pushing scoped work, inspect each diff, run the relevant checks, and stage only the intended paths; preserve unrelated or unvalidated changes and ask if their disposition is unclear. If the user authorizes discarding changes, verify repository scope and target upstream first, then reset tracked work and remove untracked non-ignored files only if explicitly included; warn that discarded work is unrecoverable unless backed up.
7. **Reconcile submodules and order combined commit/pull work.** Updating a submodule can change its Gitlink relative to the parent. When both local commits and merges are requested, inspect and commit authorized child changes, then pull/merge child repositories first; reconcile and commit authorized parent Gitlink updates after child heads settle, then pull/merge the parent last. This keeps the superproject pinned to the actual child commits. If the parent’s incoming Gitlink overlaps a local update, get the incoming target with `git rev-parse <remote>/main:<submodule>` and verify it is an ancestor of the child `HEAD` with `git -C <submodule> merge-base --is-ancestor <target> HEAD`. If so, stage only that Gitlink, commit it, then merge the parent; Git can fast-forward the pointer. If ancestry fails, stop and preserve the state for review. A child or parent commit is not a push; publish only with explicit authorization. Do not silently restore a pin, stage unrelated paths, or publish a Gitlink update; preserve unrelated parent changes and report blockers.
8. **Verify exhaustively.** Recheck every repository’s branch, tracking ref, ahead/behind state, and working-tree status; recheck the parent separately. After a push, fetch and confirm the exact remote ref equals the pushed commit. Distinguish clean checkouts from clean superproject Gitlinks.

## Pitfalls

- A submodule is an independent repository; the parent records one Gitlink commit, not a branch or its working-tree files.
- A detached HEAD can equal remote `main` without satisfying “use the main branch.”
- A local feature branch that is ahead of its remote is not fixed by merely switching to `main`; do not rewrite it unless asked.
- Updating all submodules to `main` may conflict with intentionally pinned tags/commits or leave the parent Gitlink dirty.
- `git clean -fd` deletes untracked non-ignored files. Use it only when the user clearly authorizes that scope.
- A remote called `origin` can still point to a fork; verify repository identity from its URL before treating its `main` as upstream.
- “Upstream-current” and “no local changes” are separate checks; verify both per repository and at the superproject.

## Verification

In each repository, confirm `git status --short --branch` shows the requested `main` tracking its remote with no ahead/behind count and no dirty paths. In the parent, confirm the same for its own `main` and ensure `git submodule status` reports the intended commits; after publishing Gitlink updates, fetch and verify the remote parent commit and a clean working tree.