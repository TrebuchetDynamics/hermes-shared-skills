#!/usr/bin/env python3
"""Cheap change gate for autogoal cron jobs (Hermes monitor_script).

Prints a STABLE snapshot; the cron scheduler skips the LLM run when it is
byte-identical to the last agent-triggering run. Change sources: repo HEAD, dirty
set (only when no worker is running), this profile's non-done cards and latest run
outcome, BLOCKERS.md/TODO.md, and the UTC date (one guaranteed run per day).

Usage: autogoal_monitor.py <profile> <workspace>    (default profile: --fleet)
"""
import hashlib, os, json, os, sqlite3, subprocess, sys, time
from pathlib import Path

DB = Path(os.environ.get('HERMES_HOME') or Path.home() / '.hermes') / "kanban.db"


def sh(args, cwd):
    try:
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=20).stdout
    except Exception as e:  # noqa: BLE001
        return f"ERR {type(e).__name__}"


def h(text):
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def fhash(path):
    try:
        return h(Path(path).read_text(errors="replace"))
    except OSError:
        return "absent"


def cards(where, params):
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10)
    rows = con.execute(
        "SELECT t.id, t.assignee, t.status, t.workspace_path, "
        " (SELECT r.id || ':' || r.status || ':' || COALESCE(r.outcome,'') FROM task_runs r "
        "  WHERE r.task_id = t.id ORDER BY r.id DESC LIMIT 1) "
        f"FROM tasks t WHERE t.status NOT IN ('done','archived') AND {where} ORDER BY t.id",
        params).fetchall()
    con.close()
    return rows


def profile_snapshot(profile, ws):
    out = [f"date {time.strftime('%Y-%m-%d', time.gmtime())}"]
    rows = cards("t.assignee = ?", (profile,))
    running = any(r[2] == "running" for r in rows)
    for r in rows:
        out.append(f"card {r[0]} {r[2]} run={r[4]}")
    out.append("head " + sh(["git", "rev-parse", "HEAD"], ws).strip())
    # While a worker runs, its edits would retrigger the picker every tick; ignore dirt then.
    out.append("dirty " + ("(worker running)" if running else h(sh(["git", "status", "--porcelain"], ws))))
    out.append("blockers " + fhash(Path(ws) / "BLOCKERS.md"))
    out.append("todo " + fhash(Path(ws) / "TODO.md"))
    return out


def fleet_snapshot():
    # Coarse 6-hour bucket so the governor still checks in a few times a day.
    out = [f"bucket {time.strftime('%Y-%m-%d', time.gmtime())} {time.gmtime().tm_hour // 6}"]
    for r in cards("1 = 1", ()):
        out.append(f"card {r[0]} {r[1]} {r[2]} run={r[4]}")
    root = Path(os.environ.get('HERMES_HOME') or Path.home() / '.hermes') / "profiles"
    # Skip hidden folders (e.g. profiles/.deleted/ left by `hermes profile delete`) and non-profiles.
    for prof in sorted(p.name for p in root.iterdir()
                       if p.is_dir() and not p.name.startswith(".") and (p / "config.yaml").is_file()):
        cfg = (root / prof / "config.yaml").read_text(errors="replace")
        ws = next((l.split("cwd:", 1)[1].strip() for l in cfg.splitlines() if l.strip().startswith("cwd:")), "")
        out.append(f"blockers {prof} {fhash(Path(ws) / 'BLOCKERS.md') if ws else 'n/a'}")
    return out


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--fleet":
        print("\n".join(fleet_snapshot()))
    elif len(sys.argv) == 3:
        print("\n".join(profile_snapshot(sys.argv[1], sys.argv[2])))
    else:
        sys.exit(__doc__)
