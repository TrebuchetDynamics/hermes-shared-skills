# Autogoal — Discovery, ranking and selection

Load when `goals.py next` returns nothing eligible, the repository has no `goals.json`, or this profile has no `repo-docs` cron job (then the repo-docs prepass section applies). The Operating priorities in SKILL.md override anything here.

## Start with a bounded repo-docs pass

For a project workspace without a scheduled `repo-docs` job (Operating priority 2),
the first project stage is a `repo-docs` pass, before building or ranking the goal
shortlist. With such a job, skip this section and work from its TODO.md. First resolve the active workspace, read
repository instructions and explicit task boundaries, and check live ownership.
These safety checks do not replace the documentation pass. Load the active
profile's `repo-docs` skill and its STE-inspired reference with `skill_view` and
apply them in this run. Merely mentioning the command, finding TODO.md, or
printing `/repo_docs` is not execution. Do not spawn a separate picker, invoke a
recursive autogoal, or enqueue another worker for this prerequisite.

Use Maintain by default. Use bounded Bootstrap only for missing, applicable docs
with current supporting evidence. This autogoal request authorizes small,
evidence-backed documentation and TODO reconciliation in the prepass; it does
not authorize implementation, generated-contract edits, upstream changes,
repository-agent-instruction changes, broad stylistic rewrites or new product
requirements. Fix an ordinary supported doc mismatch now instead of deferring it
merely to populate the goal queue. Preserve STE literal/meaning safeguards,
accepted decisions, existing task IDs, uncommitted work and authoritative tracker
links. Do not create every default document, empty scaffolds or filler tasks.

When any live worker/cron owns the affected workspace or instructions require
read-only work, perform an Audit pass only. Do not write shared TODO/docs or
claim ownership. Reconcile the live task instead of launching another. A terminal
blocked card still blocks only its slice and dependencies; its exclusions and
owned files remain binding. Missing repo-docs is a prerequisite blocker: disclose
it rather than silently pretending the pass ran or installing another profile's
skills. The default manager's Hermes configuration directory is not a product
repo: record `not_applicable_manager` with the actual boundary, do not bootstrap
README/TODO there, and retain supported skill-maintenance capability checks.

Keep the pass cheap and useful. Inspect the nearest accepted milestone, its
README/plan/spec/runbook or API owner, the current queue and implicated source,
tests and manifests. Follow relevant links. Every occurrence checks live ownership
and continuity. If a prior scoped pass has unchanged relevant source/doc
fingerprints, task status and prerequisites, do a lightweight revalidation and
reuse its receipt with an explicit reason. New relevant changes, missing prior
coverage or contrary evidence require a fresh scoped pass. A HEAD match alone
cannot prove a dirty tree is unchanged. Do not perform a full documentation
inventory, build, browser run, broad suite, date bump or rewrite every hour.

Record a profile-local `repo_docs_pass` receipt in the autogoal journal: mode,
workspace, checked paths/symbols and scoped source fingerprints, actual changes
and checks, findings/unknowns, ownership, TODO/tracker handoff and next eligible
candidates. Read back edited docs and check their affected links/contracts. A
no-change pass is valid when supported by inspection, not an excuse to invent
work. Then compare meaningful docs, bug, delivery, refactor and architecture
candidates using the remaining policy. Documentation is not automatically the
winning goal, and a TODO entry is not execution permission. Do not select a doc
repair that the prepass already completed.

Every new worker contract includes `Repo-docs pass:` with the actual mode and
receipt/evidence pointer. Both CLI and native-tool handoffs require it. The helper
checks structural presence, not whether the pass truly occurred; the picker must
verify its evidence. If the prepass delivered useful docs but no eligible goal
remains, report that documentation result rather than silently discarding it or
claiming a worker started. Unchanged no-op reporting remains silent under cron.

## Discover the real work source

1. Resolve the active workspace and any explicit user source or objective. An explicit source wins; never override it with a different backlog. Preserve current thread decisions, ownership, approved plans, and unfinished work. The default profile's Hermes configuration directory is not an implicit coding project.
2. Inspect repository instructions, git status, README/context, and current task/goal ledgers before choosing. Missing BACKLOG.md or TODO.md is not a stop condition. Run the bundled read-only helper with `terminal`: `python <this-skill-directory>/scripts/discover_sources.py <absolute-workspace>`. Use its paths as leads, not authoritative task status. Pass repeatable `--exclude <root-relative-directory>` for established upstream/reference-only boundaries; exclude the reference/upstream directories the profile's SOUL names (e.g. vendored upstream checkouts) from goal-source discovery. They may still be read deliberately as parity references, never treated as editable project backlogs.
3. Search in this order: current thread's accepted objective and referenced plan; live project tracker/goal/ownership ledger explicitly used by the repository; root BACKLOG/TODO/TASKS/ROADMAP/PLAN/GOALS and CONTEXT/STATUS/README pointers; component-level backlog/roadmap; current linked docs/plans, docs/product, docs/quality, and equivalent project directories. Follow the selected current documents' links and acceptance evidence. Read only the small relevant set; do not recursively ingest the whole repository.
4. Prefer explicit Now/Next, in-progress, unblocked, unresolved, failed-gate, and acceptance criteria sections over historical dates or unchecked boxes. Treat completed/archived/superseded plans as historical until live evidence proves otherwise. Verify named paths, implementation, tests, and known receipts. A stale unchecked box is not a new task. A recently modified document is not proof of priority. If the repo uses a board, inspect its current state with the available approved read tooling; do not create/claim/move tickets merely because a document mentions them.
5. If no usable project queue exists, select a concrete defect or missing validation already evidenced by current logs, tests, the user's request, or documented requirements. A bounded investigation or regression reproduction is useful work if its output and success signal are clear. Do not invent features, manufacture failures, expand product scope, or perform broad speculative cleanup. If no evidence-backed candidate remains, report the sources checked and the exact missing decision/source instead of a bare filename complaint.

### Consume the repo-docs handoff

When `repo-docs` maintains a root `TODO.md`, use its evidence-backed `Now` and
`Next` items as candidates, not automatic execution permission. Prefer tasks
linked (`Goal: <id>`) to partial or unmet milestone goals in its `Goal coverage`
table. When you finish a slice, update that goal's row and its task status, so the
next run sees the goal move. Follow each item's
source, scope, project payoff, acceptance check, dependencies, and ownership; verify
these against current repository state before selecting. Skip `Done`, proposed or
unapproved work, and `Blocked / Needs decision` items until their actual gate is
resolved. Preserve task IDs and authoritative tracker links rather than copying the
queue into a competing ledger. A standalone bare `/repo_docs` (or the profile's
`repo-docs` cron job) maintains docs and this handoff. `/autogoal` runs the bounded
repo-docs pass above only when Operating priority 2 says no repo-docs job covers the
repository, then selects only one remaining eligible slice under its existing
goal-worker contract. Do not manufacture tasks
when no supported candidate exists.

## Escape an exhausted shortlist without escaping authority

On EVERY idle occurrence, including after terminal-result reconciliation, do not
infer repository-wide absence of work from unchanged fingerprints of an exhausted
candidate set. Do not wait for two consecutive no-selection receipts to explore.
A fingerprint revalidates inspected bytes, not discovery completeness. Refresh
current interactive/worker ownership from actual latest receipts and live claims;
a past ownership note is not a permanent lease, but dirty work remains preserved.
If ownership prevents mutations, keep exploration read-only and resource-disjoint.

Perform one bounded exploration pass in a DIFFERENT authorized component of the
nearest accepted milestone: inspect one or two implicated source/caller/test seams
using existing discovery/engineering-signals tools, then nominate at most a few
concrete defects, missing acceptance surfaces or reversible prerequisites. Record
which new component was checked, its evidence/fingerprint, candidate eligibility
and why it does or does not share the old gate. Do not repeat this exploration on
unchanged component evidence; alternate only when a distinct accepted seam exists.
Rotate the next inspected seam across authorized components recorded in `work_search`;
if all seams were previously inspected, revalidate one relevant caller/test or
accepted delivery criterion rather than claiming unchanged evidence permits no
search. Do not repeat an unchanged broad audit. No exhaustive scan, broad suite, fabricated task, product expansion, lease theft,
upstream edit or gate waiver is authorized. Ordinary implementation details are not
a product decision; explicit compatibility/security/financial/live/scope gates stay.

A missing user-space prerequisite is provisioned by the agent under standing
authorization (Operating priority 3), but its existence is not product acceptance.
Keep installations separate from project implementation and retain actual smoke/
review requirements. Do not substitute a new equivalent card for a blocked one.
If no concrete eligible delta emerges, report `Checked scope exhausted` with the
checked components and exact remaining decision/ownership gate, not a claim that
the whole repository has no useful work. Under cron, unchanged no-op still returns
exactly `[SILENT]`. This is selector guidance, not an enforced runtime guarantee.

## Build a project-progress shortlist

Discover work in the repository, not only in its queue. Start with a one-sentence project outcome and its nearest unfinished milestone from current user decisions, README, roadmap, and accepted architecture. Build a bounded shortlist (normally 3–5 candidates across at least two relevant work classes when evidence exists); do not take the first unchecked box or manufacture candidates to fill a quota. Inspect one small implicated implementation/test surface per serious candidate. Record candidates, current evidence, eligibility, expected improvement, verification, and why the winner beats the alternatives in the profile journal; send only the winner and its project payoff to Telegram. Include at least one evidence-backed docs/refactor/architecture alternative when relevant, not just several differently worded tests of the same gate. For each serious alternative identify the implicated current code/docs paths and the specific milestone/user/developer cost it changes. Avoid broad source scans or a category quota when one explicit urgent objective dominates.

Look for these work classes within authorized project code/docs:
- Bugs/reliability: reproduce a documented failure, broken user flow, incorrect result, lifecycle/race/cancellation/error-path defect, or missing regression for a previously fixed bug. Check the actual failing surface; prioritize an in-scope fix plus regression over another bughunt when the root cause and expected behavior are established.
- Delivery: implement the next accepted feature/parity slice or remove a demonstrated prerequisite blocking an existing milestone. Prefer a usable vertical slice with an executable acceptance check, not another plan about a plan.
- Documentation/developer experience: repair an inaccurate setup command, missing API/operational contract, stale architecture explanation, or troubleshooting gap tied to an observed developer/user failure. Verify commands/links against current implementation. Cosmetic wording, routine status churn, and rewriting correct docs are low-value.
- Refactoring/maintainability: remove demonstrated duplication, tangled responsibilities, fragile dependency seams, or repeated change hotspots that make the next accepted feature or repair harder. Show concrete call sites/change history or reproduction and name the downstream work it enables. File length, TODO counts, or a preference for cleaner style alone do not justify it. Preserve behavior with characterization/regression checks before a small extraction.
- Architecture/performance: isolate one evidenced boundary/coupling problem, lifecycle ownership defect, API/data contract mismatch, or measured bottleneck. Choose a reversible seam/adapter/invariant fix that improves a named user flow or unblocker. For an uncertain cross-module redesign, do a bounded measured spike/ADR with a decision and prototype/test rather than rewriting the system or drafting an ungrounded grand design.

Read manifests/build scripts, CI definitions, relevant recent changes and tests as needed. When the existing queue offers no useful disjoint work or the shortlist is only repeated audit/verification tasks, select one or two authorized implementation directories from the current milestone and run `python <this-skill-directory>/scripts/engineering_signals.py <workspace> --path <component-source-directory> [--path <another-directory>]` through terminal. This read-only helper never imports/runs code; it reports source-comment markers and the largest modules with explicit scan/omission limits, no raw source snippets. Follow up a few leads with `read_file`/`search_files`, actual callers, tests and relevant change history. Do not scan the whole multi-repo tree, datasets, credentials, generated code, upstreams or reference corpora. File length alone never licenses extraction; show a real responsibility/duplication/change-friction problem. Generated-sourced catalogs and data tables can be large without architectural debt; trace the generator/provenance rather than propose manually refactoring emitted data. Read-only reports still require permission, join-cardinality, temporal and history semantics checks: do not infer link access or coverage from labels/latest records alone. Missing markers do not mean no useful work exists. For bugs and refactors, link code evidence to the existing behavior contract; for docs, link a misleading command/contract to actual current implementation. Source discovery is not a replacement for session recovery or live ownership.

Search bounded source locations for TODO/FIXME/unimplemented branches and swallowed errors using `search_files`. Treat these as leads, never as confirmed bugs. Never run unsafe broad test collection, production probes, fitting/training, or costly suites just to discover work. Old audits and retired plans only nominate hypotheses that current code must confirm.

## Cheap discovery, explicit progress, and native evidence

Select before running a broad baseline. During the picker, read the nearest milestone, a few implicated sources/callers/tests, live ownership, and existing receipts. If a suspected defect needs execution to establish eligibility, run only its safe focused reproduction. A clean 931-test suite before selecting a contract does not identify the best task; defer expensive baseline/full-suite/browser/build checks to the goal worker when the chosen diff or acceptance contract requires them. Do not rerun predecessor suites on unchanged source merely to furnish a new picker receipt.

For each serious candidate record one concrete before/after delta. A bug changes a reproduced wrong result/lifecycle into the contracted behavior; docs correct a proved workflow/API/architecture mismatch; a refactor removes a demonstrated dependency/duplication hotspot and names its next enabled change; an architecture slice restores a specific ownership/boundary invariant with a characterization check. For an investigation, state the unresolved question and the executable reproducer, measurement or decision it will deliver, including what the result will allow next. If known scope and root cause permit an authorized fix, choose fix plus regression rather than another investigation. Do not dress an unchanged successful audit as delivery.

The upstream goal judge consumes the latest response against the title/body. Native completion, blocking and review states terminate the loop; a judge is not a runtime test or independent review. Before completion, workers include `Acceptance evidence:` mapping every criterion to the artifact and actual command/result or inspected contract plus scoped source fingerprint/revision; distinguish delivered change from checks, and preserve NOT_CHECKED ceilings. Require independent review only when the existing project/card contract requires it; never create reviewers or relax review gates implicitly.

The installed verify-on-stop guard uses per-session/workspace evidence and marks evidence stale after later edits. A narrow command might not be recognized as canonical evidence; a successor session does not inherit the previous session ledger merely because its source hashes match. Diagnose recognition/freshness rather than claiming an upstream verifier bug or disabling the guard. Honor required canonical checks or the host's bounded ad-hoc check, retaining honest coverage; never forge ledger records. Upstream source-study notes and stable source pointers are in [references/upstream-goal-selection.md](references/upstream-goal-selection.md). Treat version-specific facts as observations, not support promises for every installation.

## Rank by real project contribution

Honor explicit priorities, locked gates, accepted contracts, and live ownership first. Reject completed, unchanged-repeat, unsupported, conflicting, unauthorized, or unverifiable candidates before ranking. Compare eligible candidates by: (1) severity/user impact and contribution to the nearest accepted milestone; (2) dependency unblock leverage; (3) strength of current evidence; (4) feasibility of a meaningful verified slice within 50 goal turns; (5) change risk, review burden, and resources. This is a reasoned comparison, not invented numerical precision. A small high-leverage doc/contract fix can beat a speculative code rewrite; a real broken flow normally beats cosmetic docs/refactoring. Do not rotate categories mechanically or always choose the easiest green check.

Every selection must answer: What currently hurts or is missing? Who/which milestone benefits? What becomes possible or reliable after this change? What exact artifact/check demonstrates that improvement? Prefer implementation plus focused verification when safe and within scope; investigation-only needs a specific uncertainty and decision/reproducer it will resolve. Architecture/refactor success must remove a demonstrated coupling, duplication, ownership, or change-friction problem while preserving the contract—not just produce an ADR. Documentation success must enable a real workflow or correct a proven contract/setup mismatch. When accumulating uncommitted slices, preserve all predecessor diffs, group changes into reviewable receipts, and record the agent branch/sha from Operating priority 14 rather than repeatedly consuming full-suite budget; never commit to the checked-out or default branch. After a clean bughunt, reconcile its result and advance to the next accepted gate or a distinct valuable task—do not hunt indefinitely on the same cleared surface without new evidence. If all milestone-critical work is owner-blocked, choose disjoint useful documentation/debt work only when it has a concrete project payoff; otherwise report the genuine gate.

## Select one useful slice

Prefer eligible P0/critical work, then the active accepted objective's next dependency-ready slice, then explicitly ranked Now/Next work, then a reproduced defect or missing acceptance check. Use documented age/source order only to break ties. Skip work with unmet dependencies or unresolved irreversible/product/security decisions; keep looking for another useful bounded candidate before stopping.

When writing a verification contract, explicitly decide whether a minimal test-harness prerequisite correction is included (for example a login-label selector) and bound its files, isolation, ownership and invariant-preserving check. Do not weaken assertions or infer permission to expand an existing assertion-only contract; that existing card requires a scope decision before repairing an excluded shared helper. This avoids both avoidable future harness dead-ends and unauthorized scope expansion.

Broad roadmap milestones should become one measurable next slice, not be rejected solely for being broad. Derive verification from the documented requirement and existing test/build harness. If a feature is already implemented but unaccepted, reproduce its exact missing acceptance check; do not reimplement it or waive its gate. Investigation must produce evidence, a scoped reproduction, or a useful decision artifact, not just read files and announce uncertainty.

Choose ordinary reversible engineering details autonomously using repository conventions, existing APIs, tests, and safe defaults. Missing implementation detail is not automatically a product decision: a thumbnail capture/storage choice can follow an existing rendering and persistence pattern. Ask (questionnaire, never a stop) only for an owner decision that materially changes authorization, compatibility, security, irreversible behavior, or intended product outcome. Never invent a numeric compatibility limit without measurements or a contract; measure/reproduce the uncertainty as the bounded task where possible.

Inspect dirty-file ownership and active work claims. A dirty tree is not a blanket blocker (see Operating priority 10 for this profile's own leftover work): choose a disjoint task, a read-only validation, or a missing test that does not race another owner. Do not overwrite another worker, duplicate a claimed slice, or treat already-running goal/cron work as available. Preserve workspace and upstream boundaries; for Wing, Hermes Agent/Desktop/Conduit stay unmodified and changes belong only in the authorized Wing/Wing Link boundaries.

State the selection in one line with its source. Define every progress-contract field below before activating the native goal execution stage. The budget is 50 goal turns, explicitly supplied to the native worker, not 20 or 12. Goal turns can contain many tool calls; they are not tool-call iterations. Stop early when complete, review-required, or genuinely blocked.
