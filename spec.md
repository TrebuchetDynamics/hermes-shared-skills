# Technical specification

## Boundary and current design

The package contains Markdown skills, Python helpers, shell installers, and cron templates.
Hermes supplies skill discovery, profiles, model execution, native Kanban, and message delivery.
There is no repository-owned HTTP API. OpenAPI is not applicable.
No new architectural decision was selected in this documentation pass.
The observed design belongs here, not in a reconstructed Accepted ADR.

## Components

| Component | Input | Output and responsibility |
| --- | --- | --- |
| [repo-docs](repo-docs/SKILL.md) | Repository intent, current source, allowed verification | Applicable core docs, goal ledger, task backlog, owner questions |
| [goals.py](repo-docs/scripts/goals.py) | Version 1 goal ledger | Canonical JSON, validation, next eligible task, generated coverage block |
| [autogoal](autogoal/SKILL.md) | Ledger, profile journal, fresh source evidence | One bounded contract and native goal-mode handoff |
| [start_goal.py](autogoal/scripts/start_goal.py) | Contract, workspace, assignee, source snapshot | Exact card readback and profile-local handoff receipt |
| [reconcile.py](autogoal/scripts/reconcile.py) | Exact handoff receipt or task ID | Typed readback without rewriting the journal |
| [fleet governor](fleet-governor/SKILL.md) | Cards, claims, blockers, integration results | Coordination within native lifecycle authority |
| [merge train](fleet-governor/references/merge-train.md) | Finished branches and candidate work | Isolated gate, permitted integration, failure receipt |
| [install helper](extras/install/install_helper.py) | Explicit profiles and options | YAML configuration, generated wrappers, optional SOUL/menu settings |
| [offline runner](scripts/check.py) | First-party files and standalone suites | Contract/syntax results and per-suite exit results |

## Ledger and task flow

`goals.json` has `version: 1`, `goals`, and `tasks`.
Goals carry `id`, `title`, `source`, `status`, `priority`, `evidence`, `tasks`, and `depends_on`.
Statuses are `met`, `partial`, `unmet`, and `unverified`.
Evidence has `kind`, `ref`, and `result`. `ran_at` is optional.
A `met` goal must contain executed/pass evidence. Formatting downgrades unsupported met claims.
This structural rule does not assess the relevance or freshness of the cited check.

Tasks carry `id`, `goal`, `title`, `status`, `section`, and `depends_on`.
The picker sorts eligible tasks by section, goal priority, status rank, and task ID.
Task and goal dependencies must be satisfied. A met goal is not eligible.
Rendering replaces only the marked Goal coverage block in `TODO.md`.
Full task scope and acceptance remain outside that generated block.

The picker creates a contract. `start_goal.py` validates required fields and source freshness.
It checks existing cards before dispatch. The native worker budget is 50 turns.
A queued receipt is not a running worker. Reconcile the original card after a timeout.
Review handoff and review approval are separate states.
See [state and recovery](autogoal/references/state-and-recovery.md) for supported schemas and recovery boundaries.

## Setup and compatibility

`bootstrap.sh` invokes `install.sh` for the default profile with menu, SOUL, approval, and pruning options.
It installs pinned vendors unless `--no-vendor` is used.
Unless suppressed, it creates default-profile merge-train and scratch-cleanup jobs.
`--no-cleanup-cron` currently suppresses both of these job creations.

`install.sh` resolves Hermes' runtime command and invokes the YAML helper.
The helper appends this checkout to `skills.external_dirs` and preserves configuration comments.
It refreshes only recognized generated wrappers and retains custom wrappers.
SOUL snippets are appended by missing heading, not replaced in place.
`--allow-all` changes approval and protected-instruction settings. It is not a harmless discovery option.

`extras/install/new_profile.sh` creates or adopts a project profile, sets `terminal.cwd`, and wires it.
It creates project jobs unless `--no-cron` is given.
OMH remains separately installed. Vendor installation is not OMH provisioning.
Fresh discovery needs its own receipt. Existing sessions can retain cached skill bodies.

`new_profile.sh` attaches `autogoal_gate.py` to newly created hourly and 15-minute autogoal jobs.
Existing jobs are skipped by name without migration. Workdir, delivery, continuity, and repo-docs linkage are retained.
The gate uses project `HERMES_HOME` as authoritative identity before workspace matching.
Default/root invocations retain workspace inference. A foreign busy card in the same workspace cannot gate a project invocation.
See the [cron template notes](extras/cron/README.md) for job wiring.

The optional `extras/install/configure_stt.py` configures local/off STT for an explicit
existing home through the Hermes CLI. Preview is non-mutating. Apply verifies each setting
with JSON readback and selects provider/model before enabling STT. Calls time out after
30 seconds, with no automatic retries. Partial application is possible; no audio or
dependency installation occurs. See [team setup](docs/team-setup.md).

## Failure and security behavior

- Invalid ledger JSON or unsupported schemas fail rather than establish completion.
- Reconciliation rejects wrong card IDs, assignees, malformed receipts, and explicit foreign run task IDs.
  `card_run_observed` records any returned run. `run_profile` and `run_ownership` separate current, other, and unknown ownership.
  `worker_observed` is true only when the latest run has a known owner equal to the requested profile.
  Current CLI readback omits per-run `task_id`. An absent field does not establish independently checked run identity.
- Fleet inventory examines only supported local/external layouts. Ambiguous configuration and unsafe paths remain UNKNOWN.
- Inventory hashes prove inspected files only. They do not prove runtime discovery or all precedence tiers.
- Keep credentials in profile-local storage. Do not commit provider or delivery settings with real secrets.
- Test fixtures and fake transports cannot establish live provider execution, Telegram delivery, or protected remote integration.

## Change and rollout boundaries

Update canonical skill files through scoped repository work. Verify a fresh session after distribution.
Do not restart healthy workers or rewrite prior sessions merely to replace cached wording.
Installer and scheduler changes need fixture coverage before an authorized staging run.
No database migration, production rollout, or release was performed by this bootstrap.
