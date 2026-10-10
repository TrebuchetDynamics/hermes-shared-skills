# Autogoal — Handoff, review and worker execution

## Recovery continuation boundary

Put authorized lifecycle/launch ownership in
the original card body, not only comments: the judge evaluates its contract.
Keep recovery review separate from product acceptance; after actual slot release,
execute the accepted parent continuation in the same reconciliation. Do not count
routing, task creation or repeated inspection as product progress. Read current
board/runs on notifications; never recreate an existing graph. Report running
only with exact card/run/process identity and observed worker initial-gate success.
Follow the recovery-continuation procedure in `references/handoff.md`.

## Main-only repositories and native evidence communication

A repository's accepted main-only policy never licenses bypassing the isolated
worktree guards. `pass_workspace.py --mode main-only` deliberately refuses
native admission: the installed dispatcher has no common-repository hook spanning
workspace setup, goal startup and the complete worker lifecycle. Do not dispatch
canonical writers, create branch/worktree substitutes, or treat a launch-only
flock or prompt preflight as serialization. Default `isolated` behavior is unchanged.
`prepare_main_only` creates a read-only filesystem snapshot from explicit,
committed byte-matched inputs including the eligible task's exact ledger and
explicit dependency closure; it never copies credentials or a dirty union.
`run_main_only` proves cooperative synchronous OS-lock lifecycle in fixtures;
its trusted ownership callback has no installed all-board native adapter. It is
not native admission, a sandbox, candidate qualification or deployment authority.

Reuse existing native tasks for evidence communication. From an already claimed
native task worker, using the installed native Python import environment:

```sh
<native-python> <this-skill-directory>/scripts/native_lifecycle.py handoff \
  --db <existing-native-board-db> --payload '<JSON>'
<native-python> <this-skill-directory>/scripts/native_lifecycle.py ack \
  --db <same-existing-native-board-db> --payload '<JSON>'
```

Handoff JSON has exactly `task_id` (existing recipient task), `source_sha`
(current full source commit), `input_hashes` (explicit root-relative filename to
SHA256), `scope`, nonempty `acceptance` string list, and `evidence` (safe reference).
The helper derives sender and recipient from native ownership, binds both task
contracts, checks actual source-task workspace bytes and returns a stable
`handoff_id` with exact committed comment readback. Ack JSON has exactly `task_id`,
`handoff_id`, the same `source_sha`/`input_hashes`, `state`
(`adopted`, `rejected`, or `needs-reproduction`), and `evidence`.
Only the actual current recipient task worker may acknowledge. Authentication
checks Linux ancestor PID/start fingerprint, current native run, lease and original
ancestor board/claim environment; copied CLI/profile/author labels are not identity.
Unclaimed chat/cron/manager callers, unsupported OS/runtime or unreadable ancestry
fail closed. A hostile same-UID actor who can rewrite the native board is outside
this local trust boundary. Duplicate, stale, malformed or conflicting events
refuse without changing task scope/ownership. Do not put secrets, absolute private
paths or transcript instructions in comments. Posting/acknowledgment is communication
only, never execution, defect reproduction, implementation adoption or delivery.
A read-only researcher may communicate source-only hypotheses within its existing
task authority, not gain configuration, source-write, test, push or deploy rights.
When no authenticated native worker origin exists, prepare a private handoff and
report acknowledgment unobserved; do not fabricate a claimed sender.

Offline core tests run in `make check`. Native comment/identity fixtures additionally
require `HERMES_NATIVE_HANDOFF_TEST=1` and installed native imports when explicitly
running `test_native_handoff.py`; they use private isolated native databases and
real fixture OS processes, never provider execution or a live product board.

## Explicit worker ledger and publication roles

`start_goal.py` defaults remain worker-local ledger closure and no worker push.
For an implementation-only lane whose canonical ledger belongs to a sole owner,
pass `--ledger-mode proposal --integration-owner <owner-profile>`: the worker
body asks only for task/goal/source/check proposals through the existing task and
contains no automatic `goals.py task/evidence/render` closure instruction.
Existing cards retain their original roles; flags never migrate or broaden them.

Optional `--publication-authority <private-owner-evidence.json>` requires proposal
mode and a matching integration owner. JSON has exactly `version: 1`, absolute
`workspace`, exact worker `profile`, `goal_task`, `contract_sha256` (SHA256 of the
stripped contract used by the helper), `remote` (an existing named remote, not a
URL), `ref` (exactly `refs/heads/agent/<profile>/<goal_task>`), `owner`, and nonempty
`evidence_ref`. All workspace/profile/task/contract bindings must match. No main,
other refs, wildcard, force/delete, merge, deploy or non-task publication is
licensed. The resulting contract permits only `git push <remote> HEAD:<exact-ref>`
after owned acceptance/commit and exact remote readback. This validates explicit
caller-supplied owner evidence, not independent permission or runtime enforcement;
current repository/host authority still applies. The helper itself performs no
publication. A parent router must explicitly forward these flags after its own
gates; adding them to shared code does not change any profile/router or authorize
live product handoff. `--validate-only` reports selected roles without dispatch.

## Ownership and verification safeguards

Each writing pass uses its own pinned Git worktree, never
the shared checkout. `start_goal.py` requires `--base`; explicit prerequisites
assemble the candidate. Run its manifest-pinned worker-start guard before the
FIRST edits, not again after authorized implementation changes. For same-card
review rework, verify the prior initial-gate result and exact attributed
implementation inputs with a pinned re-entry check; put that lifecycle in the
original card body before returning it to implementation. Preserve the original
manifest, refusal checks, acceptance and attempt budget. Never treat the worker's
own verified edits as foreign dirt or ask the owner to approve routine re-entry.
Follow the review-rework recipe in references/handoff.md; card instructions alone
are not an automatic runtime hook or filesystem sandbox.
An assigned cwd cannot prevent absolute-path writes by a noncooperative worker.
Ledger writes go to the canonical integration owner through `goals.py` locking
and revision checks. A temporary index alone does not isolate edits or tests.
Preserve foreign leases; see references/handoff.md. Workers run focused checks;
the integration owner runs one broader frozen-candidate gate.
Follow the coherent integration-candidate checks in references/handoff.md;
never verify a moving source tree or weaken refusal tests.
Reuse checks only while source, dependencies and environment match; receipt-only
edits do not invalidate behavior checks. Policy tests prove orchestration rules,
not product journeys; report the gates separately. For native/model-backed
checks, require externally enforced spending and descendant limits; turn caps,
cost accounting and CLI process-group cleanup alone do not enforce them.
Synthetic reservation units qualify admission logic only; real spending requires
vetted provider charge bounds and complete controller-bound request routing.


Load on every run that hands a slice to a worker, before writing the contract. The Operating priorities in SKILL.md override anything here.

## Vertical-slice contract and delivery standard

Read `python ~/.hermes/shared-skills/repo-docs/scripts/goals.py focus <repo> --json`
before selecting. Keep one primary milestone and its observable user outcome in
`Objective`/`Project payoff`; quote the focus, goal and task IDs in `Source`.
Choose a bounded end-to-end workflow advancing that milestone, not disconnected
file changes. Keep the helper's existing required top-level fields; put these
details inside them (no additional contract fields are required):

- `Scope`/`Expected change`: workflow entry, implementation through its actual
  platform/backend, usable result, owned files/resources and explicit exclusions.
- `Acceptance`: observable success AND failure/recovery behavior, regression and
  QA checks, remaining milestone gaps and the next slice. Missing required live
  or platform checks remain gaps, even if this card's narrower acceptance passes.
- `Verification`: exact commands, source SHA or immutable snapshot (including
  dirty-file hashes), dependency/lockfile state, environment, platform/backend,
  fixtures vs live data, results and evidence paths. Fixture != live;
  Chromium != Android. Never substitute either for the requested target.
- `Stop conditions`: worker implementation/checks and review handoff finish the
  CARD, not the product milestone. Name the integration owner and remaining
  qualification/PR/merge gates; retain the selected 50/100-turn budget and 3 attempts.

Report three distinct states: **implemented** means the scoped artifact exists;
**qualified** means checks passed on a named platform/backend against exact
source; **delivered** means the qualified outcome is verified merged into main.
Read back the merged PR and main commit/reachable source before claiming delivery.
Neither a fixture pass, local commit, review handoff nor a passing isolated branch
proves a usable milestone delivered on main.

Claim files and give each new write worker an isolated Git worktree. Preserve
and attribute dirty edits; age never authorizes including another owner's work.
Workers run focused tests. One integration owner assembles the candidate, freezes
its exact source/dependencies/environment and runs the broader acceptance gate once.
Rerun only affected checks after a relevant change, not after receipt-only edits.
Coordinate heavy jobs/resource leases instead of duplicate concurrent full suites.
Reuse evidence only for the exact source/dependencies/environment and relevant
check inputs; invalidate affected checks after changes, not all checks reflexively.
Record commands, duration, repeated failures and verification cost (actual tool or
usage receipts; unknown cost is unknown, not zero). Run only required PR checks
for landing; no optional-suite treadmill. Land through a protected PR with required
checks satisfied; no direct main pushes, admin override or protection bypass.

Product receipts/reporting retain the primary milestone, merged user outcomes,
qualification boundaries, remaining gaps, recurring failure causes and verification
cost. Card counts and green fixtures are not product progress or milestone closure.

## Reconcile parallel implementation and harness results

1. Read each worker's exact receipt, attributed change set and final test summary.
   Match its owned source hashes against the integrated candidate. Inspect the actual
   consumer seam as well as the producer API: agreed control IDs do not prove the
   harness invokes the final picker, constructor or callback contract correctly.
2. Freeze a coherent candidate including changed callers, generated outputs and test
   inputs. Run the deduplicated union of affected test targets with bounded concurrency.
   Record the combined run's total rather than summing overlapping child runs.
3. Re-run preparation checks with the receipt's explicit interpreter or virtualenv.
   Preserve a separate exit status for every command; do not let a later successful
   syntax check hide an earlier failing test in a semicolon-separated shell command.
   If the environment differs, restore or reproduce the recorded non-privileged
   environment and rerun; do not relabel the earlier result as passing.
4. Keep verification seams explicit. Supplying a selected document through a picker
   seam can exercise production parsing, authentication and transport, but does not
   qualify the operating-system chooser. Record chooser, actual native app and live
   host results separately. A fixture probe or harness unit test closes preparation
   acceptance only, not a dependent platform qualification task.
5. Close only the implementation acceptance actually proved. Reconcile affected
   current-state docs with final source, retain historical failed receipts as earlier
   snapshots, and keep native/live successors open. Archive the completed task body
   losslessly before removing it from the live backlog. Let the integration owner
   apply ledger transitions; children must not close a parent or sibling task.

## Recheck unresolved work immediately before handoff

Capture a bounded source snapshot BEFORE inspecting the serious candidate and
writing its contract: `python <this-skill-directory>/scripts/source_freshness.py
capture <workspace> --path <implicated-source-or-doc> [--path <another-file>]`.
Save the returned JSON with `write_file` under the active profile's autogoal
receipts and preserve that original snapshot. Make any selection-time doc or ledger write
first — booking the task, recording the evidence the contract cites — and capture after it:
the helper compares these exact bytes again at dispatch, so a snapshot taken before your own
write refuses the handoff on your own change, and re-capturing afterwards to clear it is the
silent refresh this section forbids. Include authoritative requirement,
implementation and relevant test/doc targets, normally a few files and never
more than 32. An absent intended output is recorded too, so its later appearance
invalidates the selection. Do not fingerprint credentials, Git internals, private
datasets or reference upstreams merely to form a receipt.

After selecting a usable task, before calling the handoff helper or native create tool,
recheck the exact unresolved requirement against CURRENT code/docs/test evidence
and latest relevant human-session decisions. Read enough of the relevant thread
to see later corrections, not only an older finding. A formerly valid audit does
not prove the task still exists. Reconcile source changes by rereading, reranking
and taking a NEW snapshot only after a genuine new selection. Never silently
refresh the snapshot to make the old contract pass.

Pass `--source-snapshot <receipt-file>` on a new CLI handoff. The helper compares
the bounded files after live card reconciliation and immediately before create;
missing/changed/malformed/wrong-workspace snapshots reject the NEW dispatch.
Existing-owned reconciliation and `--validate-only` remain non-dispatch paths.
Native-tool handoffs perform the equivalent freshness check. A hash match proves
only unchanged selected bytes, not an unresolved defect, approval, atomic lease
or current test success. Ownership and other-board/process claims still need
checking; this check is not an atomic filesystem/board transaction.

If another authorized session or the docs prepass already delivered the repair,
reconcile its attributed evidence and choose other useful work instead of
creating a duplicate correction card or claiming its edits. Preserve any existing
blocked duplicate and owner gate; do not silently retry, close or relabel it.

## Executable isolated Git write passes

New `start_goal.py` write handoffs require `--base <full-immutable-commit>`.
`--candidate <explicit-committed-ref-or-commit>` defaults to that base. Declare
attributed sibling inputs with repeated `--prerequisite <ref>=<full-commit>` and
runtime dependency files with repeated `--required-path <root-relative-file>`.
The helper reuses `candidate_identity.py`, resolves the candidate to a commit,
assembles only those pinned prerequisites in a new detached Git worktree, and
checks their ancestry/ref pins and required files. Missing siblings, moved pins,
merge conflicts, missing closure files or a candidate outside base ancestry refuse
create. This is explicit dependency assembly, not inferred dependency discovery.
An untracked/dirty sibling is never copied merely because it is in the checkout;
the integration owner must first provide its attributed committed prerequisite.

Before spending the picker budget on a contract, resolve the proposed candidate
with `git rev-parse <candidate>^{commit}` and inspect each selected input with
`git diff <candidate> -- <path>`; check untracked inputs separately because
`git diff` does not enumerate them. Include `goals.json` in this comparison whenever
focused admission requires it. Compare exact bytes or hashes where a candidate
is assembled from prerequisites rather than a single ref. A current ledger absent
from the candidate is a closure mismatch, not evidence that it changed during
this run. Do not describe a guard's generic source-change diagnostic as concurrent
editing without checking which boundary differs. Keep validation, candidate
admission, card creation and observed worker execution distinct in the report;
a passing `--validate-only` does not exercise worktree assembly. This preflight
detects missing inputs; it does not authorize committing them or replace the
helper's final freshness and ownership checks.

`--workspace` remains the canonical profile source cwd for ownership reconciliation
and source/ledger admission. The actual new native card's `dir:` workspace is the
isolated worktree under `--pass-root` (default
`~/.hermes/cache/scratch/autogoal-passes`), never the shared source checkout.
The pass root must be outside that checkout. Worker edits, focused tests, local
agent commits and doc/ledger changes belong only in the card workspace. A dirty
shared source checkout is a read-only input, not permission for shared writes.
Selection fingerprints must match BOTH source and the assembled candidate; this
intentionally refuses uncommitted selection inputs absent from the candidate.

Before create, the helper checks original snapshot bytes, fresh source/ledger,
unchanged admission and the exact clean candidate again after assembly, with no
intervening native CLI lookup. Handoff receipts embed the immutable candidate
identity, expected source fingerprints and ledger hash, plus an exclusive manifest
file and its hash. The card includes this initial worker gate:

```sh
python3 <this-skill-directory>/scripts/pass_workspace.py \
  --manifest <exact-card-manifest.json> --manifest-sha256 <hash-from-original-card> \
  --workspace <exact-card-worktree>
```

For an initial command, append `-- <command> [args...]`; the executable wrapper
checks before launching it in that workspace, with a 180-second command bound.
Manifest replacement, source retraction, ledger change/appearance, moved
prerequisite, different HEAD or already-dirty worktree refuses before that command
can edit production. Stop on the original card with the diagnostic; never silently
refresh evidence, reinterpret a retracted finding as a fresh task, or create a
replacement. Run this gate at INITIAL worker start, not after authorized worker
changes or as a resume/migration operation. Existing cards retain their original
workspace, ID and budget. `already_owned`, native idempotency reconciliation and
non-dispatch `--validate-only` do not migrate active cards. New shared-checkout
write dispatch without a base now explicitly refuses; structural validation is
not a write-pass admission proof.

Local real-Git tests and mocked native create/readback exercise this path; they
are **not live dispatch or worker adoption proof**. The gate is executable but
is not wired into Hermes' native dispatcher as a runtime hook: the worker must
execute the command carried in its card, or use the wrapper for its initial write.
Neither a worktree nor this helper is a filesystem sandbox, semantic unresolved-
finding detector, atomic source/board transaction, resource lease or security
boundary against absolute-path writes. Independent source changes after the final
check remain possible; the initial worker check narrows that gap but cannot make
it atomic. Qualification does not include installed profiles, real boards,
providers, remote actions or proof that a live worker followed the gate.

### Same-card entry after review requests changes

1. Inspect `hermes kanban show <card> --json` and the owning profile's filtered
   board. Preserve the exact original workspace and card; a notification is not
   proof of its current status or a reason to create a replacement.
2. Verify that the original implementation run executed its initial admission
   gate. Inspect the attributed implementation commit and compare its owned blobs
   with retained workspace files. Check HEAD, original manifest hash, ledger and
   dependency inputs, staged changes, and unexpected tracked/untracked product
   files. Do not reset the worktree or refresh the original selection to make it
   clean: authorized implementation edits are expected during review rework.
3. Pin a pre-edit re-entry verifier to those exact inputs. Require it to reject
   changed manifest/HEAD, unexpected staged or foreign files, mismatched owned
   bytes and redirected inputs. Test both admission and refusal paths; a syntax
   check alone does not qualify the verifier. Run it once before rework, not after
   authorized fixes. Keep its scope and original initial-start refusal tests intact.
4. Have the authorized parent apply and read back the lifecycle correction in the
   ORIGINAL card body. State that first-start checks are initial-only and the
   pinned verifier governs this re-entry. Preserve review findings, product
   acceptance, scope, attempts and budget; a comment alone may not change the
   worker's mandatory instructions. Return that same card to implementation through
   the supported lifecycle operation, then read back its status.
5. Require the worker to reproduce the review failure, fix it within owned paths,
   rerun affected checks and request the same native review lane. Observe its actual
   re-entry check and run before reporting execution. Gate repair is orchestration
   progress, not a product fix, review approval or main delivery.

## Check delivery boundaries when changing dependencies

When a selected repair adds/extracts/imports a shared module, trace the affected
entrypoint to its actual delivery boundary. A source-run seed/admin CLI, copied
shell helper, asset loader, production-only dependency set or hand-picked runtime
image can work from the checkout while omitting the new dependency at delivery.
Inspect the relevant transitive local imports and manifest/COPY/package/assets
rules, not just unit tests or the application's unrelated bundled build. Derive
the smallest discriminating closure check from current project conventions.
Do not impose container checks on tasks with no affected packaging boundary.

State whether the minimal packaging correction is included in the new contract,
and capture its authoritative manifest/source targets in the selection snapshot.
Existing scope exclusions still win: record the missing dependency and scope gate
rather than edit excluded Dockerfiles/manifests. Preserve prerequisite source and
other owners' diffs. A static dependency-closure guard is static coverage; image
build, image execution, production/live acceptance and deployment remain
NOT_CHECKED unless separately authorized and actually executed. Never seed a real
database or rebuild/restart/deploy a live service just to validate a source-only
repair. A legitimate inherited owner authorization must be recovered from its
actual current scope and conditions, never inferred from an earlier restart.

## Qualification receipts and required runner verdicts

For a named accepted-plan handoff, run the existing read-only
`python ~/.hermes/shared-skills/repo-docs/scripts/goals.py backlog-check <repo>
--plan <repo-relative-path#heading> --tasks <existing-task-IDs>` once against the
canonical ledger; reuse its receipt while the pinned inputs match. Linked-worktree
calls require `--canonical-repo`. Missing canonical acceptance goes to the ledger's
integration owner, not a fabricated replacement task or another unchanged gate run.
There is no `goals.py show`: use `read_file` on `goals.json`, or `focus --json` and
`next --json` for their supported queries.

Use `check_receipt.py` with explicit argv, declared candidate inputs and immutable
prerequisites. An external helper script passed by absolute/escaping path is
augmented-local evidence, never clean-candidate qualification. Commit attributable
helper sources or provision pinned external dependencies through the owning
workflow; do not symlink/copy untracked shared helpers to manufacture a green
candidate. Declared external lock/environment files remain hash-bound inputs,
not proof that hidden producers were committed. Candidate scripts are trusted:
these checks are dependency declarations and post-run checks, not access tracing
or a malicious-code sandbox. Receipts predating `declared-snapshot-v3` are not
reusable as exact evidence. Reuse must repeat every `--path` and `--external-path`;
omitting the CLI input contract does not mean “trust the old contract.”

A shell's last-command exit is not an overall verdict: shell invocations yielding
zero receive `unverified_shell_status`, not a passing reusable receipt. Run each
required command as argv with its own receipt, or use a tested runner that
propagates every required failure. Do not infer application, preservation or
runner pass from each other. In `delivery_state.evaluate`, declare the contract's
nonempty unique `qualification.required_checks` names and supply a distinct
candidate-bound passing receipt for every required name (for example app,
preservation and runner). Missing, failed or duplicate checks prevent qualification
and delivery; old reports without the required-check contract need reconciliation,
not reexecution of unchanged passing app tests. These are helper report safeguards,
not native review admission or proof that a runner preserved unobserved files.

Unsupported main-only native admission stays fail-closed: the missing prerequisite
is an owning native-dispatcher hook covering every mutation from setup/startup
through worker termination and legal same-task capability-stop reporting. Route
that prerequisite to the separately authorized native lifecycle workflow; shared
fixtures cannot install it. Retain the original task and receipts, resume only when
prerequisite evidence changes, and do not repeat the same gate or auto-create work.
Reports must take current profile/workspace identity from their observed metadata,
not a copied project's name; missing identity is unknown, not rename authority.

For restricted shared-only verification, use short ignored fixture homes and keep
`TMPDIR` under that home's `.hermes/cache/scratch`; native fixture receipt roots
must match, and Unix socket names have a hard length limit. Preserve the installed
Python dependency path explicitly when changing HOME. Prevent no-Git fixtures from
inheriting the enclosing checkout without weakening canonical identity guards.
Installer fixtures may call the real native config function only after asserting
that the exact target is inside fixture storage; never invoke a bootstrapping
launcher, provision dependencies or claim live-profile coverage from that test.

## Separate review readiness from final acceptance

For a contract requiring native same-card review, explicitly distinguish worker
implementation/test acceptance from final approval. The worker's authorized end
state is ready for review after its implementation checks and required independent
review; final closure remains dependent on the native review lane. Do not phrase
approval by that lane as a prerequisite to requesting entry into it. This does
not waive review, transfer review authority, or guarantee judge acceptance.

If `kanban_request_review` rejects entry solely because review is pending, follow
Operating priority 8: one corrected request citing the card's Definition of done,
deliverables and executed checks, not a governor escalation. Preserve the exact
response/card/run and source-bound receipts if that still fails; do not loop,
force done, invent approval, replace the card, change its acceptance or rerun
unchanged product tests for a lifecycle error. Separate actual review findings
from lifecycle refusal. Workers never patch goal/judge code or assume manager
powers; review handoff never closes qualification or milestone delivery gaps.

## Budget review and repeat checks deliberately

Only when the contract explicitly requires PRE-WRITE/final reviewer subagents (Operating priority 8), budget them before execution.
Use one consolidated pre-write consultation with exact scoped source and safety
invariants, then implement and verify, and reserve capacity for final review of
the actual artifact and acceptance evidence. Avoid exhausting delegation on
repeated equivalent plans. Re-consult when the source, plan or concrete safety
finding changes, not merely to repeat an approval. Do not waive mandatory final
review or move a still-unreviewed passing task to done. If a native delegation
cap blocks required review, record the exact remaining gate on the original card;
never relaunch a replacement task as a way around that cap.

Falsification checks must restore task-owned source bytes and verify their
fingerprints before final GREEN checks. Prefer isolated copies when the test
supports them. A restored production file does not justify a new product change
claim. Respect host verification gates, but investigate session evidence
freshness/command recognition before replaying a full suite. On frequent cron
runs, silence suppresses delivery, NOT model or tool cost: use scoped unchanged
fingerprints and prerequisite probes to bound no-op work. Do not change
cadence or providers yourself; bounded seam inspection and receipt reuse bound
no-op cost without suppressing discovery.
A newly configured profile with no sessions or journal has NO observed outcome;
absence is not success, a defect or permission to schedule it.

## Hand off to the native goal loop

Use 50 turns by default. For a coherent larger outcome, pass `--goal-max-turns 100`
and add a nonempty `Goal budget rationale:` contract field explaining why that
outcome needs the larger budget. This is structural validation, not a scope grant
or a proof of the estimate. Use the same flag for `--validate-only` and dispatch.
Native-tool handoffs use the same contract rule and selected goal_max_turns.
Stop when acceptance and review handoff are satisfied; do not burn unused turns.
Do not split debugging, fixes, tests or review handoff into intermediate cards.
The assigned worker owns that whole outcome within its scope and retry limits.
An interrupted run retains its original card and worker session: inspect the exact
run/claim before supported same-card recovery. Never reset its budget or create a
replacement because another picker tick arrived. The helper returns an existing
owned card's persisted budget unchanged, even if this invocation requests another.
A new budget applies only to a newly created card, not a resume API. Native `/goal`
is same-session; this separate kanban worker never sets a goal in the picker chat.

The picker must not implement the selected code task in its one-shot cron turn; the bounded repo-docs prepass is the explicit documentation-only exception. First inspect the board and existing workspace claims; do not replace an existing goal or launch overlapping work. On the default board, a runnable/actively executing assigned card wins: reconcile it instead of adding another. A terminal blocked card blocks its own slice and dependent work, not every task in the repository. After checking the blocker, compare disjoint, authorized candidates with a concrete payoff; preserve the original card, never silently retry/replace it, and exclude its owned files/resources/dependencies. If no genuinely disjoint worthwhile candidate exists, return the unchanged no-op. After selection, save a contract file under the active profile's autogoal directory with nonempty, unique top-level `Objective:`, `Scope:`, `Verification:`, `Source:`, `Project payoff:` (milestone/user benefit), `Current evidence:` (live paths/lines or measured reproduction), `Expected change:` (the concrete before/after artifact or behavior), `Acceptance:` (observable criterion and discriminating check), and `Stop conditions:` (complete/review/block boundaries), plus `Repo-docs pass:` (actual mode and checked journal receipt/evidence pointer). The helper rejects incomplete, empty or duplicate fields before any CLI call; structural validity is not factual proof or authorization. For native-tool handoffs apply the same preflight, acceptance-evidence instructions and safety boundaries; do not bypass them by using a different surface. Append `--validate-only` to the helper command below to check structural readiness without subprocess calls, journal writes, subscriptions or dispatch; this does not check facts, priorities, ownership, configured cwd or permissions. Use the native kanban tools if exposed with `goal_mode: true`, `goal_max_turns: 50` (or explicit 100 with the rationale above), this profile as assignee, the prepared isolated Git worktree as `dir:<absolute-pass-worktree>`, the pinned manifest/initial worker gate described above, and `completion_contract: local-only`. Never use the configured shared source cwd as a new native write workspace. Read the exact card back and confirm those fields. If native board tools are not exposed, use the bundled stdlib helper through terminal:

`python <this-skill-directory>/scripts/start_goal.py --profile <active-profile> --workspace <absolute-configured-cwd> --title <selected-slice> --contract-file <absolute-contract-file> --source-snapshot <absolute-selection-snapshot> --base <full-immutable-base-commit> [--candidate <committed-candidate>] [--prerequisite <ref>=<full-commit>] [--required-path <dependency-file>] [--goal-task <ledger-task-id>] [--fallback-file <structured-fallback.json>]`

When `goals.json` sets `primary_milestone`, `--goal-task` is required and the selection snapshot must include fresh `goals.json`. The task must be dependency-ready under the ledger's existing rules. An unrelated task requires a structured fallback matching workspace, focus, selected task, ledger hash and snapshot hash, with a typed reason/evidence reference for every eligible focused slice, or an explicit attributed reprioritization. Missing, stale or partial fallback data refuses new create. These are caller attestations, not proof that a claimed ownership/environment/authority constraint is true; inspect that evidence separately. Active-card reconciliation still occurs first. `--validate-only` checks this admission without native calls or writes; no-focus repositories retain legacy structural validation. Native-tool handoffs must perform the same admission checks, not bypass the CLI's refusal.

New receipts record stable board/task identity, selected task/focus/fallback and UTC creation time. Historical receipts preserve original bytes under dated content-addressed archive names; legacy undated records remain undated and existing aliases are not overwritten.

The helper uses the supported profile-scoped CLI, a per-profile handoff lock, stable idempotency key, and exact card readback. For an evidenced resource-disjoint candidate only, the default governor may supply `--disjoint-terminal-triage <exact-original-id>` after inspecting both resource scopes, latest human instructions and live ownership. The helper rechecks same-profile/workspace triage, a terminal blocked/crashed run and absent claim/PID under the lock; ordinary picker defaults remain conservative. Never use this exception for an equivalent replacement, a scope/dependency overlap, unrun triage, or a live worker. Preserve the original card and its unresolved gate. This attestation is not an atomic resource lease or automatic semantic disjointness proof. It also refuses an active default-board directory-workspace card owned by another profile; do not subscribe this profile to that owner's card. This board check is not an atomic workspace lease and does not replace checking live cron/process/repository claims or other boards. It saves the exact verified handoff before fallible notification setup, archives the previous receipt under `autogoal/handoffs/`, and returns `notification_blocked` plus the existing task ID on transport failure; reconcile that card, never create a replacement. Current CLI JSON omits the goal fields, so the helper reads only that card's goal_mode/goal_max_turns from the CLI-resolved canonical SQLite board in read-only mode; never assume an omitted field is false. It explicitly sets `--goal --goal-max-turns <50|100>` (default 50) and three attempts (`--max-retries 3`), never relying on the default 20 turns. The existing gateway dispatcher starts the named-profile worker; queue/readback is not proof that it started. Record the card ID in the journal and report it as handed off until a worker run is observed. The helper registers and reads back a native passive Telegram terminal-event subscription for profiles with a configured home channel; this reports completed/blocked/review outcomes without waiting for the next hourly picker and does not wake or enqueue another agent. Profiles without a configured home channel remain local-only. A missing/failed subscription is a delivery blocker on the existing card, never a reason to create another. Reconcile the board's latest run/events, not the immutable creation receipt's old `ready` status. Preserve the prior handoff ID before overwriting it; inspect unreported terminal results before selecting another slice. Do not recreate a blocked slice by changing its title or contract wording; use the same card and resolve the evidenced prerequisite before any explicitly authorized retry. Native tools must establish the equivalent notification subscription as well as creating the card. Do not silently fall back to a single-turn implementation if dispatch is unavailable; report that blocker. Do not attach the autogoal picker skill to its execution worker: that would recursively select tasks.

Hermes `delegate_task` children may be refused native Kanban mutation by an enforced child-context restriction. Keep that restriction intact: return exact candidate/contract/readback inputs and have the parent perform authorized native mutations. Do not treat a delegated diagnosis or a note on a completed routing card as acknowledged repair ownership. Verify the exact new card/run and live process identity before reporting execution.

### Admission recovery and parent continuation

1. Keep candidate assembly separate from product admission. The recovery card owns
   its profile's worker slot: produce attributable immutable closure and a validated
   product launch payload, then finish native review handoff. Assign subsequent
   canonical product dispatch and runtime verification to the parent after slot
   release; never require a nested same-profile worker while recovery holds the slot.
   Preserve source/ledger refusal tests, foreign dirt and existing parked scope.
2. Encode this lifecycle in the original title/body, Definition of done, Verification
   and Acceptance before review. Comments alone do not change the judge's contract.
   If an authorized lifecycle correction conflicts with persisted wording, have the
   parent apply/read back only that correction on the same card. Preserve product
   acceptance, evidence pins and attempt limits; do not patch the judge, reset retries,
   force completion or create a substitute card. This is not permission to weaken an
   unmet product requirement.
3. Before terminal completion, preserve contract, original selection, requirement
   fingerprints, launch argument array, bundle and verification receipts in private
   durable storage outside the native worker workspace. Hash-verify copies and make
   launch paths durable; keep build/pass outputs in ignored project folders or approved
   scratch. Native cleanup can remove workspace-local handoff files at completion.
   If cleanup already occurred, recover exact retained write arguments or complete
   read results and require original hash matches before reuse. A deterministic
   reconstruction is acceptable only when its bytes match the original pin; never
   refresh a selection to clear refusal. Reject truncated display lines as file bytes;
   recover the complete argument array rather than guessing a truncated shell string.
4. On each notification, use `hermes kanban show <card> --json` and
   `hermes kanban runs <card> --json`, then filtered owning-profile board queries.
   Reconcile the latest run, not the notification's older status. A review run can
   still occupy the slot after handoff; completion must release it before continuation.
   Reuse existing downstream cards. Once released, recheck competing path/resource
   ownership, requirement/selection/ledger pins, candidate ref and ancestry. Validate
   the durable payload, then call canonical `start_goal.py` once; an existing-owned
   result means reconcile that card, not repeat create.
5. Read back exact card/workspace/budget/retries and observe its run. If needed, use
   supported `hermes kanban dispatch --max 1 --json`; an empty spawned list is not
   proof of failure because the gateway dispatcher may claim the card independently.
   Re-read the exact card before any further dispatch. On Linux verify PID start ticks,
   profile and cwd, plus only `HERMES_KANBAN_TASK` from `/proc/<pid>/environ` rather
   than dumping environment secrets. The card identifier may be embedded in a query
   argv, not a standalone token. Correlate the worker's own initial manifest-gate
   result with that card/session/workspace: a parent's pre-dispatch gate pass does not
   prove worker adoption. Register/read back the parent's terminal `notify+wake`
   continuation when needed, and keep implementation, qualification and main delivery
   distinct in the report.

When already inside a Kanban worker (`HERMES_KANBAN_TASK` is set), execute only its assigned contract, never run the picker or helper. The default manager does not enqueue skill-maintenance workers; it records proposed lessons for the owner. Project profiles must not edit the shared skill.

## Source-bound check receipts (Linux)

For an authorized local check, `scripts/check_receipt.py` records source hashes
before and after execution, the command, exit status, elapsed time, Python
runtime/package/executable identity and hashes of the actual execution environment.
It runs once under an explicit finite timeout, configurable above 300 seconds,
and a bounded shared heavyweight-resource lock. A timeout kills the process group.
It never retries a mutation or approves a review. Name platform/backend, fixture
or live mode and toolchain identities explicitly for qualification.

```sh
python <this-skill-directory>/scripts/check_receipt.py run \
  --workspace /absolute/project --receipt /private/scratch/check.json \
  --path src/changed.py --path requirements.lock --path verification-environment.json \
  --timeout 60 -- python -m unittest tests.test_changed
python <this-skill-directory>/scripts/check_receipt.py reuse \
  --workspace /absolute/project --receipt /private/scratch/check.json \
  -- python -m unittest tests.test_changed
```

The example without candidate flags is shared-tree declared-input proof only.
For exact qualification, add `--base <full-commit> --candidate <ref-or-commit>
--tree <tree-id>` and each `--prerequisite <ref>=<full-commit>`, plus
`--platform <name> --backend <name> --mode fixture|live --toolchain <name>=<identity>`.
Checks run in an isolated frozen worktree; missing prerequisite ancestry refuses
qualification. Unsupported opaque/shared-checkout command patterns and declared
outputs remain weaker than exact proof. Undeclared untracked/ignored additions
invalidate qualification. This is dependency-declared verification, not a
filesystem sandbox or read tracer. Trusted checks must not manufacture transient
undeclared source dependencies. Receipt-backed delivery-state evaluation checks
freshness and retains scope; one delivered slice never closes a whole milestone.

Declare every relevant source, dependency and non-secret environment input.
Include non-Python tool versions and backend settings in the environment input;
the helper cannot infer the dependency closure. Keep receipts private: they
contain paths, commands, runtime metadata and a bounded failure diagnostic.
Never use this helper for secret-bearing checks. Never supply credentials in command
arguments or commit machine-specific receipts. Failed checks, timeouts, changed
inputs, changed runtime or changed commands reject reuse. A matching receipt
proves only its declared check, not that selection remains useful or a native
review system acknowledged it. Existing receipts are never overwritten.

Reusable verification lesson: test timeout descendants, not just the immediate
process; test source drift during the check as well as between checks; compare
both source and environment before and after. A fixture review sink must echo the
exact candidate and receipt, and must stay labeled fixture evidence. Read native
review acknowledgement separately before claiming a verified review handoff.

## Local agent commits (Operating priority 14)

After acceptance, use `<this-skill-directory>/scripts/agent_commit.sh <repo>
<profile> <card-id> "<message>" <files>...` with only files this worker changed.
It writes `agent/<profile>/<card-id>` through a temporary index without switching
branches or touching HEAD, the real index, working tree or foreign dirty files.
Commit again after review fixes on the same agent branch. Never commit secrets or
generated build output. Report the branch and SHA in the completion receipt.
The integration owner assembles attributed commits and lands a protected PR only
after required checks; workers never merge or push. Explicit task restrictions
(such as no commit) still win over this standing local-commit permission.

## Execute and verify (goal worker)

Before solution design or implementation, load `ponytail`; preserve test-driven-development
and never waive safety, acceptance criteria or required checks for a smaller diff.
Include this instruction in native-tool handoffs as well as the CLI-generated body.
Use ponytail's integrated complexity review, not a separate ponytail-review load.
Skill consolidation lesson: archive the old discovery entry with provenance, remove
it from vendor sync, and verify fresh command resolution; an existing session's
cached catalog is not proof. Prompt selection is not observed worker adoption or
measured time/token savings.

Implement only the selected slice with regression tests and real checks, or execute the selected bounded reproduction/acceptance investigation. Do not ask the user to choose among ordinary safe candidates. Resolve retrievable facts yourself. Iterate fix → rerun until acceptance (Operating priority 4). Stop on the slice's completion, runtime budget, 5 attempts without new evidence, an ownership conflict, or a necessary owner decision. Do not start a second task.

Do not commit outside the local agent branch (Operating priority 14), push, deploy, publish, spend money, place trades, contact third parties, change other profiles, or activate recurring automation without separate authorization for that exact action. Approval bypass does not expand scope. Read back external writes. Preserve repository instructions and unrelated dirty work. Never mutate upstream software to obtain a capability absent from its public interfaces.

## Coherent integration candidates

Capture a compilable immutable candidate before parent verification; never run a
combined gate against files a worker is actively changing. Constructors, callers,
localization inputs and generated outputs must land as one coherent increment:
otherwise the compiler observes mismatched API generations rather than a stable
regression. When tightening dispatch prerequisites, migrate integration fixtures
to real committed repositories and use returned worker workspaces for writes and
receipts; preserve negative refusal checks instead of bypassing the new guard.
If an explicitly requested fresh test catches an intermediate edit,
report the failed check honestly, steer the owning worker with the exact errors,
and require a new source-bound run after coherence is restored; do not repeatedly
run the same gate against the moving tree or overwrite the worker's lease.
