---
name: autogoal
description: "Use when picking project work. Delegate a bounded task."
version: 0.23.0
author: Hermes Agent
platforms: [linux, macos]
metadata:
  hermes:
    tags: [autonomy, planning, backlog, verification]
---

# Autogoal

## When to use

Use /autogoal or an explicit autonomous-work request. Select one bounded task in the active profile's authorized workspace. Hand it to Hermes' native persistent goal-mode worker with 50 turns by default (explicit 100 for a coherent larger outcome), enforced by the shipped goal judge/continuation engine—not a prompt-only limit. No recurring jobs are authorized.

## Operating priorities (v0.22 — these override anything later in this file and in references/)

1. **Step 0 — reconcile, never fingerprint-exit.** Resolve workspace instructions,
   current human decisions, journal and live ownership before selecting.
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
   Queue exhaustion, no TODO/FIXME markers, green previous tests and unchanged HEAD
   are not proof that useful work is absent. Prefer implementing an accepted next
   slice or fixing an evidenced defect with regression over repeated audits or
   ledger-only receipts. Silence is allowed only AFTER the required work search
   finds no eligible delta. Record `work_search`: milestone/source, checked seam
   and evidence, candidates, eligibility/rejection reasons and next seam. This is
   prompt policy, not a runtime guarantee of autonomous progress.
2. **Repo-docs runs separately; autogoal works from its backlog.**
   Do not run a repo-docs prepass for a usable backlog task, even without a docs cron.
   Record `Repo-docs pass: existing backlog <source/receipt>` or `delegated to cron <job id>`.
   With no usable task, load discovery.md; a missing/stale backlog may justify one
   bounded prepass, at most once per day, only when no enabled docs job covers it.
   Missing TODO.md or an old mtime alone does not invalidate a usable goals.json task.
   **Selection order:**
   (a) the reconciled live/previous card;
   (b) `python ~/.hermes/shared-skills/repo-docs/scripts/goals.py next <repo> --json`.
       It returns open Now/Next tasks with their dependencies satisfied:
       `unverified`/`partial` goals (prove or finish what exists) first, then
       `unmet` (new work), each in priority order. Take the first that is not
       claimed by a live owner;
   (c) without `goals.json`: TODO.md `Now` tasks linked to unmet/partial goals,
       then other `Now`, then `Next`;
   (d) only if none of these is eligible, the broader discovery in `references/discovery.md`.
   A goal counts as met only with an executed, passing check (the met rule). An
   `unverified` goal's task is to run or add that check, not to reimplement the
   feature.
   Build the worker contract directly from the task's Scope, Acceptance and Sources,
   and quote its task ID and goal ID. Mark it with `goals.py task <repo> <TASK>
   in_progress` at handoff. If the backlog is stale against the code (a task already
   done, a path gone), correct that one entry via `goals.py task`, then pick again;
   repo-docs' next run does the rest.
3. **Fix your own environment.** Missing non-privileged tooling is agent work:
   install it in user space or in the project (venv/uv, project `npm i`,
   `npx playwright install chromium`, `~/.local/bin`, `~/.hermes/tools/`), add PATH
   entries (e.g. `$HOME/.bun/bin`), use `xvfb-run`, and create local fixtures. Record
   what you installed. Only sudo/system packages, credentials and paid resources
   become owner questions (priority 9).
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
7. **Done means done.** When every acceptance item has evidence, complete or
   request review. No extra polishing, suites or re-verification. An item needing
   unavailable infrastructure is reported NOT_CHECKED, and the card still completes
   unless the contract makes that item mandatory.
8. **One review.** When the card goes through the native review lane, that lane is
   the independent review. Every card body starts with a *Definition of done* that makes
   the review handoff the goal's last step. If a worker reports "review entry rejected
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
10. **Ownership.** A whole workspace is owned only by a kanban worker on a card or an
    exact file claim. An interactive session active in the repo (Hermes CLI or Telegram
    chat, a `claude`/`codex` TTY) owns only the files it touched recently: dirty files
    modified in the last 2 hours. Dispatch tasks whose scope is disjoint from those files,
    listing them as exclusions in the contract. Never go silent just because a chat is open. Dirty files that match this
    profile's own completed or approved card diffs are this profile's work: build
    on them and list them in the commit handoff. Do not freeze the repo over them.
    Dirty files older than 2 hours with no live card (in the repo or its submodules) are
    unowned: the daily merge train lands them. A task may overlap them: build on them and
    preserve them, unless an open owner question covers exactly those files.
11. **Model refusals.** A provider safety refusal or crash is infrastructure: reword
    the contract neutrally (or set a `hermes kanban set-model` override) and retry
    the same card once. After two failures, record it in the journal and move on.
12. **Board queries.** Use `hermes kanban list/show/runs --json` piped through `jq`
    with `--assignee`/`--status` filters. Never hand-write SQL against kanban.db,
    and never `json.loads` raw terminal output of a whole-board listing.
14. **Local commits.** After acceptance, use only `scripts/agent_commit.sh` for owned
    files on `agent/<profile>/<card-id>`; see references/handoff.md for exact commands.
    Never commit to main/master/the checked-out branch, never
    push, merge, rebase, amend or force-update a branch you did not create.
    Preserve foreign work; never commit secrets or generated output. The integration
    owner lands a protected PR after required checks, no direct main push or bypass.
    Workers never merge or push. Review/commit alone is not delivery.
13. **State hygiene.** Keep `autogoal/state.json` under ~20 KB: the last 20 entries
    with a fixed schema; older entries go to `autogoal/history/`. Keep picker
    receipts to the last 10.

## Each run (picker)

**Picker budget:** a scheduled picker run spends at most about 30 tool calls or 10 minutes. It reconciles,
selects, hands off and stops. Deep investigation (reading source, re-verifying branches, re-running
checks) belongs to the worker's contract, not the picker. Over budget: hand off the best candidate so
far, or reply `[SILENT]` and leave a one-line note for the next run.

1. **Reconcile first.** Use `scripts/reconcile.py --profile <profile> [--task-id <id>]`
   once for the prior handoff; reuse its readback instead of repeating show/journal reads.
   Apply owner replies and report new terminal results. Preserve the original card and worker session
   after interruption; a new tick never licenses a replacement, budget reset or overlapping worker.
   Check live ownership again at dispatch (the helper does this under its lock).
   Load `references/state-and-recovery.md` for schema/session/recovery details and
   `references/blockers-and-history.md` for failed/blocked cards. Retry limits still apply.
2. **Select.** Run `python ~/.hermes/shared-skills/repo-docs/scripts/goals.py next <repo> --json`
   and take the first eligible task not claimed by a live owner (Operating priority 2). If a
   returned task is not actually runnable, repair the backlog instead of going silent. If it needs an
   owner action or decision, run `goals.py section <repo> <TASK> "Needs decision"` and ask (hard-blockers).
   If it bundles excluded scope, register the in-scope slice with `goals.py add-task` and park the rest.
   Then pick again, within the picker budget. Load `references/discovery.md` only if
   no usable milestone task remains (including the TODO fallback); do not double-check
   a usable task with a broad discovery or documentation pass.
3. **Hand off.** Load `references/handoff.md`. Write the contract file with every field:
   `Objective`, `Scope`, `Verification`, `Source`, `Project payoff`, `Current evidence`,
   `Expected change`, `Acceptance`, `Stop conditions`, `Repo-docs pass`. Build it from the
   goals.json task (quote its task and goal IDs), run `scripts/start_goal.py … --validate-only`,
   then the real handoff (same selected 50/100 budget, 3 attempts), and mark the task with
   `goals.py task <repo> <TASK> in_progress`. The picker never implements the slice itself.
4. **Report** per the Output contract. Reply exactly `[SILENT]` when nothing changed since
   your previous report. When the busy gate printed `idle`, `[SILENT]` is allowed only if
   `goals.py next` is empty after backlog repair and discovery found nothing; an idle profile
   with eligible tasks hands one off.

References (load only when step 1–3 says so): `references/discovery.md`,
`references/handoff.md`, `references/blockers-and-history.md`, `references/maintenance.md`
(skill maintenance only; never in a scheduled run), `references/upstream-goal-selection.md` (background).

## Output contract

Selection: `<task> — source: <path/section or current objective>.`
Completion: objective, changed files/artifact, actual verification result, remaining gap. Keep Telegram receipts short (normally 4–6 lines); report the goal/state, evidence/result, next step and open questions with defaults applied, and any project-required safety/status banner. Do not turn queue-field/hash verification into the main progress story, and never fabricate project gates marked NOT_CHECKED. A queued handoff is expected asynchronous dispatch, not an execution failure; classify it as a dispatch blocker only after inspecting the configured dispatcher and live run/events.
Questions: each open owner question as a numbered multiple-choice item with the default marked, what is already proceeding on that default, and the single step (if any) that waits for the answer. Never report the turn itself as blocked; do not say no eligible goals solely because preferred filenames are missing.
Nothing eligible: `Checked scope exhausted` plus inspected sources/components and evidence that considered candidates are complete, claimed, blocked, or unsupported; do not claim repository-wide completeness from a scoped search.

No skill invocation or queued card alone proves a running goal loop, Telegram delivery, scheduler activation, or completed downstream task. Record the native task ID, selected 50/100-turn budget, and observed queued/running/completed/blocked state in the durable receipt. In the human-facing scheduled summary, translate the observed state plainly and include IDs only when needed for an owner action or diagnosis. This goal worker has its own durable session; it does not set a /goal in the originating Telegram or CLI conversation.
