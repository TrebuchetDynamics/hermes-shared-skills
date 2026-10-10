#!/usr/bin/env python3
"""goals.json: the machine-readable goal list that repo-docs writes and autogoal reads.

TODO.md stays the human view; its `Goal coverage` table is rendered from this file.
Agents change goals.json only through these commands, never by hand-editing JSON.

  goals.py validate <repo>                       structural + evidence-rule check (exit 1 on errors)
  goals.py fmt <repo>                            canonical byte-stable rewrite (applies the "met" rule)
  goals.py next <repo> [--json]                  next eligible open task (dependencies satisfied)
  goals.py focus <repo> <GOAL>                   set the primary milestone without changing priorities
  goals.py focus <repo> --json                   read primary milestone without writing
  goals.py focus <repo> --clear                  remove focus and restore legacy selection order
  goals.py redact <repo> --replacements-file JSON --archive-dir PRIVATE
                                                redact historical refs/sources and render under one lock
  goals.py revision <repo>                       content token for goals.json and TODO.md
  goals.py render <repo>                         rewrite TODO.md's goal-coverage block from goals.json
  goals.py backlog-check <repo> --plan path#heading --tasks T1,T2 [--receipt prior.json]
                                                read-only consumer-bound completion receipt (0 ready, 1 draft, 2 ineligible)
  Every command accepts --expected-revision TOKEN and --canonical-repo PRIMARY.
  Native common-config repoDocs.backlogAuthority may bind a registered same-repo worktree.
  Unbound linked worktrees require explicit canonical targeting; workers return proposals.
  CLI operations lock the common Git directory (or a local no-Git fixture) before load.
  goals.py task <repo> <TASK> <open|in_progress|done>
  goals.py section <repo> <TASK> <Now|Next|Needs decision>
  goals.py add-task <repo> <TASK> --goal <GOAL> --title <text> [--section Now|Next|Needs decision] [--depends-on T1,T2]
  goals.py evidence <repo> <GOAL> --kind executed|inspection --ref <cmd/path> --result pass|fail [--ran-at ISO]

Rule (the met rule): a goal is `met` only with at least one evidence entry of kind `executed`
and result `pass`. Anything else claimed as met is downgraded to `unverified` by fmt.
Optional `primary_milestone` names one existing goal. Its eligible tasks sort first,
even in Next; all eligible fallback tasks remain available after them in next --json.
"""
import argparse
from contextlib import contextmanager
from contextvars import ContextVar
import fcntl
import hashlib
import json
import os
import tempfile
import re
import subprocess
import sys
from pathlib import Path

GOAL_STATUS = ('unmet', 'partial', 'unverified', 'met')
TASK_STATUS = ('open', 'in_progress', 'done')
SECTIONS = ('Now', 'Next', 'Needs decision', 'Done')
KINDS = ('executed', 'inspection')
RESULTS = ('pass', 'fail')
# Order: primary milestone first, then section (Now before Next), goal priority, then status as a
# tie-break: unverified/partial (prove or finish what exists) before unmet (new work).
STATUS_RANK = {'unverified': 0, 'partial': 1, 'unmet': 2, 'met': 3}
SECTION_RANK = {'Now': 0, 'Next': 1}
BEGIN, END = '<!-- goals:coverage:begin -->', '<!-- goals:coverage:end -->'
TRANSACTION = ContextVar('goals_transaction', default=None)


def path_of(repo):
    return Path(repo) / 'goals.json'


def load(repo):
    p = path_of(repo)
    if not p.exists():
        sys.exit(f'{p} not found')
    return json.loads(p.read_text())


def proven(goal):
    return any(e.get('kind') == 'executed' and e.get('result') == 'pass' for e in goal.get('evidence', []))


def normalize(data):
    """Apply the met rule, fill defaults and sort into a stable order."""
    goals, tasks = data.get('goals', []), data.get('tasks', [])
    for g in goals:
        g.setdefault('depends_on', []); g.setdefault('evidence', []); g.setdefault('tasks', [])
        g.setdefault('priority', 100)
        if g.get('status') == 'met' and not proven(g):
            g['status'] = 'unverified'
        g['evidence'] = sorted(g['evidence'], key=lambda e: (e.get('kind', ''), e.get('ref', '')))
        g['depends_on'] = sorted(set(g['depends_on'])); g['tasks'] = sorted(set(g['tasks']))
    for t in tasks:
        t.setdefault('depends_on', []); t.setdefault('section', 'Next'); t.setdefault('status', 'open')
        t['depends_on'] = sorted(set(t['depends_on']))
        if t['status'] == 'done':
            t['section'] = 'Done'
    # Goals keep authoring order (priority, then id); tasks follow section then id.
    goals.sort(key=lambda g: (g['priority'], g['id']))
    tasks.sort(key=lambda t: (SECTIONS.index(t['section']) if t['section'] in SECTIONS else 9, t['id']))
    normalized = {'version': 1, 'goals': goals, 'tasks': tasks}
    if 'primary_milestone' in data:
        normalized['primary_milestone'] = data['primary_milestone']
    return normalized


def errors(data):
    errs = []
    goals, tasks = data.get('goals'), data.get('tasks')
    if data.get('version') != 1:
        errs.append('version must be 1')
    if not isinstance(goals, list) or not isinstance(tasks, list):
        return errs + ['goals and tasks must be lists']
    gids = [g.get('id') for g in goals]; tids = [t.get('id') for t in tasks]
    if 'primary_milestone' in data:
        focus = data['primary_milestone']
        if not isinstance(focus, str) or not focus or focus not in gids:
            errs.append('primary_milestone must name an existing goal')
    for dup in {i for i in gids if gids.count(i) > 1} | {i for i in tids if tids.count(i) > 1}:
        errs.append(f'duplicate id {dup}')
    for g in goals:
        gid = g.get('id', '?')
        for k in ('id', 'title', 'source', 'status'):
            if not g.get(k):
                errs.append(f'{gid}: missing {k}')
        if g.get('status') not in GOAL_STATUS:
            errs.append(f'{gid}: status must be one of {GOAL_STATUS}')
        if g.get('status') == 'met' and not proven(g):
            errs.append(f'{gid}: met without executed+pass evidence (run fmt to downgrade to unverified)')
        for e in g.get('evidence', []):
            if e.get('kind') not in KINDS or e.get('result') not in RESULTS or not e.get('ref'):
                errs.append(f'{gid}: evidence needs kind {KINDS}, result {RESULTS} and ref')
        for d in g.get('depends_on', []):
            if d not in gids:
                errs.append(f'{gid}: depends_on unknown goal {d}')
        for t in g.get('tasks', []):
            if t not in tids:
                errs.append(f'{gid}: unknown task {t}')
        open_tasks = [t for t in tasks if t.get('goal') == gid and t.get('status') != 'done']
        if g.get('status') != 'met' and not open_tasks:
            errs.append(f'{gid}: {g.get("status")} goal has no open task')
    for t in tasks:
        tid = t.get('id', '?')
        for k in ('id', 'goal', 'title', 'status'):
            if not t.get(k):
                errs.append(f'{tid}: missing {k}')
        if t.get('goal') not in gids:
            errs.append(f'{tid}: unknown goal {t.get("goal")}')
        if t.get('status') not in TASK_STATUS:
            errs.append(f'{tid}: status must be one of {TASK_STATUS}')
        if t.get('section', 'Next') not in SECTIONS:
            errs.append(f'{tid}: section must be one of {SECTIONS}')
        for d in t.get('depends_on', []):
            if d not in tids:
                errs.append(f'{tid}: depends_on unknown task {d}')
    return errs


def checked_bytes(path):
    if path.is_symlink():
        sys.exit(f'refusing symlink: {path}')
    if path.exists() and not path.is_file():
        sys.exit(f'expected regular file: {path}')
    return path.read_bytes() if path.exists() else None


def revision(repo):
    digest = hashlib.sha256()
    for name in ('goals.json', 'TODO.md'):
        path = Path(repo) / name
        blob = checked_bytes(path)
        digest.update(name.encode() + b'\0')
        digest.update(b'missing\0' if blob is None else str(len(blob)).encode() + b'\0' + blob)
    return digest.hexdigest()


def git_identity(repo):
    """Return common Git directory and whether this is the primary checkout."""
    # Identity belongs to the explicit path, never an inherited Git session.
    # Drop all GIT_* settings (repository/index/object/discovery/config, including
    # numbered config keys) only in these child processes; keep PATH, HOME and
    # the rest of the caller environment, and do not mutate os.environ.
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    def query(option):
        try:
            result = subprocess.run(['git', '-C', str(repo), 'rev-parse', option],
                                    capture_output=True, text=True, timeout=10, env=env)
        except FileNotFoundError:
            return None
        return result.stdout.strip() if result.returncode == 0 else None
    root = query('--show-toplevel')
    if root is None:
        if (repo / '.git').exists() or (repo / '.git').is_symlink():
            sys.exit('cannot resolve Git repository identity; refusing fixture fallback')
        return None
    if Path(root).resolve() != repo:
        sys.exit('repo must name the repository root')
    common, local = query('--git-common-dir'), query('--git-dir')
    if common is None or local is None:
        sys.exit('cannot resolve Git repository identity')
    common = (repo / common).resolve(strict=True)
    local = (repo / local).resolve(strict=True)
    return common, common == local


def backlog_authority(repo, identity):
    """Use only the repository's native common config and registered worktrees."""
    if identity is None:
        return None
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    config = subprocess.run(['git', 'config', '--file', str(identity[0] / 'config'),
                             '--get-all', 'repoDocs.backlogAuthority'],
                            capture_output=True, text=True, timeout=10, env=env)
    if config.returncode == 1:
        return None
    if config.returncode != 0 or len(config.stdout.splitlines()) != 1:
        sys.exit('invalid native backlog authority binding')
    target = Path(config.stdout.strip())
    if not target.is_absolute():
        sys.exit('native backlog authority must be an absolute registered worktree')
    target = target.resolve(strict=True)
    worktrees = subprocess.run(['git', '-C', str(repo), 'worktree', 'list', '--porcelain'],
                               capture_output=True, text=True, timeout=10, env=env)
    registered = [Path(line[9:]).resolve() for line in worktrees.stdout.splitlines()
                  if line.startswith('worktree ')]
    target_identity = git_identity(target)
    if (worktrees.returncode != 0 or target not in registered or target_identity is None
            or target_identity[0] != identity[0]):
        sys.exit('native backlog authority is not a registered worktree of this repository')
    return target


@contextmanager
def coordination(repo, canonical_repo=None):
    repo = Path(repo).resolve(strict=True)
    identity = git_identity(repo)
    authority = backlog_authority(repo, identity)
    if canonical_repo is not None:
        target = Path(canonical_repo).resolve(strict=True)
        target_identity = git_identity(target)
        if identity is None or target_identity is None or identity[0] != target_identity[0]:
            sys.exit('canonical target must be in the same repository')
        if authority is not None and target != authority:
            sys.exit('canonical target does not match native backlog authority')
        if authority is None and not target_identity[1]:
            sys.exit('canonical target must be the primary repository checkout')
        repo = target
    elif authority is not None:
        repo = authority
    elif identity is not None and not identity[1]:
        sys.exit('linked worktree requires --canonical-repo <primary checkout>; return a scoped proposal to the integration owner')
    lock_dir = identity[0] if identity is not None else repo
    lock_path = lock_dir / '.repo-docs-goals.lock'
    if lock_path.is_symlink():
        sys.exit(f'refusing symlink lock: {lock_path}')
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if backlog_authority(repo, identity) != authority:
            sys.exit('native backlog authority changed while acquiring lock; retry current state')
        token = TRANSACTION.set((repo, revision(repo)))
        try:
            yield repo
        finally:
            TRANSACTION.reset(token)
            fcntl.flock(lock, fcntl.LOCK_UN)


def atomic_write(path, text):
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as stream:
            if path.exists():
                os.fchmod(stream.fileno(), path.stat().st_mode & 0o777)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        snapshot = TRANSACTION.get()
        if snapshot is not None and revision(snapshot[0]) != snapshot[1]:
            sys.exit(f'stale write: {path}; repository changed during command; no write')
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def dump(repo, data):
    atomic_write(path_of(repo), json.dumps(normalize(data), indent=2, sort_keys=True, ensure_ascii=False) + '\n')


def redact(repo, data, replacements_file, archive_dir):
    """Redact historical metadata, preserving original bytes outside the repo.

    This uses the existing cooperative lock/stale guard, not a crash-atomic
    two-file transaction or protection against writers ignoring the lock.
    """
    repo = Path(repo)
    replacements = json.loads(checked_bytes(Path(replacements_file)))
    if not isinstance(replacements, dict) or not replacements or any(
            not isinstance(k, str) or not Path(k).is_absolute()
            or not isinstance(v, str) or not v or Path(v).is_absolute()
            for k, v in replacements.items()):
        sys.exit('replacements must map absolute literal prefixes to nonempty portable placeholders')
    if any(prefix in value for prefix in replacements for value in replacements.values()):
        sys.exit('portable placeholders must not contain replacement prefixes')
    archive = Path(archive_dir).resolve()
    if archive == repo or repo in archive.parents:
        sys.exit('archive directory must be outside repository')
    # One pass, longest literal first: overlapping mappings never cascade.
    pattern = re.compile('|'.join(re.escape(k) for k in sorted(replacements, key=len, reverse=True)))
    changed = False
    for goal in data['goals']:
        source = goal.get('source')
        if isinstance(source, str):
            new = pattern.sub(lambda m: replacements[m.group()], source)
            changed |= new != source
            goal['source'] = new
        for entry in goal.get('evidence', []):
            ref = entry.get('ref')
            if isinstance(ref, str):
                new = pattern.sub(lambda m: replacements[m.group()], ref)
                if new != ref:
                    entry['ref'] = new
                    entry['redacted'] = True
                    changed = True
    if not changed:
        print('ok no redaction needed'); return
    originals = {n: checked_bytes(repo / n) for n in ('goals.json', 'TODO.md')}
    token = TRANSACTION.get()[1]
    destination = archive / token
    if destination.is_symlink():
        sys.exit('refusing symlink archive revision directory')
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    hashes = {}
    for name, blob in originals.items():
        hashes[name] = hashlib.sha256(blob).hexdigest() if blob is not None else None
        path = destination / name
        existing = checked_bytes(path)
        if existing is not None and existing != blob:
            sys.exit(f'archive mismatch: {path}; no write')
        if blob is not None:
            if existing is None:
                atomic_write(path, blob.decode('utf-8'))
            if checked_bytes(path) != blob:
                sys.exit(f'archive verification failed: {path}; no write')
    manifest = json.dumps({'revision': token, 'sha256': hashes}, indent=2, sort_keys=True) + '\n'
    path = destination / 'manifest.json'
    existing = checked_bytes(path)
    if existing is not None and existing != manifest.encode():
        sys.exit(f'archive mismatch: {path}; no write')
    atomic_write(path, manifest)
    if checked_bytes(path) != manifest.encode():
        sys.exit('archive manifest verification failed; no write')
    # Do not normalize: redaction must not change status, ordering or other metadata.
    output = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + '\n'
    atomic_write(path_of(repo), output)
    # Advance only to our exact expected bytes, never bless an intervening edit.
    digest = hashlib.sha256()
    for name, blob in (('goals.json', output.encode()), ('TODO.md', originals['TODO.md'])):
        digest.update(name.encode() + b'\0')
        digest.update(b'missing\0' if blob is None else str(len(blob)).encode() + b'\0' + blob)
    TRANSACTION.set((repo, digest.hexdigest()))
    render(repo, data)
    print(f'ok redacted historical metadata; originals archived at {destination}')


def eligible(data):
    goals = {g['id']: g for g in data['goals']}
    tasks = {t['id']: t for t in data['tasks']}
    out = []
    for t in data['tasks']:
        g = goals.get(t['goal'])
        if t['status'] == 'done' or t.get('section') not in SECTION_RANK or not g or g['status'] == 'met':
            continue
        if any(tasks.get(d, {}).get('status') != 'done' for d in t['depends_on']):
            continue
        if any(goals.get(d, {}).get('status') != 'met' for d in g['depends_on']):
            continue
        focus_rank = 0 if g['id'] == data.get('primary_milestone') else 1
        out.append((focus_rank, SECTION_RANK[t['section']], g['priority'], STATUS_RANK[g['status']], t['id'], t, g))
    return [(t, g) for *_, t, g in sorted(out, key=lambda r: r[:5])]


def render(repo, data):
    tasks = {t['id']: t for t in data['tasks']}
    rows = ['| Goal | Status | Evidence | Task |', '| --- | --- | --- | --- |']
    for g in data['goals']:
        ev = '; '.join(f"{e['kind']}" + (' (redacted historical evidence)' if e.get('redacted') else '')
                       + f" `{e['ref']}` → {e['result']}" for e in g['evidence']) or '—'
        open_t = [t for t in g['tasks'] if tasks.get(t, {}).get('status') != 'done']
        rows.append(f"| {g['id']}: {g['title']} | {g['status']} | {ev} | {', '.join(open_t) or '—'} |")
    block = '\n'.join([BEGIN, '', 'Generated from `goals.json` by `goals.py render`. `met` requires an executed, passing check.', '', *rows, '', END])
    todo = Path(repo) / 'TODO.md'
    text = todo.read_bytes().decode('utf-8') if todo.exists() else '# TODO\n\n## Goal coverage\n\n'
    if BEGIN in text and END in text:
        text = text[:text.index(BEGIN)] + block + text[text.index(END) + len(END):]
    elif '## Goal coverage' in text:
        head, tail = text.split('## Goal coverage', 1)
        nxt = re.search(r'\n## ', tail)
        rest = tail[nxt.start():] if nxt else '\n'
        text = head + '## Goal coverage\n\n' + block + '\n' + rest
    else:
        text = text + '\n\n## Goal coverage\n\n' + block + '\n'
    atomic_write(todo, text)


def local_reference(repo, ref, blobs, reasons):
    """Resolve maintained Markdown links inside this authority; bind whole files."""
    if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', ref):
        return ''  # Remote sources are not locally qualified.
    name, _, anchor = ref.partition('#')
    path = Path(name or 'TODO.md')
    if path.is_absolute() or '..' in path.parts:
        reasons.append(f'nonlocal reference {ref}')
        return ''
    for parent in (path, *path.parents):
        if (repo / parent).is_symlink():
            reasons.append(f'symlink reference {ref}')
            return ''
    name = path.as_posix()
    if name not in blobs:
        blobs[name] = checked_bytes(repo / path)
    blob = blobs[name]
    if blob is None:
        reasons.append(f'missing reference {ref}')
        return ''
    if not anchor:
        return blob.decode('utf-8') if path.suffix.lower() in ('.md', '.markdown') else ''
    text = blob.decode('utf-8')
    headings = []
    counts = {}
    for match in re.finditer(r'^#{1,6}\s+(.+?)\s*#*\s*$', text, re.M):
        slug = re.sub(r'[^\w\- ]', '', match[1].lower()).replace(' ', '-')
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        headings.append((slug + (f'-{count}' if count else ''), match.start(), match.end()))
    found = next((i for i, row in enumerate(headings) if row[0] == anchor), None)
    if found is None:
        reasons.append(f'missing anchor {ref}')
        return ''
    end = headings[found + 1][1] if found + 1 < len(headings) else len(text)
    return text[headings[found][2]:end]


def task_bodies(text):
    """Only checkbox entries outside generated coverage are task contracts."""
    text = re.sub(re.escape(BEGIN) + r'.*?' + re.escape(END), '', text, flags=re.S)
    matches = list(re.finditer(r'^[-*] \[([ xX])\]\s+(?:\*\*)?`?([A-Za-z0-9][A-Za-z0-9_-]*)`?(?=\s|:)', text, re.M))
    bodies = {}
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[match.end():end]
        section_end = re.search(r'^##\s', block, re.M)
        if section_end:
            block = block[:section_end.start()]
        sections = re.findall(r'^##\s+(.+)', text[:match.start()], re.M)
        bodies.setdefault(match[2], []).append((block, match[1], sections[-1] if sections else ''))
    return bodies


def backlog_check(a):
    """Check the consumer, not the author's fixture; never mutate the backlog."""
    repo = Path(a.repo)
    blobs = {name: checked_bytes(repo / name) for name in ('TODO.md', 'goals.json')}
    reasons = [f'missing {name}' for name, blob in blobs.items() if blob is None]
    identity = git_identity(repo)
    if identity is None:
        reasons.append('unbound non-Git fixture is not consumer authority')
    plan_path, _, anchor = a.plan.partition('#')
    plan = repo / plan_path
    if not plan_path or Path(plan_path).is_absolute() or '..' in Path(plan_path).parts:
        reasons.append('plan must be repo-relative')
    else:
        blobs[plan_path] = checked_bytes(plan)
        if blobs[plan_path] is None:
            reasons.append('missing accepted plan')
    ids = a.tasks.split(',')
    if len(ids) != len(set(ids)) or any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', tid) for tid in ids):
        reasons.append('tasks must name unique existing IDs without normalization')
    if not anchor:
        reasons.append('accepted plan requires a heading anchor')
    if plan_path and not Path(plan_path).is_absolute() and '..' not in Path(plan_path).parts:
        decision = local_reference(repo, a.plan, blobs, reasons)
        if not re.search(r'^\s*(?:\*\*)?Status:(?:\*\*)?\s*Accepted\s*$', decision, re.M | re.I):
            reasons.append('plan section lacks explicit Status: Accepted')
        for ref in re.findall(r'\[[^\]]*\]\(([^\s)]+)\)', decision):
            if not re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', ref):
                name, separator, heading = ref.partition('#')
                resolved = os.path.normpath(Path(plan_path).parent / name) if name else plan_path
                local_reference(repo, resolved + (separator + heading if separator else ''), blobs, reasons)
    picks = []
    data = None
    if not reasons:
        try:
            ledger_blob = blobs['goals.json']
            assert ledger_blob is not None
            data = json.loads(ledger_blob)
            reasons.extend(errors(data))
            if not reasons:
                picks = [t['id'] for t, _ in eligible(normalize(json.loads(ledger_blob)))]
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            reasons.append(f'invalid backlog: {exc}')
            data = None
    if data is not None and not reasons:
        todo_blob = blobs['TODO.md']
        assert todo_blob is not None
        bodies = task_bodies(todo_blob.decode('utf-8'))
        known = {t['id'] for t in data['tasks']}
        for tid, entries in bodies.items():
            if tid not in known and any(mark == ' ' and section in SECTION_RANK
                                       for _, mark, section in entries):
                reasons.append(f'{tid}: executable body has no ledger task')
        for t in data['tasks']:
            tid = t['id']
            if t['status'] == 'done':
                continue
            entries = bodies.get(tid, [])
            if len(entries) != 1:
                reasons.append(f'{tid}: missing or duplicate task body')
                continue
            body, checked, section = entries[0]
            fields = {}
            for label in ('Goal', 'Scope', 'Acceptance', 'Dependencies', 'Sources'):
                match = re.search(r'^\s*(?:[-*]\s+)?(?:\*\*)?' + label
                                  + r':(?:\*\*)?[ \t]*(\S[^\n]*)', body, re.M)
                if not match:
                    reasons.append(f'{tid}: missing {label}')
                else:
                    fields[label] = match[1]
            if not re.match(r'`?' + re.escape(t['goal']) + r'`?(?:[.\s]|$)', fields.get('Goal', '')):
                reasons.append(f'{tid}: Goal does not match ledger')
            if checked != ' ' or section != t.get('section', 'Next'):
                reasons.append(f'{tid}: checkbox/section does not match ledger')
            goal = next(g for g in data['goals'] if g['id'] == t['goal'])
            for dep in t.get('depends_on', []) + goal.get('depends_on', []):
                if not re.search(r'(?<![\w-])' + re.escape(dep) + r'(?![\w-])', fields.get('Dependencies', '')):
                    reasons.append(f'{tid}: Dependencies do not name {dep}')
            sources = re.findall(r'\[[^\]]*\]\(([^\s)]+)\)', fields.get('Sources', ''))
            if tid in ids and a.plan not in sources:
                reasons.append(f'{tid}: Sources do not link accepted plan')
            for ref in re.findall(r'\[[^\]]*\]\(([^\s)]+)\)', body):
                local_reference(repo, ref, blobs, reasons)
        for g in data['goals']:
            local_reference(repo, g['source'], blobs, reasons)
            actual = {t['id'] for t in data['tasks'] if t['goal'] == g['id']}
            if actual != set(g.get('tasks', [])):
                reasons.append(f'{g["id"]}: task membership does not match ledger')
    ineligible = []
    if data is not None and not reasons:
        tasks = {t['id']: t for t in data['tasks']}
        goals = {g['id']: g for g in data['goals']}
        for tid in ids:
            t = tasks.get(tid)
            if t is None:
                reasons.append(f'unknown task {tid}')
                continue
            g = goals[t['goal']]
            if tid not in picks:
                ineligible.append(f'{tid}: not eligible (status={t["status"]}, section={t["section"]}, goal={g["status"]})')
            if t['status'] == 'in_progress':
                ineligible.append(f'{tid}: already in progress')
            for dep in t.get('depends_on', []):
                if tasks[dep]['status'] != 'done':
                    ineligible.append(f'{tid}: unmet task dependency {dep}')
            for dep in g.get('depends_on', []):
                if goals[dep]['status'] != 'met':
                    ineligible.append(f'{tid}: unmet goal dependency {dep}')
        if picks and picks[0] not in ids:
            ineligible.append(f'current frontier {picks[0]} precedes requested plan')
    authority = backlog_authority(repo, identity)
    if identity and ((authority is not None and authority != repo) or (authority is None and not identity[1])):
        reasons.append('native backlog authority changed during check')
    binding = {'git_common_dir': str(identity[0]) if identity else None,
               'registered_authority': str(authority) if authority else None}
    if any(checked_bytes(repo / name) != blob for name, blob in blobs.items()):
        reasons.append('inputs changed during check')
    state = ('draft_saved' if reasons else 'backlog_reconciled_not_eligible'
             if ineligible else 'ready_for_autogoal')
    receipt = {'state': state, 'authority_binding': binding,
               'authoritative_repo': str(repo), 'plan': a.plan, 'task_ids': ids,
               'primary_milestone': data.get('primary_milestone') if data else None,
               'eligible_task_ids': picks, 'live_ownership': 'unknown',
               'sha256': {name: hashlib.sha256(blob).hexdigest() if blob is not None else None
                          for name, blob in blobs.items()}, 'reasons': reasons + ineligible}
    if a.receipt:
        try:
            previous = json.loads(checked_bytes(Path(a.receipt)))
        except (ValueError, TypeError, OSError):
            previous = None
        if previous != receipt:
            reasons.append('stale receipt')
            receipt['state'] = 'draft_saved'
            receipt['reasons'] = reasons + ineligible
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 1 if reasons else 2 if ineligible else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('validate', 'fmt', 'render', 'revision'):
        sub.add_parser(name).add_argument('repo')
    n = sub.add_parser('next'); n.add_argument('repo'); n.add_argument('--json', action='store_true')
    f = sub.add_parser('focus'); f.add_argument('repo'); f.add_argument('goal', nargs='?')
    f.add_argument('--clear', action='store_true', help='remove primary milestone focus')
    f.add_argument('--json', action='store_true', help='read primary milestone without writing')
    t = sub.add_parser('task'); t.add_argument('repo'); t.add_argument('task'); t.add_argument('status', choices=TASK_STATUS)
    s2 = sub.add_parser('section'); s2.add_argument('repo'); s2.add_argument('task')
    s2.add_argument('section', choices=[s for s in SECTIONS if s != 'Done'])
    n2 = sub.add_parser('add-task'); n2.add_argument('repo'); n2.add_argument('task')
    n2.add_argument('--goal', required=True); n2.add_argument('--title', required=True)
    n2.add_argument('--section', default='Next', choices=[s for s in SECTIONS if s != 'Done'])
    n2.add_argument('--depends-on', default='')
    r = sub.add_parser('redact'); r.add_argument('repo')
    r.add_argument('--replacements-file', required=True, help='JSON absolute literal prefix to portable placeholder map')
    r.add_argument('--archive-dir', required=True, help='private original-byte archive outside repository')
    e = sub.add_parser('evidence'); e.add_argument('repo'); e.add_argument('goal')
    e.add_argument('--kind', choices=KINDS, required=True); e.add_argument('--ref', required=True)
    e.add_argument('--result', choices=RESULTS, required=True); e.add_argument('--ran-at', default='')
    b = sub.add_parser('backlog-check'); b.add_argument('repo')
    b.add_argument('--plan', required=True, help='accepted repo-relative path#heading')
    b.add_argument('--tasks', required=True, help='existing comma-separated task IDs')
    b.add_argument('--receipt', help='prior JSON stdout receipt to recheck for staleness')
    for parser in sub.choices.values():
        parser.add_argument('--expected-revision', help='refuse if goals.json or TODO.md changed since revision')
        parser.add_argument('--canonical-repo', help='explicit primary checkout of the same Git repository')
    a = ap.parse_args()
    if a.cmd == 'focus' and sum((a.clear, a.goal is not None, a.json)) != 1:
        f.error('provide exactly one of GOAL, --clear or --json')
    with coordination(a.repo, a.canonical_repo) as repo:
        a.repo = str(repo)
        current = revision(repo)
        if a.expected_revision is not None and a.expected_revision != current:
            sys.exit(f'stale revision: expected {a.expected_revision}, current {current}; no write')
        if a.cmd == 'revision':
            print(current); return
        if a.cmd == 'backlog-check':
            sys.exit(backlog_check(a))
        execute(a)


def execute(a):
    data = load(a.repo)

    if a.cmd == 'redact':
        redact(a.repo, data, a.replacements_file, a.archive_dir); return

    if a.cmd == 'focus':
        if a.json:
            print(json.dumps({'primary_milestone': data.get('primary_milestone')})); return
        if a.clear:
            data.pop('primary_milestone', None)
            dump(a.repo, data); print('ok focus cleared'); return
        if not any(g['id'] == a.goal for g in data['goals']):
            sys.exit(f'unknown goal {a.goal}')
        data['primary_milestone'] = a.goal
        dump(a.repo, data); print(f'ok focus -> {a.goal}'); return

    if a.cmd == 'validate':
        errs = errors(data)
        print('\n'.join(errs) if errs else 'ok')
        sys.exit(1 if errs else 0)
    if a.cmd == 'fmt':
        dump(a.repo, data); print('ok'); return
    if a.cmd == 'render':
        render(a.repo, normalize(data)); print('ok'); return
    if a.cmd == 'next':
        picks = eligible(normalize(data))
        if a.json:
            print(json.dumps([{'task': t, 'goal': g['id'], 'goal_status': g['status']} for t, g in picks], indent=2))
        elif picks:
            t, g = picks[0]
            print(f"{t['id']} ({t['section']}) → {g['id']} [{g['status']}]: {t['title']}")
        else:
            print('none')
        return
    if a.cmd == 'task':
        task = next((x for x in data['tasks'] if x['id'] == a.task), None) or sys.exit(f'unknown task {a.task}')
        task['status'] = a.status
        dump(a.repo, data)
        goal = next((g for g in data['goals'] if g['id'] == task['goal']), None)
        still_open = [t for t in data['tasks'] if t.get('goal') == task['goal'] and t.get('status') != 'done']
        if a.status == 'done' and goal and goal.get('status') != 'met' and not still_open:
            print(f"WARNING: {goal['id']} is still {goal['status']} with no open task. Record the check you ran: "
                  f"goals.py evidence {a.repo} {goal['id']} --kind executed --ref \"<command>\" --result pass")
        print('ok'); return
    if a.cmd == 'section':
        task = next((x for x in data['tasks'] if x['id'] == a.task), None) or sys.exit(f'unknown task {a.task}')
        if task.get('status') == 'done':
            sys.exit(f'task {a.task} is done')
        task['section'] = a.section
        dump(a.repo, data); print(f'ok {a.task} -> {a.section}'); return
    if a.cmd == 'add-task':
        if any(x['id'] == a.task for x in data['tasks']):
            sys.exit(f'task {a.task} already exists')
        goal = next((x for x in data['goals'] if x['id'] == a.goal), None) or sys.exit(f'unknown goal {a.goal}')
        deps = [d for d in a.depends_on.split(',') if d]
        known = {x['id'] for x in data['tasks']}
        missing = [d for d in deps if d not in known]
        if missing:
            sys.exit(f'unknown depends_on task(s): {missing}')
        data['tasks'].append({'id': a.task, 'goal': a.goal, 'title': a.title, 'status': 'open',
                              'section': a.section, 'depends_on': deps})
        goal['tasks'] = sorted(set(goal.get('tasks', []) + [a.task]))
        dump(a.repo, data); print(f'ok {a.task} -> {a.goal} ({a.section})'); return
    if a.cmd == 'evidence':
        goal = next((x for x in data['goals'] if x['id'] == a.goal), None) or sys.exit(f'unknown goal {a.goal}')
        entry = {'kind': a.kind, 'ref': a.ref, 'result': a.result}
        if a.ran_at:
            entry['ran_at'] = a.ran_at
        goal['evidence'] = [x for x in goal.get('evidence', []) if (x.get('kind'), x.get('ref')) != (a.kind, a.ref)] + [entry]
        if a.kind == 'executed' and a.result == 'pass' and goal.get('status') in ('unmet', 'unverified', 'partial') \
                and all(t.get('status') == 'done' for t in data['tasks'] if t.get('goal') == a.goal):
            goal['status'] = 'met'
        if a.kind == 'executed' and a.result == 'fail' and goal.get('status') == 'met':
            goal['status'] = 'partial'
        dump(a.repo, data); print(f"ok {goal['id']} → {goal['status']}"); return


if __name__ == '__main__':
    main()
