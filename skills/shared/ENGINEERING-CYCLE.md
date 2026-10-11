# Repository engineering cycle

Use the existing repo-docs backlog and autogoal executor. This is workflow guidance,
not a scheduler, new database or `/cycle` command. Documentation work alone never
launches autogoal. Only an explicit whole-spec implementation request authorizes
continuation through that accepted scope; default autogoal still hands off one slice.
Design approval alone does not authorize execution. Preserve no-commit, no-push,
no-deploy and other user boundaries throughout; skill defaults cannot expand them.

## Autonomous decisions are the default

Within the user's authorized outcome, decide routine reversible choices yourself:
implementation approach, internal naming, test seams, document structure, supported
metadata repair and dependency-ready ordering within the accepted focus. Inspect
existing conventions and constraints first, choose the smallest sufficient option,
record the reason and verifying check, then act. Do not ask the user to choose
between equivalent engineering options or approve each phase again. An agent's
own plan is not a new approval gate. Missing certainty calls for a bounded source
inspection or discriminating test, not an automatic owner question.

Use this decision order: explicit user/repository constraints → accepted contracts
and existing conventions → evidence from a cheap reversible probe → simplest
compatible implementation. For a consequential choice, compare viable alternatives
and record why the selected one wins. For trivial choices, proceed without creating
an ADR or decision task. Stop investigating once evidence distinguishes the options;
revisit only when a check fails or new evidence changes the choice.

Ask only for a missing fact or decision that materially changes the user's outcome,
conflicts with accepted requirements, crosses ownership/scope, or needs authority
not already granted. Explain the exact missing input, recommend an option and keep
independent work moving. Silence is never permission, review acceptance or evidence.
Routine decisions are made under existing authority, not "approved by default".
Existing explicit authority carries forward; do not request it again. Docs-only
scope stays docs-only, and required independent review and commit gates remain.

Record `Decision: <choice>; Evidence: <source>; Reason: <tradeoff>; Check: <proof>`
in the existing task/plan owner when material. Carry that decision into the worker
contract so it is not re-interviewed. Label inferred product intent as proposed;
never relabel it Accepted merely because the engineering choice is reversible.

## Load the skill needed at the current step

Resolve bundled skills through `hermes-toolset:repo-docs` and
`hermes-toolset:autogoal`, or their actual loaded SKILL.md paths. For addyosmani
skills, inspect the active profile's skill catalog and `skills/.hub/lock.json` to
confirm the installed file and source `addyosmani/agent-skills`. Load by the exact
catalog identity when unambiguous; otherwise read the verified SKILL.md path.
Do not invent an `addyosmani:` namespace or assume the default profile's home.
Record selected identity/path and any unavailable dependency in the handoff.

| Need | Targeted addyosmani skill | Apply to the existing owner |
| --- | --- | --- |
| Missing owner intent that evidence cannot resolve | `interview-me` | Ask only the material owner question; routine engineering decisions use the autonomy rule above. |
| Missing specification | `spec-driven-development` | Reuse the accepted spec/PRD; do not restart accepted design. |
| Changed behavior or architectural decision | `documentation-and-adrs` | Amend affected docs/ADR with observed facts; repo-docs owns backlog reconciliation. |
| Accepted work needs bounded tasks | `planning-and-task-breakdown` | Add dependencies, scope and checks to canonical `goals.json` and root `TODO.md`. |
| A consequential planning assumption needs scrutiny | `doubt-driven-development` | Test the artifact/contract; record corrections and unresolved risks. |
| Implement an eligible slice | `incremental-implementation` | Keep one observable result, owned files and task ID. |
| Changed logic or a bug | `test-driven-development` | Run the repository's discriminating red/green checks. |
| Review an implemented slice | `code-review-and-quality` | Use its review criteria within the required native review lane. |
| Ambiguous new product direction | `idea-refine` | Refine the existing outcome and alternatives; do not reopen accepted scope. |
| Missing or overloaded task context | `context-engineering` | Give the worker only relevant constraints, source, decisions and checks. |
| Quality requirements or a weakened check | `constraint-driven-development` | Bind existing quality requirements to observable checks; no invented owner-approved thresholds. |
| APIs, schemas or module boundaries | `api-and-interface-design` | Specify callers, compatibility, error behavior and contract checks. |
| UI or interaction work | `frontend-ui-engineering` | Plan/build states, accessibility, responsive behavior and relevant interaction checks. |
| Replacing/removing behavior or data formats | `deprecation-and-migration` | Identify consumers, compatibility, transition steps, rollback and migration checks. |
| Build, test automation or packaging boundaries | `ci-cd-and-automation` | Bind the changed boundary to runnable pipeline/build checks. |
| Services, jobs, retries or integration operations | `observability-and-instrumentation` | Define operational questions, useful signals and a verification path; preserve sensitive data. |
| Proven unnecessary complexity | `code-simplification` | Simplify owned code while preserving observable behavior; avoid unrelated cleanup. |
| Owned changes ready to commit | `git-workflow-and-versioning` | Group validated changes; autogoal's finish_task.py/agent_commit.sh remains the commit mechanism. |
| Release or rollout planning in accepted scope | `shipping-and-launch` | Capture readiness and rollback criteria; planning does not itself authorize deployment. |
| Reproduction or failing checks | `debugging-and-error-recovery` | Diagnose before changing code; use the verified fallback below when unavailable. |
| Measured performance requirement | `performance-optimization` | Establish a baseline, target the measured cause and compare the same workload. |
| Trust boundaries or sensitive input | `security-and-hardening` | Trace threats to mitigations and abuse-case checks within the task. |
| Browser behavior needs qualification | `browser-testing-with-devtools` | Exercise the actual journey on the required environment; static checks are not browser proof. |
| External implementation/API behavior is uncertain | `source-driven-development` | Verify authoritative source/contracts before relying on remembered behavior. |

At intake and whenever the work changes phase, match the actual task against this
matrix. Repo-docs planning uses `planning-and-task-breakdown` and
`documentation-and-adrs`, plus spec/constraint/domain skills for evidenced gaps.
Autogoal implementation uses `incremental-implementation`, the relevant domain
skills, `test-driven-development` for behavior changes, and
`code-review-and-quality` plus `git-workflow-and-versioning` at closeout. Reuse
existing accepted specs, plans and quality bars instead of recreating them.

For each relevant skill, read its verified instructions, apply its method and keep
one compact receipt in the existing task/plan: `Skill application: trigger, verified
skill path, decision/artifact, check/result`. Carry planning receipts into the
worker contract; workers add implementation and verification receipts at handoff.
A skill name in a list or a loaded file alone is not evidence of use. Report
unavailable skills with the actual fallback and any remaining coverage gap. Select
by applicability, not an arbitrary quota; reassess after new risks or failures.

Load only relevant skills, not this whole table. Adapt upstream examples such as
`tasks/todo.md`, new spec files and automatic commits to existing owners and
permissions; never create a competing backlog or duplicate accepted tasks.

For repo-docs, apply these skills through
[decisive planning](../repo-docs/references/decisive-planning.md): evidence-backed
Now/Next ordering, bounded bodies and repaired consumer contracts are the outputs.
Record selected skill → changed owner/decision/check; a list of loaded skills does
not establish application. A usable accepted backlog does not need repeated planning.

TDD identity collision: addyosmani's copy may be at
`<profile-home>/skills/test-driven-development/SKILL.md`, while Hermes's bundled
copy resolves as `software-development/test-driven-development`. Verify the former
against the install lock and read that explicit path when bare
`test-driven-development` is ambiguous. If unavailable, disclose the fallback and
load the verified bundled identity; do not claim addyosmani's version was loaded.

If a domain skill is scanner-blocked or unavailable, use verified repository
procedures/checklists for its same obligations and report any missing capability;
do not bypass the scanner or silently omit the risk.
If `debugging-and-error-recovery` is scanner-blocked or unavailable, report that
fact and use an available, verified `systematic-debugging` skill for diagnosis.
If that fallback is also absent, use the repository's documented reproduction and
debugging procedure and report the limitation. Do not install, bypass the scanner,
or waive the same acceptance checks to obtain a supporting skill. Missing required
execution/review capability remains an explicit unresolved gate.

Check referenced support files before claiming to have read them. Per-skill installs
may omit upstream root `references/definition-of-done.md`,
`references/security-checklist.md` or `references/performance-checklist.md` even
when SKILL.md loads. Disclose missing support; use the accepted task's repository
criteria and available project checklists, retaining required security/performance
coverage. Mark unavailable required checks NOT_CHECKED, never pretend they passed.

## One canonical backlog, one executor, one closure owner

1. Repo-docs reconciles accepted requirements into existing goal/task IDs and full
   TODO bodies. Use [plan handoff](PLAN-HANDOFF.md) and its consumer backlog-check;
   drafts, missing acceptance and unresolved dependencies do not become ready work.
   A usable backlog skips another bootstrap or broad audit.
2. For explicitly authorized whole-spec execution, the integration owner reads
   `goals.py next <repo> --json`, restricts selection to accepted IDs, checks live
   ownership and fresh sources, and hands off a dependency-ready slice through
   existing start_goal admission. Use `--ledger-mode proposal --integration-owner
   <owner>` with the existing base, source snapshot, task ID and complete contract.
   Mark in_progress only after actual handoff. No new scheduler or substitute run.
3. The worker loads the relevant verified skills, implements, runs checks and
   updates scoped documentation. It returns task/goal IDs, changed paths, source
   fingerprints, exact checks/results, documentation changes and remaining gaps.
   Proposal workers never mutate canonical goals.json, goal coverage or closure;
   they send receipts to the named integration owner and request required review.
4. The owner verifies implementation evidence and required review acceptance at
   the tested source before closure. Pending/rejected review keeps the task
   in_progress and dependent tasks ineligible; do not encode review as an executed
   test pass. Native review handoff can finish the worker card while canonical
   task closure remains pending. Reconcile that same card, do not redispatch it.
   Check exact integration evidence when the accepted task requires integration.
5. After those gates, the owner uses the bundled `goals.py task <repo> <TASK> done`
   and `goals.py evidence <repo> <GOAL> --kind executed --ref "<actual command>"
   --result pass|fail` for actual check receipts. The helper requires all goal tasks
   done and an executed pass to promote an unmet goal; it does not independently
   verify review, source freshness or truth of caller-supplied evidence.
   Run narrow repo-docs Maintain to reconcile affected docs and task bodies, then
   `goals.py validate <repo>` and `goals.py render <repo>`; use canonical authority
   and revision guards and preserve concurrent edits. Rendering covers only the
   goal table, not implementation docs or TODO task-body status.
6. Re-read `next` and ownership after reconciliation. Continue only inside the
   explicit whole-spec mandate; otherwise report the next eligible slice and stop.
   Exhausted budget, unresolved review/capability or ownership is recorded honestly;
   it never grants broader scope. Report implementation, checks, review, integration
   and delivery separately. Offline fixtures are not native/model execution proof.
