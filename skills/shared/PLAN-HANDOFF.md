# Accepted plan handoff

Keep ideas and unanswered decisions in their existing documentation owner until
accepted. An accepted plan section names its status (`Status: Accepted`), scope,
acceptance and sources. Preserve existing task/goal IDs and completed history.
Repo-docs reconciles accepted work into `goals.json` and complete `TODO.md` task
bodies; rendered goal coverage alone is not an executable task.

Resolve `goals.py` from the sibling repo-docs skill as described in the
[shared contract](COMMON-CONTRACT.md). Use its supported mutations and validate
and render the canonical ledger; preserve concurrency/revision guards. Check the
actual consumer with `backlog-check <repo> --plan path#heading --tasks T1,T2`.
Report its JSON state and exit: `draft_saved` (1),
`backlog_reconciled_not_eligible` (2), or `ready_for_autogoal` (0).
Readiness is not execution authorization or a live ownership check.

Diagnose all check reasons before closing the handoff. When existing owner acceptance
unambiguously covers the section, repo-docs repairs its exact status metadata and
other clerical contract defects in the authorized Maintain pass, then reruns the
same consumer check. Preserve approval evidence, scope exclusions and Proposed
decisions. Missing approval stays draft. See
[decisive planning](../repo-docs/references/decisive-planning.md); never stop at a
repairable `draft_saved` or substitute queue size for an ordered implementation plan.

For an explicit plan slice, select only its named IDs. Reconcile existing workers,
dependencies, current source and primary milestone before handoff. A usable
backlog does not require a fresh documentation prepass. If the named slice differs
from the primary milestone, retain the focus unless the owner reprioritizes it;
use start_goal's existing `--goal-task` and structured `--fallback-file` admission
with fresh source evidence and attributed reasons, as specified in
[autogoal handoff](../autogoal/references/handoff.md). There is no new override
flag and no permission to select an unrelated global task or bypass a refusal.

The worker contract carries the IDs, scope, sources, expected change, acceptance,
verification and stop conditions. Mark in_progress only after confirmed handoff.
Workers implement and check their authorized slice and submit review evidence;
a queued card or review request does not prove execution, approval or delivery.
Apply task/evidence transitions only through the authorized ledger owner and
supported helper. Proposal-mode workers return receipts to the integration owner.
Reconcile affected docs and task bodies against verified outcomes, preserving
remaining milestone gaps. Do not mark unverified work complete.
