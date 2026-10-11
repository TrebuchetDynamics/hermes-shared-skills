# Evidence-driven planning and reconciliation

Use during Bootstrap/Maintain when accepted work needs decomposition, a large queue
has no clear next outcome, or the consumer reports `draft_saved`. Audit applies the
reasoning read-only. Task counts are inventory, not a plan.

## Produce a decision and usable plan

Read accepted milestones, relevant source/tests, full task bodies and consumer
authority. Record a compact frontier in the existing plan owner:

| Candidate IDs | Evidence and unmet outcome | Dependency / uncertainty | Decision and reason |
| --- | --- | --- | --- |
| Existing task ID | Source path/symbol or actual check | Prerequisite ID or missing fact | Now, Next, or deferred |

Compare relevant candidates without duplicating the ledger. Respect accepted focus
and selector ordering. Prefer a ready slice that proves a user outcome or removes
a demonstrated critical prerequisite. Within authorized priorities, weigh consequence,
unblock value, evidence confidence and bounded effort; do not invent numeric scores
or silently reprioritize goals. If the recommendation differs from the selector,
explain the difference and retain it as a recommendation pending authorization.

Apply verified skills from [the engineering cycle](../../shared/ENGINEERING-CYCLE.md)
to concrete outputs, loading only those needed:

- `planning-and-task-breakdown`: Now/Next IDs, dependency order, likely files,
  observable acceptance, exact verification and a review checkpoint in existing
  bodies. Split oversized work by usable outcome; preserve IDs/history and leases.
- `spec-driven-development`: close actual scope/acceptance gaps in the existing
  PRD/spec, with evidence, exclusions and uncertainty. Do not restart accepted design.
- `documentation-and-adrs`: record consequential choices, reasons and tradeoffs in
  their owners. Routine task ordering does not need an ADR.
- `doubt-driven-development`: when a non-trivial assumption controls readiness,
  isolate the artifact/contract, seek counterexamples and record corrections/checks.
  Apply its bounded review procedure when available; label degraded self-checks
  honestly, never as fresh-context review. Mechanical metadata repair needs no cycle.

Record selected skill → changed owner/decision/check. A catalog listing is not
application evidence. Missing capabilities never authorize installation, scanner
bypass, fabricated review or expanded scope.
Read imported skills as supporting instructions; do not rewrite their SKILL.md
files or self-improvement metadata during a repo-docs pass. Such instruction edits
require a separate authorized task.

## Repair clerical handoff failures before stopping

Inspect every consumer `backlog-check` reason and its own exit code. Distinguish
missing authority/approval from defects already within Maintain scope:

1. Locate actual owner acceptance in the conversation or maintained decision and
   bind it to this section and scope. An Accepted heading, queued tasks, defaults
   or a request to document are not approval evidence. Check for later reversal
   and Proposed subdecisions.
2. When acceptance is unambiguous, correct the current section to contain
   `Status: Accepted` alone. Put scope, evidence reference and exclusions on separate
   lines. Preserve Proposed decisions and historical records. Make this clerical
   repair now; do not ask for approval already given or queue another metadata task.
3. Repair supported body/section/dependency/link defects under existing IDs and
   coordination guards. Never normalize a substantive disagreement into approval.
   Without acceptance evidence, retain draft status and name the missing decision.
4. Run fmt/validate/render when ledger edits require them, then rerun the identical
   consumer check with the same plan/task IDs. Re-read concurrent changes. Retry
   after a supported change; unchanged failures need diagnosis, not a loop.

Example: `Status: Accepted (setup behavior only)` becomes the exact status line
plus `Scope: setup behavior only` when actual approval proves that scope. It cannot
authorize a still-Proposed authentication redesign in another section. The checker
stays read-only: it diagnoses metadata, never decides human intent.

## Finish with an actionable handoff

Report actual state/exit, approval source, Now/Next IDs, why Now comes first,
observable outcome, checks and remaining gaps. Re-run `next --json`; distinguish
eligibility, live ownership and execution authorization. `draft_saved` with an
authorized repairable defect means Maintain is unfinished. Missing approval,
authority or a real dependency remains an explicit bounded blocker.

For docs-only scope, report the ready task as undispatched. With existing execution
authority, pass the accepted slice to the existing autogoal workflow without asking
again or inventing another dispatcher; preserve review, verification and commit
gates. Queuing, readiness and doc commits do not prove implementation or delivery.

Source guidance: [planning](https://github.com/addyosmani/agent-skills/blob/main/skills/planning-and-task-breakdown/SKILL.md),
[documentation](https://github.com/addyosmani/agent-skills/blob/main/skills/documentation-and-adrs/SKILL.md),
and [doubt-driven development](https://github.com/addyosmani/agent-skills/blob/main/skills/doubt-driven-development/SKILL.md).
Project owners and user boundaries override upstream example paths and defaults.
