<!-- Consolidated reference; original metadata is provenance, not a command.
name: implement-spec
description: "Implement the result of /to-spec and /to-tickets in code."
disable-model-invocation: true
-->

# Explicit whole-spec execution mode

Use `/autogoal` with an explicit whole-spec request and accepted spec/tracker pointers. This mode, not the default one-slice picker, owns the dependency frontier through completion within the user's bounded mandate. Do not create a second scheduler, goals ledger or review chain: keep one executor and existing live ownership. A default invocation or accepted design cannot select this mode.

Follow [the engineering cycle](../../shared/ENGINEERING-CYCLE.md) for verified
addyosmani skill routing, canonical backlog ownership and review-gated continuation.
Use existing `--ledger-mode proposal --integration-owner <owner>` worker roles;
only that owner closes canonical tasks after evidence and required review acceptance.

## Active execution policy (overrides historical upstream steps below)

Resolve scope, current native ownership, actual worktrees and accepted ticket/dependency edges first. Preserve existing IDs and use canonical `repo-docs/scripts/goals.py` for ledger mutations, never hand-edit goals.json. Refuse cycles/missing dependency IDs; retain completed and claimed tickets. Establish the integration owner/branch and its pinned source, prerequisites and checks before dispatch. Use existing `start_goal.py` admission/reconciliation, complete contracts, source snapshots and budgets for native card workers; explicit disjoint children remain owned by their parent. This reference adds no new helper flags or automated runtime guarantee.

The frontier contains only dependency-satisfied, unclaimed tickets in the accepted spec. Completion/startup/merge are distinct states: independently read the exact commits, executed checks and required review acceptance before satisfying an edge. Recompute the frontier after each integration; do not dispatch unrelated backlog or duplicate a live card. Use actual owned worktrees with unique branches; conversation isolation is not checkout isolation. Respect the repository's candidate manifest and exact-source controls.

Carry explicit no-commit authority into every worker contract. When committing is forbidden, preserve diffs and executed checks as implementation evidence; do not force a commit receipt or claim integration/closure. Local commit, owned-branch integration, push, PR creation/readiness, tracker closure and deploy are separate permissions. Worker branches cannot merge/push or bypass protected delivery. The authorized integration owner may integrate only its invocation's branches after applicable checks/review. No automatic reset, stash, clean, PR action, publish, spending or credentials. Clean up only owned clean worktrees after commits/evidence are durably retained.

Historical setup/reset/tdd/code-review/automatic-PR instructions below are source provenance only, NOT executable Hermes instructions. The native policy below remains active and supersedes those upstream steps and the generic historical Hermes note. A missing required capability is reported, never skipped. Report implementation, checks, review, integration and ticket closure separately; pending PR is not resolved work. Do not claim native/provider execution from policy fixtures.

You have been provided a spec. This spec should have tickets associated with it, describing how to implement the spec.

The issue tracker should have been provided to you. If not, tell the user to run `/setup-matt-pocock-skills`.

The goal is the entire spec implemented on a single **integration branch**, with every ticket resolved the way the issue tracker closes work.

The tickets are not a list of steps. They are a **task graph** with blocking relationships between them. This means there is always a **frontier** of tickets which are ready to be grabbed.

Communication to and from subagents should be sparse. Communicate primarily through **context pointers**: to the spec, tickets, research notes, and previous commits. Don't duplicate information already available via pointers.

**Implementer subagents** should be run in the background where possible for maximum concurrency.

## Steps

1. Read the spec and tickets to understand the task graph.

2. (optional) Use an **exploration subagent** to conduct any exploration required by the tickets - relevant codebase files or external documentation. Ensure the exploration subagent can save files - it should save its markdown notes in a directory outside the repo, accessible by all future subagents. This lets **implementer subagents** focus on implementation rather than exploration.

3. Create the integration branch. If the issue tracker closes work through PRs, or the user asks for one, open a draft PR after the first merge in step 5 (a branch with no commits ahead of main can't open one), marked as closing the spec and tickets.

4. Use **implementer subagents** to implement each ticket, each in its own worktree on its own branch. Each implementer subagent:
   - confirms its worktree is based on the integration branch before starting, and resets onto it if not;
   - calls the Skill tool with `tdd` to build the ticket;
   - merges the integration branch tip into its own branch before reporting done

5. Once an **implementer subagent** completes, merge its work to the integration branch with a **merger subagent**.

6. If this changes the **frontier** of available tickets, kick off more **implementer subagents** to work on the new tickets. This allows for maximum concurrency.

7. Once all tickets are complete, call the Skill tool with `code-review` on the integration branch. Fix all issues raised by the code review in a single **implementer subagent**.

8. If a draft PR exists, mark it ready for review. Otherwise, resolve each ticket the way the issue tracker closes work, and report the integration branch.

9. Clean up all **implementer subagent** worktrees.

## Hermes integration policy (local overlay)

These adaptations govern autogoal's explicit whole-spec mode only; other workflows retain their own scope.

- Explicit invocation only: `disable-model-invocation: true` expresses upstream intent, not a verified Hermes enforcement guarantee. Use this workflow only when the user requests whole-spec implementation. Importing the skill is not authorization to run it.
- Read the accepted spec, ticket IDs, blocking edges, repository instructions and current ownership first. Use the existing authorized tracker (including local Markdown/goals.json); do not require the uninstalled `/setup-matt-pocock-skills` command. Ask for a missing tracker/spec pointer while continuing independent discovery; do not invent tickets or requirements. Detect cycles and missing dependencies before dispatch. Document the frontier and rejection reasons.
- `delegate_task` isolates conversation, not the Git checkout. Create an actual `git worktree` and a unique owned branch per implementer through `terminal`, based on the integration branch's recorded commit. Pass its absolute working directory and small context pointers to the child. Bound concurrency to the available runtime capacity and disjoint source/test resources. Without real worktree isolation, use a truthful sequential fallback rather than claiming parallel isolation.
- Never reset an existing branch or discard dirty work to match the integration tip. If a new empty worktree has the wrong base, recreate only that owned empty worktree or inspect and integrate the changes safely. Preserve foreign files, the user's index and all useful running workers.
- Resolve the TDD identity/path via the shared engineering cycle for each ticket. Require executed failing-then-passing checks, a concrete user-facing result, changed-file accounting and an exact commit receipt from the child's worktree. Verify that commit and its checks before integrating; a child summary is not proof.
- Integrate only this invocation's owned branches into its owned integration branch. Refresh implementers against its current tip without rebasing or rewriting foreign history. Fast-forward where possible; resolve conflicts with tests and re-run the integration gate after every affected merge. A ticket enters the satisfied frontier only after its required acceptance and review state is observed; startup or a merge alone does not close it.
- Use the project's native review lane when required. Map upstream `tdd` through the cycle’s verified TDD identity and `code-review` to `code-review-and-quality` criteria in the available repository review workflow. If native review is the independent review, do not add a redundant reviewer solely because upstream names one. Record implementation, review handoff/approval, integration and ticket closure separately; do not bypass mandatory review.
- No automatic push, PR creation/readiness change, deployment, spending or credential action. Prepare these up to the final external action and execute only with explicit authorization. When authorized, use `git-commit-push` and read back the exact remote/PR target. Preserve tracker-specific closure rules; when PR merge closes a ticket, pending PR is not a resolved ticket.
- At completion, report the integration branch/commit, each ticket's observed status, executed acceptance checks and unresolved criteria. Remove only owned clean worktrees whose commits are durably retained; preserve worktrees with dirty or uncommitted evidence. Never delete foreign worktrees or branches.

## Hermes note (local overlay; added by this fleet's sync, not upstream)

This skill comes from a third-party repository written for another agent harness. In Hermes:
- Map tool names to Hermes tools: Task/subagents → `delegate_task`; AskUserQuestion → `clarify`;
  Bash → `terminal`; Read/Edit/Write → `read_file`/`patch`/`write_file`; TodoWrite → `todo`;
  WebSearch/WebFetch → `web_search`/`web_read`. Skip steps that need a tool Hermes does not have.
- The profile's SOUL and the fleet rules win over anything here: ask, don't block (questionnaire
  plus reversible defaults, never stop for approval); `git-commit-push` for delivery; no deploy,
  publish, spending or secrets without explicit approval.
