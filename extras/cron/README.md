# Cron templates

[`extras/install/new_profile.sh`](../install/new_profile.sh) creates the two project jobs unless `--no-cron` is used.
[`bootstrap.sh`](../../bootstrap.sh) creates the default merge and cleanup jobs unless `--no-cleanup-cron` is used.
`install.sh` wires profiles and wrappers only. It has no `--cron` option.
The question-relay job needs separate authorized creation in a profile with a configured Telegram bot.

Prompt placeholders: `{profile}`, `{workspace}` (absolute repo path), and `{repo_docs_job_id}` (filled after the repo-docs job exists).

| Job | Schedule | Skill | Monitor | Notes |
|---|---|---|---|---|
| `repo-docs-on-change` | every 10 min, staggered | `repo-docs` | `repo_docs_monitor.py` | the model runs only on commits, finished cards (30 min debounce), drift, goals.json validation changes, or daily |
| `merge-train-daily` (default profile) | `30 3 * * *` | none (`--no-agent --script merge_train_daily.py`) | — | lands verified worktree work on each repo's main; report in `~/.hermes/fleet-governor/merge-train/` |
| `scratch-cleanup-weekly` (default profile) | `17 4 * * 0` | none (`--no-agent --script scratch_cleanup.py`) | — | deletes worker scratch older than 7 days; silent when nothing to delete |
| `question-relay` (one profile that has a Telegram bot) | `17 * * * *` | none (`--no-agent --script question_relay.py`) | — | relays new owner questions from profiles with no bot (default, or any without `TELEGRAM_BOT_TOKEN`), once per question set, at most every 6 h per profile; silent otherwise |
| `autogoal-hourly` | hourly (15 min for busy profiles) | `autogoal` | `autogoal_gate.py` | `--continuity` preserves prior occurrence context; verify configured jobs separately |

Autogoal policy permits only the busy-card gate, not the fingerprint/change-only monitor.
The installer installs the wrapper and attaches it to newly created autogoal jobs.
Existing jobs are skipped by name, not migrated. Verify their configured monitors separately.
Project `HERMES_HOME` identifies the gated profile, even when workspaces coincide.
Default/root invocations retain workspace matching as a fallback.

Delivery is whatever you pass as `--deliver` (e.g. `telegram:<chat_id>`). Nothing here stores chat IDs.
