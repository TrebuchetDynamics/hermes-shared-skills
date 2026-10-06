# Cron templates

`install.sh --cron` creates these jobs with `hermes -p <profile> cron create`. Placeholders:
`{profile}`, `{workspace}` (absolute repo path), `{repo_docs_job_id}` (filled after the repo-docs job exists).

| Job | Schedule | Skill | Monitor | Notes |
|---|---|---|---|---|
| `repo-docs-on-change` | every 10 min, staggered | `repo-docs` | `repo_docs_monitor.py` | the model runs only on commits, finished cards (30 min debounce), drift, goals.json validation changes, or daily |
| `scratch-cleanup-weekly` (default profile) | `17 4 * * 0` | none (`--no-agent --script scratch_cleanup.py`) | — | deletes worker scratch older than 7 days; silent when nothing to delete |
| `autogoal-hourly` | hourly (15 min for busy profiles) | `autogoal` | none | `context_from: self` so it sees its previous report |

Delivery is whatever you pass as `--deliver` (e.g. `telegram:<chat_id>`). Nothing here stores chat IDs.
