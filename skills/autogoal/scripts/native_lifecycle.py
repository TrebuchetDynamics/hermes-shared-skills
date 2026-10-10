#!/usr/bin/env python3
"""Native lifecycle controls and source-bound task-comment communication.

handoff --db EXISTING_DB --payload JSON requires task_id, source_sha,
input_hashes (named SHA256 values), scope, acceptance (nonempty list), evidence.
ack --db EXISTING_DB --payload JSON requires task_id, handoff_id, source_sha,
input_hashes, state (adopted/rejected/needs-reproduction), evidence.

Communication commands require a Linux native worker ancestor with matching
spawn fingerprint, original board/task/run/claim environment and a fresh lease.
No author/profile overrides, task creation, reassignment or dispatch. Source
hashes/evidence are attributed assertions, not independent reproduction proof.
Paid execution remains gated: no vetted external spending controller yet.
"""


import argparse
import copy
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any

SCRATCH = (Path.home() / '.hermes/cache/scratch/executable-safeguards/native-harness')
ROOT = Path(__file__).resolve().parents[2]


class Refused(RuntimeError):
    pass


def execution_gate(enabled=False, runtime=None, budget_control=None):
    if not enabled:
        raise Refused('native/model execution is default off')
    if not isinstance(runtime, int) or isinstance(runtime, bool) or not 1 <= runtime <= 180:
        raise Refused('explicit hard runtime in 1..180 seconds required')
    if not budget_control:
        raise Refused('externally enforced spending control required')
    raise Refused('no vetted executable spending/descendant-containment backend installed; '
                  'budget files, accounting, included cost and turn caps are not enforcement')


class Harness:
    def __init__(self, root, inherited=None, cli=None):
        self.root = Path(root).resolve()
        if not self.root.is_relative_to(SCRATCH.resolve()) or self.root == SCRATCH.resolve():
            raise Refused('workspace must be a new private child of native-harness scratch')
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if any(self.root.iterdir()):
            raise Refused('workspace must be empty; refusing existing state')
        self.root.chmod(0o700)
        source = os.environ if inherited is None else inherited
        self.env = {k: source[k] for k in ('PATH', 'LANG', 'LC_ALL') if k in source}
        self.repo = self.root / 'repo'
        self.receipts = self.root / 'receipts'
        for name in ('repo', 'receipts', 'home', 'board', 'os-home', 'temp'):
            (self.root / name).mkdir(mode=0o700)
        self.env.update(HOME=str(self.root / 'os-home'),
                        TMPDIR=str(self.root / 'temp'), TMP=str(self.root / 'temp'),
                        TEMP=str(self.root / 'temp'),
                        HERMES_HOME=str(self.root / 'home'),
                        HERMES_KANBAN_HOME=str(self.root / 'board'),
                        HERMES_KANBAN_BOARD='native-harness')
        if cli is None:
            # Installed launcher needs a dependency record in the selected home.
            # Use its already-installed venv interpreter (no install/copy/repair),
            # but execute the CURRENT native module, not editable snapshot scripts.
            candidates = [Path(p) / 'python' for p in source.get('PATH', '').split(os.pathsep)
                          if Path(p).name == 'bin' and (Path(p).parent / 'pyvenv.cfg').is_file()]
            if not candidates:
                raise Refused('installed native venv interpreter missing; supply explicit cli argv')
            # Resolve through the selected installed runtime, not this script's
            # import path or a particular user's checkout location.
            try:
                resolved = subprocess.run([str(candidates[0]), '-I', '-c',
                    'from hermes_cli.config import get_project_root; print(get_project_root())'],
                    capture_output=True, text=True, timeout=3, check=True)
            except (OSError, subprocess.SubprocessError) as exc:
                raise Refused('installed native project resolution failed; supply explicit cli argv') from exc
            native_source = Path(resolved.stdout.strip())
            if not native_source.is_absolute():
                raise Refused('installed native project resolution must return an absolute path')
            boot = ('import sys,runpy; sys.path.insert(0,' + repr(str(native_source)) + '); '
                    'runpy.run_module("hermes_cli.main",run_name="__main__")')
            self.cli = [str(candidates[0]), '-I', '-c', boot]
        else:
            self.cli = list(cli)
        self.serial = 0

    def command(self, argv, timeout: float = 30, json_output=True,
                *, output_limit=1024 * 1024) -> Any:
        """Private-fixture capture cap, not secret redaction or process containment.

        observed_bytes counts bytes actually read, not all bytes a process emitted;
        retained_bytes counts raw bytes before text/newline normalization. Capture
        is complete only when both pipes reach EOF without discarded bytes/errors.
        """
        if (not isinstance(output_limit, int) or isinstance(output_limit, bool) or
                not 0 < output_limit <= 16 * 1024 * 1024):
            raise Refused('combined output limit must be a positive integer <=16 MiB')
        if not 0 < timeout <= 180:
            raise Refused('command hard runtime must be in (0,180] seconds')
        import threading
        if threading.current_thread() is not threading.main_thread():
            raise Refused('command cleanup requires main-thread shutdown handlers')
        interrupted = []
        handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
        def latch(sig, frame):
            interrupted.append(sig)
        try:
            for sig in handlers:
                signal.signal(sig, latch)
            return self._command(argv, timeout, json_output, interrupted, output_limit)
        finally:
            for sig, handler in handlers.items():
                signal.signal(sig, handler)

    def _command(self, argv, timeout, json_output, interrupted, output_limit):
        self.serial += 1
        receipt = {'argv': list(argv), 'cwd': str(self.repo), 'timed_out': False,
                   'interrupted': interrupted, 'errors': [], 'output_limit': output_limit,
                   'observed_bytes': 0, 'retained_bytes': 0,
                   'output_limit_exceeded': False, 'output_truncated': False,
                   'output_complete': False}
        receipt_path = self.receipts / f'{self.serial:04d}.json'
        try:
            proc = subprocess.Popen(argv, cwd=self.repo, env=self.env,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    start_new_session=True)
        except OSError as exc:
            receipt.update(returncode=None, stdout='', stderr='')
            receipt['errors'].append(f'spawn: {type(exc).__name__}')
            receipt_path.write_text(json.dumps(receipt, indent=2))
            raise Refused(f'command failed; receipt {self.serial:04d}.json') from exc
        # waitid(WNOWAIT) observes exit without releasing the leader PID/PGID.
        # Read pipes independently: communicate/poll/wait would reap too early.
        import selectors
        chunks = {proc.stdout: bytearray(), proc.stderr: bytearray()}
        def collect(pipe, data):
            receipt['observed_bytes'] += len(data)
            remaining = output_limit - receipt['retained_bytes']
            kept = data[:remaining]
            chunks[pipe].extend(kept)
            receipt['retained_bytes'] += len(kept)
            if len(kept) < len(data):
                receipt['output_limit_exceeded'] = True
                receipt['output_truncated'] = True
        deadline = time.monotonic() + timeout
        receipt['errors'] = []
        owned = True
        try:
            with selectors.DefaultSelector() as selector:
                for pipe in chunks:
                    assert pipe is not None
                    os.set_blocking(pipe.fileno(), False)
                    selector.register(pipe.fileno(), selectors.EVENT_READ, pipe)
                while True:
                    status = os.waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOWAIT | os.WNOHANG)
                    if status is not None or interrupted or receipt['output_limit_exceeded']:
                        break
                    if time.monotonic() >= deadline:
                        receipt['timed_out'] = True
                        break
                    for key, _ in selector.select(min(.02, max(0, deadline - time.monotonic()))):
                        data = os.read(key.fd, 65536)
                        if data:
                            collect(key.data, data)
                            if receipt['output_limit_exceeded']:
                                break
                        else:
                            selector.unregister(key.fd)
        except ChildProcessError as exc:
            owned = False
            receipt['timed_out'] = time.monotonic() >= deadline
            receipt['errors'].append('ownership lost: child already reaped')
        except Exception as exc:
            receipt['timed_out'] = time.monotonic() >= deadline
            receipt['errors'].append(f'observe: {type(exc).__name__}: exit observation unavailable' +
                                     (' after deadline' if receipt['timed_out'] else ''))
        finally:
            # No reaping operation until ALL group signals have finished.
            try:
                if owned:
                    os.killpg(proc.pid, signal.SIGKILL)
            except OSError as exc:
                receipt['errors'].append(f'signal: {type(exc).__name__}')
            try:
                # Drain with the same bounded collector, never communicate().
                # EOF on BOTH pipes is the only evidence of complete capture.
                drain_deadline = time.monotonic() + 2
                with selectors.DefaultSelector() as selector:
                    for pipe in chunks:
                        assert pipe is not None
                        os.set_blocking(pipe.fileno(), False)
                        selector.register(pipe.fileno(), selectors.EVENT_READ, pipe)
                    while selector.get_map() and not receipt['output_limit_exceeded']:
                        remaining = drain_deadline - time.monotonic()
                        if remaining <= 0:
                            raise subprocess.TimeoutExpired('private command drain', 2)
                        for key, _ in selector.select(min(.02, remaining)):
                            data = os.read(key.fd, 65536)
                            if data:
                                collect(key.data, data)
                                if receipt['output_limit_exceeded']:
                                    break
                            else:
                                selector.unregister(key.fd)
                    receipt['output_complete'] = not selector.get_map()
            except Exception as exc:
                receipt['errors'].append(f'drain: {type(exc).__name__}')
            finally:
                for pipe in chunks:
                    if pipe is not None:
                        pipe.close()
                try:
                    proc.wait(timeout=2)
                except Exception as exc:
                    receipt['errors'].append(f'reap: {type(exc).__name__}')
        import locale
        def text(prefix):
            data = bytes(prefix)
            encoding = locale.getpreferredencoding(False)
            try:
                value = data.decode(encoding)
            except UnicodeError as exc:
                receipt['errors'].append(f'decode: {type(exc).__name__}')
                value = data.decode(encoding, errors='replace')
            return value.replace('\r\n', '\n').replace('\r', '\n')
        out = text(chunks[proc.stdout])
        err = text(chunks[proc.stderr])
        receipt['output_complete'] = (receipt['output_complete'] and
                                      not receipt['output_truncated'] and not receipt['errors'])
        # Popen maps ECHILD to zero internally; that is not an observed exit.
        receipt.update(returncode=proc.returncode if owned else None, stdout=out, stderr=err)
        receipt_path.write_text(json.dumps(receipt, indent=2))
        if (receipt['timed_out'] or receipt['errors'] or interrupted or proc.returncode or
                receipt['output_limit_exceeded']):
            raise Refused(f'command failed; receipt {self.serial:04d}.json')
        return json.loads(out) if json_output else out

    def kanban(self, *args, timeout: float = 30):
        if args and args[0] == 'dispatch' and '--dry-run' not in args:
            execution_gate(False, None, None)
        return self.command(self.cli + ['kanban', '--board', 'native-harness', *args],
                            timeout=timeout, json_output='--json' in args)

    def preflight(self):
        self.command(self.cli + ['kanban', 'create', '--help'], json_output=False)
        self.command(self.cli + ['kanban', 'boards', 'create', 'native-harness'], json_output=False)
        boards = self.command(self.cli + ['kanban', 'boards', 'list', '--json'])
        board = next(b for b in boards if b['slug'] == 'native-harness')
        db = Path(board['db_path']).resolve()
        if not db.is_relative_to(self.root / 'board'):
            raise Refused('native board escaped isolated root')
        self.command(['git', 'init', '-q'], json_output=False)
        ledger = {'version': 1, 'goals': [{'id': 'G-native', 'title': 'Native integration',
                  'source': 'README.md', 'status': 'unmet', 'tasks': ['T-native'], 'priority': 1}],
                  'tasks': [{'id': 'T-native', 'goal': 'G-native', 'title': 'Native lifecycle artifact',
                             'status': 'open', 'section': 'Now'}]}
        (self.repo / 'goals.json').write_text(json.dumps(ledger))
        (self.repo / 'README.md').write_text('Isolated native harness repository.\n')
        selected = self.command([sys.executable, str(ROOT / 'repo-docs/scripts/goals.py'),
                                 'next', str(self.repo), '--json'])[0]['task']
        body = ('TASK: create artifact.txt containing exactly native-lifecycle\\n.\n'
                'DELIVERABLE: artifact.txt in the assigned isolated repository.\n'
                'SCOPE: only artifact.txt; no network, downloads, credentials or remote writes.\n'
                'VERIFY: read exact file contents.\n'
                'STOP WHEN: verified; call kanban_request_review with summary and metadata '
                '{"artifact":"artifact.txt"}; do not complete or invent approval.')
        args = ['create', selected['title'], '--body', body, '--workspace', f'dir:{self.repo}',
                '--idempotency-key', 'native-lifecycle:T-native', '--max-runtime', '30s',
                '--max-retries', '1', '--completion-contract', 'local-only', '--json']
        card = self.kanban(*args)
        duplicate = self.kanban(*args)
        if card['id'] != duplicate['id']:
            raise Refused('native idempotency failed')
        show = self.kanban('show', card['id'], '--json')
        runs = self.kanban('runs', card['id'], '--json')
        dry = self.kanban('dispatch', '--dry-run', '--max', '1', '--json')
        after = self.kanban('show', card['id'], '--json')
        if runs or after['runs'] or after['task']['id'] != card['id']:
            raise Refused('preflight unexpectedly produced a worker run')
        report = {'native_lifecycle': 'NOT_RUN', 'boundary': 'native_create_dedup_dry_dispatch',
                  'selected_task': selected['id'], 'card_id': card['id'],
                  'dedup_card_id': duplicate['id'], 'board_db': str(db), 'runs': runs,
                  'dry_dispatch': dry, 'status': show['task']['status'],
                  'evidence': str(self.receipts)}
        (self.root / 'preflight.json').write_text(json.dumps(report, indent=2))
        return report


def drive_protocol(transport, card_id, repo, *, runtime, builder, verifier, reviewer,
                   fixture_only=False):
    """FIXTURE-ONLY orchestration, not a paid-execution or containment boundary.

    The explicit flag labels caller intent; neither it nor Python type identity
    proves control of an arbitrary transport. No controller-bound transport is
    installed. The CLI run gate and Harness worker dispatch stay fail-closed.
    Never supply a live/wrapped dispatcher; this seam is for synthetic fixtures.
    """
    if fixture_only is not True:
        raise Refused('public protocol is fixture-only until controller-bound transport exists')
    if not isinstance(runtime, int) or isinstance(runtime, bool) or not 1 <= runtime <= 180:
        raise Refused('bounded lifecycle runtime required')
    if len({builder, verifier, reviewer}) != 3:
        raise Refused('distinct builder, verifier and reviewer required')
    deadline = time.monotonic() + runtime
    observed = []
    timeout_runs = []

    def call(*args):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise Refused('lifecycle deadline exhausted before transport call')
        result = transport.kanban(*args, timeout=remaining)
        if time.monotonic() >= deadline:
            raise Refused('transport returned after lifecycle deadline')
        return result

    contracts = {}
    histories = {}

    def checked_show(task_id):
        show = call('show', task_id, '--json')
        task = show['task']
        if task.get('id') != task_id:
            raise Refused('observation changed original task identity')
        fields = ('body', 'workspace_kind', 'workspace_path', 'completion_contract')
        contract = {key: task.get(key) for key in fields}
        if (not contract['body'] or contract['workspace_kind'] != 'dir' or
                contract['workspace_path'] != str(repo) or
                contract['completion_contract'] != 'local-only'):
            raise Refused('missing or mismatched original task contract')
        if task_id in contracts and contracts[task_id] != contract:
            raise Refused('observation changed immutable task contract')
        contracts.setdefault(task_id, copy.deepcopy(contract))
        runs = {run['id']: run for run in show['runs']}
        if len(runs) != len(show['runs']):
            raise Refused('duplicate run identity in history')
        previous = histories.get(task_id, {})
        if any(runs.get(ident) != old for ident, old in previous.items()):
            raise Refused('observation rewrote or removed immutable prior run history')
        histories[task_id] = copy.deepcopy({ident: run for ident, run in runs.items()
                                          if run.get('ended_at')})
        return show

    def linked_claim(run, show):
        # Native show JSON omits run.task_id/claim_lock and event.task_id.
        # Its exact task lookup/list_runs binds the rows; claimed payload is
        # the supported run_id/lock evidence (not a spending capability).
        return any(e.get('run_id') == run['id'] and e.get('kind') == 'claimed' and
                   isinstance(e.get('payload'), dict) and
                   isinstance(e['payload'].get('lock'), str) and e['payload']['lock'] and
                   e['payload'].get('run_id') == run['id']
                   for e in show['events'])

    checked_show(card_id)

    def run_and_observe(task_id, profile, outcome, status, prior_ids, timeout_retries=1):
        if time.monotonic() >= deadline:
            raise Refused('lifecycle deadline exhausted before dispatch')
        baseline = checked_show(task_id)
        if any(not run.get('ended_at') for run in baseline['runs']):
            raise Refused('preexisting active run prevents fresh dispatch')
        prior_ids = set(prior_ids) | {run['id'] for run in baseline['runs']}
        dispatch_started_at = int(time.time())
        dispatch = call('dispatch', '--max', '1', '--failure-limit', '1', '--json')
        if [s['task_id'] for s in dispatch.get('spawned', [])] != [task_id]:
            raise Refused('dispatch did not spawn exactly the expected native card')
        while time.monotonic() < deadline:
            show = checked_show(task_id)
            for run in show['runs']:
                if run['id'] in prior_ids or not run.get('ended_at'):
                    continue
                if (not isinstance(run.get('started_at'), int) or
                        not isinstance(run.get('ended_at'), int) or
                        run['started_at'] < dispatch_started_at or
                        run['ended_at'] < run['started_at']):
                    raise Refused('run lacks fresh ordered native timestamps')
                if run.get('outcome') == 'timed_out':
                    metadata = run.get('metadata') or {}
                    claim = linked_claim(run, show)
                    linked = any(e.get('run_id') == run['id'] and e.get('kind') == 'timed_out'
                                 for e in show['events'])
                    if (run.get('task_id', task_id) != task_id or run.get('profile') != profile or
                            not run.get('worker_pid') or not claim or
                            not linked or show['task']['status'] not in ('blocked', 'ready', 'review') or
                            metadata.get('pid') != run['worker_pid'] or
                            not isinstance(metadata.get('limit_seconds'), int) or
                            metadata['limit_seconds'] <= 0 or
                            not isinstance(metadata.get('elapsed_seconds'), int) or
                            metadata['elapsed_seconds'] < metadata['limit_seconds'] or
                            not isinstance(metadata.get('sigkill'), bool)):
                        raise Refused('missing linked native timeout evidence')
                    timeout_runs.append(copy.deepcopy(run))
                    if timeout_retries == 0:
                        raise Refused('fixture timeout retry exhausted; original card/history retained')
                    if show['task']['status'] == 'blocked':
                        call('unblock', task_id, '--reason', 'Fixture-only bounded timeout recovery')
                    return run_and_observe(task_id, profile, outcome, status,
                                           prior_ids | {run['id']}, timeout_retries=0)
                if (run.get('task_id', task_id) != task_id or
                        not run.get('worker_pid') or run.get('profile') != profile or
                        run.get('outcome') != outcome or not run.get('summary') or
                        not isinstance(run.get('metadata'), dict) or
                        run['metadata'].get('artifact') != 'artifact.txt' or
                        show['task']['status'] != status):
                    raise Refused('missing genuine worker outcome/structured acknowledgement')
                if not linked_claim(run, show):
                    raise Refused('worker acknowledgement lacks linked native claim')
                if not any(e.get('run_id') == run['id'] and e.get('kind') == outcome
                           for e in show['events']):
                    raise Refused('worker acknowledgement lacks linked native event')
                artifact = Path(repo) / 'artifact.txt'
                try:
                    if artifact.is_symlink() or artifact.read_bytes() != b'native-lifecycle\n':
                        raise Refused('artifact readback differs from exact contract')
                except OSError as exc:
                    raise Refused('artifact readback unavailable') from exc
                if time.monotonic() >= deadline:
                    raise Refused('lifecycle deadline exhausted after artifact readback')
                observed.append(copy.deepcopy({'task_id': task_id, 'run': run, 'show': show,
                                               'dispatch': dispatch, 'baseline': baseline}))
                return run
            if show['task']['status'] in ('blocked', 'done', 'archived'):
                raise Refused('unexpected terminal lifecycle state; no automatic duplicate card')
            time.sleep(min(.25, max(0, deadline - time.monotonic())))
        raise Refused('hard lifecycle deadline exhausted; external controller must cancel descendants')

    call('assign', card_id, builder)
    first = run_and_observe(card_id, builder, 'review_requested', 'review', set())
    # Exactly one deliberate recovery; preserve original card and immutable run.
    call('reopen-review', card_id, '--reason', 'Native harness same-card recovery')
    second = run_and_observe(card_id, builder, 'review_requested', 'review', {first['id']})
    call('assign', card_id, 'none')  # park review while independent helper verifies
    helper = call('create', 'Independently verify native artifact', '--body',
              'Read artifact.txt; require exactly native-lifecycle\\n. Do not modify the artifact. '
              'Call kanban_complete only after verification; summary and metadata must name artifact.txt.',
              '--assignee', verifier, '--workspace', f'dir:{repo}',
              '--idempotency-key', f'native-helper:{card_id}', '--max-runtime', f'{runtime}s',
              '--max-retries', '1', '--completion-contract', 'local-only', '--json')
    helper_ack = run_and_observe(helper['id'], verifier, 'completed', 'done', set())
    call('assign', card_id, reviewer)
    review_ack = run_and_observe(card_id, reviewer, 'completed', 'done', {first['id'], second['id']})
    return {'native_lifecycle': 'NOT_RUN', 'boundary': 'fixture_only_protocol',
            'card_id': card_id, 'recovery_runs': [first['id'], second['id']],
            'helper_ack': helper_ack, 'review_ack': review_ack, 'observed': observed,
            'timeout_runs': timeout_runs}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def _digest(value):
    import hashlib
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _task_contract(conn, task_id):
    row = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if row is None:
        raise Refused('existing task required')
    fields = ('id', 'title', 'body', 'assignee', 'workspace_kind', 'workspace_path',
              'branch_name', 'tenant', 'completion_contract')
    return _digest({key: row[key] for key in fields})


def _worker_origin(conn):
    """Linux process ancestry + native spawn identity, never CLI/env attribution.

    This authenticates native worker origin within the trusted local board/OS
    boundary, not against a hostile same-UID actor who can rewrite that board.
    Environments are read in memory only; claim locks are never published.
    """
    from hermes_cli import kanban_db_dispatch as dispatch
    db = next(Path(r[2]).resolve() for r in conn.execute('PRAGMA database_list')
              if r[1] == 'main')
    pid = os.getppid()  # the command itself may not claim to be its own worker
    seen = set()
    while pid > 1 and pid not in seen:
        seen.add(pid)
        try:
            stat = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
            if stat[0] == 'Z':
                raise Refused('worker ancestry contains a dead process')
            row = conn.execute('SELECT * FROM tasks WHERE worker_pid = ?', (pid,)).fetchall()
            if row:
                if len(row) != 1:
                    raise Refused('ambiguous native worker origin')
                task = row[0]
                run = conn.execute('SELECT * FROM task_runs WHERE id = ?',
                                   (task['current_run_id'],)).fetchone()
                env = dict(item.split(b'=', 1) for item in
                           Path(f'/proc/{pid}/environ').read_bytes().split(b'\0') if b'=' in item)
                fingerprint = dispatch._process_fingerprint(pid)
                if (not fingerprint or task['worker_started_at'] != fingerprint or
                        task['status'] != 'running' or not task['assignee'] or
                        not task['claim_lock'] or (task['claim_expires'] or 0) <= time.time() or
                        run is None or run['ended_at'] is not None or
                        run['task_id'] != task['id'] or run['profile'] != task['assignee'] or
                        run['worker_pid'] != pid or run['worker_started_at'] != fingerprint or
                        run['claim_lock'] != task['claim_lock'] or
                        (run['claim_expires'] or 0) <= time.time() or
                        env.get(b'HERMES_KANBAN_TASK') != task['id'].encode() or
                        env.get(b'HERMES_KANBAN_RUN_ID') != str(run['id']).encode() or
                        env.get(b'HERMES_KANBAN_CLAIM_LOCK') != task['claim_lock'].encode() or
                        not env.get(b'HERMES_KANBAN_DB') or
                        Path(os.fsdecode(env[b'HERMES_KANBAN_DB'])).resolve() != db):
                    raise Refused('native worker identity/run/lease/board binding failed')
                return {'task_id': task['id'], 'run_id': run['id'],
                        'profile': run['profile']}
            pid = int(stat[1])
        except (OSError, ValueError, IndexError) as exc:
            raise Refused('Linux native worker ancestry unreadable; no label authentication') from exc
    raise Refused('authenticated native worker ancestor required; manager/cron/env labels are not identity')


def _validate_source(payload):
    import re
    if not isinstance(payload, dict):
        raise Refused('message must be a JSON object')
    sha = payload.get('source_sha')
    hashes = payload.get('input_hashes')
    if not isinstance(sha, str) or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', sha):
        raise Refused('exact lowercase source SHA required')
    if (not isinstance(hashes, dict) or not hashes or
            any(not isinstance(k, str) or not k.strip() or
                not isinstance(v, str) or not re.fullmatch(r'[0-9a-f]{64}', v)
                for k, v in hashes.items())):
        raise Refused('nonempty named SHA256 input hashes required')


def _validate_protocol_comment(message, task_id):
    import re
    try:
        _validate_source(message)
        if (message['task_id'] != task_id or
                not re.fullmatch(r'[0-9a-f]{64}', message['handoff_id'])):
            raise ValueError('target/id')
        if message['kind'] == 'handoff':
            if set(message) != {'task_id', 'source_sha', 'input_hashes', 'scope', 'acceptance',
                                'evidence', 'protocol', 'kind', 'sender', 'recipient', 'author',
                                'task_contract', 'sender_contract', 'handoff_id'}:
                raise ValueError('handoff fields')
            for key in ('task_contract', 'sender_contract'):
                if not re.fullmatch(r'[0-9a-f]{64}', message[key]):
                    raise ValueError('contract')
            for key in ('scope', 'evidence'):
                if not isinstance(message[key], str) or not message[key].strip():
                    raise ValueError(key)
            if (not isinstance(message['acceptance'], list) or not message['acceptance'] or
                    any(not isinstance(v, str) or not v.strip() for v in message['acceptance'])):
                raise ValueError('acceptance')
            recipient = message['recipient']
            if set(recipient) != {'task_id', 'profile'} or recipient['task_id'] != task_id:
                raise ValueError('recipient')
            actor = message['sender']
            expected = dict(message)
            ident = expected.pop('handoff_id')
            if _digest(expected) != ident:
                raise ValueError('handoff hash')
        elif message['kind'] == 'ack':
            if (set(message) != {'task_id', 'handoff_id', 'source_sha', 'input_hashes', 'state',
                                 'evidence', 'protocol', 'kind', 'responder', 'author', 'handoff'} or
                    message['state'] not in ('adopted', 'rejected', 'needs-reproduction') or
                    not isinstance(message['evidence'], str) or not message['evidence'].strip()):
                raise ValueError('ack fields')
            _validate_protocol_comment(message['handoff'], task_id)
            actor = message['responder']
        else:
            raise ValueError('kind')
        if (set(actor) != {'task_id', 'run_id', 'profile'} or
                not isinstance(actor['task_id'], str) or not actor['task_id'] or
                type(actor['run_id']) is not int or actor['run_id'] <= 0 or
                not isinstance(actor['profile'], str) or not actor['profile'].strip() or
                actor['profile'] != message['author']):
            raise ValueError('actor')
    except (KeyError, TypeError, ValueError, Refused) as exc:
        raise Refused('invalid protocol comment; repair through its owning task') from exc


def _protocol_comments(conn, task_id):
    from hermes_cli import kanban_db as kb
    messages = []
    for comment in sorted(kb.list_comments(conn, task_id), key=lambda c: c.id):
        try:
            message = json.loads(comment.body)
        except (ValueError, TypeError):
            continue
        if isinstance(message, dict) and message.get('protocol') == 'native-handoff/v1':
            if comment.body != _canonical(message) or comment.author != message.get('author'):
                raise Refused('conflicting protocol comment attribution or encoding')
            _validate_protocol_comment(message, task_id)
            messages.append(message)
    return messages


def _comment_readback(conn, task_id, author, message):
    from hermes_cli import kanban_db as kb
    body = _canonical(message)
    ident = kb.add_comment(conn, task_id, author, body)
    exact = [c for c in kb.list_comments(conn, task_id) if c.id == ident]
    if (len(exact) != 1 or exact[0].body != body or exact[0].author != author or
            exact[0].task_id != task_id):
        raise Refused('exact native comment readback failed')
    return {'comment_id': ident, 'message': message, 'boundary': 'communication_only'}


def _verify_source_inputs(conn, task_id, payload):
    """Bind declarations to the source task's actual native workspace bytes."""
    import importlib.util
    row = conn.execute('SELECT workspace_path FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if row is None or not row[0]:
        raise Refused('source task must have an explicit native Git workspace')
    root = Path(row[0]).resolve(strict=True)
    try:
        from importlib import util
        spec = util.spec_from_file_location('handoff_freshness', Path(__file__).with_name('source_freshness.py'))
        assert spec is not None and spec.loader is not None
        freshness = util.module_from_spec(spec)
        spec.loader.exec_module(freshness)
        expected = {'version': 1, 'workspace': str(root), 'files': [
            {'path': name, 'sha256': digest} for name, digest in payload['input_hashes'].items()]}
        actual = subprocess.run(['git', '-C', str(root), 'rev-parse', '--verify', 'HEAD'],
                                capture_output=True, text=True, timeout=5, check=True,
                                env={k: v for k, v in os.environ.items() if not k.startswith('GIT_')})
        if actual.stdout.strip() != payload['source_sha'] or not freshness.check(expected, root)['fresh']:
            raise Refused('source inputs changed; exact current SHA and byte hashes required')
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        raise Refused('source inputs changed or unsafe; capture fresh attributed source evidence') from exc


def task_handoff(conn, payload):
    from hermes_cli import kanban_db as kb
    _validate_source(payload)
    required = {'task_id', 'source_sha', 'input_hashes', 'scope', 'acceptance', 'evidence'}
    if set(payload) != required or any(not isinstance(payload[k], str) or not payload[k].strip()
                                      for k in ('task_id', 'scope', 'evidence')):
        raise Refused('handoff requires exactly task/source/inputs/scope/acceptance/evidence')
    acceptance = payload['acceptance']
    if not isinstance(acceptance, list) or not acceptance or any(
            not isinstance(item, str) or not item.strip() for item in acceptance):
        raise Refused('nonempty acceptance checks required')
    with kb.write_txn(conn):
        origin = _worker_origin(conn)
        _verify_source_inputs(conn, origin['task_id'], payload)
        target = kb.get_task(conn, payload['task_id'])
        if target is None or not target.assignee or target.status in ('done', 'archived'):
            raise Refused('existing nonterminal assigned recipient task required')
        if target.id == origin['task_id'] or target.assignee == origin['profile']:
            raise Refused('distinct recipient task/profile required')
        message = dict(payload, protocol='native-handoff/v1', kind='handoff',
                       sender=origin, recipient={'task_id': target.id, 'profile': target.assignee},
                       author=origin['profile'], task_contract=_task_contract(conn, target.id),
                       sender_contract=_task_contract(conn, origin['task_id']))
        message['handoff_id'] = _digest(message)
        prior = _protocol_comments(conn, target.id)
        if any(m.get('handoff_id') == message['handoff_id'] for m in prior):
            raise Refused('duplicate handoff refused')
        return _comment_readback(conn, target.id, origin['profile'], message)


def task_ack(conn, payload):
    from hermes_cli import kanban_db as kb
    _validate_source(payload)
    required = {'task_id', 'handoff_id', 'source_sha', 'input_hashes', 'state', 'evidence'}
    if (set(payload) != required or
            any(not isinstance(payload[k], str) or not payload[k].strip()
                for k in ('task_id', 'handoff_id', 'state', 'evidence')) or
            payload['state'] not in ('adopted', 'rejected', 'needs-reproduction')):
        raise Refused('ack requires exact handoff/source/inputs and adopted/rejected/needs-reproduction evidence')
    with kb.write_txn(conn):
        origin = _worker_origin(conn)
        messages = _protocol_comments(conn, payload['task_id'])
        matches = [m for m in messages if m.get('kind') == 'handoff' and
                   m.get('handoff_id') == payload['handoff_id']]
        if len(matches) != 1:
            raise Refused('one exact native handoff required')
        handoff = matches[0]
        expected = dict(handoff)
        ident = expected.pop('handoff_id')
        if _digest(expected) != ident:
            raise Refused('conflicting handoff content/hash')
        if (origin['task_id'] != handoff['recipient']['task_id'] or
                origin['profile'] != handoff['recipient']['profile']):
            raise Refused('only the authenticated recipient task worker may acknowledge')
        if any(m.get('kind') == 'ack' and m.get('handoff_id') == ident for m in messages):
            raise Refused('acknowledgment already exists; duplicate/conflicting response refused')
        same_route = [m for m in messages if m.get('kind') == 'handoff' and
                      m.get('sender', {}).get('task_id') == handoff['sender']['task_id'] and
                      m.get('recipient') == handoff['recipient']]
        if (same_route[-1] != handoff or
                payload['source_sha'] != handoff['source_sha'] or
                payload['input_hashes'] != handoff['input_hashes'] or
                _task_contract(conn, payload['task_id']) != handoff['task_contract'] or
                _task_contract(conn, handoff['sender']['task_id']) != handoff['sender_contract']):
            raise Refused('stale handoff source/inputs/task contract; fresh handoff required')
        _verify_source_inputs(conn, handoff['sender']['task_id'], handoff)
        message = dict(payload, protocol='native-handoff/v1', kind='ack',
                       responder=origin, author=origin['profile'], handoff=handoff)
        return _comment_readback(conn, payload['task_id'], origin['profile'], message)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['preflight', 'run', 'handoff', 'ack'], nargs='?', default='run')
    parser.add_argument('--db', type=Path, help='existing native board database; never initialized here')
    parser.add_argument('--payload', help='JSON message; no author/profile identity overrides')
    parser.add_argument('--enable-native', action='store_true')
    parser.add_argument('--max-runtime', type=int)
    parser.add_argument('--budget-control', help='not a budget file; no vetted backend is installed')
    args = parser.parse_args(argv)
    try:
        if args.mode in ('handoff', 'ack'):
            import sqlite3
            if args.db is None or not args.db.is_file() or not args.payload:
                raise Refused('existing native board --db and JSON --payload required')
            try:
                payload = json.loads(args.payload)
                with __import__('contextlib').closing(sqlite3.connect(
                        args.db.resolve().as_uri() + '?mode=rw', uri=True, timeout=5)) as conn:
                    conn.row_factory = sqlite3.Row
                    report = (task_handoff if args.mode == 'handoff' else task_ack)(conn, payload)
                    # Read the exact committed target again, not just INSERT success.
                    from hermes_cli import kanban_db as kb
                    exact = [c for c in kb.list_comments(conn, payload['task_id'])
                             if c.id == report['comment_id']]
                    if len(exact) != 1 or exact[0].body != _canonical(report['message']):
                        raise Refused('committed native comment readback failed')
            except (ValueError, OSError, sqlite3.Error, ImportError, PermissionError) as exc:
                raise Refused('native comment protocol unavailable: ' + type(exc).__name__) from exc
            print(json.dumps(report))
            return 0
        if args.mode == 'run':
            # Gate before mkdir, profile configuration, board mutation or dispatch.
            execution_gate(args.enable_native, args.max_runtime, args.budget_control)
        SCRATCH.mkdir(parents=True, exist_ok=True)
        path = Path(tempfile.mkdtemp(prefix='preflight-', dir=SCRATCH))
        report = Harness(path).preflight()
        print(json.dumps(report, indent=2))
        return 0
    except Refused as exc:
        print(json.dumps({'native_lifecycle': 'NOT_RUN', 'boundary': 'refused_before_dispatch',
                          'reason': str(exc)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
