---
name: git-commit-push
description: "Ship local Git changes: inspect, isolate own work in shared worktrees, validate once, commit coherently, push and verify the remote. Use for /git-commit-push, commit, push, ship, delivery audit or delivery blockers; not deploys or releases."
version: 1.2.0
license: MIT
metadata:
  hermes:
    tags: [git, commit, push, delivery, worktree, fleet]
    related_skills: [lgtm, autogoal, hard-blockers, systematic-debugging]
---

# Git Commit Push

Adapted from TrebuchetDynamics/pi-toolset `skills/delivery/git-commit-push` (rev 2fbe70a):
https://github.com/TrebuchetDynamics/pi-toolset/tree/main/skills%2Fdelivery%2Fgit-commit-push
Merged with the fleet's shared-worktree rules and autogoal's local agent-branch helper.

Ship finished work without turning delivery into another project. Local changes are the
delivery queue, not a reason to stop and ask.

## When this applies

- The user asks to commit, push, or ship ("commit and push", "ship it", "push that").
- `/git-commit-push` (CLI) or `/git_commit_push` (Telegram) was invoked: that invocation **is** the ship request. Any text after the command narrows scope (paths, topic, "audit", "dry run", "no push").
- LGTM accepts a checkpoint that explicitly offered commit/push (see the `lgtm` skill). A generic
  LGTM after an implementation report never implies shipping.
- Audit: the user asks for delivery status, a dry run, or "what would you commit". Do not
  stage, commit, or push.

## Pick the delivery target first

| Situation | Target | Push? |
|---|---|---|
| User (or an accepted checkpoint) explicitly asked to commit/push | the checked-out branch, then its upstream | yes |
| Autonomous goal slice / kanban card, no explicit ship request | `agent/<profile>/<card-id>` via autogoal's helper | **never** |
| Audit request | nothing | no |

Card branch helper (temporary index, so HEAD, the real index, and other agents' dirty work
are untouched):

```bash
~/.hermes/shared-skills/autogoal/scripts/agent_commit.sh <repo> <profile> <card-id> "<message>" <files>...
```

Report the branch and sha it prints. Never point it at main/master or the checked-out branch.

## Fast path

1. **Inspect once.**
   - Read repo instructions (`AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING`), then run
     `git status --short --branch`, `git diff --stat`, `git diff --cached --stat`, and
     `git status --porcelain --untracked-files=all`. `git diff --stat` does not list untracked files.
   - Check upstream: `git rev-parse --abbrev-ref @{u}` and `git rev-list --left-right --count @{u}...HEAD`.
   - Classify every path: **ship now**, **leave local** (with a concrete reason), **needs one
     owner decision**, or **red line**. What this conversation or card produced counts as evidence of ownership.

2. **Separate your work from other writers (fleet worktrees are shared).**
   - Running cards on this repo: `hermes kanban list --status running --assignee <profile>`.
   - Path age: `now=$(date +%s); for f in <paths>; do echo "$(( (now - $(stat -c %Y "$f")) / 60 ))m $f"; done`.
     A path written in the last few minutes, while a card owning that area is running, is
     mid-write. Exclude it and name it; it stays dirty for its owner's commit.
   - A finished card's own files: `git diff --name-only $(git merge-base HEAD agent/<p>/<card>)..agent/<p>/<card>`.
     A path listed there is that card's, even if it looks like part of your work.
   - Ownership is per hunk, not per file. Read the diff of every co-touched file; if foreign
     hunks cannot be split out safely (`git add -p` is unavailable; use `git apply --cached`
     on an edited patch), hold the whole file.
   - Ledgers (`TODO.md`, `BLOCKERS.md`, trackers) usually carry other passes' uncommitted
     prose. If you stage one, say so in the commit message and report; never present it as
     only your change.
   - Re-measure `git status --porcelain` right before staging. A count that moved means a
     writer is live.

3. **Prepare the smallest delivery.**
   - Group in-scope work into the fewest coherent commits, one per component or topic. Keep
     each change with its tests and docs. Never commit code without the test that pins it.
   - Make only safe mechanical fixes (formatting, imports, ignored local output, stale paths).
     Do not expand product scope.
   - When a feature depends on uncommitted predecessors, trace required symbols and
     select only their necessary hunks with regression tests. Do not import a whole
     backend merely because one fixture gained a contract. If whole-file inclusion
     changes unrelated runtime outcomes, narrow the dependency or report the blocker.
   - Gate that curated index in a complete `git checkout-index --all --prefix=.../`
     snapshot, not the dirty root or a partial source mirror. Preserve tracked native
     hosts/docs/source-contract inputs, verify every snapshot blob against the index,
     and identify historical local-only receipt links rather than importing unrelated
     ledgers or generated evidence to make Markdown closure pass.

4. **Validate once, in the right order: stage → gate → push.**
   - Reuse existing results only when they cover the unchanged bytes: compare
     `git hash-object <path>` with the blob you gated; equal blobs mean the result stands.
     Otherwise run the user's checks, or the repo's normal gate, plus `git diff --cached --check`.
   - Run guards **after** staging. Guards built on `git grep` cannot see untracked files, and a
     new file can turn them red the moment it is tracked.
   - If the gate may outlive the terminal timeout, run it as a background process and wait for
     its exit code. A run that timed out did not pass. Never push while a gate is still running.
   - On failure, fix the smallest safe cause and rerun only the failed or affected checks
     (load `systematic-debugging` for a real behavior failure).

5. **Commit.**
   - Stage explicit paths only (`git add -- <paths>`); never `git add -A` / `git add .` on a
     shared tree. Verify with `git diff --cached --name-status` that the staged set is exactly
     what you meant, and that the files you held back are still unstaged.
   - Scan staged content for secrets: `git diff --cached | grep -nEi '(api[_-]?key|secret|token|passw|BEGIN [A-Z ]*PRIVATE KEY)'`.
     Look at every hit before committing.
   - Follow the repo's commit-message convention (check `git log --oneline -10`). Read the
     message back before pushing; once it is on a shared branch, fixing it would need a force-push.
   - If a hook rewrites content, rerun only the affected checks.

6. **Push (explicit ship target only).**
   - Push the configured upstream; with one `origin` and no upstream, `git push -u origin HEAD`.
   - Do not `git pull` / `--autostash` first. Push; on rejection, `git fetch` and inspect.
     Fast-forward only when the incoming commits don't overlap yours and it is clearly safe. Merge or rebase needs
     explicit approval. Never force-push.
   - Verify the remote: `git fetch -q && [ "$(git rev-parse HEAD)" = "$(git rev-parse @{u})" ] && echo MATCH`.
     The push output alone is not proof.

7. **Close the loop.**
   - `git status --short --branch`; report hashes, the push result, and every remaining path with its reason.
   - If a tracker or `BLOCKERS.md` entry authorized the commit, mark it with the SHAs using an
     anchored patch (reread the file first). Don't rewrite the whole file.
   - If any safe topic shipped, the outcome is SHIPPED, even with other paths left local.

## Red lines

- Never commit secrets, `.env*`, credentials, private keys, logs, caches, build output,
  databases or service data roots, `.understand-anything/` or other generated artifacts, or machine state.
- **Project ledgers are not generated artifacts.** `goals.json` (the repo-docs goal ledger,
  written via `goals.py`), `TODO.md`, `BLOCKERS.md`, and impeccable's `PRODUCT.md`, `DESIGN.md`
  (+ sidecar) and `.impeccable/` config/briefs are tracked project files. Ship them with
  the work that changed them; check them with `goals.py validate` for goals.json. Only
  `.impeccable/mocks/` and screenshot/evidence folders follow the repo's gitignore.
- Do not discard, stash, revert, or `git clean` other agents' or the owner's work to make a commit tidy.
- Committed is not deployed. Do not deploy, publish, release, rebuild images, restart live
  services, run migrations, force-push, rewrite history, rebase, merge divergent history,
  change remotes, or delete branches without explicit approval for that exact action.
- Ask only when ownership, intended behavior, secret handling, destructive history,
  dependency policy, or remote integration changes what the safe action is. A long list of
  changed files is not a reason to ask; inspect and isolate it.

## Outcomes

- **SHIPPED**: safe commits pushed (or written to the agent branch). Unrelated paths may remain.
- **NO-OP**: nothing of yours to commit; branch level with upstream.
- **ASKED**: no safe topic can ship without one owner choice. Ask one yes/no question
  with `clarify` (reply `yes` to ship, `no` to leave local), or at most three numbered options.
- **HELD**: a red line, missing credentials, a conflict, a hard validation failure, or an
  unsafe remote state remains after one focused repair attempt. Record it in `BLOCKERS.md`
  only if it meets the `hard-blockers` criteria, and ask any owner question as a questionnaire.

ASKED and HELD describe this delivery only. The surrounding goal or card keeps going: they never mean the work is paused.

## Report (chat-sized: Telegram/Discord first)

At most three lines. Leave out empty fields and don't repeat a hash or path.

```text
SHIPPED|NO-OP|ASKED|HELD — <hashes + push result | agent branch + sha | exact reason>
Checks: <gate(s) and result>; inspected all modified and untracked paths
Left local: <path — reason, …> | Need: <one action>
```

Audit mode starts with `AUDIT — <what would be committed, grouped>` and never changes Git state.

Follow [the shared skill contract](../shared/COMMON-CONTRACT.md) for repo hygiene,
verification evidence, and safety defaults.
