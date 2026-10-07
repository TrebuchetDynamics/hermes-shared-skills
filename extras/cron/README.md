# Cron templates

`install.sh --cron` creates these jobs with `hermes -p <profile> cron create`. Placeholders:
`{profile}`, `{workspace}` (absolute repo path), `{repo_docs_job_id}` (filled after the repo-docs job exists).

| Job | Schedule | Skill | Monitor | Notes |
|---|---|---|---|---|
| `repo-docs-on-change` | every 10 min, staggered | `repo-docs` | `repo_docs_monitor.py` | the model runs only on commits, finished cards (30 min debounce), drift, goals.json validation changes, or daily |
| `merge-train-daily` (default profile) | `30 3 * * *` | none (`--no-agent --script merge_train_daily.py`) | — | lands verified worktree work on each repo's main; report in `~/.hermes/fleet-governor/merge-train/` |
| `scratch-cleanup-weekly` (default profile) | `17 4 * * 0` | none (`--no-agent --script scratch_cleanup.py`) | — | deletes worker scratch older than 7 days; silent when nothing to delete |
| `question-relay` (one profile that has a Telegram bot) | `17 * * * *` | none (`--no-agent --script question_relay.py`) | — | relays new owner questions from profiles with no bot (default, or any without `TELEGRAM_BOT_TOKEN`), once per question set, at most every 6 h per profile; silent otherwise |
| `autogoal-hourly` | hourly (15 min for busy profiles) | `autogoal` | `autogoal_gate.py` (skips only while this profile's card is running/ready and nothing finished) | `context_from: self` so it sees its previous report |

Delivery is whatever you pass as `--deliver` (e.g. `telegram:<chat_id>`). Nothing here stores chat IDs.
