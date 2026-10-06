#!/usr/bin/env python3
"""Delete stale fleet-worker scratch so agents cannot fill the disk.

Targets (top-level folders only, untouched for --days, default 7):
- ~/.cache/<name> whose name matches a worker-scratch pattern (w20*, t_<card>*, qa-*, mb-*,
  megabot-*, rrl-*, hermes-wing-*, server-polyrover-*, *-target, ...). App and tool caches never match.
- $HERMES_HOME/cache/scratch/<anything> (the sanctioned per-card scratch root).
A folder is skipped while any process has its cwd inside it. Prints a summary only when something
was deleted (empty output = silent cron run).

  scratch_cleanup.py [--days 7] [--dry-run]
"""
import argparse
import os
import re
import shutil
import time
from pathlib import Path

HERMES_HOME = Path(os.environ.get('HERMES_HOME') or Path.home() / '.hermes')
CACHE = Path.home() / '.cache'
PATTERN = re.compile(r'^(w[0-9]+[a-z0-9-]*|t_[0-9a-f]{8}([-a-z]*)?|t[0-9a-f]{7,}[-a-z0-9]*|qa-.+|mb-.+|mbval-.+|'
                     r'megabot-.+|rrl-.+|server-polyrover-.+|polyrover-upstream-target|hermes-wing-.+|'
                     r'arenaton-v[0-9].*|v[0-9]+[a-z0-9]*|bughunt.*|val-.+|valmut-.+|[a-z0-9-]+-target)$')
KEEP = {'megabot-local-traindb'}  # live data, never touch


def newest_mtime(path, limit=20000):
    """Latest mtime inside path (bounded walk), so an old folder with fresh files is kept."""
    latest = path.stat().st_mtime
    for n, (root, dirs, files) in enumerate(os.walk(path)):
        for f in files[:200]:
            try:
                latest = max(latest, (Path(root) / f).stat().st_mtime)
            except OSError:
                pass
        if n > limit:
            break
    return latest


def busy_paths():
    cwds = set()
    for proc in Path('/proc').iterdir():
        if proc.name.isdigit():
            try:
                cwds.add(os.readlink(proc / 'cwd'))
            except OSError:
                pass
    return cwds


def size_gb(path):
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                total += (Path(root) / f).lstat().st_size
            except OSError:
                pass
    return total / 1e9


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=float, default=7)
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    cutoff = time.time() - a.days * 86400
    candidates = []
    if CACHE.is_dir():
        candidates += [p for p in CACHE.iterdir() if p.is_dir() and not p.is_symlink()
                       and PATTERN.match(p.name) and p.name not in KEEP]
    scratch = HERMES_HOME / 'cache' / 'scratch'
    if scratch.is_dir():
        candidates += [p for p in scratch.iterdir() if p.is_dir() and not p.is_symlink()]
    busy = busy_paths()
    removed, freed, failed = [], 0.0, []
    for p in sorted(candidates):
        try:
            if newest_mtime(p) > cutoff or any(c == str(p) or c.startswith(str(p) + '/') for c in busy):
                continue
            gb = size_gb(p)
            if not a.dry_run:
                shutil.rmtree(p)
            removed.append(f'{p} ({gb:.1f} GB)'); freed += gb
        except OSError as e:
            failed.append(f'{p}: {e.strerror}')
    if removed or failed:
        verb = 'would delete' if a.dry_run else 'deleted'
        print(f'scratch cleanup: {verb} {len(removed)} folder(s), {freed:.1f} GB (older than {a.days:g} days)')
        for line in removed[:20]:
            print(f'  - {line}')
        for line in failed[:10]:
            print(f'  ! {line}')


if __name__ == '__main__':
    main()
