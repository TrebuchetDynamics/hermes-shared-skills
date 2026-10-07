#!/usr/bin/env python3
"""Relay new owner questions from profiles whose cron jobs deliver locally (no Telegram bot).

Run as a no-agent cron job in a profile that has a bot; stdout is delivered verbatim and empty
stdout sends nothing. Each question block is sent once (hash kept in a state file).

  question_relay.py [--profiles default,abstra,portal-crazy] [--since-hours 24] [--cooldown-hours 6] [--dry-run]

Profiles default to every profile without a TELEGRAM_BOT_TOKEN in its .env.
"""
import argparse
import hashlib
import json
import os
import re
import time
from pathlib import Path

ROOT = Path(os.environ.get('HERMES_HOME') or Path.home() / '.hermes')
ROOT = ROOT.parents[1] if ROOT.parent.name == 'profiles' else ROOT
STATE = ROOT / 'cache' / 'question_relay.json'
HEAD = re.compile(r'^\W*(questions?\b.*|### question.*)$', re.I)
NONE = re.compile(r'\bnone\b', re.I)


def home(name):
    return ROOT if name == 'default' else ROOT / 'profiles' / name


def botless():
    names = ['default'] + sorted(p.name for p in (ROOT / 'profiles').iterdir()
                                 if p.is_dir() and not p.name.startswith('.') and (p / 'config.yaml').exists())
    return [n for n in names if not re.search(r'^TELEGRAM_BOT_TOKEN=\S', (home(n) / '.env').read_text()
                                              if (home(n) / '.env').exists() else '', re.M)]


def job_names(name):
    try:
        jobs = json.loads((home(name) / 'cron' / 'jobs.json').read_text())
    except (OSError, ValueError):
        return {}
    jobs = jobs.get('jobs', jobs) if isinstance(jobs, dict) else jobs
    return {j.get('id'): j.get('name', j.get('id')) for j in jobs if isinstance(j, dict)}


def questions(text):
    """The Questions block of a run's response, or None."""
    resp = text.split('## Response', 1)
    if len(resp) < 2:
        return None
    lines = resp[1].strip().splitlines()
    for i, line in enumerate(lines):
        m = HEAD.match(line.strip())
        if not m:
            continue
        block = [line.strip()]
        for nxt in lines[i + 1:]:
            if nxt.startswith('#') and not HEAD.match(nxt.strip()):
                break
            block.append(nxt.rstrip())
        body = '\n'.join(block).strip()
        first = re.sub(r'^\W*questions?[^:]*:?\**', '', block[0], flags=re.I).strip()
        if len(block) == 1 and (not first or NONE.search(first[:40])):
            return None
        if NONE.match(first.strip('* ')) and len(block) == 1:
            return None
        return body
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--profiles', default='')
    ap.add_argument('--since-hours', type=float, default=24)
    ap.add_argument('--cooldown-hours', type=float, default=6)
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    try:
        state = json.loads(STATE.read_text())
    except (OSError, ValueError):
        state = {}
    seen = set(state.get('seen', []))
    cutoff = time.time() - a.since_hours * 3600
    out = []
    sent = state.get('sent', {})
    for name in [p for p in a.profiles.split(',') if p] or botless():
        names = job_names(name)
        files = sorted((f for f in (home(name) / 'cron' / 'output').glob('*/*.md') if f.stat().st_mtime >= cutoff),
                       key=lambda f: f.stat().st_mtime, reverse=True)
        found = next(((f, q) for f in files for q in [questions(f.read_text(errors='replace'))] if q), None)
        if not found:
            continue
        f, q = found
        key = hashlib.sha256(re.sub(r'[^a-z]+', '', q.lower())[:400].encode()).hexdigest()[:16]
        if key in seen or time.time() - sent.get(name, 0) < a.cooldown_hours * 3600:
            continue  # same questions, or this profile was relayed recently (reworded repeats)
        seen.add(key)
        sent[name] = time.time()
        out.append(f'[{name} · {names.get(f.parent.name, f.parent.name)}]\n{q[:1500]}')
    if out:
        print('Owner questions from profiles without a Telegram bot (defaults already applied).\n'
              f'Answer in that profile: hermes -p <profile> chat\n\n' + '\n\n'.join(out))
    if not a.dry_run:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps({'seen': sorted(seen)[-500:], 'sent': sent}))


if __name__ == '__main__':
    main()
