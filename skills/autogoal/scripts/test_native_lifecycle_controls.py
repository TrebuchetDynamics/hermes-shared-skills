"""Offline control tests. External CLI fixtures NEVER qualify native acceptance."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from typing import Any

MODULE = Path(__file__).with_name('native_lifecycle.py')
SCRATCH = Path.home() / '.hermes/cache/scratch/executable-safeguards/native-harness'


class FixtureTransport:
    """Explicitly FAKE native JSON; no workers, spending or containment evidence."""
    def __init__(self, repo, fault=None):
        import copy
        self.copy = copy.deepcopy
        self.repo, self.fault = str(repo), fault
        self.calls, self.timeouts, self.phase = [], [], 0
        self.cards = {'original': self.card('original', 'Original immutable artifact contract')}
        self.histories = {'original': []}
        self.events = {'original': []}
        self.profiles = {'original': 'build'}
        if fault == 'stale':
            self.append_run('original', 101, 'build', 'review_requested')

    def card(self, ident, body):
        return {'id': ident, 'body': body, 'workspace_kind': 'dir',
                'workspace_path': self.repo, 'completion_contract': 'local-only', 'status': 'ready'}

    def append_run(self, ident, run_id, profile, outcome):
        import time
        now = int(time.time())
        run = {'id': run_id, 'worker_pid': 12345,
               'profile': profile, 'outcome': outcome, 'ended_at': now, 'started_at': now,
               'summary': 'fixture artifact.txt verification', 'metadata': {'artifact': 'artifact.txt'}}
        self.histories[ident].append(run)
        self.events[ident].extend([
            {'kind': 'claimed', 'run_id': run_id,
             'payload': {'lock': f'fixture-lock-{run_id}', 'expires': now + 30, 'run_id': run_id}},
            {'kind': outcome, 'run_id': run_id}])
        self.cards[ident]['status'] = 'done' if outcome == 'completed' else 'review'

    def kanban(self, *args, timeout=None) -> Any:
        self.calls.append(args)
        self.timeouts.append(timeout)
        op = args[0]
        if op == 'assign':
            self.profiles[args[1]] = args[2]
        if op == 'reopen-review':
            self.cards[args[1]]['status'] = 'ready'
        if op == 'create':
            self.cards['helper'] = self.card('helper', args[args.index('--body') + 1])
            self.histories['helper'], self.events['helper'] = [], []
            self.profiles['helper'] = 'verify'
            return {'id': 'helper'}
        if op == 'dispatch':
            self.phase += 1
            ident = 'helper' if self.phase == 3 else 'original'
            if not (self.fault == 'stale' and self.phase == 1):
                self.append_run(ident, self.phase, self.profiles[ident],
                                'completed' if self.phase >= 3 else 'review_requested')
            return {'spawned': [{'task_id': ident}]}
        if op == 'show':
            ident = args[1]
            result = self.copy({'task': self.cards[ident], 'runs': self.histories[ident],
                                'events': self.events[ident]})
            if self.fault == 'synthetic' and result['runs']:
                result['runs'][-1]['worker_pid'] = None
            return result
        return {}


class TimeoutFixtureTransport(FixtureTransport):
    """FAKE timed_out/gave_up state and native unblock seam, never actual recovery."""
    def __init__(self, repo, exhaust=False):
        super().__init__(repo)
        self.exhaust, self.timeout_count = exhaust, 0

    def kanban(self, *args, timeout=None) -> Any:
        if args[0] == 'unblock':
            self.cards[args[1]]['status'] = 'ready'
        if args[0] == 'dispatch' and (self.exhaust or self.timeout_count == 0):
            self.calls.append(args)
            self.timeouts.append(timeout)
            self.timeout_count += 1
            self.append_run('original', 100 + self.timeout_count, 'build', 'timed_out')
            run = self.histories['original'][-1]
            run.update(summary=None, error='fixture runtime exceeded',
                       metadata={'pid': 12345, 'elapsed_seconds': 30, 'limit_seconds': 30,
                                 'sigkill': True, 'retry_status': 'ready'})
            self.cards['original']['status'] = 'blocked'
            return {'spawned': [{'task_id': 'original'}]}
        return super().kanban(*args, timeout=timeout)


class Controls(unittest.TestCase):
    def load(self):
        self.assertTrue(MODULE.exists(), 'native lifecycle controls not implemented')
        spec = importlib.util.spec_from_file_location('native_lifecycle', MODULE)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_fixture_rejects_preexisting_run_as_fresh_dispatch(self):
        m = self.load()
        fake = FixtureTransport('/isolated/repo', fault='stale')
        with self.assertRaises(m.Refused):
            m.drive_protocol(fake, 'original', '/isolated/repo', runtime=1,
                             builder='build', verifier='verify', reviewer='review', fixture_only=True)
        self.assertEqual(fake.phase, 1)

    def test_fixture_rejects_run_linked_to_wrong_card(self):
        m = self.load()
        class WrongCard(FixtureTransport):
            def append_run(self, ident, run_id, profile, outcome):
                super().append_run(ident, run_id, profile, outcome)
                self.histories[ident][-1]['task_id'] = 'unrelated'
        with self.assertRaises(m.Refused):
            m.drive_protocol(WrongCard('/isolated/repo'), 'original', '/isolated/repo',
                             runtime=1, builder='build', verifier='verify', reviewer='review', fixture_only=True)

    def test_fixture_rejects_ack_without_native_claim(self):
        m = self.load()
        class NoClaim(FixtureTransport):
            def append_run(self, ident, run_id, profile, outcome):
                super().append_run(ident, run_id, profile, outcome)
                self.events[ident] = [e for e in self.events[ident] if e['kind'] != 'claimed']
        with self.assertRaises(m.Refused):
            m.drive_protocol(NoClaim('/isolated/repo'), 'original', '/isolated/repo',
                             runtime=1, builder='build', verifier='verify', reviewer='review', fixture_only=True)

    def test_fixture_rejects_arbitrary_artifact_metadata(self):
        m = self.load()
        class ArbitraryAck(FixtureTransport):
            def append_run(self, ident, run_id, profile, outcome):
                super().append_run(ident, run_id, profile, outcome)
                self.histories[ident][-1]['metadata'] = {'unrelated': True}
        with self.assertRaises(m.Refused):
            m.drive_protocol(ArbitraryAck('/isolated/repo'), 'original', '/isolated/repo',
                             runtime=1, builder='build', verifier='verify', reviewer='review', fixture_only=True)

    def test_fixture_rejects_final_success_returned_after_deadline(self):
        import time
        m = self.load()
        class LateSuccess(FixtureTransport):
            def kanban(self, *args, timeout=None) -> Any:
                if args[0] == 'show' and self.phase == 4:
                    time.sleep(1.1)
                return super().kanban(*args, timeout=timeout)
        repo = self.fixture_repo()
        fake = LateSuccess(repo)
        with self.assertRaisesRegex(m.Refused, 'deadline'):
            m.drive_protocol(fake, 'original', repo, runtime=1,
                             builder='build', verifier='verify', reviewer='review', fixture_only=True)
        self.assertTrue(fake.timeouts)
        self.assertTrue(all(v is not None and 0 < v <= 1 for v in fake.timeouts))
        self.assertEqual(fake.timeouts, sorted(fake.timeouts, reverse=True))

    def fixture_repo(self, content: bytes | None = b'native-lifecycle\n'):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(temp.cleanup)
        repo = Path(temp.name)
        if content is not None:
            (repo / 'artifact.txt').write_bytes(content)
        return repo

    def test_fixture_rejects_missing_or_inexact_artifact_readback(self):
        m = self.load()
        for content in (None, b'native-lifecycle', b'native-lifecycle\r\n', b'wrong\n'):
            with self.subTest(content=content):
                repo = self.fixture_repo(content)
                with self.assertRaisesRegex(m.Refused, 'artifact'):
                    m.drive_protocol(FixtureTransport(repo), 'original', repo, runtime=1,
                                     builder='build', verifier='verify', reviewer='review', fixture_only=True)

    def test_fixture_rejects_changed_original_contract(self):
        m = self.load()
        for field, value in [('body', 'overwritten'), ('workspace_path', '/unrelated'),
                             ('workspace_kind', 'worktree'), ('completion_contract', None)]:
            with self.subTest(field=field):
                class ChangedContract(FixtureTransport):
                    def append_run(self, ident, run_id, profile, outcome):
                        super().append_run(ident, run_id, profile, outcome)
                        self.cards[ident][field] = value
                repo = self.fixture_repo()
                with self.assertRaisesRegex(m.Refused, 'contract'):
                    m.drive_protocol(ChangedContract(repo), 'original', repo, runtime=1,
                                     builder='build', verifier='verify', reviewer='review', fixture_only=True)

    def test_fixture_rejects_rewritten_or_removed_prior_run_history(self):
        m = self.load()
        for remove in (False, True):
            with self.subTest(remove=remove):
                class RewriteHistory(FixtureTransport):
                    def kanban(self, *args, timeout=None) -> Any:
                        if args[0] == 'reopen-review':
                            if remove:
                                self.histories['original'].clear()
                            else:
                                self.histories['original'][0]['summary'] = 'rewritten'
                        return super().kanban(*args, timeout=timeout)
                repo = self.fixture_repo()
                with self.assertRaisesRegex(m.Refused, 'history'):
                    m.drive_protocol(RewriteHistory(repo), 'original', repo, runtime=1,
                                     builder='build', verifier='verify', reviewer='review', fixture_only=True)

    def test_public_protocol_is_explicitly_fixture_only(self):
        m = self.load()
        repo = self.fixture_repo()
        fake = FixtureTransport(repo)
        with self.assertRaisesRegex(m.Refused, 'fixture-only'):
            m.drive_protocol(fake, 'original', repo, runtime=1,
                             builder='build', verifier='verify', reviewer='review')
        self.assertEqual(fake.calls, [])

    def test_wrapped_harness_cannot_dispatch_workers(self):
        m = self.load()
        repo = self.fixture_repo()
        fake = FixtureTransport(repo)
        h = object.__new__(m.Harness)
        h.cli = []
        h.command = lambda argv, **kwargs: fake.kanban(*argv[3:], timeout=kwargs['timeout'])
        class Wrapper:
            def kanban(self, *args, timeout=None) -> Any:
                return h.kanban(*args, timeout=timeout)
        with self.assertRaises(m.Refused):
            m.drive_protocol(Wrapper(), 'original', repo, runtime=1, builder='build',
                             verifier='verify', reviewer='review', fixture_only=True)
        self.assertFalse(any(c[0] == 'dispatch' for c in fake.calls))

    def test_fixture_timeout_recovers_same_card_with_bounded_attempts(self):
        m = self.load()
        repo = self.fixture_repo()
        fake = TimeoutFixtureTransport(repo)
        original = fake.copy(fake.cards['original'])
        result = m.drive_protocol(fake, 'original', repo, runtime=2, builder='build',
                                  verifier='verify', reviewer='review', fixture_only=True)
        self.assertEqual(result['native_lifecycle'], 'NOT_RUN')
        self.assertEqual(result['timeout_runs'][0]['id'], 101)
        self.assertEqual([c[1] for c in fake.calls if c[0] == 'unblock'], ['original'])
        self.assertEqual(len([c for c in fake.calls if c[0] == 'dispatch']), 5)
        self.assertEqual([r['id'] for r in fake.histories['original']], [101, 1, 2, 4])
        for field in ('id', 'body', 'workspace_path', 'workspace_kind', 'completion_contract'):
            self.assertEqual(fake.cards['original'][field], original[field])
        self.assertEqual(len([c for c in fake.calls if c[0] == 'create']), 1)

    def test_fixture_timeout_retry_exhaustion_retains_original_card_history(self):
        m = self.load()
        repo = self.fixture_repo()
        fake = TimeoutFixtureTransport(repo, exhaust=True)
        original = fake.copy(fake.cards['original'])
        with self.assertRaisesRegex(m.Refused, 'retry exhausted'):
            m.drive_protocol(fake, 'original', repo, runtime=2, builder='build',
                             verifier='verify', reviewer='review', fixture_only=True)
        self.assertEqual(len([c for c in fake.calls if c[0] == 'dispatch']), 2)
        self.assertEqual([c[1] for c in fake.calls if c[0] == 'unblock'], ['original'])
        self.assertFalse(any(c[0] in ('create', 'complete', 'request-review') for c in fake.calls))
        self.assertEqual([r['id'] for r in fake.histories['original']], [101, 102])
        self.assertTrue(all(r['outcome'] == 'timed_out' for r in fake.histories['original']))
        self.assertEqual(fake.cards['original']['status'], 'blocked')
        for field in ('id', 'body', 'workspace_path', 'workspace_kind', 'completion_contract'):
            self.assertEqual(fake.cards['original'][field], original[field])

    def test_fixture_allows_fresh_running_run_to_end(self):
        m = self.load()
        class InProgress(FixtureTransport):
            def __init__(self, repo):
                super().__init__(repo)
                self.pending = False
            def kanban(self, *args, timeout=None) -> Any:
                if args[0] == 'dispatch':
                    result = super().kanban(*args, timeout=timeout)
                    ident = result['spawned'][0]['task_id']
                    self.pending = ident
                    return result
                result = super().kanban(*args, timeout=timeout)
                if args[0] == 'show' and self.pending:
                    result['runs'][-1]['ended_at'] = None
                    result['task']['status'] = 'running'
                    self.pending = False
                return result
        repo = self.fixture_repo()
        result = m.drive_protocol(InProgress(repo), 'original', repo, runtime=3, builder='build',
                                  verifier='verify', reviewer='review', fixture_only=True)
        self.assertEqual(result['review_ack']['outcome'], 'completed')

    def test_fixture_accepts_supported_native_show_schema_without_invented_fields(self):
        m = self.load()
        class NativeShape(FixtureTransport):
            def kanban(self, *args, timeout=None) -> Any:
                result = super().kanban(*args, timeout=timeout)
                if args[0] == 'show':
                    for run in result['runs']:
                        for field in ('task_id', 'claim_lock', 'claim_expires'):
                            run.pop(field, None)
                    for event in result['events']:
                        event.pop('task_id', None)
                return result
        repo = self.fixture_repo()
        result = m.drive_protocol(NativeShape(repo), 'original', repo, runtime=1, builder='build',
                                  verifier='verify', reviewer='review', fixture_only=True)
        self.assertEqual(result['native_lifecycle'], 'NOT_RUN')

    def test_fixture_rejects_old_timestamps_on_newly_presented_run(self):
        m = self.load()
        class OldRun(FixtureTransport):
            def append_run(self, ident, run_id, profile, outcome):
                super().append_run(ident, run_id, profile, outcome)
                self.histories[ident][-1].update(started_at=1, ended_at=2)
        repo = self.fixture_repo()
        with self.assertRaisesRegex(m.Refused, 'fresh'):
            m.drive_protocol(OldRun(repo), 'original', repo, runtime=1, builder='build',
                             verifier='verify', reviewer='review', fixture_only=True)

    def test_fixture_rejects_boolean_runtime(self):
        m = self.load()
        repo = self.fixture_repo()
        fake = FixtureTransport(repo)
        with self.assertRaisesRegex(m.Refused, 'runtime'):
            m.drive_protocol(fake, 'original', repo, runtime=True, builder='build',
                             verifier='verify', reviewer='review', fixture_only=True)
        self.assertEqual(fake.calls, [])

    def test_fixture_refuses_dispatch_with_preexisting_active_run(self):
        m = self.load()
        repo = self.fixture_repo()
        fake = FixtureTransport(repo)
        fake.append_run('original', 777, 'build', 'review_requested')
        fake.histories['original'][0]['ended_at'] = None
        fake.cards['original']['status'] = 'running'
        with self.assertRaisesRegex(m.Refused, 'active'):
            m.drive_protocol(fake, 'original', repo, runtime=1, builder='build',
                             verifier='verify', reviewer='review', fixture_only=True)
        self.assertFalse(any(c[0] == 'dispatch' for c in fake.calls))

    def test_fixture_snapshots_complete_run_history_before_every_dispatch(self):
        m = self.load()
        repo = self.fixture_repo()
        fake = FixtureTransport(repo)
        result = m.drive_protocol(fake, 'original', repo, runtime=1, builder='build',
                                  verifier='verify', reviewer='review', fixture_only=True)
        self.assertEqual([[r['id'] for r in item['baseline']['runs']]
                          for item in result['observed']], [[], [1], [], [1, 2]])
        for index, args in enumerate(fake.calls):
            if args[0] == 'dispatch':
                self.assertEqual(fake.calls[index - 1][0], 'show')
        self.assertEqual([r['id'] for r in result['observed'][-1]['show']['runs']], [1, 2, 4])

    def test_fixture_rejects_mismatched_profile_or_claim_event(self):
        m = self.load()
        for defect in ('profile', 'claim_run_id', 'claim_lock', 'ack_run_id', 'task_id'):
            with self.subTest(defect=defect):
                class Mismatched(FixtureTransport):
                    def kanban(self, *args, timeout=None) -> Any:
                        result = super().kanban(*args, timeout=timeout)
                        if args[0] == 'show' and result['runs']:
                            if defect == 'profile':
                                result['runs'][-1]['profile'] = 'wrong'
                            elif defect == 'claim_run_id':
                                result['events'][0]['payload']['run_id'] = -99
                            elif defect == 'claim_lock':
                                result['events'][0]['payload']['lock'] = ''
                            elif defect == 'ack_run_id':
                                result['events'][-1]['run_id'] = -99
                            else:
                                result['task']['id'] = 'wrong-card'
                        return result
                repo = self.fixture_repo()
                with self.assertRaises(m.Refused):
                    m.drive_protocol(Mismatched(repo), 'original', repo, runtime=1, builder='build',
                                     verifier='verify', reviewer='review', fixture_only=True)

    def test_execution_refused_before_any_subprocess(self):
        m = self.load()
        for enabled, runtime, budget in [(False, None, None), (True, None, None),
                                         (True, 20, None), (True, 20, 'owner-budget.json'),
                                         (True, 20, 'included-cost'), (True, 20, 'turn-cap')]:
            with self.subTest(enabled=enabled, runtime=runtime, budget=budget):
                with self.assertRaises(m.Refused):
                    m.execution_gate(enabled, runtime, budget)

    def test_isolation_removes_routing_credentials_and_creates_private_paths(self):
        m = self.load()
        self.assertTrue(hasattr(m, 'Harness'), 'isolated runner missing')
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temp:
            h = m.Harness(Path(temp), inherited={'PATH': os.environ['PATH'],
                         'HERMES_HOME': '/live', 'HERMES_KANBAN_HOME': '/live-board',
                         'HERMES_PROFILE': 'live', 'HERMES_KANBAN_TASK': 'live-task',
                         'HERMES_KANBAN_BOARD': 'live-board', 'OPENAI_API_KEY': 'do-not-copy'})
            self.assertEqual(h.env['HERMES_HOME'], str(Path(temp) / 'home'))
            self.assertEqual(h.env['HERMES_KANBAN_HOME'], str(Path(temp) / 'board'))
            self.assertNotIn('HERMES_PROFILE', h.env)
            self.assertNotIn('HERMES_KANBAN_TASK', h.env)
            self.assertNotIn('OPENAI_API_KEY', h.env)
            self.assertEqual(h.env['HOME'], str(Path(temp) / 'os-home'))
            self.assertEqual(h.env.get('TMPDIR'), str(Path(temp) / 'temp'))
            self.assertTrue(h.repo.is_dir())
            self.assertEqual(h.root.stat().st_mode & 0o777, 0o700)

    def test_runner_retains_json_receipts_and_uses_hard_process_group_timeout(self):
        m = self.load()
        self.assertTrue(hasattr(m, 'Harness'), 'bounded runner missing')
        import sys
        import time
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temp:
            h = m.Harness(Path(temp))
            result = h.command([sys.executable, '-c', 'print("{\\"native\\": false}")'], timeout=2)
            self.assertEqual(result, {'native': False})
            receipt = __import__('json').loads(next(h.receipts.glob('*.json')).read_text())
            self.assertEqual(receipt['returncode'], 0)
            self.assertIn('stdout', receipt)
            start = time.monotonic()
            with self.assertRaises(m.Refused):
                h.command([sys.executable, '-c', 'import subprocess,time; subprocess.Popen(["sleep","60"]); time.sleep(60)'], timeout=.1)
            self.assertLess(time.monotonic() - start, 3)
            receipts = [__import__('json').loads(p.read_text()) for p in h.receipts.glob('*.json')]
            self.assertTrue(any(r['timed_out'] for r in receipts))

    def command_harness(self):
        m = self.load()
        SCRATCH.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(temp.cleanup)
        h = m.Harness(Path(temp.name), cli=['unused-fixture-cli'])
        return m, h

    def test_command_output_cap_validation_before_launch(self):
        from unittest.mock import patch
        m, h = self.command_harness()
        with patch.object(m.subprocess, 'Popen') as launch:
            for cap in (0, -1, True, 1.5, '1024', None, 16 * 1024 * 1024 + 1):
                with self.subTest(cap=cap), self.assertRaises(m.Refused):
                    h.command(['unused'], output_limit=cap)
            launch.assert_not_called()
        self.assertEqual(h.serial, 0)

    def test_command_refuses_combined_live_output_flood(self):
        import json
        import sys
        m, h = self.command_harness()
        try:
            with self.assertRaises(m.Refused):
                h.command([sys.executable, '-c',
                           'import os; os.write(1,b"a"*4096); os.write(2,b"b"*4096)'],
                          timeout=1, json_output=False, output_limit=5000)
            receipt = json.loads((h.receipts / '0001.json').read_text())
            self.assertTrue(receipt['output_limit_exceeded'])
            self.assertEqual(receipt['output_limit'], 5000)
            self.assertGreater(receipt['observed_bytes'], 5000)
            self.assertEqual(receipt['retained_bytes'], 5000)
            self.assertEqual(len(receipt['stdout'].encode()) + len(receipt['stderr'].encode()), 5000)
            self.assertTrue(receipt['output_truncated'])
            self.assertFalse(receipt['output_complete'])
            self.assertLess((h.receipts / '0001.json').stat().st_size, 7000)
        finally:
            self.save_output_receipts(h, 'live-flood')

    def test_command_bounds_postexit_held_pipe_without_communicate(self):
        self.output_identity_fixture(postexit=True)

    def test_command_flood_cleans_owned_identities_and_preserves_foreign(self):
        self.output_identity_fixture(postexit=False)

    def output_identity_fixture(self, postexit):
        import ctypes
        import json
        import signal
        import subprocess
        import sys
        import time
        from unittest.mock import patch
        m, h = self.command_harness()
        libc = ctypes.CDLL(None, use_errno=True)
        previous = ctypes.c_int()
        self.assertEqual(libc.prctl(37, ctypes.byref(previous), 0, 0, 0), 0)
        self.assertEqual(libc.prctl(36, 1, 0, 0, 0), 0)
        foreign = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'],
                                   start_new_session=True)
        def identity(pid):
            return Path(f'/proc/{pid}/stat').read_text().split(') ')[1].split()[19]
        foreign_start = identity(foreign.pid)
        original_waitid, original_killpg = os.waitid, os.killpg
        leaders = []
        def only_after_exit(*args):
            end = time.monotonic() + 1
            while time.monotonic() < end:
                status = original_waitid(*args)
                if status is not None:
                    return status
                time.sleep(.005)
            self.fail('fixture leader did not exit')
        def pinned_signal(pid, sig):
            original_waitid(os.P_PID, pid, os.WEXITED | os.WNOWAIT | os.WNOHANG)
            leaders.append({'pid': pid, 'starttime': identity(pid)})
            original_killpg(pid, sig)
        child = ('import os,time,json; from pathlib import Path; '
                 'ident={"pid":os.getpid(),"starttime":'
                 'Path("/proc/self/stat").read_text().split(") ")[1].split()[19]}; '
                 'Path("child.json").write_text(json.dumps(ident)); '
                 'os.write(1,b"z"*8192); Path("ready").touch(); ' +
                 ('time.sleep(20)' if postexit else '\nwhile True: os.write(2,b"y"*8192)\n'))
        leader = ('import subprocess,sys,time; from pathlib import Path; '
                  'subprocess.Popen([sys.executable,"-c",' + repr(child) + ']); '
                  '\nwhile not Path("ready").exists(): time.sleep(.005)\n' +
                  ('' if postexit else 'time.sleep(20)'))
        started = time.monotonic()
        try:
            with patch.object(m.os, 'waitid', only_after_exit if postexit else original_waitid), \
                    patch.object(m.os, 'killpg', pinned_signal), \
                    patch.object(m.subprocess.Popen, 'communicate',
                                 side_effect=AssertionError('unbounded communicate forbidden')) as communicate:
                with self.assertRaises(m.Refused):
                    h.command([sys.executable, '-c', leader], timeout=1,
                              json_output=False, output_limit=5000)
            communicate.assert_not_called()
            receipt = json.loads((h.receipts / '0001.json').read_text())
            self.assertTrue(receipt['output_limit_exceeded'])
            self.assertEqual(receipt['retained_bytes'], 5000)
            if postexit:
                self.assertEqual(receipt['observed_bytes'], 8192)
            else:
                self.assertGreater(receipt['observed_bytes'], 5000)
            self.assertLessEqual(receipt['observed_bytes'], 5000 + 65536)
            self.assertLess((h.receipts / '0001.json').stat().st_size, 9000)
            self.assertTrue(receipt['output_truncated'])
            self.assertFalse(receipt['output_complete'])
            self.assertLess(time.monotonic() - started, 3)
            owned = json.loads((h.repo / 'child.json').read_text())
            self.assertEqual(identity(owned['pid']), owned['starttime'])
            self.assertEqual(os.waitpid(owned['pid'], 0)[0], owned['pid'])
            self.assertFalse(Path(f'/proc/{owned["pid"]}').exists())
            self.assertFalse(Path(f'/proc/{leaders[-1]["pid"]}').exists())
            self.assertIsNone(foreign.poll())
            self.assertEqual(identity(foreign.pid), foreign_start)
            (h.receipts / 'identities.json').write_text(json.dumps({
                'owned': owned, 'leader': leaders[-1], 'owned_absent': True,
                'foreign': {'pid': foreign.pid, 'starttime': foreign_start, 'alive': True}}))
        finally:
            if (h.repo / 'child.json').exists():
                owned = json.loads((h.repo / 'child.json').read_text())
                if Path(f'/proc/{owned["pid"]}').exists():
                    self.assertEqual(identity(owned['pid']), owned['starttime'])
                    os.kill(owned['pid'], signal.SIGKILL)
                    os.waitpid(owned['pid'], 0)
            foreign.kill()
            foreign.wait(timeout=2)
            libc.prctl(36, previous.value, 0, 0, 0)
            self.save_output_receipts(h, 'postexit-held-pipe' if postexit else 'live-owned-flood')

    def test_command_default_limit_and_exact_limit_success(self):
        import json
        import sys
        m, h = self.command_harness()
        try:
            self.assertEqual(h.command([sys.executable, '-c',
                                        'import os; os.write(1,b"abcd"); os.write(2,b"ef")'],
                                       timeout=1, json_output=False, output_limit=6), 'abcd')
            receipt = json.loads((h.receipts / '0001.json').read_text())
            self.assertEqual(receipt['observed_bytes'], 6)
            self.assertEqual(receipt['retained_bytes'], 6)
            self.assertFalse(receipt['output_truncated'])
            self.assertFalse(receipt['output_limit_exceeded'])
            self.assertTrue(receipt['output_complete'])
            with self.assertRaises(m.Refused):
                h.command([sys.executable, '-c',
                           'import os; os.write(1,b"a"*(1024*1024)); os.write(2,b"b"*8192)'],
                          timeout=2, json_output=False)
            receipt = json.loads((h.receipts / '0002.json').read_text())
            self.assertEqual(receipt['output_limit'], 1024 * 1024)
            self.assertTrue(receipt['output_limit_exceeded'])
            self.assertEqual(receipt['retained_bytes'], 1024 * 1024)
            self.assertGreater(receipt['observed_bytes'], receipt['retained_bytes'])
            self.assertLessEqual(receipt['observed_bytes'], receipt['retained_bytes'] + 65536)
            self.assertTrue(receipt['output_truncated'])
            self.assertFalse(receipt['output_complete'])
            self.assertLess((h.receipts / '0002.json').stat().st_size, 1024 * 1024 + 2000)
            self.assertEqual(h.command([sys.executable, '-c', 'print("{}")'],
                                       timeout=1, output_limit=16 * 1024 * 1024), {})
        finally:
            self.save_output_receipts(h, 'default-and-exact-limit')

    def test_command_errors_never_serialize_arbitrary_exception_payload(self):
        import json
        import sys
        from unittest.mock import patch
        m, h = self.command_harness()
        class PayloadError(RuntimeError):
            def __str__(self):
                return 'discarded-private-payload-' + 'x' * 100000
        try:
            with patch.object(m.os, 'waitid', side_effect=PayloadError()):
                with self.assertRaises(m.Refused):
                    h.command([sys.executable, '-c', 'import time; time.sleep(20)'], timeout=1)
            raw = (h.receipts / '0001.json').read_text()
            self.assertNotIn('discarded-private-payload', raw)
            self.assertLess(len(raw), 2000)
            self.assertIn('PayloadError', str(json.loads(raw)['errors']))
        finally:
            self.save_output_receipts(h, 'exception-payload')

    def save_output_receipts(self, h, label):
        import shutil
        target = Path.home() / '.hermes/cache/scratch/executable-safeguards/native-command-output'
        target.mkdir(parents=True, exist_ok=True)
        shutil.copytree(h.receipts, target / (label + '-' + h.root.name))

    def save_command_receipts(self, h, label):
        import shutil
        target = Path.home() / '.hermes/cache/scratch/executable-safeguards/native-command-cleanup'
        target.mkdir(parents=True, exist_ok=True)
        shutil.copytree(h.receipts, target / (label + '-' + h.root.name))

    def test_command_persists_failure_when_exit_observation_breaks(self):
        import json
        import sys
        from unittest.mock import patch
        m, h = self.command_harness()
        original = os.waitid
        def broken_observation(*args):
            status = original(*args)
            if status is not None:
                raise OSError('fixture exit observation unavailable')
            return status
        try:
            with patch.object(m.os, 'waitid', broken_observation):
                with self.assertRaises(m.Refused):
                    h.command([sys.executable, '-c', 'import sys; print("failure"); sys.exit(7)'],
                              timeout=1, json_output=False)
            receipt = json.loads((h.receipts / '0001.json').read_text())
            self.assertEqual(receipt['returncode'], 7)
            self.assertIn('observation unavailable', str(receipt['errors']))
            self.assertIn('failure', receipt['stdout'])
        finally:
            self.save_command_receipts(h, 'observation-error')

    def test_command_latches_repeated_shutdown_during_cleanup(self):
        import json
        import signal
        import sys
        import time
        from unittest.mock import patch
        m, h = self.command_harness()
        saved = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
        def interrupt(sig, frame):
            raise InterruptedError('fixture prior handler interrupted cleanup')
        for sig in saved:
            signal.signal(sig, interrupt)
        original = os.killpg
        def repeated_shutdown(pid, sig):
            original(pid, sig)
            for shutdown in (signal.SIGINT, signal.SIGTERM, signal.SIGINT, signal.SIGTERM):
                os.kill(os.getpid(), shutdown)
        started = time.monotonic()
        try:
            with patch.object(m.os, 'killpg', repeated_shutdown):
                with self.assertRaises(m.Refused):
                    h.command([sys.executable, '-c', 'import time; time.sleep(20)'], timeout=.1)
            receipt = json.loads((h.receipts / '0001.json').read_text())
            self.assertTrue(receipt['timed_out'])
            self.assertEqual(receipt.get('interrupted'), [2, 15, 2, 15])
            self.assertEqual(receipt['returncode'], -signal.SIGKILL)
            self.assertLess(time.monotonic() - started, 3)
            for sig in saved:
                self.assertIs(signal.getsignal(sig), interrupt)
        finally:
            for sig, handler in saved.items():
                signal.signal(sig, handler)
            self.save_command_receipts(h, 'repeated-shutdown')

    def test_command_never_signals_a_relinquished_group(self):
        import json
        import sys
        from unittest.mock import patch
        m, h = self.command_harness()
        original = os.waitid
        def relinquish(*args):
            status = original(*args)
            if status is not None:
                os.waitpid(args[1], 0)
                raise ChildProcessError('fixture external reaper relinquished ownership')
            return status
        try:
            with patch.object(m.os, 'waitid', relinquish), patch.object(m.os, 'killpg') as group_signal:
                with self.assertRaises(m.Refused):
                    h.command([sys.executable, '-c', 'raise SystemExit(7)'], timeout=1)
            group_signal.assert_not_called()
            receipt = json.loads((h.receipts / '0001.json').read_text())
            self.assertIsNone(receipt['returncode'])
            self.assertIn('ownership', str(receipt['errors']))
        finally:
            self.save_command_receipts(h, 'ownership-lost')

    def test_command_retains_timeout_receipt_when_drain_fails(self):
        import json
        import subprocess
        import sys
        import time
        from unittest.mock import patch
        m, h = self.command_harness()
        original_read, original_killpg = os.read, os.killpg
        draining = False
        def begin_drain(pid, sig):
            nonlocal draining
            original_killpg(pid, sig)
            draining = True
        def failed_drain(fd, size):
            if draining:
                raise subprocess.TimeoutExpired('private fixture', 2,
                                                output=b'discarded payload', stderr=b'discarded payload')
            return original_read(fd, size)
        started = time.monotonic()
        try:
            with patch.object(m.os, 'killpg', begin_drain), patch.object(m.os, 'read', failed_drain):
                with self.assertRaises(m.Refused):
                    h.command([sys.executable, '-c',
                               'import os,time; os.write(1,b"partial stdout"); '
                               'os.write(2,b"partial stderr"); time.sleep(20)'], timeout=.1)
            receipt = json.loads((h.receipts / '0001.json').read_text())
            self.assertTrue(receipt['timed_out'])
            self.assertEqual(receipt['returncode'], -9)
            self.assertIn('partial stdout', receipt['stdout'])
            self.assertIn('partial stderr', receipt['stderr'])
            self.assertIn('TimeoutExpired', str(receipt['errors']))
            self.assertNotIn('discarded payload', json.dumps(receipt))
            self.assertFalse(receipt['output_complete'])
            self.assertEqual(receipt['observed_bytes'], receipt['retained_bytes'])
            self.assertLess(time.monotonic() - started, 3)
        finally:
            self.save_command_receipts(h, 'drain-failure')

    def test_command_preserves_text_and_nonzero_receipt_semantics(self):
        import json
        import sys
        m, h = self.command_harness()
        try:
            self.assertEqual(h.command([sys.executable, '-c',
                                        'import os,time; os.write(1,b"first\\r\\n"); '
                                        'time.sleep(.05); os.write(1,b"last\\r")'],
                                       timeout=1, json_output=False), 'first\nlast\n')
            self.assertEqual(h.command([sys.executable, '-c', 'print("{\\"ok\\": true}")'],
                                       timeout=1), {'ok': True})
            with self.assertRaises(m.Refused):
                h.command([sys.executable, '-c', 'import sys; print("bad"); sys.exit(7)'],
                          timeout=1, json_output=False)
            self.assertEqual(json.loads((h.receipts / '0003.json').read_text())['returncode'], 7)
        finally:
            self.save_command_receipts(h, 'text-semantics')

    def test_command_keeps_elapsed_timeout_when_observation_fails(self):
        import json
        import sys
        import time
        from unittest.mock import patch
        m, h = self.command_harness()
        def broken_observation(*args):
            time.sleep(.12)
            raise OSError('fixture observation failed after deadline')
        try:
            with patch.object(m.os, 'waitid', broken_observation):
                with self.assertRaises(m.Refused):
                    h.command([sys.executable, '-c', 'import time; time.sleep(20)'], timeout=.1)
            receipt = json.loads((h.receipts / '0001.json').read_text())
            self.assertTrue(receipt['timed_out'])
            self.assertEqual(receipt['returncode'], -9)
            self.assertIn('after deadline', str(receipt['errors']))
        finally:
            self.save_command_receipts(h, 'timeout-observation-error')

    def test_command_persists_spawn_failure_without_signalling(self):
        import json
        from unittest.mock import patch
        m, h = self.command_harness()
        try:
            with patch.object(m.os, 'killpg') as group_signal:
                with self.assertRaises(m.Refused):
                    h.command([str(h.repo / 'missing-fixture-executable')], timeout=1)
            group_signal.assert_not_called()
            receipt = json.loads((h.receipts / '0001.json').read_text())
            self.assertIsNone(receipt['returncode'])
            self.assertFalse(receipt['timed_out'])
            self.assertIn('FileNotFoundError', str(receipt['errors']))
        finally:
            self.save_command_receipts(h, 'spawn-failure')

    def test_command_reserves_leader_until_last_group_signal(self):
        import signal
        import subprocess
        import sys
        from unittest.mock import patch
        m, h = self.command_harness()
        foreign = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'],
                                   start_new_session=True)
        foreign_identity = Path(f'/proc/{foreign.pid}/stat').read_text().split(') ')[1].split()[19]
        original = os.killpg
        signals = []
        def checked_killpg(pid, sig):
            try:
                os.waitid(os.P_PID, pid, os.WEXITED | os.WNOWAIT | os.WNOHANG)
            except ChildProcessError:
                self.fail('group signal after leader ownership released')
            signals.append((pid, sig))
            return original(pid, sig)
        try:
            import ctypes
            import json
            import time
            libc = ctypes.CDLL(None, use_errno=True)
            previous = ctypes.c_int()
            self.assertEqual(libc.prctl(37, ctypes.byref(previous), 0, 0, 0), 0)
            self.assertEqual(libc.prctl(36, 1, 0, 0, 0), 0)  # isolated test process adopts orphan
            descendant = None
            try:
                child = ('import os,signal,time,json; from pathlib import Path; '
                         'signal.signal(signal.SIGTERM,signal.SIG_IGN); '
                         'identity={"pid":os.getpid(),"starttime":'
                         'Path("/proc/self/stat").read_text().split(") ")[1].split()[19]}; '
                         'Path("descendant.json").write_text(json.dumps(identity)); time.sleep(20)')
                leader = ('import subprocess,sys,time; from pathlib import Path; '
                          'subprocess.Popen([sys.executable,"-c",' + repr(child) + ']); '
                          '\nwhile not Path("descendant.json").exists(): time.sleep(.005)\n'
                          'print("{}")')
                started = time.monotonic()
                with patch.object(m.os, 'killpg', checked_killpg):
                    self.assertEqual(h.command([sys.executable, '-c', leader], timeout=1), {})
                owned_identity = json.loads((h.repo / 'descendant.json').read_text())
                descendant = owned_identity['pid']
                identity = owned_identity['starttime']
                self.assertEqual(Path(f'/proc/{descendant}/stat').read_text().split(') ')[1].split()[19],
                                 identity)
                self.assertEqual(os.waitpid(descendant, 0)[0], descendant)
                self.assertFalse(Path(f'/proc/{descendant}').exists())
                self.assertLess(time.monotonic() - started, 3)
                evidence = {'descendant_pid': descendant, 'descendant_starttime': identity,
                            'descendant_absent': True, 'leader_pid': signals[-1][0],
                            'foreign_pid': foreign.pid, 'foreign_starttime': foreign_identity}
                (h.receipts / 'cleanup-identities.json').write_text(json.dumps(evidence))
            finally:
                if (h.repo / 'descendant.json').exists():
                    owned_identity = json.loads((h.repo / 'descendant.json').read_text())
                    descendant = owned_identity['pid']
                    stat = Path(f'/proc/{descendant}/stat')
                    if stat.exists():
                        self.assertEqual(stat.read_text().split(') ')[1].split()[19],
                                         owned_identity['starttime'])
                        os.kill(descendant, signal.SIGKILL)
                        os.waitpid(descendant, 0)
                libc.prctl(36, previous.value, 0, 0, 0)
            self.assertTrue(signals)
            self.assertIsNone(foreign.poll())
            self.assertEqual(Path(f'/proc/{foreign.pid}/stat').read_text().split(') ')[1].split()[19],
                             foreign_identity)
            self.assertFalse(Path(f'/proc/{signals[-1][0]}').exists())
        finally:
            foreign.kill()
            foreign.wait(timeout=2)
            self.save_command_receipts(h, 'ownership')

    def test_real_native_preflight_selects_creates_deduplicates_and_never_dispatches_worker(self):
        m = self.load()
        self.assertTrue(hasattr(m.Harness, 'preflight'), 'native preflight missing')
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temp:
            h = m.Harness(Path(temp))
            try:
                result = h.preflight()
            finally:
                import shutil
                receipts_root = Path.home() / '.hermes/cache/scratch/executable-safeguards/native-repairs'
                receipts_root.mkdir(parents=True, exist_ok=True)
                snapshot = Path(tempfile.mkdtemp(prefix='preflight-receipts-', dir=receipts_root))
                shutil.copytree(h.receipts, snapshot / 'receipts')
                print(f'Native scratch-only preflight receipts: {snapshot}')
            self.assertEqual(result['native_lifecycle'], 'NOT_RUN')
            self.assertEqual(result['selected_task'], 'T-native')
            self.assertEqual(result['card_id'], result['dedup_card_id'])
            self.assertEqual(result['runs'], [])
            self.assertTrue(result['board_db'].startswith(str(Path(temp) / 'board')))
            self.assertEqual(result['boundary'], 'native_create_dedup_dry_dispatch')

    def test_protocol_fixture_recovers_original_card_and_requires_worker_review_ack(self):
        m = self.load()
        self.assertTrue(hasattr(m, 'drive_protocol'), 'native lifecycle orchestration missing')
        repo = self.fixture_repo()
        fake = FixtureTransport(repo)
        result = m.drive_protocol(fake, 'original', repo, runtime=10,
                                 builder='build', verifier='verify', reviewer='review', fixture_only=True)
        self.assertEqual(result['card_id'], 'original')
        self.assertEqual(result['review_ack']['profile'], 'review')
        self.assertEqual([c[1] for c in fake.calls if c[0] == 'reopen-review'], ['original'])
        self.assertEqual(len([c for c in fake.calls if c[0] == 'create']), 1)
        self.assertFalse(any(c[0] in ('complete', 'request-review') for c in fake.calls))
        with self.assertRaises(m.Refused):
            m.drive_protocol(FixtureTransport('/isolated/repo', fault='synthetic'), 'original', '/isolated/repo',
                             runtime=10, builder='build', verifier='verify', reviewer='review', fixture_only=True)

    def test_cli_defaults_to_not_run_and_rejects_owner_budget(self):
        import json
        import subprocess
        import sys
        self.load()
        for args in ([], ['run', '--enable-native', '--max-runtime', '30',
                          '--budget-control', 'owner-budget.json']):
            p = subprocess.run([sys.executable, str(MODULE), *args], capture_output=True,
                               text=True, timeout=5)
            self.assertEqual(p.returncode, 2)
            result = json.loads(p.stdout)
            self.assertEqual(result['native_lifecycle'], 'NOT_RUN')
            self.assertEqual(result['boundary'], 'refused_before_dispatch')

    def test_default_cli_resolves_installed_project_with_existing_helper(self):
        import subprocess
        from unittest.mock import patch
        m = self.load()
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temp:
            root = Path(temp) / 'fresh'
            original_is_file = Path.is_file
            def is_file(path):
                return path == Path('/opt/fixture-venv/pyvenv.cfg') or original_is_file(path)
            with patch.object(m.subprocess, 'run', return_value=subprocess.CompletedProcess(
                    [], 0, '/opt/fixture-runtime\n', '')) as resolve, \
                    patch.object(Path, 'is_file', is_file):
                harness = m.Harness(root, inherited={'PATH': '/opt/fixture-venv/bin'})
            resolve.assert_called_once_with(['/opt/fixture-venv/bin/python', '-I', '-c',
                'from hermes_cli.config import get_project_root; print(get_project_root())'],
                capture_output=True, text=True, timeout=3, check=True)
            self.assertEqual(harness.cli[:3], ['/opt/fixture-venv/bin/python', '-I', '-c'])
            self.assertIn("sys.path.insert(0,'/opt/fixture-runtime')", harness.cli[3])
            self.assertIn('hermes_cli.main', harness.cli[3])
            self.assertEqual(harness.env['HERMES_HOME'], str(root / 'home'))

    def test_scratch_default_uses_runtime_user_home(self):
        from unittest.mock import patch
        with patch.object(Path, 'home', return_value=Path('/home/fixture-user')):
            m = self.load()
        self.assertEqual(m.SCRATCH, Path('/home/fixture-user/.hermes/cache/scratch/executable-safeguards/native-harness'))

    def test_unsafe_or_existing_workspace_is_refused(self):
        m = self.load()
        with self.assertRaises(m.Refused):
            m.Harness((Path.home() / '.hermes'))
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temp:
            (Path(temp) / 'existing').write_text('preserve')
            with self.assertRaises(m.Refused):
                m.Harness(Path(temp))
            self.assertEqual((Path(temp) / 'existing').read_text(), 'preserve')

    def test_protocol_checks_deadline_before_dispatch(self):
        m = self.load()
        import time
        class SlowFixtureTransport:
            """Fake external CLI timing fixture; no native acceptance."""
            def __init__(self):
                self.calls = []
            def kanban(self, *args, timeout=None) -> Any:
                self.calls.append(args)
                time.sleep(1.05)
                return {}
        fake = SlowFixtureTransport()
        with self.assertRaises(m.Refused):
            m.drive_protocol(fake, 'original', '/isolated/repo', runtime=1,
                             builder='build', verifier='verify', reviewer='review', fixture_only=True)
        self.assertFalse(any(c[0] == 'dispatch' for c in fake.calls))


if __name__ == '__main__':
    unittest.main()
