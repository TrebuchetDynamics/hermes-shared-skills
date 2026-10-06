---
name: git-pull-merge
description: "Use when pulling or merging Git changes safely."
version: 1.0.0
license: MIT
metadata:
  hermes:
    tags: [git, pull, merge, sync, worktree, fleet]
    related_skills: [git-commit-push, shared-worktree-commit-safety, systematic-debugging]
---

# Git Pull Merge

The counterpart of `git-commit-push`: bring changes **in** without losing anyone's work. In a fleet
worktree, other agents may have uncommitted edits, so a pull is a coordination problem before it
is a git problem.

## When this applies

- The user asks to pull, sync, "update from origin/main", or merge a branch into the current one.
- `/git-pull-merge` (CLI) or `/git_pull_merge` (Telegram) was invoked: that invocation **is** the
  request. Text after the command names the source ("agent/wing/t_1234", "origin/develop", "PR 52")
  or narrows scope ("audit", "dry run", "ff-only").
- Audit: the user asks what a pull would bring in. Fetch and report; change nothing.

## Pick the source first

| Request | Source | Integration |
|---|---|---|
| bare `/git-pull-merge`, "pull", "sync" | the branch's upstream (`@{u}`) | fast-forward, else merge |
| "merge <branch>" / an agent card branch | that branch (fetch it first if remote) | merge commit |
| "merge PR <n>" | `gh pr checkout`-free: `git fetch origin pull/<n>/head:pr-<n>` | merge commit |
| audit / dry run | as above | none (report only) |

Never rebase or rewrite history, never `--force`, never `git pull --rebase`, and never `reset --hard`.

## Fast path

1. **Inspect once.**
   - Read repo instructions, then run `git status --short --branch`, `git fetch --prune origin`,
     `git rev-list --left-right --count HEAD...<source>` and `git log --oneline HEAD..<source>`.
   - Already up to date (`0` incoming) → report NO-OP and stop.
2. **Check the worktree before touching it (fleet worktrees are shared).**
   - List the files the source changes: `git diff --name-only HEAD...<source>`.
   - Intersect them with the dirty set from `git status --porcelain`. No overlap → git can update
     safely around the dirty files; go to step 3.
   - **Overlap with your own uncommitted work:** commit it first (`git-commit-push` rules, or the
     card's `agent_commit.sh` branch), then integrate.
   - **Overlap with someone else's live work** (recent mtime, a running card on that area, see
     `shared-worktree-commit-safety`): do not stash, revert or overwrite it. Integrate into an
     isolated worktree instead (`git worktree add <scratch> <branch>`, merge there, verify), or
     report exactly which files are blocked and by whom.
   - Never bare `git stash`/`stash pop` in a shared worktree. If a stash is unavoidable, use
     `git stash push -m "<unique-tag>" -- <paths>`, record its SHA, and restore with `stash apply <sha>`.
3. **Integrate.**
   - Upstream sync: `git merge --ff-only @{u}` when local has no unique commits. If both sides moved,
     `git merge --no-ff @{u}`, with a message naming what came in.
   - Named branch: `git merge --no-ff <source> -m "Merge <source>: <one-line summary>"`.
   - Submodules: `git submodule update --init --recursive` when the merge moved a gitlink.
4. **Resolve conflicts** (only when step 3 stops with conflicts).
   - Resolve mechanical conflicts yourself: imports, formatting, both-sides-added lists, lockfiles
     (regenerate with the package manager rather than hand-merging), generated files (regenerate).
   - For semantic conflicts, keep both behaviours where they compose. Otherwise prefer the side
     matching the accepted requirement or ADR, and record why in the merge message.
   - A conflict that is a real product decision becomes an owner question (ask, don't block):
     apply the recommended side, keep it reversible, and ask in the report.
   - Check nothing is left behind: `git diff --name-only --diff-filter=U` must be empty, and no
     `<<<<<<<` markers may remain (`git grep -n '^<<<<<<< '`).
5. **Re-gate.** Run the repo's normal checks for the areas the merge touched, at minimum
   build/analyze plus the nearest tests, and `git diff --check HEAD~1`. A failure caused by the merge
   is part of this task: fix it, or roll back with `git merge --abort` (before committing) or
   `git revert -m 1 <merge>` (after). Never `reset --hard`.
6. **Close the loop.**
   - Report the before and after HEAD, what came in (commit count and highlights), conflicts and how
     they were resolved, and the checks run.
   - Push only if the user asked ("pull and push", "merge and push") or the accepted checkpoint
     said so; use `git-commit-push` rules (no force; PR when the branch is protected).
   - A merged agent card branch is reported by card ID, so the board and goals.json can be reconciled.

## Red lines

- Never discard, stash-and-drop, revert or overwrite other agents' or the owner's uncommitted work.
- Never rebase, force-push, `reset --hard`, delete branches or rewrite published history without
  explicit approval for that exact action.
- Do not merge into a protected branch locally and push around its PR rule. Open a PR instead.
- Do not "resolve" a conflict by deleting one side's tests or weakening assertions.

## Outcomes

- **MERGED**: the source is integrated (fast-forward or merge commit) and checks pass.
- **NO-OP**: already up to date.
- **ASKED**: integrated on a reversible default, with an owner question about a conflict.
- **HELD**: it cannot integrate without losing someone's work or with failing checks after one
  focused repair. Nothing is left half-merged: `git merge --abort` was run, or the merge is reverted.

ASKED and HELD describe this integration only; the surrounding goal or card keeps going.

## Report (chat-sized: Telegram/Discord first)

At most three lines:

```text
MERGED|NO-OP|ASKED|HELD — <source> → <branch>: <before>..<after> (<n> commits; ff|merge)
Checks: <gate(s) and result>; conflicts: <none | files + how resolved>
Blocked/Need: <files held for live work | one owner question>  # omit when empty
```

Audit mode starts with `AUDIT — <n> incoming commits, overlapping dirty files: <list|none>` and changes nothing.

Follow [the shared skill contract](../shared/COMMON-CONTRACT.md) for repo hygiene, verification
evidence, and safety defaults.
