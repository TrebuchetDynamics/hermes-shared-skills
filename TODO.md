# TODO

[goals.json](goals.json) is authoritative for status, evidence, and selection.
The coverage table is generated. Task details below are maintained prose.
The README workflow order sets priorities. Each broad non-met goal has one Now and one Next slice.
These slices are independently eligible and unclaimed. They reduce coverage gaps, not automatically close broad live acceptance.
Do not run paid models, live provisioning, real transports, scheduler changes, commits, or pushes without separate authorization.
Fixture remotes and fake providers establish only their tested boundary.

## Goal coverage

<!-- goals:coverage:begin -->

Generated from `goals.json` by `goals.py render`. `met` requires an executed, passing check.

| Goal | Status | Evidence | Task |
| --- | --- | --- | --- |
| DOCS: Keep core docs and goal backlog current | partial | inspection `repo-docs/SKILL.md` → pass | DOCS-1, DOCS-2 |
| WORKER: Dispatch one bounded goal-linked worker | unverified | executed `python autogoal/scripts/test_pipeline.py -v (fixture lifecycle only)` → pass; inspection `autogoal/scripts/start_goal.py` → pass | WORKER-1, WORKER-2 |
| PROOF: Keep executed evidence tied to acceptance | partial | executed `python autogoal/scripts/test_check_receipt.py -v` → pass; inspection `repo-docs/scripts/goals.py` → pass | PROOF-1, PROOF-2 |
| MERGE: Gate and integrate finished work safely | unverified | inspection `fleet-governor/references/merge-train.md` → pass | MERGE-1, MERGE-2 |
| QUESTIONS: Relay owner questions while work continues | partial | inspection `extras/maintenance/question_relay.py` → pass | QUESTIONS-1, QUESTIONS-2 |
| SETUP: Wire profiles and discover canonical shared skills | unverified | executed `PYTHONDONTWRITEBYTECODE=1 TMPDIR=/home/xel/.hermes/cache/scratch make test` → pass; executed `PYTHONDONTWRITEBYTECODE=1 TMPDIR=/home/xel/.hermes/cache/scratch python3 extras/install/test_new_profile.py -v` → pass; executed `PYTHONDONTWRITEBYTECODE=1 TMPDIR=/home/xel/.hermes/cache/scratch python3 extras/monitors/test_autogoal_gate.py -v` → pass; executed `TMPDIR=/home/xel/.hermes/cache/scratch PYTHONDONTWRITEBYTECODE=1 python extras/install/smoke_stt.py` → pass; executed `TMPDIR=/home/xel/.hermes/cache/scratch PYTHONDONTWRITEBYTECODE=1 python extras/install/test_configure_stt.py` → pass; executed `TMPDIR=/home/xel/.hermes/cache/scratch PYTHONDONTWRITEBYTECODE=1 python extras/install/test_provisioning.py -v` → pass; executed `TMPDIR=/home/xel/.hermes/cache/scratch python extras/monitors/test_autogoal_gate.py -v` → pass; executed `python extras/install/test_provisioning.py -v` → pass; executed `python extras/install/test_provisioning.py -v; make test (curated Linux portability snapshot)` → pass; inspection `extras/install/new_profile.sh` → pass | SETUP-AUDIO |
| OFFLINE: Provide one reliable offline verification entry point | met | executed `TMPDIR=/home/xel/.hermes/cache/scratch PYTHONDONTWRITEBYTECODE=1 python scripts/check.py` → pass; executed `make test` → pass; executed `python fleet-status/scripts/test_status.py` → pass | — |

<!-- goals:coverage:end -->

## Now

### DOCS-1

- [ ] Prove Bootstrap and no-op Maintain on an isolated repository. Goal: DOCS.
- Payoff: keep core docs and goal backlog current without replacing acceptance with a claim.
- Sources: [requirement](PRD.md#requirements-and-acceptance), [implementation](repo-docs/scripts/test_goals.py), [verification](test-plan.md#risk-based-scenarios).
- Scope: Add a provider-free composed fixture around core-role ownership and goals helpers in repo-docs/scripts/test_goals.py or a new offline suite. Cover missing docs and preservation of existing equivalents.
- Exclusions: real profiles, secrets, live jobs, paid calls, real remotes, upstream Hermes, and unrelated workers' files.
- Acceptance: A new offline regression asserts all applicable owners, two slices per non-met goal, and byte-identical second-pass ledger/coverage. Run the focused suite and make test.
- Dependencies: none. Ownership: unclaimed.

### WORKER-1

- [ ] Prove pick-to-handoff-to-reconcile with a fake native lifecycle. Goal: WORKER.
- Payoff: dispatch one bounded goal-linked worker without replacing acceptance with a claim.
- Sources: [requirement](PRD.md#requirements-and-acceptance), [implementation](autogoal/scripts/test_goal_handoff.py), [verification](test-plan.md#risk-based-scenarios).
- Scope: Add an offline composed scenario across goals.py selection, start_goal.py handoff and reconcile.py readback with fake CLI/board fixtures.
- Exclusions: real profiles, secrets, live jobs, paid calls, real remotes, upstream Hermes, and unrelated workers' files.
- Acceptance: The selected task maps to one exact card with source freshness and a 50-turn budget. The fixture observes owned worker readback and review handoff without a provider call. Run the composed suite and make test.
- Dependencies: none. Ownership: unclaimed.

### PROOF-1

- [ ] Prove evidence survives task completion without closing remaining slices. Goal: PROOF.
- Payoff: keep executed evidence tied to acceptance without replacing acceptance with a claim.
- Sources: [requirement](PRD.md#requirements-and-acceptance), [implementation](repo-docs/scripts/test_goals.py), [verification](test-plan.md#risk-based-scenarios).
- Scope: Add a composed offline goals.py CLI test for task completion, executed evidence, remaining open slices, and rendered coverage.
- Exclusions: real profiles, secrets, live jobs, paid calls, real remotes, upstream Hermes, and unrelated workers' files.
- Acceptance: A partial goal stays non-met while other slices remain. Unsupported met claims downgrade. Exact refs survive fmt/render unchanged. Run repo-docs/scripts/test_goals.py and make test.
- Dependencies: none. Ownership: unclaimed.

### MERGE-1

- [ ] Prove finished-card landing against an isolated bare remote. Goal: MERGE.
- Payoff: gate and integrate finished work safely without replacing acceptance with a claim.
- Sources: [requirement](PRD.md#requirements-and-acceptance), [implementation](fleet-governor/scripts/test_merge_train.py), [verification](test-plan.md#risk-based-scenarios).
- Scope: Add one composed Git fixture for the merge_train.py entry point using temporary repositories, a finished agent branch, and fake board readback.
- Exclusions: real profiles, secrets, live jobs, paid calls, real remotes, upstream Hermes, and unrelated workers' files.
- Acceptance: The gated tree equals the landed local-remote tree. A newly introduced failure prevents landing. Run fleet-governor/scripts/test_merge_train.py and make test. No real push occurs.
- Dependencies: none. Ownership: unclaimed.

### QUESTIONS-1

- [ ] Prove botless question output reaches a fake delivery sink. Goal: QUESTIONS.
- Payoff: relay owner questions while work continues without replacing acceptance with a claim.
- Sources: [requirement](PRD.md#requirements-and-acceptance), [implementation](extras/maintenance/test_question_relay.py), [verification](test-plan.md#risk-based-scenarios).
- Scope: Compose cron-output fixtures, relay output, and a fake delivery sink without credentials or a network client.
- Exclusions: real profiles, secrets, live jobs, paid calls, real remotes, upstream Hermes, and unrelated workers' files.
- Acceptance: One new question set reaches the sink with the profile and defaults context. Repeated output produces no second delivery. Run extras/maintenance/test_question_relay.py and make test.
- Dependencies: none. Ownership: unclaimed.


## Next

### DOCS-2

- [ ] Make documentation drift checks resolve canonical local anchors. Goal: DOCS.
- Payoff: keep core docs and goal backlog current without replacing acceptance with a claim.
- Sources: [requirement](PRD.md#requirements-and-acceptance), [implementation](extras/monitors/repo_docs_monitor.py), [verification](test-plan.md#risk-based-scenarios).
- Scope: Extend extras/monitors/repo_docs_monitor.py and its offline tests for core-doc navigation, valid local anchors, and intentional conditional omissions.
- Exclusions: real profiles, secrets, live jobs, paid calls, real remotes, upstream Hermes, and unrelated workers' files.
- Acceptance: Fixtures distinguish a real broken local link from valid anchors, planned paths, and inapplicable OpenAPI/ADR. Run extras/monitors/test_repo_docs_monitor.py and make test.
- Dependencies: none. Ownership: unclaimed.

### WORKER-2

- [ ] Preserve one original handoff through timeout and foreign-run recovery. Goal: WORKER.
- Payoff: dispatch one bounded goal-linked worker without replacing acceptance with a claim.
- Sources: [requirement](PRD.md#requirements-and-acceptance), [implementation](autogoal/scripts/reconcile.py), [verification](test-plan.md#risk-based-scenarios).
- Scope: Extend autogoal offline reconciliation and handoff tests with delayed readback, an explicit foreign task ID, and mixed run owners.
- Exclusions: real profiles, secrets, live jobs, paid calls, real remotes, upstream Hermes, and unrelated workers' files.
- Acceptance: Retries reconcile the original card without duplicate dispatch. Foreign/unknown run ownership never establishes an owned worker. Run autogoal/scripts/test_reconcile.py and test_goal_handoff.py plus make test.
- Dependencies: none. Ownership: unclaimed.

### PROOF-2

- [ ] Carry source-bound criterion receipts into worker review handoff. Goal: PROOF.
- Payoff: keep executed evidence tied to acceptance without replacing acceptance with a claim.
- Sources: [requirement](PRD.md#requirements-and-acceptance), [implementation](autogoal/scripts/start_goal.py), [verification](test-plan.md#risk-based-scenarios).
- Scope: Extend offline handoff contract fixtures for acceptance-to-artifact/check/source mappings and NOT_CHECKED boundaries.
- Exclusions: real profiles, secrets, live jobs, paid calls, real remotes, upstream Hermes, and unrelated workers' files.
- Acceptance: Generated worker instructions require each criterion receipt and distinguish queued/runtime/delivery proof. Tests prevent unrelated suites from being presented as whole-goal proof. Run autogoal/scripts/test_goal_handoff.py and make test.
- Dependencies: none. Ownership: unclaimed.

### MERGE-2

- [ ] Prove PR-required and submodule integration paths in fixtures. Goal: MERGE.
- Payoff: gate and integrate finished work safely without replacing acceptance with a claim.
- Sources: [requirement](PRD.md#requirements-and-acceptance), [implementation](fleet-governor/scripts/merge_train.py), [verification](test-plan.md#risk-based-scenarios).
- Scope: Extend merge-train regressions with a fake PR transport and local submodule remotes.
- Exclusions: real profiles, secrets, live jobs, paid calls, real remotes, upstream Hermes, and unrelated workers' files.
- Acceptance: PR-required candidates never bypass the PR path. Submodule receipts precede parent candidate integration and failures preserve the original tree. Run the focused merge-train suite and make test.
- Dependencies: none. Ownership: unclaimed.

### QUESTIONS-2

- [ ] Keep malformed relay state from losing independent questions. Goal: QUESTIONS.
- Payoff: relay owner questions while work continues without replacing acceptance with a claim.
- Sources: [requirement](PRD.md#requirements-and-acceptance), [implementation](extras/maintenance/question_relay.py), [verification](test-plan.md#risk-based-scenarios).
- Scope: Add relay recovery behavior and fixtures for invalid state/jobs shapes, one unreadable profile, and another valid profile.
- Exclusions: real profiles, secrets, live jobs, paid calls, real remotes, upstream Hermes, and unrelated workers' files.
- Acceptance: The helper reports recoverable failures without publishing secrets or suppressing an independent valid question. Dry-run does not write state. Run the relay suite and make test.
- Dependencies: none. Ownership: unclaimed.



### SETUP-AUDIO

- [ ] Run opt-in local audio acceptance without downloads. Goal: SETUP.
- Payoff: distinguish working speech recognition from configuration readiness.
- Scope: an already-installed local dependency, cached model, approved non-sensitive
  audio and the expected-phrase check in `extras/install/local_stt.py`.
- Acceptance: The bounded offline transcription exits 0 and reports phrase match.
  Dependency/configuration checks alone do not satisfy this criterion.
- Exclusions: automatic package/model installation, cloud fallback, sensitive audio,
  live profile changes and paid providers.
- Sources: [team setup](docs/team-setup.md#offline-readiness-and-opt-in-audio-check).
- Dependencies: installed local dependency and cached model; absent in this run.
  Ownership: unclaimed. No new owner-only decision is required.

## Blocked / Needs decision

None. No new owner-only question is required for this evidence-backed bootstrap.
[BLOCKERS.md](BLOCKERS.md) is the canonical owner-input ledger.

## Done

### SETUP-1

- [x] Prove default and project provisioning twice with a fake Hermes CLI. Goal: SETUP.
- Payoff: wire profiles and discover canonical shared skills without replacing acceptance with a claim.
- Sources: [requirement](PRD.md#requirements-and-acceptance), [implementation](extras/install/test_install.py), [verification](test-plan.md#risk-based-scenarios).
- Scope: Add a shell-level offline composed fixture for bootstrap.sh and new_profile.sh using a fake runtime/profile/cron CLI, isolated HERMES_HOME, and --no-vendor.
- Exclusions: real profiles, secrets, live jobs, paid calls, real remotes, upstream Hermes, and unrelated workers' files.
- Acceptance: Two runs preserve custom files and do not duplicate jobs. Verify job workdir, delivery, schedule, --no-cron, and both default jobs under --no-cleanup-cron. Run the installer suite and make test.
- Dependencies: none. Ownership: unclaimed.


### SETUP-4

- [x] Prove canonical wrapper relocation and discovery inputs in composed setup fixtures. Goal: SETUP.
- Payoff: extend SETUP-1 job composition to canonical shared-skill inputs without claiming live discovery.
- Sources: [requirement](PRD.md#requirements-and-acceptance), [installer tests](extras/install/test_install.py), [verification](test-plan.md#risk-based-scenarios).
- Scope: Compose real installer helpers with an offline fake CLI. Assert external_dirs and generated wrapper targets after checkout relocation, preserving custom wrappers.
- Exclusions: profile writes outside fixtures, OMH installation, live discovery, paid calls, scheduler changes, commits, and pushes.
- Acceptance: A relocated fixture resolves canonical scripts and discovery configuration. A second run is byte-identical. Run the composed fixture and make test. Live discovery remains separately unverified.
- Dependencies: none. Ownership: unclaimed.


### SETUP-OPTIONS

- [x] Review and close the existing option/adoption fixture slice. Goal: SETUP.
- Scope: `extras/install/test_provisioning.py` covers customized profile adoption,
  SOUL/menu/prune values, preserved fixture credentials/jobs and exact default job arguments.
- Acceptance: Run that suite and the offline gate on the candidate. Fixture proof
  does not establish live scheduler delivery. Independent candidate review and
  the exact staged-source offline gate passed.
- Sources: [test plan](test-plan.md#linux-portability-and-pipeline-continuation).
- Evidence: `python extras/install/test_provisioning.py -v` (11 tests) and
  `make test` (27 offline suites) passed on the curated snapshot.


### SETUP-2

- [x] Make project job wiring and cron instructions agree. Goal: SETUP.
- Scope: Newly created autogoal jobs attach `autogoal_gate.py`; existing jobs are not migrated. OMH remains separately installed.
- Evidence: `PYTHONDONTWRITEBYTECODE=1 TMPDIR=/home/xel/.hermes/cache/scratch python3 extras/install/test_new_profile.py -v` passed all three tests after two expected missing-monitor failures.
- Acceptance: Hourly/15m wiring, exact repo-docs ID linkage, workdir, local delivery, continuity, no-cron, and two-run job idempotency passed. The full offline `make test` run passed.
- Sources: [script](extras/install/new_profile.sh), [fixture](extras/install/test_new_profile.py), [cron notes](extras/cron/README.md).
- Limits: Fake CLI adoption does not prove fresh profile creation, OMH, live discovery, or delivery. SETUP-1 and SETUP-4 were subsequently verified with isolated composed fixtures.

### SETUP-3

- [x] Keep invoking monitor identity authoritative with shared workspaces. Goal: SETUP.
- Scope: Project `HERMES_HOME` wins over coincident workspace matches. Default/root fallback remains.
- Evidence: `PYTHONDONTWRITEBYTECODE=1 TMPDIR=/home/xel/.hermes/cache/scratch python3 extras/monitors/test_autogoal_gate.py -v` passed all four tests after the foreign-busy fixture failed before the fix.
- Acceptance: Foreign busy same-workspace cards cannot suppress the invoking idle project. Own busy cards, terminal-event changes, and root fallback passed. The full offline `make test` run passed.
- Sources: [gate](extras/monitors/autogoal_gate.py), [fixture](extras/monitors/test_autogoal_gate.py).
- Limits: Shared changes affect future invocations. No live profile, job, board, or scheduler state was changed.

### OFFLINE-RECEIPT

- [x] Execute `make test`. Goal: OFFLINE.
- Evidence: PASS, 25 skill contracts and Python/shell syntax; 19 offline suites passed, zero failed; two model-backed suites excluded.
- Scope: the existing local offline runner. No dependency install or model-backed tests.
- Acceptance: all discovered skill contracts, syntax checks, and offline suites pass.
- Sources: [Makefile](Makefile), [runner](scripts/check.py), [test plan](test-plan.md#automated-offline-gate).
- Dependencies: none. Ownership: completed by this documentation pass with the executed receipt in goals.json.

Core documentation repairs were completed in this bootstrap rather than queued as future implementation.
