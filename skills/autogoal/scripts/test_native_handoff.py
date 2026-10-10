"""Native comments integration: isolated SQLite + real claimed OS fixture workers.
Run explicitly with HERMES_NATIVE_HANDOFF_TEST=1, the installed native interpreter,
and its already-installed dependencies/native source on PYTHONPATH.
No dispatch, provider, live board, or product operations.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from typing import Any

import native_lifecycle as lifecycle
kb: Any = None
kbc: Any = None
dispatch: Any = None
NATIVE_TESTS = os.environ.get('HERMES_NATIVE_HANDOFF_TEST') == '1'
if NATIVE_TESTS:
    from hermes_cli import kanban_db as kb
    from hermes_cli import kanban_db_connect as kbc
    from hermes_cli import kanban_db_dispatch as dispatch


def worker():
    for line in sys.stdin:
        request = json.loads(line)
        args = request['args'] if isinstance(request, dict) else request
        env = dict(os.environ, **request.get('env', {})) if isinstance(request, dict) else None
        result = subprocess.run([sys.executable, str(Path(lifecycle.__file__)), *args],
                                text=True, capture_output=True, timeout=10, env=env)
        print(json.dumps({'code': result.returncode, 'out': result.stdout,
                          'err': result.stderr}), flush=True)


class OfflineInventory(unittest.TestCase):
    def test_offline_source_validation_rejects_unsafe_hashes(self):
        for bad in ({}, {'source_sha': 'A' * 40, 'input_hashes': {'x': 'b' * 64}},
                    {'source_sha': 'a' * 40, 'input_hashes': {}},
                    {'source_sha': 'a' * 40, 'input_hashes': {'x': 'not-sha256'}}):
            with self.assertRaises(lifecycle.Refused):
                lifecycle._validate_source(bad)
        lifecycle._validate_source({'source_sha': 'a' * 40, 'input_hashes': {'x': 'b' * 64}})

    def test_offline_protocol_integrity_rejects_scope_tampering(self):
        message = {'task_id': 'fixture-target', 'source_sha': 'a' * 40,
                   'input_hashes': {'fixture.txt': 'b' * 64}, 'scope': 'bounded reproduction',
                   'acceptance': ['exact comparison'], 'evidence': 'fixture://source',
                   'protocol': 'native-handoff/v1', 'kind': 'handoff',
                   'sender': {'task_id': 'fixture-source', 'run_id': 1, 'profile': 'fixture-source'},
                   'recipient': {'task_id': 'fixture-target', 'profile': 'fixture-recipient'},
                   'author': 'fixture-source', 'task_contract': 'c' * 64, 'sender_contract': 'd' * 64}
        message['handoff_id'] = lifecycle._digest(message)
        lifecycle._validate_protocol_comment(message, 'fixture-target')
        for change in ({'scope': 'broadened scope'}, {'handoff_id': 'f' * 64}, {'author': 'forged'}):
            with self.assertRaises(lifecycle.Refused):
                lifecycle._validate_protocol_comment(dict(message, **change), 'fixture-target')

    def test_native_fixture_is_opt_in_without_native_imports(self):
        env = dict(os.environ)
        env.pop('HERMES_NATIVE_HANDOFF_TEST', None)
        result = subprocess.run([sys.executable, '-m', 'unittest',
                                 'test_native_handoff.Handoff', '-v'],
                                capture_output=True, text=True, env=env, timeout=10,
                                cwd=Path(__file__).parent)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('skipped', result.stderr)


@unittest.skipUnless(NATIVE_TESTS, 'opt-in native fixture requires HERMES_NATIVE_HANDOFF_TEST=1')
class Handoff(unittest.TestCase):
    def setUp(self):
        lifecycle.SCRATCH.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='handoff-', dir=lifecycle.SCRATCH)
        self.h = lifecycle.Harness(self.temp.name, cli=[sys.executable])
        from unittest.mock import patch
        isolated = dict(self.h.env, PYTHONPATH=os.environ.get('PYTHONPATH', ''),
                        PYTHONDONTWRITEBYTECODE='1', HERMES_NATIVE_HANDOFF_TEST='1')
        self.environment = patch.dict(os.environ, isolated, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.addCleanup(self.temp.cleanup)
        self.db = self.h.root / 'board/kanban.db'
        import hashlib
        self.h.command(['git', 'init', '-q'], json_output=False)
        self.h.command(['git', 'config', 'user.name', 'Fixture'], json_output=False)
        self.h.command(['git', 'config', 'user.email', 'fixture@local'], json_output=False)
        (self.h.repo / 'fixture.txt').write_text('source input\n')
        self.h.command(['git', 'add', 'fixture.txt'], json_output=False)
        self.h.command(['git', 'commit', '-qm', 'fixture'], json_output=False)
        source_sha = self.h.command(['git', 'rev-parse', 'HEAD'], json_output=False).strip()
        self.conn = kbc.connect(db_path=self.db)
        self.sender = kb.create_task(self.conn, title='Fixture evidence sender',
                                     assignee='fixture-source', body='Source-only finding',
                                     workspace_kind='dir', workspace_path=str(self.h.repo))
        self.target = kb.create_task(self.conn, title='Fixture recipient',
                                     assignee='fixture-recipient', body='Bounded reproduction')
        self.workers = []
        self.source = self.start_worker(self.sender)
        self.recipient = self.start_worker(self.target)
        self.payload = {'task_id': self.target, 'source_sha': source_sha,
                        'input_hashes': {'fixture.txt': hashlib.sha256(b'source input\n').hexdigest()},
                        'scope': 'Reproduce the source-only fixture finding',
                        'acceptance': ['Compare exact fixture bytes'],
                        'evidence': 'fixture://source-finding'}

    def tearDown(self):
        for proc in self.workers:
            proc.stdin.close()
            proc.wait(timeout=5)
            proc.stdout.close()
        self.conn.close()
        self.temp.cleanup()

    def start_worker(self, task_id):
        claimed = kb.claim_task(self.conn, task_id, ttl_seconds=60)
        self.assertIsNotNone(claimed)
        assert claimed is not None and claimed.claim_lock is not None
        env = dict(self.h.env, PYTHONPATH=os.environ.get('PYTHONPATH', ''),
                   HERMES_KANBAN_DB=str(self.db), HERMES_KANBAN_TASK=task_id,
                   HERMES_KANBAN_RUN_ID=str(claimed.current_run_id),
                   HERMES_KANBAN_CLAIM_LOCK=claimed.claim_lock,
                   PYTHONDONTWRITEBYTECODE='1')
        proc = subprocess.Popen([sys.executable, str(Path(__file__)), '--worker'],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                text=True, env=env)
        self.workers.append(proc)
        dispatch._set_worker_pid(self.conn, task_id, proc.pid)
        return proc

    def call(self, proc, mode, payload, env=None):
        args = [mode, '--db', str(self.db), '--payload', json.dumps(payload)]
        proc.stdin.write(json.dumps({'args': args, 'env': env or {}}) + '\n')
        proc.stdin.flush()
        return json.loads(proc.stdout.readline())

    def successful(self, proc, mode, payload):
        result = self.call(proc, mode, payload)
        self.assertEqual(result['code'], 0, result)
        return json.loads(result['out'])

    def comments(self):
        return kb.list_comments(self.conn, self.target)

    def ack_payload(self, message, state='adopted'):
        return {'task_id': self.target, 'handoff_id': message['handoff_id'],
                'source_sha': message['source_sha'], 'input_hashes': message['input_hashes'],
                'state': state, 'evidence': 'fixture://recipient-reproduction'}

    def test_actual_source_retraction_refuses_ack_and_forged_send(self):
        message = self.successful(self.source, 'handoff', self.payload)['message']
        (self.h.repo / 'fixture.txt').write_text('retracted source\n')
        self.assert_refused(self.recipient, 'ack', self.ack_payload(message), 'source inputs changed')
        changed = dict(self.payload, evidence='fixture://new-but-stale')
        self.assert_refused(self.source, 'handoff', changed, 'source inputs changed')

    def test_ack_exact_native_readback_and_duplicate_conflict_refusal(self):
        for state in ('adopted', 'rejected', 'needs-reproduction'):
            with self.subTest(state=state):
                self.payload['evidence'] = 'fixture://finding/' + state
                handoff = self.successful(self.source, 'handoff', self.payload)['message']
                before = [dict(r) for r in self.conn.execute('SELECT * FROM tasks ORDER BY id')]
                payload = self.ack_payload(handoff, state)
                result = self.successful(self.recipient, 'ack', payload)
                exact = next(c for c in self.comments() if c.id == result['comment_id'])
                self.assertEqual(json.loads(exact.body), result['message'])
                self.assertEqual(exact.author, 'fixture-recipient')
                self.assertEqual(result['message']['responder']['task_id'], self.target)
                self.assertEqual(result['message']['responder']['run_id'],
                                 kb.get_task(self.conn, self.target).current_run_id)
                self.assertEqual(result['message']['state'], state)
                self.assertEqual(result['message']['handoff'], handoff)
                count = len(self.comments())
                for response in (state, 'rejected' if state != 'rejected' else 'adopted'):
                    payload['state'] = response
                    refused = self.call(self.recipient, 'ack', payload)
                    self.assertEqual(refused['code'], 2, refused)
                    self.assertIn('acknowledgment already exists', refused['out'])
                self.assertEqual(len(self.comments()), count)
                self.assertEqual(before, [dict(r) for r in self.conn.execute('SELECT * FROM tasks ORDER BY id')])

    def assert_refused(self, proc, mode, payload, reason, env=None):
        before = len(self.comments())
        tasks = [dict(r) for r in self.conn.execute('SELECT * FROM tasks ORDER BY id')]
        result = self.call(proc, mode, payload, env)
        self.assertEqual(result['code'], 2, result)
        self.assertIn(reason, result['out'])
        self.assertNotIn('Traceback', result['err'])
        self.assertEqual(len(self.comments()), before)
        self.assertEqual(tasks, [dict(r) for r in self.conn.execute('SELECT * FROM tasks ORDER BY id')])

    def test_parent_native_api_home_and_board_are_isolated(self):
        self.assertEqual(os.environ.get('HERMES_HOME'), self.h.env['HERMES_HOME'])
        self.assertEqual(os.environ.get('HERMES_KANBAN_HOME'), self.h.env['HERMES_KANBAN_HOME'])
        self.assertFalse(any(k in os.environ for k in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY',
                                                      'HERMES_DELEGATED_CHILD_CONTEXT')))

    def test_duplicate_handoff_and_untrusted_payload_labels_refused(self):
        self.successful(self.source, 'handoff', self.payload)
        self.assert_refused(self.source, 'handoff', self.payload, 'duplicate handoff')
        for change in ({'author': 'fixture-recipient'}, {'profile': 'fixture-recipient'},
                       {'source_sha': 'A' * 40}, {'input_hashes': {}},
                       {'scope': ''}, {'acceptance': []}):
            with self.subTest(change=change):
                self.assert_refused(self.source, 'handoff', dict(self.payload, **change), 'required' if
                                    'source_sha' in change or 'input_hashes' in change or
                                    'acceptance' in change else 'handoff requires')

    def test_sender_cannot_ack_even_with_recipient_environment_labels(self):
        message = self.successful(self.source, 'handoff', self.payload)['message']
        target = kb.get_task(self.conn, self.target)
        assert target is not None and target.claim_lock is not None
        spoof = {'HERMES_KANBAN_TASK': self.target,
                 'HERMES_KANBAN_RUN_ID': str(target.current_run_id),
                 'HERMES_KANBAN_CLAIM_LOCK': target.claim_lock,
                 'HERMES_PROFILE': 'fixture-recipient'}
        self.assert_refused(self.source, 'ack', self.ack_payload(message),
                            'authenticated recipient', spoof)
        result = self.successful(self.recipient, 'ack', self.ack_payload(message))
        self.assertNotIn(target.claim_lock, json.dumps(result))

    def test_different_native_task_with_same_recipient_profile_cannot_ack(self):
        message = self.successful(self.source, 'handoff', self.payload)['message']
        other = kb.create_task(self.conn, title='Fixture other recipient task',
                               assignee='fixture-recipient', body='Unrelated contract')
        other_worker = self.start_worker(other)
        self.assert_refused(other_worker, 'ack', self.ack_payload(message), 'authenticated recipient')
        self.successful(self.recipient, 'ack', self.ack_payload(message))

    def test_unclaimed_manager_process_with_copied_worker_env_refused(self):
        target = kb.get_task(self.conn, self.target)
        assert target is not None and target.claim_lock is not None
        env = dict(self.h.env, PYTHONPATH=os.environ['PYTHONPATH'],
                   HERMES_KANBAN_DB=str(self.db), HERMES_KANBAN_TASK=self.target,
                   HERMES_KANBAN_RUN_ID=str(target.current_run_id),
                   HERMES_KANBAN_CLAIM_LOCK=target.claim_lock)
        result = subprocess.run([sys.executable, str(Path(lifecycle.__file__)), 'handoff',
                                 '--db', str(self.db), '--payload', json.dumps(self.payload)],
                                text=True, capture_output=True, env=env, timeout=10)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('authenticated native worker ancestor required', result.stdout)
        self.assertEqual(self.comments(), [])

    def test_stale_source_inputs_scope_assignment_and_superseded_handoff_refused(self):
        message = self.successful(self.source, 'handoff', self.payload)['message']
        for change in ({'source_sha': 'c' * 40}, {'input_hashes': {'fixture.txt': 'd' * 64}}):
            self.assert_refused(self.recipient, 'ack', dict(self.ack_payload(message), **change),
                                'stale handoff')
        for field, value in (('body', 'Changed fixture scope'), ('assignee', 'fixture-other')):
            old = self.conn.execute(f'SELECT {field} FROM tasks WHERE id = ?', (self.target,)).fetchone()[0]
            with kb.write_txn(self.conn):
                self.conn.execute(f'UPDATE tasks SET {field} = ? WHERE id = ?', (value, self.target))
            self.assert_refused(self.recipient, 'ack', self.ack_payload(message),
                                'stale handoff' if field == 'body' else 'binding failed')
            with kb.write_txn(self.conn):
                self.conn.execute(f'UPDATE tasks SET {field} = ? WHERE id = ?', (old, self.target))
        self.h.command(['git', 'commit', '--allow-empty', '-qm', 'fresh fixture revision'], json_output=False)
        self.payload['source_sha'] = self.h.command(['git', 'rev-parse', 'HEAD'], json_output=False).strip()
        fresh = self.successful(self.source, 'handoff', self.payload)['message']
        self.assert_refused(self.recipient, 'ack', self.ack_payload(message), 'stale handoff')
        self.successful(self.recipient, 'ack', self.ack_payload(fresh))

    def test_expired_lease_mismatched_run_lock_and_pid_fingerprint_refused(self):
        for table, key, field, value in (
                ('tasks', self.sender, 'claim_expires', 1),
                ('tasks', self.sender, 'worker_started_at', 'unverified'),
                ('tasks', self.sender, 'current_run_id', 999999),
                ('tasks', self.sender, 'claim_lock', 'fixture-wrong-lock'),
                ('task_runs', kb.get_task(self.conn, self.sender).current_run_id, 'ended_at', 1),
                ('task_runs', kb.get_task(self.conn, self.sender).current_run_id, 'claim_expires', 1)):
            with self.subTest(table=table, field=field):
                old = self.conn.execute(f'SELECT {field} FROM {table} WHERE id = ?', (key,)).fetchone()[0]
                with kb.write_txn(self.conn):
                    self.conn.execute(f'UPDATE {table} SET {field} = ? WHERE id = ?', (value, key))
                self.assert_refused(self.source, 'handoff', self.payload, 'binding failed')
                with kb.write_txn(self.conn):
                    self.conn.execute(f'UPDATE {table} SET {field} = ? WHERE id = ?', (old, key))
        self.successful(self.source, 'handoff', self.payload)

    def test_missing_board_and_unknown_task_never_created(self):
        missing = self.h.root / 'board/missing.db'
        result = subprocess.run([sys.executable, str(Path(lifecycle.__file__)), 'handoff',
                                 '--db', str(missing), '--payload', json.dumps(self.payload)],
                                text=True, capture_output=True, env=dict(self.h.env,
                                PYTHONPATH=os.environ['PYTHONPATH']), timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(missing.exists())
        self.assert_refused(self.source, 'handoff', dict(self.payload, task_id='fixture-missing'),
                            'assigned recipient task required')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM tasks').fetchone()[0], 2)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM task_runs').fetchone()[0], 2)

    def test_malformed_protocol_comment_fails_closed_without_traceback(self):
        forged = dict(self.payload, protocol='native-handoff/v1', kind='handoff',
                      author='fixture-source')
        forged['handoff_id'] = lifecycle._digest(forged)
        kb.add_comment(self.conn, self.target, 'fixture-source', lifecycle._canonical(forged))
        result = self.call(self.recipient, 'ack', self.ack_payload(forged))
        self.assertEqual(result['code'], 2, result)
        self.assertIn('invalid protocol comment', result['out'])
        self.assertNotIn('Traceback', result['err'])
        self.assertEqual(len(self.comments()), 1)

    def test_handoff_exact_native_readback_preserves_ownership(self):
        before = [dict(r) for r in self.conn.execute('SELECT * FROM tasks ORDER BY id')]
        result = self.successful(self.source, 'handoff', self.payload)
        comments = self.comments()
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0].id, result['comment_id'])
        self.assertEqual(json.loads(comments[0].body), result['message'])
        self.assertEqual(comments[0].author, 'fixture-source')
        self.assertEqual(result['message']['sender']['task_id'], self.sender)
        self.assertEqual(result['message']['recipient']['task_id'], self.target)
        self.assertEqual(result['message']['scope'], self.payload['scope'])
        self.assertEqual(result['message']['acceptance'], self.payload['acceptance'])
        self.assertEqual(result['message']['evidence'], self.payload['evidence'])
        self.assertEqual(before, [dict(r) for r in self.conn.execute('SELECT * FROM tasks ORDER BY id')])


if __name__ == '__main__':
    if sys.argv[1:] == ['--worker']:
        worker()
    else:
        unittest.main()
