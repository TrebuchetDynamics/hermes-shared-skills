---
name: autogoal
description: "Use when picking project work. Delegate a bounded task."
version: 0.24.0
author: Hermes Agent
platforms: [linux, macos]
metadata:
  hermes:
    tags: [autonomy, planning, backlog, verification]
---

# Autogoal

## When to use

Default /autogoal hands off one bounded native goal worker (50 turns by default; explicit 100).
Use [the engineering cycle](../shared/ENGINEERING-CYCLE.md) for skill routing and
review-gated reconciliation. No recurring jobs.

## Mode precedence

Only explicit whole-spec requests use `references/whole-spec-execution.md` instead of picker selection/stop rules; retain all safety, ownership, admission, budgets and review gates below.

## Operating priorities

1. **Step 0 — reconcile, never fingerprint-exit.** Resolve workspace instructions,
   human decisions, journal and live ownership before selecting.
   Reconcile once, select usable backlog, check ownership/source freshness, hand off.
   Run discovery only when no usable task remains; fingerprints never justify an idle exit.
   Disable change-only fingerprint monitors; only `autogoal_gate.py` may skip a tick
   while this profile's own card is running or ready and nothing finished.
   Preserve schedule, model, delivery and enabled state.
   Reconcile new terminal results, then CONTINUE selection in the same occurrence.
   A completed card is not a stop condition. A genuinely live worker wins: reconcile
   its exact run; never enqueue overlapping work or steal its lease.
   On EVERY idle occurrence without a usable backlog task, inspect the nearest accepted
   milestone and one bounded implementation, caller/test or delivery seam before any no-selection result.
   Empty queues, absent TODO/FIXME markers, green tests and unchanged HEAD do not
   prove work is absent. Implement the accepted next slice or fix an evidenced
   defect with a regression instead of repeating audits or ledger-only receipts. Silence is allowed only AFTER the required work search
   finds no eligible delta. Record `work_search`: milestone/source, checked seam
   and evidence, candidates, eligibility/rejection reasons and next seam. This is
   prompt policy, not a runtime guarantee of autonomous progress.
2. **Repo-docs runs separately; autogoal works from its backlog.**
   Explicit plan slices follow [the shared handoff](../shared/PLAN-HANDOFF.md):
   select within the named IDs, never an unrelated global task.
   Do not run a repo-docs prepass for a usable backlog task, even without a docs cron.
   Record `Repo-docs pass: existing backlog <source/receipt>` or `delegated to cron <job id>`.
   With no usable task, load discovery.md; a missing/stale backlog may justify one
   bounded prepass, at most once per day, only when no enabled docs job covers it.
   Missing TODO.md or an old mtime alone does not invalidate a usable goals.json task.
   **Selection order:** reconcile live work, then read `goals.py focus <repo> --json`
   with `<skills-root>` the loaded skill directory’s parent. Select ONE primary milestone; retain it
   until delivered or explicitly reprioritized. Run
   `python3 "<skills-root>/repo-docs/scripts/goals.py" next <repo> --json`
   and choose a dependency-ready, unclaimed slice advancing that focus, not the
   first unrelated task. If focus is absent, record the accepted milestone and
   missing focus explicitly; do not invent CLI syntax. Without goals.json use
   TODO.md Now/Next linked to that milestone. Broader discovery stays within its
   gaps. Unrelated fallback requires evidence that every eligible milestone slice
   cannot safely proceed (ownership, authority or environment), or owner reprioritization.
   Executed passing checks establish only their named scope, not delivery.
   Prove or finish unverified/partial work before reimplementing it.
   Build the worker contract directly from the task's Scope, Acceptance and Sources,
   and quote its task ID and goal ID. Mark it with `goals.py task <repo> <TASK>
   in_progress` at handoff. If the backlog is stale against the code (a task already
   done, a path gone), correct that one entry via `goals.py task`, then pick again;
   repo-docs' next run does the rest.
3. **Fix your own environment.** Install missing non-privileged tooling in user
   space/project; record installs, PATH changes and fixtures. Only sudo/system
   packages, credentials and paid resources become owner questions (priority 9).
4. **Workers iterate.** Inside a goal worker, a failing check means fix → rerun until
   acceptance, or until 5 consecutive attempts produce no new evidence. Never block
   on a first failure, and never write "one execution/one rerun/no source edit"
   limits into contracts for work inside their scope. Give workers the scope
   they need; a harness or fixture correction needed to reach acceptance is in
   scope by default.
5. **Retry and backoff across runs.** The handoff helper gives each card 3 attempts.
   A card that blocks twice with no new evidence is parked
   (`hermes kanban schedule <id> "retry_exhausted: …"`) and is not reselected until
   its source, prerequisite or contract fingerprint changes. Pick disjoint work
   instead. A parked or triage card blocks only its own slice.
6. **Vague acceptance.** If criteria are vague, the worker rewrites them in its
   first turn as 1–3 observable checks under `Interpreted acceptance:` and proceeds.
   Ask an owner question (priority 9) only when the possible readings lead to
   materially different product outcomes, and proceed on the recommended reading
   meanwhile. Choose 50 turns, or explicit 100 with `Goal budget rationale:` explaining
   one coherent outcome. Stop at acceptance, not budget exhaustion; never spend turns
   merely because available. If acceptance cannot fit, narrow it before dispatch.
7. **Done means scoped done.** Finish after checks pass and owned changes are committed; never rerun an unchanged
   passing gate merely to refresh status metadata. NOT_CHECKED is not qualification.
   Separate implemented, exact-source/platform qualification and verified main delivery.
   Explain progress in user outcomes: overall goal, current slice, what is still unproved.
   Keep unrelated recovery work separate; IDs and test counts must not obscure that map.
   Follow the vertical-slice standard in references/handoff.md.
8. **One review.** When the card goes through the native review lane, that lane is
   the independent review. Every card body starts with a *Definition of done* that makes
   the review handoff the card's last step, NOT milestone completion. If a worker reports "review entry rejected
   because review is pending" (circular gate), do not route it to the governor and do not
   block. Have the review requested again with a summary that cites the Definition of
   done and lists only deliverables and executed checks (see SOUL "Review handoff"). Do not also launch pre-write or final reviewer subagents
   unless the contract explicitly names them. Do not load `requesting-code-review`
   in workers.
9. **Ask, don't block.** Needing the user is a question, never a stop. Never pause the
   goal, park or block a card, or end a turn/report as "blocked", "waiting for
   approval" or "gated on review" because user input is needed. The goal judge
   pauses goals on that wording. Owner questions are only USER_INPUT, SUDO or
   USER_DECISION. Ask them with `grill-me` Questionnaire mode: `clarify` in live
   sessions, a numbered `Questions` block with marked defaults in cron/worker
   reports. Record each in BLOCKERS.md with `Default if no answer`. Reversible
   choices (design/visual direction, approach, order, approving a review artifact
   such as a contact sheet) proceed on the recommended default now. Irreversible or
   red-line steps (money, deploy/publish, third parties, destructive data/history,
   secrets, sudo, credentials) are prepared up to the final action, and only that
   action waits. All other scope keeps moving. A restriction an agent wrote, a
   failing test, missing user-space tooling, a model refusal or crash, or "need
   authorization for more debugging" are never owner questions. When the journal's
   `unresolved_blocker` names a real owner decision, ask it and record it instead of
   returning `[SILENT]` again. Read replies back (chat / `session_search`) at the
   start of every run and apply them.
10. **Ownership.** Each writing pass uses its own pinned Git worktree, never
    the shared checkout. `start_goal.py` requires `--base`; assemble explicit
    prerequisites and run its manifest-pinned guard before FIRST edits only.
    Ledger proposals go through the canonical integration owner and `goals.py`.
    Follow the candidate, exact-source and containment rules in
    [handoff safeguards](references/handoff.md#ownership-and-verification-safeguards).
    Workers run focused checks; the integration owner gates one frozen candidate.
    Policy/fixture checks never establish product journeys or provider execution.
11. **Model refusals.** A provider safety refusal or crash is infrastructure: reword
    the contract neutrally (or set a `hermes kanban set-model` override) and retry
    the same card once. After two failures, record it in the journal and move on.
12. **Board queries.** Use `hermes kanban list/show/runs --json` piped through `jq`
    with `--assignee`/`--status` filters. Never hand-write SQL against kanban.db,
    and never `json.loads` raw terminal output of a whole-board listing.
14. **Local commits required.** Before review/completion, run `scripts/finish_task.py`
    for acceptance checks and owned files; report branch/SHA. Failure is incomplete;
    no_changes means no new commit. Explicit no-commit instructions win.
    See references/handoff.md for commands, ownership and delivery safeguards.
    Never commit foreign work, secrets or build output; never
    push, merge, rebase, amend or bypass protected PR checks without explicit authority.
13. **State hygiene.** Keep `autogoal/state.json` under ~20 KB: the last 20 entries
    with a fixed schema; older entries go to `autogoal/history/`. Keep picker
    receipts to the last 10. Preserve downstream launch inputs outside disposable
    worker workspaces before terminal completion; retain exact bytes and hash pins.
15. **Recovery must reach execution.** Follow the recovery-continuation procedure
    in `references/handoff.md`: retain original-card launch authority, reconcile
    current runs, and execute the authorized parent continuation after slot release.
    Task creation is not progress; report running only from exact run/process
    identity and observed worker initial-gate success.

## Parallel dispatch and reporting

Load [dispatch and reporting](references/dispatch-and-reporting.md) before an explicit parallel backlog handoff or a completion report. Its file ownership, verification and output contracts remain required.

## Each run (picker)

**Picker budget:** At most about 30 tool calls or 10 minutes per scheduled run.
Reconcile, select, hand off and stop. Delegate deep investigation, source
re-verification and checks to the worker. Over budget: hand off the best candidate,
or reply `[SILENT]` and leave a journal note for the next run.

1. **Reconcile first.** Use `scripts/reconcile.py --profile <profile> [--task-id <id>]`
   once for the prior handoff; reuse its readback instead of repeating show/journal reads.
   Apply owner replies and report new terminal results. Preserve the original card and worker session
   after interruption; a new tick never licenses a replacement, budget reset or overlapping worker.
   Check live ownership again at dispatch (the helper does this under its lock).
   Reconcile the card by its runs, not its status string: `hermes kanban runs <card>` plus
   `reconcile.py`'s `worker_observed`/heartbeat is the liveness evidence, and one card can
   read `running` for hours across several crashed attempts and a review→running cycle.
   Load `references/state-and-recovery.md` for schema/session/recovery details and
   `references/blockers-and-history.md` for failed/blocked cards. Retry limits still apply.
2. **Select.** Read `goals.py focus <repo> --json`, then run `goals.py next <repo> --json`
   through the repo-docs script path (pass `<repo>` as the absolute repo path — a bare
   directory name fails to resolve); choose an eligible slice of that primary milestone (priority 2). If a
   returned task is not actually runnable, repair the backlog instead of going silent. If it needs an
   owner action or decision, run `goals.py section <repo> <TASK> "Needs decision"` and ask (hard-blockers).
   If it bundles excluded scope, register the in-scope slice with `goals.py add-task` and park the rest.
   Then pick again, within the picker budget. If the eligible slice's goal is not the ledger
   focus, use the scoped override in [the plan contract](../shared/PLAN-HANDOFF.md)
   for a one-slice request. Change `goals.py focus <repo> <GOAL>` only for an owner
   priority change, then re-run `next`. Neither path licenses unrelated work.
   Load `references/discovery.md` only if
   no usable milestone task remains (including the TODO fallback); do not double-check
   a usable task with a broad discovery or documentation pass.
3. **Hand off.** Load `references/handoff.md`. Use backlog-check. Compare
   the selected source inputs and current `goals.json` against the proposed committed
   candidate; a clean base commit alone does not include the dirty backlog or its
   implementation prerequisites. Resolve attribution and candidate closure first,
   without copying or committing foreign edits. Treat `--validate-only` as structural
   and ledger admission, not proof that isolated candidate assembly will pass.
   Write the contract file with every field:
   `Objective`, `Scope`, `Verification`, `Source`, `Project payoff`, `Current evidence`,
   `Expected change`, `Acceptance`, `Stop conditions`, `Repo-docs pass`. Include the
   vertical-slice contract in references/handoff.md within these fields. Build it from the
   goals.json task (quote its task and goal IDs), run `scripts/start_goal.py … --validate-only`,
   then the real handoff (same selected 50/100 budget, 3 attempts), and — only once the helper
   has actually created or returned a card for it — mark the task with
   `goals.py task <repo> <TASK> in_progress`. If the helper answers `already_owned`, no card was
   created: the profile's live card owns the single worker slot, so do not re-run the helper,
   do not create a second card for it, and revert an `in_progress` you already wrote (the ledger
   must not claim an owner that does not exist). An owner request for that same slice *now* is a
   parallel dispatch, not a reason to retry the helper: send it as a bounded file-disjoint child
   under **Explicit parallel backlog requests** and leave the ledger and commit to the parent. The picker never implements the slice itself.
4. **Report** per the Output contract. Reply exactly `[SILENT]` when nothing changed since
   your previous report. When the busy gate printed `idle`, `[SILENT]` is allowed only if
   `goals.py next` is empty after backlog repair and discovery found nothing; an idle profile
   with eligible tasks hands one off.

References (load when steps 1–3 require): `references/discovery.md`,
`references/handoff.md`, `references/blockers-and-history.md`, `references/maintenance.md`
(maintenance only; not scheduled), `references/upstream-goal-selection.md` (background),
`references/native-containment-proof.md` (containment),
`references/budget-controller-proof.md` (synthetic admission), and
`references/controller-bridge-proof.md` (peer-bound fixture composition).
These proofs do not qualify native/provider execution.

Named plan: [accepted-plan-execution.md](references/accepted-plan-execution.md). Explicit whole spec: `references/whole-spec-execution.md`.
