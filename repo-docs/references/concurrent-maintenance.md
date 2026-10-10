# Concurrent ledger maintenance

## One canonical owner

Use one integration owner for repository-root `goals.json`, `TODO.md`, and their task bodies.
Workers in linked worktrees return scoped proposals, not replacement ledger snapshots.
A proposal names the goal/task IDs, base revision, intended CLI operations, evidence,
source identity, and complete task-body changes. It does not authorize a new goal,
change acceptance, or close the parent milestone.

The integration owner checks each proposal against the current canonical ledger.
Apply accepted operations through `scripts/goals.py`. Do not copy a worker's
`goals.json` or `TODO.md` over the canonical files. Allocate task IDs against the
current ledger under owner control. An occupied ID requires reconciliation,
not overwrite or automatic reinterpretation of the proposal.

## Executable coordination

Every CLI command takes an exclusive advisory lock before reading the ledger.
The lock covers loading, command validation, mutation, replacement, and rendering
for that invocation. In Git repositories, the lock lives at
`<git-common-dir>/.repo-docs-goals.lock`. Primary and linked worktrees share it.
Without Git metadata, local fixtures use `<resolved-repo>/.repo-docs-goals.lock`.
Do not remove an active lock file: replacing its inode can create two lock owners.

Before Git repository-identity subprocesses, construct an environment that removes
all inherited `GIT_*` overrides while retaining unrelated process settings.
Repository, worktree, common-directory, index, object-store and config overrides
can redirect discovery even when `cwd` names the intended checkout. Apply the
same sanitization to canonical-target validation and lock discovery; otherwise
one invocation can validate one repository and lock another.

Verify this boundary with real temporary Git repositories and CLI processes:
1. Hold the intended repository's lock; inject another repository's Git overrides
   into a mutation and require it to remain excluded until the correct lock releases.
2. Invoke a linked worktree without `--canonical-repo` under primary-checkout
   overrides and require refusal with both ledgers unchanged.
3. Exercise config-based overrides as well as directory/index/object overrides;
   retain ordinary aliases, no-Git fixtures and explicit canonical-target tests.
Run `python -m unittest test_goal_concurrency -v` from the scripts directory after
changing identity discovery. Passing ordinary concurrent-update tests alone does
not exercise redirected lock identity.

A linked-worktree invocation must explicitly select the primary checkout:

```sh
python <skill>/scripts/goals.py revision <worker> --canonical-repo <primary>
python <skill>/scripts/goals.py evidence <worker> GOAL-1 --canonical-repo <primary> --expected-revision <revision> --kind executed --ref '<exact check>' --result pass
```

The default target must be the primary checkout of the same Git common directory.
An existing native common-config `repoDocs.backlogAuthority` binding can instead
name an absolute, registered worktree of that same repository. `goals.py` verifies
registration/common-directory identity, resolves all commands (including `next`)
to that owner, and requires explicit `--canonical-repo` to match it. Global,
worktree-local and inherited Git configuration overrides do not establish this
binding. A worktree registration alone is not backlog authority. Do not set this
key during plan persistence or to force a passing gate; an actual integration
owner must already have designated the consumer's backlog owner.
The CLI refuses implicit writes and reads against an unbound linked worktree's stale
ledger. It does not silently infer or merge another snapshot. The explicit flag
selects the canonical target; it does not grant a worker integration authority.
The designated integration owner applies proposals. Workers do not use the flag
to bypass that ownership contract.

Use `revision <repo>` to get a SHA-256 token over the exact ledger and TODO bytes,
including a missing-file distinction. Pass `--expected-revision <token>` to a
later command. A mismatch exits nonzero with `stale revision` before either
content file is written. Obtain a fresh token after each accepted operation.
Do not retry a rejected snapshot blindly. Re-read current state and reconcile.

The CLI rechecks the transaction snapshot immediately before `os.replace`.
A detected out-of-band edit exits nonzero with `stale write`; temporary output
is removed. Replacement uses a flushed, fsynced temporary file in the same
directory. Existing permission bits are retained. Repository path aliases are
resolved before coordination. Symlink ledger, TODO, and lock files are refused.
Git targets must name their repository root, not a subdirectory.

`render` reads both files under the same lock and replaces only the coverage
block. Complete task bodies and their continuation bytes outside an existing
marked block remain unchanged, including CRLF and trailing blank lines.
When no coverage section exists, rendering appends it without trimming existing
bytes. An existing unmarked `## Goal coverage` section retains its legacy
migration behavior. Rendering does not create task bodies or archive entries.
After all accepted mutations, run `validate` and a final `render` against the
canonical target. Mutations retain the existing CLI behavior: they do not
implicitly render. A render before a later mutation describes its own snapshot,
not the later ledger revision.

### Limits

This is local POSIX advisory coordination, not a distributed transaction,
authorization system, or new tracker. It requires `fcntl` and local filesystem
lock/rename behavior. Direct writes that ignore the lock cannot be made fully
atomic with the comparison: a hostile or uncoordinated writer can change a file
between the final comparison and rename. All participating writers must use this
CLI, or acquire the same lock and reconcile current bytes. The stale guard detects
observed edits before comparison; it does not promise protection against hostile
filesystem races, NFS semantics, or crash-atomic updates of multiple files.
Python helper imports are not the serialized user interface. Use the CLI.

Keep full task-body edits under the integration owner. If a separate tool edits
TODO, it must share this lock across read/compare/write. Otherwise return the body
change as a proposal and let the integration owner apply it with current-byte
comparison. Never publish a worker's stale full-file rewrite.

For a scoped dirty-worktree documentation proposal:
1. Capture exact baseline bytes for each writable document and author against a
   private pinned candidate containing those bytes, not HEAD alone.
2. Return targeted old/new replacements and a baseline-to-candidate patch; a
   repository-wide Git diff includes unrelated pre-existing work.
3. Under the shared lock, compare all targeted canonical baselines before applying
   replacements. On any mismatch, reread and reconcile instead of replaying the
   candidate. Verify that integrated authored bytes equal the candidate.
4. Release the manually held lock before invoking `goals.py`, because the CLI
   acquires that lock itself. Apply evidence/status operations only through the CLI.
5. Run `fmt`, `validate` and `render` against the canonical target. Confirm every
   live ledger ID has a task body outside the generated coverage block. Repeat
   `fmt`/`render` and compare both files byte-for-byte; unchanged inputs should yield
   a no-op, while a concurrent update requires a fresh snapshot rather than a
   nondeterminism claim.

### Verify task-only additions without absorbing foreign changes

1. Save exact canonical `TODO.md` and `goals.json` baselines before authoring.
   Prepare a targeted insertion in the private pinned worktree; do not use its
   HEAD version as the baseline when canonical documents already contain edits.
2. Allocate each numeric ID from the current ledger immediately before `add-task`.
   Obtain a fresh `revision` token for each mutation and pass `--expected-revision`;
   reserving a sequence in memory does not protect it from another writer.
3. After integration and `fmt`/`validate`/`render`, compare every pre-existing task
   object with its baseline. Require unchanged statuses, dependencies, sections and
   focus, unless the pass explicitly authorizes those changes. For each affected
   goal, allow only the intended additions to its task list.
4. For an insertion-only TODO change, normalize only the marked generated coverage
   block in both snapshots, remove the exact authored insertion once, and require
   the remaining bytes to equal the baseline. Check insertion multiplicity so this
   comparison cannot hide a duplicated body or an unrelated deletion.
5. Match all open/in-progress ledger IDs to actual task-entry markers outside the
   generated coverage block. Do not count incidental prose or table references as
   complete bodies. Validate added links and anchors in the canonical checkout and
   the artifact-free documentation candidate, then repeat `fmt`/`render` and require
   byte-identical ledger and TODO output when no concurrent change occurred.
6. Report the new outcomes and first eligible open slice separately from in-progress
   entries. State that backlog validation proves neither worker dispatch nor product
   qualification; do not add its passing checks as evidence that a feature is met.

Preserve completed task statuses, priorities and historical plan bodies during
source-study adoption. Record research as inspection evidence for the owning goals,
not as executed proof that the requested product outcome works.

## Evidence and acceptance contracts

### Hypotheses are not accepted causes

Record a plausible explanation as an evidence-graded hypothesis. Name supporting
and conflicting observations, alternatives, reproduction conditions, and the
next discriminating check. Do not publish it as an accepted causal claim before
reproduction and independent verification. A passing local fixture can verify a
code path without proving a causal explanation or a deployed outcome. Keep
hypothesis, reproduced observation, independently verified cause, and accepted
decision separate. These instructions establish a workflow contract; they do not
claim that a radio, SDR, HF service, or production defect has been fixed.

### Runtime claims need measurements

Record the exact command, source/test/dependency identity, environment, date,
measured duration, exit status, and captured output. State the measured scope.
Do not replace a missing measurement with an approximate claim such as `~30s`.
Choose the cheapest sufficient focused check before expensive gates. Reuse a
receipt only when its relevant source and environment binding still matches.
A changed dependency invalidates that reuse. Full-suite, live qualification, and
mission delivery remain separate gates; focused tests do not close them.

### API route coverage is a normative contract

Compare the authoritative supported operation set with registered runtime routes
and contract-test coverage using a machine-readable comparison. Include methods,
paths, versions, authentication, responses, and errors where applicable. Report
missing, extra, and unverified operations. A manually written status table or a
valid OpenAPI document alone does not prove runtime conformance. If comparison
cannot run in scope, preserve the normative route requirement and record an
unverified gap. Do not lower the required coverage to match current code.

### RF metrics retain the accepted bar

Separate controllable implementation metrics from environmental observations.
Examples of controllable checks include configured sample-rate behavior, DSP
correctness against fixtures, buffering, and bounded recovery. RF propagation,
antennas, interference, and station availability require their own environmental
context and observation interval. Do not treat an environmental failure as proof
of a code cause, or a fixture pass as RF mission success. Record measurements,
limits, and remaining mission criteria without weakening the accepted bar.
Changes to acceptance require an authoritative owner decision, not a documentation
pass that makes the current implementation appear complete.

## Focused verification

Run the local executable checks without profiles, providers, or production:

```sh
cd <skill>/scripts
python -m unittest test_goals test_milestone_focus test_goal_concurrency -v
```

`test_goal_concurrency.py` uses real CLI processes, temporary Git repositories,
and linked worktrees. It checks shared-lock exclusion, retained parallel updates,
canonical targeting, stale TODO refusal, in-flight edit refusal, exact task-body
preservation, symlink refusal, and existing file permissions. These are fixture
results, not proof of production deployment or all workflow policy execution.
