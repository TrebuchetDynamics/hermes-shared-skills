---
name: git-commit-push
description: "Use when committing and pushing scoped Git changes."
version: 1.3.3
license: MIT
metadata:
  hermes:
    tags: [git, commit, push, delivery, worktree, fleet]
    related_skills: [lgtm, autogoal, hard-blockers, systematic-debugging, git-pull-merge]
---

# Git Commit Push

Adapted from TrebuchetDynamics/pi-toolset `skills/delivery/git-commit-push` (rev 2fbe70a):
https://github.com/TrebuchetDynamics/pi-toolset/tree/main/skills%2Fdelivery%2Fgit-commit-push
Merged with the fleet's shared-worktree rules and autogoal's local agent-branch helper.

Ship finished work without turning delivery into another project. Local changes are the
delivery queue, not a reason to stop and ask. Prefer direct execution for a bounded
stage/gate/commit sequence; delegate only when substantial ownership or dependency
analysis needs isolation. Do not add another reviewer or repeat a completed gate
merely because delivery moved from a worker to its parent. Verify the candidate
identity and existing receipts first; unchanged evidence can satisfy that handoff.

## When this applies

- The user asks to commit, push, or ship ("commit and push", "ship it", "push that").
- `/git-commit-push` (CLI) or `/git_commit_push` (Telegram) was invoked: that invocation **is** the ship request. Any text after the command narrows scope (paths, topic, "audit", "dry run", "no push").
- LGTM accepts a checkpoint that explicitly offered commit/push (see the `lgtm` skill). A generic
  LGTM after an implementation report never implies shipping.
- Audit: the user asks for delivery status, a dry run, or "what would you commit". Do not
  stage, commit, or push.

## Pick the delivery target first

Resolve the repository's branch policy before choosing any helper, worktree or
remote route. A main-only policy overrides this skill's agent-branch and delivery-PR
recipes: curate owned changes in the canonical checkout and use complete immutable
filesystem exports for QA, without creating branches or branch-based worktrees.
Recheck that policy after a user correction or resumed handoff; an earlier candidate
branch is preserved evidence, not permission to keep developing there.

Compare the permitted route with effective remote protection before expensive gates.
If main-only delivery conflicts with a PR requirement, ask only about that policy
conflict; do not create a PR or weaken protection under generic shipping authority.
When the owner explicitly authorizes removal of the PR requirement, remove only that
rule, preserve every other protection and verify the ruleset plus effective branch
rules. Follow [GitHub protection changes](references/github-protection.md).
A successful protection change resolves only the delivery-route question: retain the
original commit/push/main-delivery obligation and continue candidate verification.

| Situation | Target | Push? |
|---|---|---|
| User explicitly asked to commit only | the checked-out branch, subject to repository branch policy | **no** |
| User explicitly asked to push, commit and push, or ship | the checked-out branch, then its upstream | yes |
| Autonomous goal slice / kanban card, no explicit ship request | `agent/<profile>/<card-id>` via autogoal's helper | **never** |
| Audit request | nothing | no |

Interpret delivery verbs separately: a request to implement and commit authorizes a local commit, not publication. Do not infer push permission from the skill name, an upstream being configured, or a broad request to finish all plans. After a local-only commit, verify `git show --stat HEAD` and repository status; omit remote fetch/push verification because no remote write occurred.

**Scope is authorization, not authorship.** An explicit repo-wide ship request covers
all eligible changes in requested scope, including completed work from other agents
or earlier sessions. Take delivery ownership after checking provenance, intended
scope, completion, dependencies, secrets and candidate-bound verification; authorship
alone never excludes changes or yields NO-OP. Do not ask again merely because the
implementer is someone else or no card exists. A path/topic allowlist stays narrow;
an autonomous worker/card without explicit repo-wide authorization remains limited
to its owned slice. Local-only requests never authorize push; audit never authorizes
Git writes. Repo-wide authorization does not override a live writer/lease, unfinished
work, unapproved product scope, secrets, or missing verification.

Card branch helper (temporary index, so HEAD, the real index, and other agents' dirty work
are untouched). Resolve `<skills-root>` as the parent of this loaded skill directory:

```bash
"<skills-root>/autogoal/scripts/agent_commit.sh" <repo> <profile> <card-id> "<message>" <files>...
```

Report the branch and sha it prints. Never point it at main/master or the checked-out branch.

## Fast path

1. **Inspect once.**
   - Read repo instructions (`AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING`), then run
     `git status --short --branch`, `git diff --stat`, `git diff --cached --stat`, and
     `git status --porcelain --untracked-files=all`. `git diff --stat` does not list untracked files.
   - Check upstream: `git rev-parse --abbrev-ref @{u}` and `git rev-list --left-right --count @{u}...HEAD`.
     The first number counts commits reachable from the first argument only, the second from the
     second only. Label them from the expression you typed, not from habit: `@{u}...HEAD` prints
     behind/ahead, `HEAD...origin/main` prints ahead/behind — reading the pair the other way round
     reports a branch you are behind as one you are ahead of.
   - For a changed submodule, compare `git -C <path> rev-parse HEAD` with its upstream, then
     compare that nested commit to the superproject's committed pointer (`git rev-parse HEAD:<path>`)
     and index pointer (`git ls-files -s -- <path>`). Do not use `git rev-parse <path>` as the
     submodule revision: a filesystem path is not a Git ref. Stage the gitlink explicitly and
     verify the staged SHA equals the intended nested `HEAD` before committing.
   - Classify every path: **ship now**, **leave local** (with a concrete reason), **needs one
     owner decision**, or **red line**. What this conversation or card produced counts as evidence of ownership.
   - **A shared checkout that is behind its upstream is not automatically the delivery queue.**
     Several agents push from sibling checkouts, so a dirty path can hold an *older revision* of a
     file upstream has since changed — its worktree blob equal to an unmerged `agent/*` branch
     tip's blob and older than `origin/<branch>`'s. Committing or overlaying it reverts reviewed
     work. Resolve every path's bytes against `origin/<branch>` and the unmerged branch tips in
     one pass before shipping a behind tree; a superseded path is an owner decision, not a flush.
     Rehearse the landing in a scratch worktree (merge, `--abort` on conflict) so the question you
     ask is specific. Depth: [shared-worktree-safety.md](references/shared-worktree-safety.md).

2. **Separate eligible completed work from live or out-of-scope work.**
   - Running cards on this repo: `hermes kanban list --status running --assignee <profile>`.
   - Path age: `now=$(date +%s); for f in <paths>; do echo "$(( (now - $(stat -c %Y "$f")) / 60 ))m $f"; done`.
     A path written in the last few minutes, while a card owning that area is running, is
     mid-write. Exclude it and name it; it stays dirty for its owner's commit.
   - A finished card's own files: `git diff --name-only $(git merge-base HEAD agent/<p>/<card>)..agent/<p>/<card>`.
     A path listed there establishes provenance, not an exclusion. Under explicit repo-wide
     authorization, compare its bytes with the target and include completed unshipped work
     after the same scope and verification checks; a card-branch commit is not proof it
     already reached the requested target.
   - A *running* card's own files: read its body (`hermes kanban show <id>`) and its latest run
     summary. A live ownership contract or lease means leave its actively-owned hunks
     to its branch commit; an "authored by" label alone does not — check
     `git log agent/<p>/<card>` for the commit that already carries them instead of shipping
     them yourself and calling them your held work. Compare the branch against the working tree
     (`git diff agent/<p>/<card> -- <paths>`): empty output means the tree's bytes are already
     committed there, which establishes provenance even while the file still reads as modified
     against HEAD. For a path untracked in the tree that same diff renders as pure deletions —
     untracked files are not in the comparison, so it is not evidence the file is missing.
   - Generated indexes and their classification ledgers: stage only eligible in-scope diffs.
     A regenerated index also carries rows for files you are not committing, and an
     index↔tree guard then fails on the pushed tree; read `git diff -- <index>` and hold the
     file when excluded rows ride along.
   - Eligibility is per hunk, not per file. Read the diff of every co-touched file; if excluded
     hunks cannot be split out safely (`git add -p` is unavailable; use `git apply --cached`
     on an edited patch), hold the whole file.
   - Ledgers (`TODO.md`, `BLOCKERS.md`, trackers) usually carry other passes' uncommitted
     prose. If you stage one, say so in the commit message and report; never present it as
     only your change. A ledger also receives a live card's own status ticks (`goals.py task
     <id> done`), so staging one can duplicate lines that card's branch commits too — name it in
     the message and reconcile by task/entry identity before staging; do not duplicate status ticks.
     - A ledger's working copy can also be **behind** the remote, and committing that deletes other
       people's work. Another pass may have pushed its entries from a different checkout, so the copy
       you hold is missing lines that exist on `origin/<branch>` and your commit removes them on push.
       Diff the ledger against the remote before staging (`git diff origin/<branch> -- <ledger>`) and
       inspect additions, removals and task identities against fresh upstream. Reconstruct only
       genuine authorized unshipped edits **on fresh upstream in an isolated candidate**;
       preserve newer remote entries via supported `goals.py task`/`add-task`/`fmt`/`render`
       operations and anchored prose edits, then validate and inspect the resulting diff.
       Never delete remote lines merely to match a stale/forked copy. A stale-only ledger
       contains no new work: leave that copy untouched and do not create a restoration commit.
     - Re-measure `git status --porcelain` right before staging. A count that moved means a
       writer is live.
   - **Completed cross-agent implementation is eligible under explicit repo-wide authorization.**
     Inspect its diff, provenance and completion evidence; run or reuse candidate-bound gates
     and include its tests/docs. Missing review or verification requires evidence, not an
     authorship veto. Attribute contributors and verification receipts in the commit message
     and report; never call their implementation your own. Hold live writer/lease hunks,
     incomplete or unverifiable work, secrets and unapproved scope. Ask only when an actual
     intent or authority gap remains; do not revert or delete held work.

3. **Prepare the smallest delivery.**
   - Group in-scope work into the fewest coherent commits, one per component or topic. Keep
     each change with its tests and docs. Never commit code without the test that pins it.
   - Make only safe mechanical fixes (formatting, imports, ignored local output, stale paths).
     Do not expand product scope.
   - Reconcile producer and consumer contracts when combining reviewed slices before the
     broad gate: run formatting, analysis and their focused regression union on the assembled
     candidate. A component-removal patch can delete a field still asserted by another slice's
     tests even when both artifacts passed independently. Remove only assertions for genuinely
     removed APIs; preserve public-behavior, ownership and recovery regressions. Resolve
     conflicts in the isolated candidate, never in an actively reviewed worker's workspace.
   - Classify grouped test failures by their first failing assertion before calling
     them production regressions or stale fixtures. If setup still supplies inventory
     through a removed transport, migrate the harness to the supported authority and
     preserve the ownership, stale-response, denial and explicit-retry assertions;
     deleting those scenarios can conceal a real recovery gap. Run the focused union
     before a broad suite. If another reviewed slice is genuinely independent, qualify
     and deliver it separately without implying the original shipping queue is finished.
   - When a feature depends on uncommitted predecessors, trace required symbols and
     select only their necessary hunks with regression tests. Do not import a whole
     backend merely because one fixture gained a contract. If whole-file inclusion
     changes unrelated runtime outcomes, narrow the dependency or report the blocker.
   - Gate that curated index in a complete `git checkout-index --all --prefix=.../`
     snapshot, not the dirty root or a partial source mirror. Preserve tracked native
     hosts/docs/source-contract inputs, verify every snapshot blob against the index,
     and identify historical local-only receipt links rather than importing unrelated
     ledgers or generated evidence to make Markdown closure pass. For main-only delivery
     with a pre-populated shared index, use the temporary-index landing recipe in
     [shared-worktree-safety.md](references/shared-worktree-safety.md#temporary-index-landing-without-a-development-branch).

4. **Validate once, in the right order: stage → gate → push.**
   - Identify the repository's canonical check command before running the gate
     (`make check`, `make test`, or the documented equivalent). Execute it from
     the complete candidate snapshot with the supported timeout control, retaining
     its exact command and result. Prefer that entry point over an equivalent
     ad-hoc wrapper: verification integrations may recognize the canonical command
     but miss a nested invocation, forcing an otherwise redundant full run.
   - Bind the gate to the curated index: record `git write-tree`, check the complete
     exported snapshot, and retain its commands, results and relevant dependency/environment
     inputs. Reuse those results only while those inputs match; unchanged source bytes alone
     do not prove unchanged tools or dependencies. Run `git diff --cached --check`.
   - Scope `GIT_DIR`, `GIT_WORK_TREE` and `GIT_INDEX_FILE` to individual Git/index-aware
     probes, not the entire gate environment. Never persist snapshot routing with
     `git config core.worktree`: it redirects other sessions' status, staging and
     commits even after the gate exits. Use `git -c core.worktree=<snapshot> ...`
     only for the individual guard that needs it. Build tools can invoke Git inside
     their own SDK checkout; inherited candidate overrides make those probes read
     the wrong repository and can corrupt SDK version detection. In Python, keep a separate
     `git_env` for index/export checks and strip these three keys from the environment
     passed to Flutter, npm and other build commands. For a Git-backed guard in a
     filesystem export, pass the candidate overrides only to that guard so its
     `git ls-files` sees the curated index rather than an empty parent-repo pathspec.
   - **Satisfy the snapshot's dependency inputs before gating it.** A snapshot made with
     `git worktree add` or `checkout-index` contains tracked files only: no installed module tree,
     no untracked runtime config. The gate then dies on its first check with a missing tool
     (`local <x> not found`) or the app cannot start, which reads as clean bytes failing for no
     visible reason. Link the already-installed module set into the candidate when the manifest and
     lockfile are identical between what ships and what is installed, copy untracked runtime env in
     (copy it, never stage or commit it), and re-run the check that failed to confirm the cause was
     the prerequisite and not the payload. For Flutter, treat `pubspec.lock` as part of the gated
     candidate: if `flutter pub get` changes it, either include that exact lockfile delta or restore
     the lock first and rerun analysis/tests against the restored dependency graph; never ship a
     lockfile different from the one those checks exercised.
   - **Decide whether a snapshot-only failure belongs to the snapshot or to the repository.** A
     guard that passes in the long-lived tree and fails in every clean checkout is resolving against
     untracked artifacts — a citation to generated output, a file only a local tool run creates.
     That is a repository defect: fix the citation to name the *tracked producer* (verify the
     producer from its own usage or argument list, never from its apparent name) or teach the guard
     to skip ignored output. Re-run it with a deliberately dangling reference injected to prove the
     guard still fails, so "it passes now" means the reference is sound and not that the check was
     neutered. Never pre-seed the missing artifact to force green. For generated
     skills/plugins, test the tracked template and exercise the actual generator
     or installer in a hermetic fixture; do not assert that an ignored installed
     payload already exists, because clean candidate exports omit it.
   - Report suite counts from that exact candidate, not a broader dirty-tree run: excluded
     foreign tests can legitimately change the totals. Never import unrelated work merely
     to reproduce an earlier count.
   - Run guards **after** staging. Guards built on `git grep` cannot see untracked files, and a
     new file can turn them red the moment it is tracked.
   - If the gate may outlive the terminal timeout, run one tracked background process with
     completion notification and retain its handle, pinned candidate, per-command logs and
     exit results. Do not start another suite merely because a foreground wait expires;
     distinguish a wait-window timeout from an actual process timeout. Inspect once if needed,
     then use the completion notification rather than repeated waits or pending-status messages.
     A running gate is not a pass. Never push while its required checks are still running.
   - Preserve the complete requested delivery obligation across asynchronous handoffs:
     local commit → passing candidate gate → verified remote push → verified PR merge when
     authorized. Record the next action with the existing delivery receipt and resume from
     completion evidence; a local-commit status report does not finish a push-and-merge request.
   - On failure, fix the smallest safe cause and rerun only the failed or affected checks
     (load `systematic-debugging` for a real behavior failure). Preserve passing receipts
     for unchanged source, tests, dependencies and tool inputs. A browser-selector-only
     repair needs browser verification, not another full Flutter suite. Repair missing
     verification metadata from the executed receipt; do not rerun an unchanged passing
     gate just to clear a stale warning or refresh a report. Explicit owner requests for
     a fresh run still apply; identify that run separately from the original qualification.
   - **Never waive a gate to ship a change that does nothing at runtime.** A guard's own escape
     hatch — an accepted-drift baseline like `KNOWN_COMMAND_DRIFT`, a `@known-failure` marker —
     exists for deliberate, permanent divergence. Spending it to push a docs-only or otherwise
     inert revision past a red gate leaves a stale waiver that hides the next real divergence.
     Record the owner's decision, leave the deploy queued, and let the blocking fix land first.
   - If a push already carried a change whose canonical gate had not run, do not rewrite
     history to hide it: run the gate against the pushed bytes now, report the miss in plain
     words (naming the commit whose message does not describe what it carried), and fix
     forward with a scoped commit if it fails. A pushed message cannot be corrected without a
     force-push, so the honest record is the report plus the after-the-fact result.

5. **Commit.**
   - Stage explicit paths only (`git add -- <paths>`); never `git add -A` / `git add .` on a
     shared tree. Verify with `git diff --cached --name-status` that the staged set is exactly
     what you meant, and that the files you held back are still unstaged.
   - Scan staged content for secrets: `git diff --cached | grep -nEi '(api[_-]?key|secret|token|passw|BEGIN [A-Z ]*PRIVATE KEY)'`.
     Classify every hit before acting on it. A real value blocks the commit, but these patterns also
     catch **names and prose**: a variable assignment whose right-hand side is another variable
     (`TEST_PASSWORD="$ADMIN_PASSWORD"`) and a sentence that says "rotate any secrets" are not
     secrets. Hold the commit for a value only; never rewrite a name or a quoted sentence to silence
     the matcher.
   - Follow the repo's commit-message convention (check `git log --oneline -10`). Read the
     message back before pushing; once it is on a shared branch, fixing it would need a force-push.
   - Immediately before committing, re-read `git diff --cached --name-only` and compare it with
     the paths this commit is meant to carry. The index survives across tool calls, so a file
     staged in an earlier step — for another topic, or for a gate you have not finished — rides
     along silently and ships under a message that does not describe it, and a pushed message
     cannot be corrected without a force-push; unstage it (`git restore --staged <path>`) or fold
 it in and say so. A pathspec commit (`git commit -F <msg> -- <paths>`) is the stronger form on
 a shared tree: it records exactly those paths whatever else the index holds, so a file left
 staged by an earlier step cannot ride along even when the re-read misses it. Then compare `git write-tree` with the recorded gated tree
     and verify HEAD has not moved; concurrent staging can otherwise change what ships.
     After committing, require `git rev-parse HEAD^{tree}` to match the gated tree. If hooks
     or another writer changed it, inspect the difference and rerun affected checks before
     claiming verification; do not replay a successful gate merely for reassurance.

6. **Push (explicit ship target only).**
   - Push the configured upstream; with one `origin` and no upstream, `git push -u origin HEAD`.
   - Do not `git pull` / `--autostash` first. Push; on rejection, `git fetch` and inspect (the
     `git-pull-merge` skill covers integrating remote changes safely).
     Fast-forward only when the incoming commits don't overlap yours and it is clearly safe. Merge or rebase needs
     explicit approval. Never force-push. Measure the overlap against the merge base, not against
     HEAD: `git diff --name-only $(git merge-base HEAD origin/main)..origin/main` lists what they
     changed, while `HEAD..origin/main` also lists your own unpushed files and reads as an overlap
     that is not there.
   - **When a shared dirty checkout cannot safely integrate incoming work**, prepare a fresh
     isolated delivery branch at a pinned upstream revision without stashing, resetting or
     switching the shared checkout. Apply only attributed completed source deltas; reconstruct
     genuine ledger changes with supported ledger operations instead of copying a stale file.
     Stage explicit paths, gate the coherent candidate and push its delivery branch. Reuse an
     existing suitable PR rather than creating a duplicate. When merge is authorized, satisfy
     repository protection, reviews and checks, then merge the exact inspected PR head and
     read back its merged state plus main inclusion. Merge authorization never permits direct
     main pushes or protection bypass where a PR is required. Preserve the original local
     branch/index/worktree and report any divergence; do not realign pointers or force-remove
     worktrees as incidental delivery cleanup.
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

- **COMMITTED**: the requested local commit exists and was read back; no push was requested or performed. Unrelated paths may remain.
- **SHIPPED**: safe commits pushed (or written to the agent branch). Unrelated paths may remain.
- **NO-OP**: no actual unshipped delta in requested scope after checking all eligible
  completed changes against the requested target, regardless of author. Already-published
  bytes and stale-only ledgers are not new work. Report behind/diverged status separately;
  withheld work awaiting safety, authority or verification is HELD/ASKED, not NO-OP.
- **ASKED**: no safe topic can ship without one owner choice. Ask one yes/no question
  with `clarify` (reply `yes` to ship, `no` to leave local), or at most three numbered options.
- **HELD**: a red line, missing credentials, a conflict, a hard validation failure, or an
  unsafe remote state remains after one focused repair attempt. Record it in `BLOCKERS.md`
  only if it meets the `hard-blockers` criteria, and ask any owner question as a questionnaire.

ASKED and HELD describe this delivery only. The surrounding goal or card keeps going: they never mean the work is paused.

## Report (chat-sized: Telegram/Discord first)

At most three lines. Leave out empty fields and don't repeat a hash or path.

```text
COMMITTED|SHIPPED|NO-OP|ASKED|HELD — <local sha, not pushed | hashes + push result | agent branch + sha | exact reason>
Checks: <gate(s) and result>; inspected all modified and untracked paths
Left local: <path — reason, …> | Need: <one action>
```

Audit mode starts with `AUDIT — <what would be committed, grouped>` and never changes Git state.

Follow [the shared skill contract](../shared/COMMON-CONTRACT.md) for repo hygiene,
verification evidence, and safety defaults.

## Shared index safety and checkout isolation

Before staging accumulated or concurrent changes, load
[shared-worktree-safety.md](references/shared-worktree-safety.md).
For a new coding checkout, load [WORKTREE-ISOLATION.md](../shared/WORKTREE-ISOLATION.md).
These references do not grant commit, push, cleanup or execution authority.

## Skill policy regression checks

For changes to this delivery policy, run through `terminal` from the shared-skills
repository: `python git-commit-push/scripts/test_delivery_scope.py -v`.
The canonical `make check` discovers this offline suite. These checks pin scope,
cross-agent eligibility, live-writer exclusions and stale-ledger reconciliation;
they are policy-contract tests, not proof of model behavior or live publication.
