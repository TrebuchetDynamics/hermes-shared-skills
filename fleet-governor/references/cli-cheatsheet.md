# Kanban / fleet CLI cheatsheet (Hermes 0.21.x)

Use these instead of `--help`, schema dumps or reading hermes-agent source.

## Read
- `hermes kanban list --json [--assignee P] [--status S]` — statuses: triage todo
  scheduled ready running blocked review done archived. Pipe through `jq`; the
  whole-board list is large, so filter with `--assignee`/`--status` before parsing.
- `hermes kanban show <id> --json` — task + comments + events.
- `hermes kanban runs <id> --json` — run history (status, outcome, summary, error).
- `hermes kanban stats` — counts per status/assignee.
- Fleet snapshot: `python3 ~/.hermes/shared-skills/fleet-status/scripts/status.py`.

## Write
- triage → ready: `~/.hermes/shared-skills/fleet-governor/scripts/triage_resume.py <id> [--body-file F] [--reason TEXT]`
  (`kanban promote` only accepts todo/blocked; `kanban specify` rewrites the body via LLM — avoid).
- blocked → ready: `hermes kanban unblock <id>`; todo/blocked → ready: `hermes kanban promote <id>`.
- Park with backoff: `hermes kanban schedule <id> "<reason/timing>"`.
- Block: `hermes kanban block <id> --kind {dependency|needs_input|capability|transient} "<reason>"`.
  Only `needs_input` and `capability` are for a human; `dependency` waits on parents.
  Repeated same-kind re-blocks route to triage automatically.
- Edit body/title: `hermes kanban edit <id> ...`; comment: `hermes kanban comment <id> "..."`.
- Model override: `hermes kanban set-model <id> ...`; reassign: `hermes kanban reassign <id> <profile>`.
- Archive (≠ done): `hermes kanban archive <id>`.

## Schema (read-only sqlite3, only if the CLI cannot answer)
`~/.hermes/kanban.db`:
- `tasks(id, title, body, assignee, status, priority, created_at, started_at,
  completed_at, workspace_kind, workspace_path, consecutive_failures,
  last_failure_error, current_run_id, skills, model_override, result)`
- `task_runs(id, task_id, profile, status, started_at, ended_at, outcome, summary, error, metadata)`
- `task_events`, `task_comments`, `task_links`.
There is no `workspace`, `updated_at`, `runs`, `events` or `jobs` column/table.
Profile directories may contain an empty `kanban.db` — the shared board is
`~/.hermes/kanban.db`.

## Cron
- `hermes cron list`, `hermes cron edit <id> ...`, `hermes cron runs <id>`.
- Per-profile commands: `hermes -p <profile> cron ...`.
