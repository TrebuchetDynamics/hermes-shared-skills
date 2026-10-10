#!/usr/bin/env python3
"""Explicit installed-backend opt-in: CONTAINMENT_LINUX_TESTS=1 python this_file."""
import json
import os
import tempfile
import unittest
from pathlib import Path
import native_containment as containment

EVIDENCE = (Path.home() / '.hermes/cache/scratch/executable-safeguards/controller-bridge/containment')

@unittest.skipUnless(os.environ.get('CONTAINMENT_LINUX_TESTS') == '1', 'installed Linux backend is opt-in')
class LinuxTests(unittest.TestCase):
    def test_controller_socket_is_reachable_only_after_trusted_registration(self):
        import socket
        import threading
        seen = []
        responses = []
        failures = []
        with tempfile.TemporaryDirectory(dir=containment.SCRATCH_ROOT) as tmp:
            root = Path(tmp)
            job = root / 'job'
            job.mkdir()
            endpoint = root / 'controller.sock'
            hidden = root / 'host-only-fixture'
            hidden.write_text('local fixture')
            with socket.socket(socket.AF_UNIX) as server:
                server.bind(str(endpoint))
                server.listen(1)
                server.settimeout(3)
                def serve():
                    try:
                        connection, _ = server.accept()
                        with connection:
                            connection.settimeout(1)
                            responses.append(connection.recv(16))
                            connection.sendall(b'ack')
                    except Exception as exc:
                        failures.append(type(exc).__name__)
                thread = threading.Thread(target=serve)
                thread.start()
                def register(info):
                    self.assertFalse(list(job.glob('.release-*')))
                    state = containment.unit_state(info['unit'])
                    self.assertEqual(state['ControlGroup'], info['control_group'])
                    pids = containment.cgroup_pids(Path('/sys/fs/cgroup' + info['control_group']))
                    self.assertTrue(info['namespace_host_pids'])
                    self.assertTrue(set(info['namespace_host_pids']).issubset(pids))
                    seen.append(info)
                    return True
                script = '''import json, socket
from pathlib import Path
with socket.socket(socket.AF_UNIX) as connection:
    connection.settimeout(1)
    connection.connect('/controller.sock')
    connection.sendall(b'fixture')
    response = connection.recv(16)
Path('/job/socket-observation.json').write_text(json.dumps({
    'ack': response == b'ack', 'host_sibling_visible': Path(%r).exists(),
    'manager_visible': Path('/run/user').exists()}))
''' % str(hidden)
                try:
                    receipt = containment.launch(['/usr/bin/python3.12', '-I', '-c', script], job,
                        receipt_path=EVIDENCE / 'socket-receipt.json', runtime_sec=2,
                        controller_socket=endpoint, before_release=register)
                finally:
                    thread.join(timeout=4)
                self.assertFalse(thread.is_alive())
                self.assertFalse(failures, failures)
                self.assertEqual(receipt['execution_status'], 'EXITED', receipt.get('error'))
                self.assertEqual(receipt['returncode'], 0)
                self.assertEqual(responses, [b'fixture'])
                observed = json.loads((job / 'socket-observation.json').read_text())
                self.assertEqual(observed, {'ack': True, 'host_sibling_visible': False, 'manager_visible': False})
                self.assertEqual(seen, [{'unit': receipt['unit'], 'control_group': receipt['control_group'],
                                        'namespace_host_pids': receipt['namespace_host_pids']}])
                self.assertTrue(all(receipt['verified_controls'].values()))
                self.assertEqual(receipt['cleanup']['status'], 'VERIFIED')
                self.assertEqual(json.loads((EVIDENCE / 'socket-receipt.json').read_text()), receipt)
        self.assertFalse(endpoint.exists())
        self.assertFalse(root.exists())
        (EVIDENCE / 'socket-observed.json').write_text(json.dumps({
            'registration': seen, 'worker_observation': observed,
            'socket_absent': not endpoint.exists(), 'fixture_root_absent': not root.exists(),
            'server_thread_stopped': not thread.is_alive()}, indent=2) + '\n')

    def test_registration_refusal_never_executes_target_and_cleans_exact_service(self):
        import socket
        def unavailable(info):
            raise RuntimeError('fixture registration unavailable')
        for label, hook in (('denied', lambda info: False), ('unavailable', unavailable)):
            with self.subTest(label=label), tempfile.TemporaryDirectory(dir=containment.SCRATCH_ROOT) as tmp:
                root = Path(tmp)
                job = root / 'job'
                job.mkdir()
                endpoint = root / 'controller.sock'
                with socket.socket(socket.AF_UNIX) as server:
                    server.bind(str(endpoint))
                    receipt = containment.launch(['/usr/bin/python3.12', '-I', '-c',
                        "from pathlib import Path; Path('/job/TARGET_EXECUTED').write_text('bad')"], job,
                        receipt_path=EVIDENCE / ('registration-' + label + '-receipt.json'),
                        runtime_sec=2, controller_socket=endpoint, before_release=hook)
                self.assertFalse((job / 'TARGET_EXECUTED').exists())
                self.assertFalse(list(job.glob('.release-*')))
                self.assertTrue(all(receipt['verified_controls'].values()))
                self.assertEqual(receipt['execution_status'], 'REFUSED')
                self.assertNotIn('released_elapsed_sec', receipt)
                self.assertEqual(receipt['cleanup']['status'], 'VERIFIED')
                self.assertLess(receipt['elapsed_sec'], 5)
            self.assertFalse(endpoint.exists())
            self.assertFalse(root.exists())

    def test_true_executes_with_verified_controls_and_exact_cleanup(self):
        self.assertTrue(callable(getattr(containment, 'launch', None)), 'executable launcher is missing')
        with tempfile.TemporaryDirectory(dir=containment.SCRATCH_ROOT) as tmp:
            receipt = containment.launch(['/usr/bin/true'], Path(tmp), receipt_path=EVIDENCE / 'true-receipt.json')
        self.assertEqual(receipt['execution_status'], 'EXITED')
        self.assertEqual(receipt['returncode'], 0)
        self.assertTrue(receipt['verified_controls'])
        self.assertTrue(receipt['control_group'].startswith('/'))
        self.assertTrue(receipt['observed_host_pids'])
        self.assertTrue(receipt['cleanup']['unit_absent'])
        self.assertTrue(receipt['cleanup']['cgroup_empty'])
        self.assertTrue(receipt['cleanup']['observed_host_pids_absent'])
        self.assertEqual(receipt['live_model_execution'], 'NOT_RUN')
        self.assertFalse(receipt['cancellation']['requested'])

    def test_detached_child_timeout_has_host_pid_proof(self):
        script = '''import json, os, signal, time
from pathlib import Path
pid = os.fork()
if pid == 0:
    os.setsid()
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    Path('/job/child.json').write_text(json.dumps({'namespace_pid': os.getpid()}))
    time.sleep(60)
else:
    time.sleep(60)
'''
        with tempfile.TemporaryDirectory(dir=containment.SCRATCH_ROOT) as tmp:
            job = Path(tmp)
            receipt = containment.launch(['/usr/bin/python3.12', '-I', '-c', script], job,
                                         receipt_path=EVIDENCE / 'timeout-receipt.json', runtime_sec=2)
            child = json.loads((job / 'child.json').read_text())
        self.assertEqual(receipt['execution_status'], 'TIMED_OUT', receipt.get('error'))
        self.assertLess(receipt['returncode'], 0, 'signal termination must not masquerade as an exit code')
        self.assertIn('host_pid_observations', receipt, 'namespace PID to host PID evidence is missing')
        matches = [p for p in receipt['host_pid_observations']
                   if p['namespace_pid'] == child['namespace_pid'] and p['isolated_pid_namespace']]
        self.assertTrue(matches, 'detached child was not observed through exact host cgroup')
        self.assertTrue(receipt['cleanup']['unit_absent'])
        self.assertTrue(receipt['cleanup']['cgroup_absent'])
        self.assertTrue(receipt['cleanup']['observed_host_pids_absent'])
        self.assertEqual(receipt['cancellation']['actor'], 'systemd')
        self.assertTrue(receipt['cancellation']['acknowledged'])
        self.assertLess(receipt['elapsed_sec'], 5)

    def test_successful_leader_exit_cleans_detached_child(self):
        script = '''import json, os, signal, time
from pathlib import Path
pid = os.fork()
if pid == 0:
    os.setsid()
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    Path('/job/child.json').write_text(json.dumps({'namespace_pid': os.getpid()}))
    time.sleep(60)
else:
    time.sleep(.4)
'''
        with tempfile.TemporaryDirectory(dir=containment.SCRATCH_ROOT) as tmp:
            job = Path(tmp)
            receipt = containment.launch(['/usr/bin/python3.12', '-I', '-c', script], job,
                                         receipt_path=EVIDENCE / 'leader-exit-receipt.json')
            child = json.loads((job / 'child.json').read_text())
        self.assertEqual(receipt['execution_status'], 'EXITED', receipt.get('error'))
        self.assertEqual(receipt['returncode'], 0)
        self.assertTrue(any(p['namespace_pid'] == child['namespace_pid'] and p['isolated_pid_namespace']
                            for p in receipt['host_pid_observations']))
        self.assertTrue(receipt['cleanup']['unit_absent'])
        self.assertTrue(receipt['cleanup']['cgroup_absent'])
        self.assertTrue(receipt['cleanup']['observed_host_pids_absent'])
        self.assertEqual(receipt['cleanup'].get('trigger'), 'leader-exit', 'cleanup trigger is missing')
        self.assertGreaterEqual(receipt['cleanup']['elapsed_sec'], 0)

    def test_host_synthetic_credentials_environment_and_manager_are_isolated(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(dir=containment.SCRATCH_ROOT) as tmp:
            host = Path(tmp)
            sentinel = host / 'synthetic-home' / '.config' / 'credentials'
            sentinel.parent.mkdir(parents=True)
            sentinel.write_text('SYNTHETIC-NOT-A-REAL-SECRET')
            job = host / 'job'
            job.mkdir()
            script = '''import json, os, socket, subprocess
from pathlib import Path
sentinel = Path(%r)
try:
    sentinel.read_text()
    readable = True
except OSError:
    readable = False
manager = subprocess.run(['/usr/bin/systemctl', '--user', 'start', 'containment-test-never-create.service'],
                         capture_output=True, text=True, timeout=1)
try:
    connection = socket.socket(socket.AF_UNIX)
    connection.connect('/run/user/%s/bus')
    bus_connected = True
except OSError:
    bus_connected = False
Path('/job/isolation.json').write_text(json.dumps({'sentinel_readable': readable,
    'environment': dict(os.environ), 'home_entries': os.listdir(os.environ['HOME']),
    'manager_returncode': manager.returncode, 'manager_stderr': manager.stderr,
    'bus_connected': bus_connected, 'interfaces': [name for _, name in socket.if_nameindex()],
    'host_home_visible': Path(%r).exists()}))
''' % (str(sentinel), os.getuid(), str(Path.home()))
            with patch.dict(os.environ, {'OPENAI_API_KEY': 'FAKE-API-KEY',
                                          'HERMES_PROVIDER': 'FAKE-ROUTING',
                                          'HOME': str(sentinel.parent.parent)}):
                receipt = containment.launch(['/usr/bin/python3.12', '-I', '-c', script], job,
                                             receipt_path=EVIDENCE / 'isolation-receipt.json')
            observed = json.loads((job / 'isolation.json').read_text())
            (EVIDENCE / 'isolation-observed.json').write_text(json.dumps(observed, indent=2) + '\n')
        self.assertEqual(receipt['execution_status'], 'EXITED', receipt.get('error'))
        self.assertEqual(receipt['returncode'], 0)
        self.assertFalse(observed['sentinel_readable'])
        self.assertFalse(observed['host_home_visible'])
        self.assertEqual(observed['home_entries'], [])
        self.assertNotIn('OPENAI_API_KEY', observed['environment'])
        self.assertNotIn('HERMES_PROVIDER', observed['environment'])
        self.assertNotEqual(observed['manager_returncode'], 0)
        self.assertIn('Failed to connect to bus', observed['manager_stderr'])
        self.assertFalse(observed['bus_connected'])
        self.assertEqual(observed['interfaces'], ['lo'])
        self.assertTrue(receipt['cleanup']['unit_absent'])
        self.assertTrue(receipt['cleanup']['observed_host_pids_absent'])

    def test_pre_release_cancellation_never_executes_target(self):
        import threading
        from unittest.mock import patch
        event = threading.Event()
        original = containment.host_pid_identity
        def cancel_on_identity(pid):
            identity = original(pid)
            if identity is not None:
                event.set()
            return identity
        with tempfile.TemporaryDirectory(dir=containment.SCRATCH_ROOT) as tmp:
            job = Path(tmp)
            with patch.object(containment, 'host_pid_identity', side_effect=cancel_on_identity):
                receipt = containment.launch(['/usr/bin/python3.12', '-I', '-c',
                    "from pathlib import Path; Path('/job/TARGET_EXECUTED').write_text('bad')"], job,
                    receipt_path=EVIDENCE / 'pre-release-cancel-receipt.json', runtime_sec=2, cancel_event=event)
            self.assertFalse((job / 'TARGET_EXECUTED').exists())
            self.assertFalse(list(job.glob('.release-*')))
        self.assertEqual(receipt['execution_status'], 'CANCELLED', receipt.get('error'))
        self.assertNotIn('released_elapsed_sec', receipt)
        self.assertTrue(receipt['cancellation']['acknowledged'])
        self.assertEqual(receipt['cleanup']['status'], 'VERIFIED')
        for key in ('unit_absent', 'cgroup_absent', 'cgroup_empty', 'observed_host_pids_absent'):
            self.assertTrue(receipt['cleanup'][key], key)
        self.assertLess(receipt['elapsed_sec'], 5)

    def test_caller_cancellation_acknowledges_exact_cleanup(self):
        import inspect
        import threading
        self.assertIn('cancel_event', inspect.signature(containment.launch).parameters,
                      'explicit caller cancellation is missing')
        event = threading.Event()
        timer = threading.Timer(.5, event.set)
        timer.start()
        try:
            with tempfile.TemporaryDirectory(dir=containment.SCRATCH_ROOT) as tmp:
                receipt = containment.launch(['/usr/bin/python3.12', '-I', '-c', 'import time; time.sleep(60)'],
                                             Path(tmp), receipt_path=EVIDENCE / 'cancel-receipt.json',
                                             runtime_sec=2, cancel_event=event)
        finally:
            timer.cancel()
            timer.join(timeout=1)
        self.assertEqual(receipt['execution_status'], 'CANCELLED')
        self.assertEqual(receipt['cancellation']['actor'], 'caller')
        self.assertTrue(receipt['cancellation']['requested'])
        self.assertTrue(receipt['cancellation']['acknowledged'])
        self.assertGreaterEqual(receipt['cancellation']['requested_elapsed_sec'], 0)
        self.assertTrue(receipt['cleanup']['unit_absent'])
        self.assertTrue(receipt['cleanup']['cgroup_absent'])
        self.assertTrue(receipt['cleanup']['observed_host_pids_absent'])

if __name__ == '__main__':
    unittest.main()
