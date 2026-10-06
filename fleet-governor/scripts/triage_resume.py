#!/usr/bin/env python3
"""Return a triage card to the runnable queue without the dashboard PATCH route.

Uses the shipped kanban_db.specify_triage_task (triage -> todo, body unchanged
unless --body-file is given), then `hermes kanban promote` (todo -> ready).

  triage_resume.py <task_id> [--body-file FILE] [--reason TEXT] [--no-promote]
"""
import argparse, os, subprocess, sys
os.environ.setdefault("HERMES_HOME", os.path.expanduser("~/.hermes"))
sys.path.insert(0, os.path.join(os.environ["HERMES_HOME"], "hermes-agent"))
import hermes_bootstrap  # noqa: F401
from hermes_cli import kanban_db as kb
from hermes_cli import kanban_db_connect as kbc

ap = argparse.ArgumentParser()
ap.add_argument("task_id")
ap.add_argument("--body-file")
ap.add_argument("--reason", default="governor: resume from triage")
ap.add_argument("--no-promote", action="store_true")
a = ap.parse_args()
body = open(a.body_file).read() if a.body_file else None
with kbc.connect_closing() as conn:
    ok = kb.specify_triage_task(conn, a.task_id, body=body, author="fleet-governor")
if not ok:
    sys.exit(f"{a.task_id}: not in triage (no change)")
print(f"{a.task_id}: triage -> todo")
subprocess.run(["hermes", "kanban", "comment", a.task_id, a.reason], capture_output=True)
with kbc.connect_closing() as conn:
    status = conn.execute("SELECT status FROM tasks WHERE id = ?", (a.task_id,)).fetchone()[0]
if status == "todo" and not a.no_promote:
    r = subprocess.run(["hermes", "kanban", "promote", a.task_id], capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip())
    sys.exit(r.returncode)
print(f"{a.task_id}: now {status}")
