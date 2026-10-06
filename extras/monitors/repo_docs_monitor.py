#!/usr/bin/env python3
"""Change gate for repo-docs cron jobs (Hermes monitor_script).

Runs in the job's workdir and prints a STABLE snapshot. The cron scheduler skips
the LLM run when it is byte-identical to the last agent-triggering run, so the model
runs only on real events:
- a new commit on the checked-out branch;
- a finished card (an `agent/*` branch tip moved);
- a committed doc change (part of HEAD) and the goals.json validation result. Uncommitted
  doc edits are ignored, so repo-docs' own working-tree edits never re-trigger it;
- a change in deterministic doc drift in the *current-state* docs (README, PRD,
  spec, test plan, runbook, CONTRIBUTING, AGENTS/CLAUDE): broken local links or
  backticked repo paths. Dated plans, audits, CHANGELOG and TODO.md legitimately
  name removed or not-yet-created files, so they are not drift-checked;
- entries listed in `.repo-docs-drift-ignore` (one drift line per line, e.g.
  `docs/CLAUDE.md: path docs/AGENTS.md`) are accepted as intentional and not reported;
- the UTC date (one guaranteed run per day).
In-progress source edits (dirty non-doc files) are ignored on purpose.
"""
import hashlib
import os
import re
import subprocess
import sys
import time
from pathlib import Path

GOALS_PY = Path(__file__).resolve().parents[2] / 'repo-docs/scripts/goals.py'
MAX_DOCS = 300
CURRENT_STATE = re.compile(r'(^|/)(readme|prd|spec|test-plan|runbook|contributing|agents|claude|architecture)\.md$', re.I)
LINK = re.compile(r'\[[^\]]*\]\(([^)\s]+)\)')
TICKED = re.compile(r'`([\w.\-]+(?:/[\w.\-]+)+)`')


def sh(*args, cwd=None):
    try:
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=30).stdout
    except Exception as e:  # noqa: BLE001
        return f'ERR {type(e).__name__}'


def h(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode()).hexdigest()[:12]


root = sh('git', 'rev-parse', '--show-toplevel').strip()
if not root:
    print(f'not-a-git-repo {Path.cwd()}')
    raise SystemExit(0)
R = Path(root)

import fnmatch
tracked = sh('git', '-C', root, 'ls-tree', '-r', '--name-only', 'HEAD').splitlines()
def is_doc(p):
    top = '/' not in p
    return ((top and (p.endswith('.md') or p == 'goals.json' or fnmatch.fnmatch(p, 'openapi*.y*ml')))
            or (p.startswith(('docs/', 'adr/')) and p.endswith('.md')))


docs = sorted(p for p in tracked if is_doc(p))[:MAX_DOCS]


def committed(path):
    try:
        return subprocess.run(['git', '-C', root, 'show', f'HEAD:{path}'], capture_output=True, timeout=20).stdout
    except Exception:  # noqa: BLE001
        return b''


ignore_file = R / '.repo-docs-drift-ignore'
ignored = {l.strip() for l in ignore_file.read_text().splitlines() if l.strip() and not l.startswith('#')} if ignore_file.exists() else set()

# Check committed docs against the same committed tree. Working-tree source
# deletions/creations must not retrigger this gate while a worker is editing.
committed_dirs = {'.'}
for path in tracked:
    committed_dirs.update(str(parent) for parent in Path(path).parents)
committed_paths = set(tracked) | committed_dirs
committed_symlinks = {}
for entry in sh('git', '-C', root, 'ls-tree', '-r', '-z', 'HEAD').split('\0'):
    metadata, sep, path = entry.partition('\t')
    if sep and metadata.startswith('120000 '):
        committed_symlinks[path] = os.fsdecode(committed(path))
top_dirs = {p.split('/', 1)[0] for p in tracked if '/' in p and not p.startswith('.')}


def target_exists(path, *, directory=False):
    # Resolve components from HEAD, never from mutable working-tree symlinks.
    try:
        pending = list(path.absolute().relative_to(R).parts)
    except ValueError:
        return Path(os.path.abspath(path)).exists()  # External links have no HEAD entry.
    resolved = []
    seen = set()
    followed = 0
    while pending:
        component = pending.pop(0)
        if component in ('', '.'):
            continue
        if component == '..':
            if not resolved:
                return False  # A repo-local symlink must not escape the committed tree.
            resolved.pop()
            continue
        candidate = '/'.join([*resolved, component])
        if candidate in committed_symlinks:
            state = (candidate, tuple(pending))
            followed += 1
            if state in seen or followed > 40:
                return False
            seen.add(state)
            target = Path(committed_symlinks[candidate])
            if target.is_absolute():
                try:
                    target = target.relative_to(R)
                except ValueError:
                    return False
                resolved = []
            pending = list(target.parts) + pending
        else:
            if candidate not in committed_paths:
                return False
            if pending and candidate not in committed_dirs:
                return False
            resolved.append(component)
    return not directory or ('/'.join(resolved) or '.') in committed_dirs


# Include aliases that resolve to directories in HEAD, including the repo root.
# File aliases and mutable working-tree targets must not widen the path scan.
top_dirs.update(name for name in committed_symlinks
                if '/' not in name and not name.startswith('.')
                and target_exists(R / name, directory=True))

broken = set()
for rel_doc in docs:
    if not rel_doc.endswith('.md') or not CURRENT_STATE.search(rel_doc):
        continue
    doc = R / rel_doc
    text = committed(rel_doc).decode(errors='replace')
    for target in LINK.findall(text):
        if re.match(r'^[a-z][a-z0-9+.-]*:', target) or target.startswith('#'):
            continue
        path = target.split('#', 1)[0]
        if path and not target_exists(doc.parent / path) and not target_exists(R / path):
            broken.add(f'{rel_doc}: link {path}')
    for token in TICKED.findall(text):
        if token.split('/', 1)[0] in top_dirs and not target_exists(R / token) and not target_exists(doc.parent / token):
            broken.add(f'{rel_doc}: path {token}')

goals = 'absent'
if (R / 'goals.json').exists() and GOALS_PY.exists():
    out = sh(sys.executable, str(GOALS_PY), 'validate', root).strip()
    goals = 'ok' if out == 'ok' else f'{len(out.splitlines())} errors {h(out)}'

print(f"head {sh('git', '-C', root, 'rev-parse', 'HEAD').strip()}")
# Debounce finished-card events: the agent-branch fingerprint advances at most every 30 min,
# so a busy profile triggers one docs pass per half hour instead of one per card.
import json
agent_now = h(sh('git', '-C', root, 'for-each-ref', '--format=%(refname) %(objectname)', 'refs/heads/agent/'))
state_file = Path(os.environ.get('HERMES_HOME') or Path.home() / '.hermes') / 'cache/repo_docs_monitor' / f'{h(root)}.json'
try:
    state = json.loads(state_file.read_text())
except (OSError, ValueError):
    state = {}
if agent_now != state.get('agent') and time.time() - state.get('at', 0) >= 1800:
    state = {'agent': agent_now, 'at': time.time()}
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state))
print(f"agent-branches {state.get('agent', agent_now)}")
broken -= ignored
print(f'goals.json {goals}')
print(f'drift {len(broken)}')
for item in sorted(broken)[:30]:
    print(f'  {item}')
print(f"day {time.strftime('%Y-%m-%d', time.gmtime())}")
