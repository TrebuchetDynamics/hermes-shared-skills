#!/usr/bin/env python3
"""Busy gate for autogoal cron jobs (Hermes monitor_script).

Skips the model only while this profile's worker is busy; it never skips an idle profile.
The cron scheduler skips the run when this output is byte-identical to the last
agent-triggering run, so:
- No running or ready card for this profile (idle): the output includes the current
  minute, so it always changes and the picker runs and dispatches work.
- A card is running or ready (busy): the output is the stable set of card IDs, their
  latest run IDs and the newest terminal event for the profile, plus a 2-hour bucket.
  It changes only when a card finishes, blocks, or is handed to review (reconcile and
  report), or every 2 hours as a safety check.

The profile is the one whose terminal.cwd matches this job's workdir (the cwd).
"""
import os
import sqlite3
import subprocess
import time
from pathlib import Path

HOME = Path(os.environ.get('HERMES_HOME') or Path.home() / '.hermes')
# Monitors run with the profile's HERMES_HOME; kanban.db lives in the fleet root.
ROOT = HOME.parents[1] if HOME.parent.name == 'profiles' else HOME


def repo_root(path):
    p = subprocess.run(['git', '-C', str(path), 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
    return Path(p.stdout.strip()).resolve() if p.returncode == 0 else Path(path).resolve()


def profile_for(cwd):
    here = repo_root(cwd)
    for cfg in sorted((ROOT / 'profiles').glob('*/config.yaml')):
        if cfg.parent.name.startswith('.'):
            continue
        for line in cfg.read_text(errors='replace').splitlines():
            if line.strip().startswith('cwd:'):
                ws = line.split('cwd:', 1)[1].strip().strip('"\'')
                if ws and repo_root(ws) == here:
                    return cfg.parent.name
    return None


def main():
    profile = profile_for(Path.cwd())
    now = time.gmtime()
    if not profile:
        print(f'unknown-profile {Path.cwd()} {time.strftime("%Y-%m-%dT%H:%M", now)}')  # always run
        return
    db = sqlite3.connect(f'file:{ROOT / "kanban.db"}?mode=ro', uri=True, timeout=10)
    live = db.execute("SELECT id, status, COALESCE(current_run_id, '') FROM tasks "
                      "WHERE assignee = ? AND status IN ('running', 'ready') ORDER BY id", (profile,)).fetchall()
    last_terminal = db.execute(
        "SELECT COALESCE(MAX(e.id), 0) FROM task_events e JOIN tasks t ON t.id = e.task_id "
        "WHERE t.assignee = ? AND e.kind IN ('completed', 'blocked', 'review_requested', 'crashed', "
        "'changes_requested')", (profile,)).fetchone()[0]
    if not live:
        print(f'idle {profile} {time.strftime("%Y-%m-%dT%H:%M", now)}')
        return
    print(f'busy {profile}')
    for tid, status, run in live:
        print(f'  card {tid} {status} run={run}')
    print(f'terminal-event {last_terminal}')
    print(f'bucket {time.strftime("%Y-%m-%d", now)} {now.tm_hour // 2}')


if __name__ == '__main__':
    main()
