#!/usr/bin/env python3
"""Daily merge train: land verified fleet work from each project repo's shared worktree onto main.

  merge_train.py run [--profiles a,b] [--plan-only] [--dry-run] [--min-age-min 30] [--ci-wait-min 90]
                    [--branch-max-age-days 14]
  merge_train.py launch [...same args]     # detached background run (for the cron wrapper); prints nothing

Per project profile (workspace = terminal.cwd in its config.yaml):
 1. plan  - dirty, non-ignored paths, minus files modified in the last --min-age-min minutes (a live
            worker may be writing them), files over 5 MB, and secret-looking paths.
 2. gate  - build the candidate tree with a temporary index (the real index and any staged work are
            untouched), check it out into an isolated worktree and run the repo's gate. A failing command
            that also fails on main is pre-existing and does not block. For Flutter tests, failing test
            files that are new/modified in the candidate are held back (re-gated once) and recorded as
            follow-up tasks; a failure in an unchanged test file that passes on main aborts this repo.
 3. land  - one commit on top of main; direct push when allowed, otherwise a PR that is merged after CI
            when every failing check also fails on main. Never force-pushes or rewrites history.
 4. report - ~/.hermes/fleet-governor/merge-train/<date>.md (+ stdout for `run`).

Branch phase (runs first): workers that run in isolated worktrees deliver on agent/<profile>/<task>
branches. A branch whose kanban card is done is merged (a real merge commit, history kept) when it is
not already on main or in the shared worktree, merges without conflicts, and touches no uncommitted
worktree file. The merged result is gated the same way; on a new failure the batch is split in half
until the failing branches are isolated and reported. Landed files are synced into the shared
worktree so it never shows them as reverted. Branches are never deleted or rewritten.

Gate source, first match wins: <repo>/.hermes/merge-train.json {"enabled", "gate": [...]};
a fenced bash block under a "Complete gate"/"Merge gate" heading in AGENTS.md or CLAUDE.md;
per-component detection for changed top-level dirs (Flutter, Go, Node test script, Python pytest).
No gate found -> the repo is reported and not landed.
"""
import argparse
import datetime as dt
import fcntl
import fnmatch
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HOME = Path(os.environ.get('HERMES_HOME') or Path.home() / '.hermes')
REPORT_DIR = HOME / 'fleet-governor' / 'merge-train'
SCRATCH = HOME / 'cache' / 'scratch' / 'merge-train'
KANBAN = HOME / 'kanban.db'
GOALS_PY = Path(__file__).resolve().parents[2] / 'repo-docs' / 'scripts' / 'goals.py'
SECRET_PATHS = ('.env', '.env.*', '*.pem', '*.key', '*.p12', '*.jks', '*.keystore', 'id_rsa*', '*credentials*.json')
SECRET_TEXT = re.compile(r'BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|sk-or-v1-[A-Za-z0-9]{30,}'
                         r'|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{20,}|AIza[0-9A-Za-z_-]{35}')
MAX_BYTES = 5 * 1024 * 1024


def sh(args, cwd=None, env=None, timeout=None, check=False):
    p = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    if check and p.returncode:
        raise RuntimeError(f"{' '.join(map(str, args))}: {p.stderr.strip()[:400]}")
    return p


def git(repo, *args, env=None, check=True):
    return sh(['git', '-C', str(repo), *args], env=env, check=check).stdout.strip()


def profiles(selected):
    root = HOME / 'profiles'
    for p in sorted(root.iterdir()) if root.is_dir() else []:
        if p.name.startswith('.') or not (p / 'config.yaml').is_file() or (selected and p.name not in selected):
            continue
        cwd = next((l.split('cwd:', 1)[1].strip().strip('"\'') for l in (p / 'config.yaml').read_text().splitlines()
                    if l.strip().startswith('cwd:')), '')
        if cwd and (Path(cwd) / '.git').exists():
            yield p.name, Path(cwd)


def repo_config(repo):
    f = repo / '.hermes' / 'merge-train.json'
    try:
        return json.loads(f.read_text()) if f.exists() else {}
    except ValueError:
        return {'enabled': False, '_error': f'invalid {f}'}


# ---------------------------------------------------------------- plan
def plan(repo, min_age_min):
    now = time.time()
    take, held = [], []
    raw = sh(['git', '-C', str(repo), 'status', '--porcelain', '--untracked-files=all', '-z'], check=True).stdout  # no strip()
    for line in raw.split('\0'):
        if not line:
            continue
        status, path = line[:2], line[3:]
        if path.endswith('/'):
            held.append((path, 'nested repository or worktree')); continue
        if (repo / path / '.git').exists():
            why = submodule_pointer_hold(repo, path)
            if why:
                held.append((path, why))
            else:
                take.append(path)
            continue
        if status.startswith('R') or status.startswith('C'):
            held.append((path, 'rename/copy (land manually)')); continue
        f = repo / path
        if any(fnmatch.fnmatch(Path(path).name, pat) for pat in SECRET_PATHS):
            held.append((path, 'secret-looking path')); continue
        if f.is_file():
            if f.stat().st_size > MAX_BYTES:
                held.append((path, 'over 5 MB')); continue
            if now - f.stat().st_mtime < min_age_min * 60:
                held.append((path, f'modified < {min_age_min} min ago (live work)')); continue
        take.append(path)
    return take, held


def submodule_pointer_hold(repo, path):
    """None when the submodule's checked-out commit moved and is on its origin; else why it is held."""
    sub = repo / path
    head = git(sub, 'rev-parse', 'HEAD', check=False)
    recorded = git(repo, 'rev-parse', f'HEAD:{path}', check=False)
    if not head or head == recorded:
        return 'submodule has only uncommitted content (landed by its own train pass)'
    if not git(sub, 'branch', '-r', '--contains', head, check=False):
        return 'submodule pointer not pushed upstream yet'
    return None


def targets(name, repo):
    """Submodules first (so their pushed commits can be pointed to), then the repo itself."""
    for line in git(repo, 'submodule', 'status', check=False).splitlines():
        parts = line[1:].split()
        if len(parts) >= 2 and (repo / parts[1] / '.git').exists():
            yield f'{name}-{parts[1].replace("/", "-")}', repo / parts[1]
    yield name, repo


def build_tree(repo, paths, index):
    env = dict(os.environ, GIT_INDEX_FILE=str(index))
    if index.exists():
        index.unlink()
    git(repo, 'read-tree', 'HEAD', env=env)
    for i in range(0, len(paths), 200):
        sh(['git', '-C', str(repo), 'add', '--', *paths[i:i + 200]], env=env, check=True)
    return git(repo, 'write-tree', env=env), env


def secret_scan(repo, tree):
    diff = git(repo, 'diff', 'HEAD', tree, '--', check=False)
    return sorted({m.group(0)[:12] + '…' for m in SECRET_TEXT.finditer(diff)})


# ---------------------------------------------------------------- gate
# Fails only on leftover merge-conflict markers; whitespace issues are reported, never blocking.
CONFLICT_CHECK = "git diff HEAD | grep -nE '^\\+(<{7}|>{7}|={7})( |$)' && exit 1 || exit 0"
DOC_PATH = re.compile(r'(\.(md|mdx|txt|rst)$)|(^docs/)|(^(goals\.json|\.gitignore|\.repo-docs-drift-ignore)$)|(^\.impeccable/)', re.I)


def component_gate(d, q):
    """Gate commands for one component directory, or [] when nothing is recognised."""
    cmds = []
    pub = d / 'pubspec.yaml'
    if pub.exists():
        flutter = 'flutter:' in pub.read_text() or 'sdk: flutter' in pub.read_text()
        cmds.append(f'(cd {q} && flutter analyze && flutter test --concurrency=1)' if flutter else f'(cd {q} && dart analyze && dart test)')
    if (d / 'go.mod').exists():
        cmds.append(f'(cd {q} && go test ./...)')
    if (d / 'Cargo.toml').exists():
        cmds.append(f'(cd {q} && cargo test --locked)')
    if (d / 'package.json').exists() and '"test"' in (d / 'package.json').read_text():
        cmds.append(f'(cd {q} && npm test --silent)')
    if (d / 'pyproject.toml').exists() or (d / 'pytest.ini').exists() or any((d / 'tests').glob('test_*.py')):
        cmds.append(f'(cd {q} && python3 -m pytest -q)')
    return cmds


def gate_commands(repo, changed):
    """(commands, source). Docs-only candidates get `git diff --check`; code needs a recognised gate."""
    # Submodule pointers were gated in the submodule's own pass.
    code = [p for p in changed if not DOC_PATH.search(p) and not (repo / p / '.git').exists()]
    if not code:
        return [CONFLICT_CHECK], 'docs-only candidate'
    cfg = repo_config(repo)
    if cfg.get('gate'):
        return list(cfg['gate']) + [CONFLICT_CHECK], '.hermes/merge-train.json'
    for doc in ('AGENTS.md', 'CLAUDE.md'):
        f = repo / doc
        if not f.exists():
            continue
        m = re.search(r'^(?:#+\s*)?(?:Complete|Merge|Full) gate:?\s*\n(?:(?!^#).*\n)*?```(?:bash|sh)?\n(.*?)```',
                      f.read_text(), re.M | re.S | re.I)
        if m:
            cmds = [c.strip() for c in m.group(1).splitlines() if c.strip() and not c.strip().startswith('#')]
            return cmds, f'{doc} gate block'
    cmds, uncovered = [], []
    root_gate = component_gate(repo, '.')
    for top in sorted({p.split('/', 1)[0] for p in code if '/' in p}):
        g = component_gate(repo / top, top) if (repo / top).is_dir() else []
        if g:
            cmds += g
        elif root_gate:
            cmds += [c for c in root_gate if c not in cmds]
        else:
            uncovered.append(top)
    if any('/' not in p for p in code):
        if root_gate:
            cmds += [c for c in root_gate if c not in cmds]
        else:
            uncovered.append('(repo root files)')
    if uncovered:
        return [], f'no gate for changed code in {uncovered}'
    return cmds + [CONFLICT_CHECK], 'component detection'


def worktree(repo, name, tree=None, at='HEAD'):
    path = SCRATCH / name
    if path.exists():
        sh(['git', '-C', str(repo), 'worktree', 'remove', '--force', str(path)])
        shutil.rmtree(path, ignore_errors=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    git(repo, 'worktree', 'add', '-q', '--detach', str(path), at)
    if tree:
        git(path, 'read-tree', '-m', '-u', 'HEAD', tree)
    # Reuse installed JS deps when the lockfile is unchanged (worktrees have no node_modules).
    for lock in repo.glob('**/package-lock.json'):
        if 'node_modules' in lock.parts:
            continue
        rel = lock.parent.relative_to(repo)
        nm = repo / rel / 'node_modules'
        if nm.is_dir() and (path / rel / 'package-lock.json').exists() and \
                (path / rel / 'package-lock.json').read_bytes() == lock.read_bytes() and not (path / rel / 'node_modules').exists():
            (path / rel / 'node_modules').symlink_to(nm)
    return path


def prepare(wt, cmds, log):
    """Install per-worktree dependencies, only in the directories the gate commands use."""
    dirs = {wt / d for c in cmds for d in re.findall(r'cd\s+([^\s&;)]+)', c)} or {wt}
    if any('cd ' not in c for c in cmds):
        dirs.add(wt)
    for pub in sorted(d / 'pubspec.yaml' for d in dirs):
        if not pub.exists():
            continue
        p = sh(['flutter', 'pub', 'get'], cwd=pub.parent, timeout=1800)
        log.write(f'(prepare) flutter pub get in {pub.parent.relative_to(wt)} -> {p.returncode}\n')
    for lock in sorted(d / 'package-lock.json' for d in dirs):
        if not lock.exists() or (lock.parent / 'node_modules').exists():
            continue
        p = sh(['npm', 'ci', '--no-audit', '--no-fund'], cwd=lock.parent, timeout=1800)
        log.write(f'(prepare) npm ci in {lock.parent.relative_to(wt)} -> {p.returncode}\n')


def run_gate(wt, cmds, log):
    prepare(wt, cmds, log)
    results = []
    for cmd in cmds:
        p = sh(['bash', '-lc', cmd], cwd=wt, timeout=3 * 3600)
        log.write(f'$ {cmd}\n{p.stdout[-20000:]}\n{p.stderr[-8000:]}\n[exit {p.returncode}]\n')
        results.append((cmd, p.returncode, p.stdout + p.stderr))
    return results


def flutter_failed_files(output, wt):
    files = set()
    for m in re.finditer(r'(\S+_test\.dart): .* \[E\]', output):
        f = m.group(1)
        files.add(os.path.relpath(f, wt) if f.startswith('/') else f)
    return files


# ---------------------------------------------------------------- land
def land(repo, tree, message, ci_wait_min, dry):
    base = git(repo, 'rev-parse', 'HEAD')
    return land_commit(repo, git(repo, 'commit-tree', tree, '-p', base, '-m', message), base, message, ci_wait_min, dry)


def land_commit(repo, commit, base, message, ci_wait_min, dry):
    if dry:
        return f'dry-run: would land {commit[:8]}'
    branch = git(repo, 'branch', '--show-current') or 'main'
    sh(['git', '-C', str(repo), 'fetch', '-q', 'origin'])
    if sh(['git', '-C', str(repo), 'rev-parse', '--verify', '-q', f'origin/{branch}']).returncode:
        return f'skipped: origin has no {branch} branch (empty repo or different default); first push is an owner decision'
    remote = git(repo, 'rev-parse', f'origin/{branch}', check=False)
    if remote and remote != base and sh(['git', '-C', str(repo), 'merge-base', '--is-ancestor', remote, base]).returncode:
        return f'skipped: origin/{branch} has commits not in local {branch}; reconcile first'
    push = sh(['git', '-C', str(repo), 'push', 'origin', f'{commit}:refs/heads/{branch}'])
    if push.returncode == 0:
        git(repo, 'update-ref', f'refs/heads/{branch}', commit, base)
        return f'pushed {commit[:8]} to {branch}'
    if 'pull request' not in (push.stderr + push.stdout).lower():
        return f'push failed: {push.stderr.strip().splitlines()[-1][:200] if push.stderr.strip() else "unknown"}'
    # Protected branch: PR flow.
    pr_branch = f"merge-train/{dt.date.today().isoformat()}-{commit[:7]}"
    sh(['git', '-C', str(repo), 'push', '-q', 'origin', f'{commit}:refs/heads/{pr_branch}'], check=True)
    slug = re.sub(r'(\.git)?$', '', git(repo, 'remote', 'get-url', 'origin').split('github.com')[-1].lstrip(':/'))
    title = message.splitlines()[0]
    pr = sh(['gh', 'pr', 'create', '--repo', slug, '--base', branch, '--head', pr_branch, '--title', title,
             '--body', message + '\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)'], check=True).stdout.strip().splitlines()[-1]
    deadline = time.time() + ci_wait_min * 60
    while time.time() < deadline:
        checks = sh(['gh', 'pr', 'checks', pr, '--repo', slug]).stdout
        if checks and '\tpending\t' not in checks:
            break
        time.sleep(60)
    rows = [l.split('\t') for l in sh(['gh', 'pr', 'checks', pr, '--repo', slug]).stdout.splitlines() if '\t' in l]
    if any(r[1] == 'pending' for r in rows):
        return f'PR {pr} opened; CI still pending after {ci_wait_min} min, left open'
    failing = {r[0] for r in rows if r[1] == 'fail'}
    base_failing = set()
    if failing:
        runs = json.loads(sh(['gh', 'api', f'repos/{slug}/commits/{base}/check-runs?per_page=100']).stdout or '{}')
        base_failing = {c['name'] for c in runs.get('check_runs', []) if c.get('conclusion') in ('failure', 'timed_out')}
        if not base_failing:  # base sha may have no runs (never pushed alone): use the branch tip's last runs
            runs = json.loads(sh(['gh', 'api', f'repos/{slug}/commits/{branch}/check-runs?per_page=100']).stdout or '{}')
            base_failing = {c['name'] for c in runs.get('check_runs', []) if c.get('conclusion') in ('failure', 'timed_out')}
    new_fail = failing - base_failing
    if new_fail:
        return f'PR {pr} left open: new failing checks {sorted(new_fail)}'
    sh(['gh', 'pr', 'merge', pr, '--repo', slug, '--merge', '--delete-branch'], check=True)
    sh(['git', '-C', str(repo), 'fetch', '-q', 'origin'])
    ff = sh(['git', '-C', str(repo), 'merge', '-q', '--ff-only', f'origin/{branch}'])
    note = f' (pre-existing failing checks: {sorted(failing)})' if failing else ''
    return f'merged {pr}{note}' + ('' if ff.returncode == 0 else '; local fast-forward failed, run git merge --ff-only')


def follow_up(repo, held_tests):
    gj = repo / 'goals.json'
    if not held_tests or not gj.exists() or not GOALS_PY.exists():
        return
    d = json.loads(gj.read_text())
    if not any(g['id'] == 'INTEGRATION' for g in d['goals']):
        d['goals'].append({'id': 'INTEGRATION', 'title': 'Keep main green: land verified fleet work daily',
                           'source': 'fleet-governor merge train', 'status': 'partial', 'priority': 1,
                           'evidence': [], 'tasks': [], 'depends_on': []})
    ids = {t['id'] for t in d['tasks']}
    for f in sorted(held_tests):
        tid = 'MT-' + re.sub(r'[^A-Z0-9]+', '-', Path(f).stem.upper())[:40]
        if tid in ids:
            continue
        d['tasks'].append({'id': tid, 'goal': 'INTEGRATION', 'status': 'open', 'section': 'Now', 'depends_on': [],
                           'title': f'Make held-back test pass so it can land: {f}'})
        for g in d['goals']:
            if g['id'] == 'INTEGRATION':
                g['tasks'] = sorted(set(g['tasks'] + [tid]))
    gj.write_text(json.dumps(d))
    for cmd in ('fmt', 'render'):
        sh([sys.executable, str(GOALS_PY), cmd, str(repo)])


# ---------------------------------------------------------------- per repo
def cleanup(repo, name):
    for suffix in ('cand', 'base', 'bcand', 'bbase'):
        path = SCRATCH / f'{name}-{suffix}'
        if path.exists():
            sh(['git', '-C', str(repo), 'worktree', 'remove', '--force', str(path)])
            shutil.rmtree(path, ignore_errors=True)
    sh(['git', '-C', str(repo), 'worktree', 'prune'])


def card_done(task_id):
    try:
        db = sqlite3.connect(f'file:{KANBAN}?mode=ro', uri=True, timeout=10)
        row = db.execute('SELECT status FROM tasks WHERE id = ?', (task_id,)).fetchone()
        return bool(row) and row[0] == 'done'
    except sqlite3.Error:
        return False


def branch_candidates(prefix, repo, max_age_days=14):
    """(mergeable branches oldest first, {reason: count}) for agent/<name>/* branches."""
    dirty = {l[3:] for l in sh(['git', '-C', str(repo), 'status', '--porcelain', '--untracked-files=all', '-z'],
                               check=True).stdout.split('\0') if l}
    take, skipped = [], {}
    refs = git(repo, 'for-each-ref', '--sort=committerdate', '--format=%(committerdate:unix) %(refname:short)',
               f'refs/heads/agent/{prefix}/')
    for when, br in (l.split(' ', 1) for l in refs.splitlines() if l):
        if sh(['git', '-C', str(repo), 'merge-base', '--is-ancestor', br, 'HEAD']).returncode == 0:
            continue
        if sh(['git', '-C', str(repo), 'merge-base', 'HEAD', br]).returncode:
            skipped['unrelated history'] = skipped.get('unrelated history', 0) + 1
            continue
        files = [f for f in git(repo, 'diff', '--name-only', f'HEAD...{br}').split('\n') if f]
        why = None
        if not files:
            why = 'no changes'
        elif all(git(repo, 'rev-parse', f'{br}:{f}', check=False) == git(repo, 'rev-parse', f'HEAD:{f}', check=False)
                 for f in files):
            why = 'already on main'
        elif time.time() - int(when) > max_age_days * 86400:
            why = f'older than {max_age_days} days (land manually)'
        elif not card_done(br.rsplit('/', 1)[-1]):
            why = 'card not done'
        elif set(files) & dirty:
            why = 'overlaps uncommitted worktree files'
        if why:
            skipped[why] = skipped.get(why, 0) + 1
        else:
            take.append((br, files))
    return take, skipped


def merge_chain(repo, base, branches):
    """Merge branches onto base one by one with real merge commits; (head, merged, conflicted)."""
    head, merged, conflicted = base, [], []
    for br, files in branches:
        p = sh(['git', '-C', str(repo), 'merge-tree', '--write-tree', '--no-messages', head, br])
        if p.returncode:
            conflicted.append(br); continue
        tree = p.stdout.split()[0]
        head = git(repo, 'commit-tree', tree, '-p', head, '-p', br, '-m', f'Merge {br} (merge train)')
        merged.append((br, files))
    return head, merged, conflicted


def branch_phase(name, repo, a, log, prefix=None):
    if git(repo, 'branch', '--show-current') not in ('main', 'master'):
        return 'branches: skipped (shared worktree is not on main)'
    take, skipped = branch_candidates(prefix or name, repo, a.branch_max_age_days)
    note = ', '.join(f'{n} {k}' for k, n in sorted(skipped.items()))
    if not take:
        return f'branches: none to merge' + (f' ({note})' if note else '')
    base = git(repo, 'rev-parse', 'HEAD')
    head, merged, conflicted = merge_chain(repo, base, take)
    files = sorted({f for _, fs in merged for f in fs})
    if a.plan_only or not merged:
        return (f'branches: {len(merged)} mergeable, {len(conflicted)} conflict' + (f' ({note})' if note else ''))
    cmds, source = gate_commands(repo, files)
    if not cmds:
        return f'branches: {len(merged)} not merged: {source}'
    log.write(f'\n## {name} branches ({repo})\ngate from {source}: {cmds}\n')
    base_wt = worktree(repo, f'{name}-bbase', at=base)
    base_rc = {c: rc for c, rc, _ in run_gate(base_wt, cmds, log)}

    def passes(commit):
        wt = worktree(repo, f'{name}-bcand', at=commit)
        return not [c for c, rc, _ in run_gate(wt, cmds, log) if rc and base_rc.get(c, 1) == 0]

    accepted, failing, cur = [], [], base
    pending = [merged]
    while pending:  # split the batch until failing branches are isolated
        batch = pending.pop(0)
        tip, ok_batch, bad = merge_chain(repo, cur, batch)
        failing += bad
        if ok_batch and passes(tip):
            cur, accepted = tip, accepted + ok_batch
        elif len(ok_batch) > 1:
            mid = len(ok_batch) // 2
            pending[:0] = [ok_batch[:mid], ok_batch[mid:]]
        else:
            failing += [br for br, _ in ok_batch]
    if not accepted:
        return f'branches: none landed; gate fails on {failing[:6]}'
    msg = (f'chore(merge-train): merge {len(accepted)} finished agent branches {dt.date.today().isoformat()}\n\n' +
           '\n'.join(f'- {br}' for br, _ in accepted) + f'\n\nGate ({source}) on the merged tree: passed.\n'
           '\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>')
    final = git(repo, 'commit-tree', f'{cur}^{{tree}}', '-p', base, '-p', cur, '-m', msg) if len(accepted) > 1 else cur
    outcome = land_commit(repo, final, base, msg, a.ci_wait_min, a.dry_run)
    if not a.dry_run and outcome.startswith(('pushed', 'merged')):
        sync_worktree(repo, base, sorted({f for _, fs in accepted for f in fs}))
    tail = (f'; {len(failing)} failing gate or conflict: {failing[:6]}' if failing else '') + (f'; {note}' if note else '')
    return f'branches: {outcome}; {len(accepted)} merged' + tail


def sync_worktree(repo, old, files):
    """After main moved, bring clean landed files into the shared worktree and index."""
    new = git(repo, 'rev-parse', 'HEAD')
    for f in files:
        if sh(['git', '-C', str(repo), 'diff', '--quiet', old, '--', f]).returncode:
            continue  # the shared copy changed meanwhile: leave it for the worktree phase
        if git(repo, 'cat-file', '-t', f'{new}:{f}', check=False) == 'blob':
            sh(['git', '-C', str(repo), 'checkout', new, '--', f])
        else:
            sh(['git', '-C', str(repo), 'rm', '-q', '--cached', '--ignore-unmatch', '--', f])
            (repo / f).unlink(missing_ok=True)


def train_repo(name, repo, a, log):
    cfg = repo_config(repo)
    if cfg.get('enabled') is False:
        return f'disabled ({cfg.get("_error", ".hermes/merge-train.json")})'
    if git(repo, 'status', '--porcelain', check=False) == '':
        return 'clean, nothing to land'
    take, held = plan(repo, a.min_age_min)
    if not take:
        return f'nothing eligible ({len(held)} held: live or excluded)'
    SCRATCH.mkdir(parents=True, exist_ok=True)
    index = SCRATCH / f'{name}.index'
    tree, _ = build_tree(repo, take, index)
    if tree == git(repo, 'rev-parse', 'HEAD^{tree}'):
        return 'no effective change'
    leaks = secret_scan(repo, tree)
    if leaks:
        return f'ABORT: secret-looking content in diff {leaks}'
    cmds, source = gate_commands(repo, take)
    if a.plan_only:
        return f'plan: {len(take)} paths to land, {len(held)} held; gate from {source}: {cmds[:4]}{" …" if len(cmds) > 4 else ""}'
    if not cmds:
        return (f'not landed: {source} ({len(take)} paths waiting). Add a "Complete gate:" block to AGENTS.md '
                f'or a .hermes/merge-train.json gate')
    log.write(f'\n## {name} ({repo})\ngate from {source}: {cmds}\n')
    held_tests = set()
    for attempt in (1, 2):
        wt = worktree(repo, f'{name}-cand', tree)
        res = run_gate(wt, cmds, log)
        failed = [(c, out) for c, rc, out in res if rc]
        if not failed:
            break
        base_wt = worktree(repo, f'{name}-base')
        base_res = {c: rc for c, rc, _ in run_gate(base_wt, [c for c, _ in failed], log)}
        blocking, retry = [], set()
        for cmd, out in failed:
            if 'flutter test' in cmd:
                files = flutter_failed_files(out, str(wt))
                changed = {f for f in files if f in take}
                unchanged = files - changed
                if unchanged and base_res.get(cmd, 1) == 0:
                    blocking.append(f'{cmd}: regression in unchanged tests {sorted(unchanged)[:5]}')
                elif changed:
                    retry |= changed
                elif base_res.get(cmd, 1) == 0:
                    blocking.append(f'{cmd}: fails only on candidate')
            elif base_res.get(cmd, 1) == 0:
                blocking.append(f'{cmd}: fails only on candidate')
        if blocking:
            return 'not landed: ' + '; '.join(blocking)[:600]
        if retry and attempt == 1:
            held_tests |= retry
            take = [p for p in take if p not in retry]
            held += [(f, 'failing test held back') for f in sorted(retry)]
            tree, _ = build_tree(repo, take, index)
            continue
        break  # remaining failures are pre-existing on main
    pre_existing = [c for c, rc, _ in res if rc]
    ws = sh(['git', '-C', str(repo), 'diff', '--check', 'HEAD', tree]).stdout.count(': trailing whitespace') + \
        sh(['git', '-C', str(repo), 'diff', '--check', 'HEAD', tree]).stdout.count(': new blank line at EOF')
    msg = (f'chore(merge-train): land verified fleet work {dt.date.today().isoformat()}\n\n'
           f'Daily fleet-governor merge train: {len(take)} paths from the shared worktree.\n'
           f'Gate ({source}) on this exact tree: passed' +
           (f'; pre-existing failures also on main: {pre_existing}' if pre_existing else '') + '.\n' +
           (f'Held back: {len(held)} paths (live work, failing tests or excluded).\n' if held else '') +
           '\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>')
    outcome = land(repo, tree, msg, a.ci_wait_min, a.dry_run)
    if not a.dry_run and not outcome.startswith(('push failed', 'skipped', 'PR')):
        sh(['git', '-C', str(repo), 'restore', '--staged', '--', *take[:5000]])
        follow_up(repo, held_tests)
    note = f'; {ws} whitespace issue(s) (non-blocking)' if ws else ''
    return f'{outcome}; {len(take)} paths' + (f', held {len(held)}' if held else '') + note


def run(a):
    selected = {x for x in a.profiles.split(',') if x}
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    lock = open(REPORT_DIR / '.lock', 'w')
    try:  # runs share scratch worktrees: never overlap
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print('another merge train run is active; not starting')
        return
    day = dt.date.today().isoformat()
    lines = [f'# Merge train {day}' + (' (dry run)' if a.dry_run else ''), '']
    with open(REPORT_DIR / f'{day}.log', 'a') as log:
        for profile, root in profiles(selected):
            for name, repo in targets(profile, root):
                try:
                    cfg = repo_config(repo)
                    try:
                        on = cfg.get('enabled') is not False and cfg.get('branches', True)
                        bres = branch_phase(name, repo, a, log, prefix=profile) if on else ''
                    except Exception as e:
                        bres = f'branches: error: {e}'
                    cleanup(repo, name)
                    result = train_repo(name, repo, a, log) + (f'; {bres}' if bres else '')
                except Exception as e:  # one repo must never stop the train
                    result = f'error: {e}'
                finally:
                    cleanup(repo, name)
                lines.append(f'- **{name}** ({repo.name}): {result}')
                print(lines[-1], flush=True)
    (REPORT_DIR / f'{day}.md').write_text('\n'.join(lines) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['run', 'launch'])
    ap.add_argument('--profiles', default='')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--plan-only', action='store_true', help='report plan and gate source; run nothing')
    ap.add_argument('--min-age-min', type=int, default=30)
    ap.add_argument('--ci-wait-min', type=int, default=90)
    ap.add_argument('--branch-max-age-days', type=int, default=14)
    a = ap.parse_args()
    if a.cmd == 'launch':
        args = [sys.executable, __file__, 'run'] + sys.argv[2:]
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        out = open(REPORT_DIR / f'{dt.date.today().isoformat()}.stdout', 'a')
        subprocess.Popen(args, stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
        return
    run(a)


if __name__ == '__main__':
    main()
