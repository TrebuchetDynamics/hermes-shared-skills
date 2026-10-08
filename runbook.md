# Local operations runbook

## Scope and prerequisites

This runbook covers the shared checkout and profile wiring. It does not describe an invented hosted service.
Use an installed Hermes CLI, a valid profile, Python 3.12+, Bash, and the YAML runtime dependency.
The default checkout is `~/.hermes/shared-skills`. Non-default locations need careful template and wrapper inspection.
Profiles and credentials remain outside this repository.

## Safe verification

From the checkout, run `make test`. Expect contract/syntax PASS and no failed offline suites.
Run `python3 repo-docs/scripts/goals.py validate .`. Expect `ok`.
Run `python3 repo-docs/scripts/goals.py next .` to inspect the next eligible task without dispatching it.
A collector result or a queued handoff is not evidence of runtime completion.

## Wiring an existing profile

Prerequisite: separate authorization to change the named profile configuration.
Inspect options before running the installer. For a preview:

```bash
./install.sh --profiles <profile> --dry-run
```

The preview reports intended changes. It does not prove live skill discovery.
For bounded wiring without the bootstrap approval/pruning options:

```bash
./install.sh --profiles <profile>
```

The helper preserves custom wrappers and refreshes recognized generated wrappers.
Inspect the exact profile afterward. Verify external skill discovery with:

```bash
hermes -p <profile> skills list
```

Then inspect a fresh session's discovery result. Existing sessions may retain cached content.
Do not restart healthy workers solely to distribute wording.

## Optional STT setup

Use the explicit-home preview and apply procedure in [team setup](docs/team-setup.md).
Preserve a private configuration backup first. The helper does not install local speech
dependencies or test recognition. On failure, inspect the three STT keys before retrying;
the multi-command update is not atomic. Do not run it concurrently with other config writers.

## Default and project setup

`bootstrap.sh` changes default-profile settings, disables approval gates, prunes skills, installs vendors, and creates jobs.
These effects need explicit operational authorization. They were not executed in this docs pass.
Use `--dry-run` to inspect intended default-profile changes. Vendor sync is skipped in that mode.
`--no-vendor` skips vendors. `--no-cleanup-cron` suppresses both default job creations in the current script.
OMH is optional and must be installed through its own instructions.

For an authorized project setup, the workspace must already exist:

```bash
./extras/install/new_profile.sh <profile> <workspace> --no-cron
```

This creates or adopts a profile and sets its workspace. It still changes approval/pruning settings through installer flags.
Without `--no-cron`, it creates repo-docs and autogoal jobs. Delivery defaults to local.
A configured delivery destination is not proof that the operator received a message.
Verify separately with `hermes -p <profile> cron list` after an authorized setup.
`install.sh` does not create cron jobs. See the [cron notes](extras/cron/README.md) for creation paths.
New autogoal jobs attach `autogoal_gate.py`. Existing jobs are not migrated by rerunning setup.
Verify their monitor configuration separately. Project `HERMES_HOME` identifies the gated profile, not a coincident workspace.
Default/root invocations use workspace matching. Shared gate changes affect future invocations without a profile rewrite or restart.
If the fleet Kanban database is absent, the gate emits `uninitialized-board` with a changing minute and lets the picker reconcile or initialize state. The monitor creates no database. Corrupt, dangling-linked or inaccessible existing state remains a monitor error; do not interpret it as an idle profile.

## Diagnosis and recovery

| Symptom | Inspect | Safe response and limit |
| --- | --- | --- |
| Missing catalog entry | Exact profile `skills.external_dirs`, disabled skills, fresh discovery | Repair only authorized profile settings. A disk hash cannot establish loaded content. |
| Wrapper points to an old checkout | Exact generated wrapper and target path | Reinstall the authorized profile. Custom wrappers are preserved and need separate owner-scoped repair. |
| Handoff times out | Exact journal/card/run through [reconciliation](autogoal/references/state-and-recovery.md) | Reconcile before retrying. Do not duplicate a worker or clear a live claim. |
| Ledger validation fails | `goals.py validate` output and source requirements | Fix the ledger through the helper, then render. Do not manufacture passing evidence. |
| Merge train fails | Exact candidate and baseline failure receipts | Use the [merge-train procedure](fleet-governor/references/merge-train.md). Do not push a failed tree. |
| Questions are not delivered | Local cron output, relay configuration, tested transport receipt | Parsing tests do not prove delivery. Keep redacted evidence outside tracked docs. |
| Shared inventory is UNKNOWN | Supported layout, configuration, path safety | Preserve uncertainty. Do not classify an unsupported resolution as a missing skill. |

## Updates, rollback, and data protection

Use the scoped git-pull-merge workflow to update canonical files while preserving dirty work.
Inspect the final diff and run the offline gate before distribution.
There is no universal installer undo command. Reinstallation does not remove old SOUL snippets or restore prior approvals.
Before authorized profile changes, preserve a private backup of the exact affected configuration and custom wrappers.
Keep backups out of this checkout. Restore only the selected profile with separate authorization.
Do not run `git reset`, clean, restore, or scheduler operations as a documentation check.
Recovery, restore, and live delivery were not exercised by this bootstrap.
