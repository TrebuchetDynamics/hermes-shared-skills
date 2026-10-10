## Explicit parallel backlog requests

When the owner explicitly asks for subagents to accelerate backlog implementation,
use parallel bounded implementation contracts rather than serial audit-only passes.
This overrides the scheduled picker's single-dispatch default for that request only;
do not change recurring cadence or replace existing live workers.

1. Reconcile live ownership, dependency readiness and the accepted milestone. Select
   independently editable implementation slices; claim exact files and exclusions.
2. Assign shared contracts, generated files and dependency edits to one producer.
   Agree on interface symbols and public-control test IDs before dispatching consumers.
3. If a downstream qualification task depends on unfinished production work, delegate
   only independent executable fixture/harness preparation. Keep its dependency and
   open status intact; harness readiness is not platform qualification.
4. Give the parent integration and ledger ownership. Children return attributed changes
   and exact executed checks; the parent verifies a coherent candidate before completion.
   Compare returned file hashes to the integrated files, then run the union of affected
   test targets once with duplicates removed. Do not add child pass counts when suites
   overlap: only the combined run establishes a combined total. Use each harness's
   recorded interpreter and environment for rechecks; a bare interpreter can exercise
   different dependencies than the worker's tested environment.
   Report running work as running, not delivered, and preserve named native gaps.
   Use the integration recipe in references/handoff.md for completion reconciliation.

## Output contract

Report the primary milestone, merged user outcomes, qualification boundaries and
remaining milestone gaps, recurring failure causes and actual verification cost;
unknown usage is unknown. Card counts do not prove product progress.

Selection: record `<task> — source: <path/section or current objective>` in the durable receipt. Tell the user the intended outcome in ordinary language and whether it is queued or actually running, per `../extras/cron/reporting.md`.
Completion: objective, changed files/artifact, actual verification result, remaining gap. Human-facing scheduled reports follow `../extras/cron/reporting.md`: lead with the project name and useful change, normally 3–5 short lines covering actual results and what happens next. Keep internal IDs, source references, execution budgets and routine safety/default boilerplate in durable receipts. Omit empty Questions sections. Preserve material uncertainty, real owner questions and required project safety warnings; never fabricate project gates marked NOT_CHECKED. A queued handoff is expected asynchronous dispatch, not an execution failure; classify it as a dispatch blocker only after inspecting the configured dispatcher and live run/events.
Questions: each open owner question as a numbered multiple-choice item with the default marked, what is already proceeding on that default, and the single step (if any) that waits for the answer. Never report the turn itself as blocked; do not say no eligible goals solely because preferred filenames are missing.
Nothing eligible: `Checked scope exhausted` plus inspected sources/components and evidence that considered candidates are complete, claimed, blocked, or unsupported; do not claim repository-wide completeness from a scoped search.

No skill invocation or queued card alone proves a running goal loop, Telegram delivery, scheduler activation, or completed downstream task. Record the native task ID, selected 50/100-turn budget, and observed queued/running/completed/blocked state in the durable receipt. In the human-facing scheduled summary, translate the observed state plainly and include IDs only when needed for an owner action or diagnosis. This goal worker has its own durable session; it does not set a /goal in the originating Telegram or CLI conversation.
