# Autogoal — Handoff, review and worker execution

Load on every run that hands a slice to a worker, before writing the contract. The Operating priorities in SKILL.md override anything here.

## Recheck unresolved work immediately before handoff

Capture a bounded source snapshot BEFORE inspecting the serious candidate and
writing its contract: `python <this-skill-directory>/scripts/source_freshness.py
capture <workspace> --path <implicated-source-or-doc> [--path <another-file>]`.
Save the returned JSON with `write_file` under the active profile's autogoal
receipts and preserve that original snapshot. Include authoritative requirement,
implementation and relevant test/doc targets, normally a few files and never
more than 32. An absent intended output is recorded too, so its later appearance
invalidates the selection. Do not fingerprint credentials, Git internals, private
datasets or reference upstreams merely to form a receipt.

After the docs prepass, before calling the handoff helper or native create tool,
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

## Separate review readiness from final acceptance

For a contract requiring native same-card review, explicitly distinguish worker
implementation/test acceptance from final approval. The worker's authorized end
state is ready for review after its implementation checks and required independent
review; final closure remains dependent on the native review lane. Do not phrase
approval by that lane as a prerequisite to requesting entry into it. This does
not waive review, transfer review authority, or guarantee judge acceptance.

If `kanban_request_review` rejects the transition solely because native review is
still pending, capture the exact tool response and current card/run, attach the
existing source-bound acceptance and independent-review receipts, and preserve
the original card for fleet-governor assessment of supported same-card
administrative review entry. A worker CLI rejection alone does not prove that
operator authorization is needed. The governor must inspect the shipped
administrative interface and its authority, preserve original requirements/goal
fields and mandatory final review, check fresh receipts/no live claim, use only
authorized entry (never force done), then read back exact target and review run.
Ask the operator only if no supported governor authority resolves the remaining
gate. Workers stop with the exact receipts; they do not assume administrative
powers or launch a competing manager. Use only currently permitted lifecycle
states/block kinds. Do not fabricate approval, silently change the existing
contract, repeatedly request the same rejected transition, replace the card, or
rerun unchanged product tests to fix a lifecycle error. Separate a new concrete
code/review finding from a lifecycle refusal. Project workers never patch upstream
goal/judge code. Manager diagnosis is read-only unless an explicitly authorized
supported same-card intervention is chosen; no automatic unblock/complete.

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

The picker must not implement the selected code task in its one-shot cron turn; the bounded repo-docs prepass is the explicit documentation-only exception. First inspect the board and existing workspace claims; do not replace an existing goal or launch overlapping work. On the default board, a runnable/actively executing assigned card wins: reconcile it instead of adding another. A terminal blocked card blocks its own slice and dependent work, not every task in the repository. After checking the blocker, compare disjoint, authorized candidates with a concrete payoff; preserve the original card, never silently retry/replace it, and exclude its owned files/resources/dependencies. If no genuinely disjoint worthwhile candidate exists, return the unchanged no-op. After selection, save a contract file under the active profile's autogoal directory with nonempty, unique top-level `Objective:`, `Scope:`, `Verification:`, `Source:`, `Project payoff:` (milestone/user benefit), `Current evidence:` (live paths/lines or measured reproduction), `Expected change:` (the concrete before/after artifact or behavior), `Acceptance:` (observable criterion and discriminating check), and `Stop conditions:` (complete/review/block boundaries), plus `Repo-docs pass:` (actual mode and checked journal receipt/evidence pointer). The helper rejects incomplete, empty or duplicate fields before any CLI call; structural validity is not factual proof or authorization. For native-tool handoffs apply the same preflight, acceptance-evidence instructions and safety boundaries; do not bypass them by using a different surface. Append `--validate-only` to the helper command below to check structural readiness without subprocess calls, journal writes, subscriptions or dispatch; this does not check facts, priorities, ownership, configured cwd or permissions. Use the native kanban tools if exposed with `goal_mode: true`, `goal_max_turns: 50`, this profile as assignee, the exact configured cwd as `dir:<absolute-path>`, and `completion_contract: local-only`. Read the exact card back and confirm those fields. If native board tools are not exposed, use the bundled stdlib helper through terminal:

`python <this-skill-directory>/scripts/start_goal.py --profile <active-profile> --workspace <absolute-configured-cwd> --title <selected-slice> --contract-file <absolute-contract-file> --source-snapshot <absolute-selection-snapshot>`

The helper uses the supported profile-scoped CLI, a per-profile handoff lock, stable idempotency key, and exact card readback. For an evidenced resource-disjoint candidate only, the default governor may supply `--disjoint-terminal-triage <exact-original-id>` after inspecting both resource scopes, latest human instructions and live ownership. The helper rechecks same-profile/workspace triage, a terminal blocked/crashed run and absent claim/PID under the lock; ordinary picker defaults remain conservative. Never use this exception for an equivalent replacement, a scope/dependency overlap, unrun triage, or a live worker. Preserve the original card and its unresolved gate. This attestation is not an atomic resource lease or automatic semantic disjointness proof. It also refuses an active default-board directory-workspace card owned by another profile; do not subscribe this profile to that owner's card. This board check is not an atomic workspace lease and does not replace checking live cron/process/repository claims or other boards. It saves the exact verified handoff before fallible notification setup, archives the previous receipt under `autogoal/handoffs/`, and returns `notification_blocked` plus the existing task ID on transport failure; reconcile that card, never create a replacement. Current CLI JSON omits the goal fields, so the helper reads only that card's goal_mode/goal_max_turns from the CLI-resolved canonical SQLite board in read-only mode; never assume an omitted field is false. It explicitly sets `--goal --goal-max-turns 50` and three attempts (`--max-retries 3`), never relying on the default 20 turns. The existing gateway dispatcher starts the named-profile worker; queue/readback is not proof that it started. Record the card ID in the journal and report it as handed off until a worker run is observed. The helper registers and reads back a native passive Telegram terminal-event subscription for profiles with a configured home channel; this reports completed/blocked/review outcomes without waiting for the next hourly picker and does not wake or enqueue another agent. Profiles without a configured home channel remain local-only. A missing/failed subscription is a delivery blocker on the existing card, never a reason to create another. Reconcile the board's latest run/events, not the immutable creation receipt's old `ready` status. Preserve the prior handoff ID before overwriting it; inspect unreported terminal results before selecting another slice. Do not recreate a blocked slice by changing its title or contract wording; use the same card and resolve the evidenced prerequisite before any explicitly authorized retry. Native tools must establish the equivalent notification subscription as well as creating the card. Do not silently fall back to a single-turn implementation if dispatch is unavailable; report that blocker. Do not attach the autogoal picker skill to its execution worker: that would recursively select tasks.

When already inside a Kanban worker (`HERMES_KANBAN_TASK` is set), execute only its assigned contract, never run the picker or helper. The default manager does not enqueue skill-maintenance workers; it records proposed lessons for the owner. Project profiles must not edit the shared skill.

## Execute and verify (goal worker)

Implement only the selected slice with regression tests and real checks, or execute the selected bounded reproduction/acceptance investigation. Do not ask the user to choose among ordinary safe candidates. Resolve retrievable facts yourself. Iterate fix → rerun until acceptance (Operating priority 4). Stop on the slice's completion, runtime budget, 5 attempts without new evidence, an ownership conflict, or a necessary owner decision. Do not start a second task.

Do not commit outside the local agent branch (Operating priority 14), push, deploy, publish, spend money, place trades, contact third parties, change other profiles, or activate recurring automation without separate authorization for that exact action. Approval bypass does not expand scope. Read back external writes. Preserve repository instructions and unrelated dirty work. Never mutate upstream software to obtain a capability absent from its public interfaces.
