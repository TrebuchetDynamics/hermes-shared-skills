"""Offline real Git/process fixtures; native dispatch remains separately gated."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import pass_workspace as passes


class MainOnly(unittest.TestCase):
    def setUp(self):
        scratch = Path.home() / '.hermes/cache/scratch'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repo'
        self.root.mkdir()
        self.git('init', '-qb', 'main')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@local')
        (self.root / 'input.txt').write_text('exact input\n')
        ledger = {'version': 1, 'goals': [{'id': 'G-one', 'title': 'Fixture',
                  'source': 'input.txt', 'status': 'unmet', 'tasks': ['T-one']}],
                  'tasks': [{'id': 'T-one', 'goal': 'G-one', 'title': 'Fixture',
                             'status': 'open', 'section': 'Now'}]}
        (self.root / 'goals.json').write_text(json.dumps(ledger))
        self.git('add', '.'); self.git('commit', '-qm', 'fixture')
        self.base = self.git('rev-parse', 'HEAD')
        self.snapshot = Path(self.temp.name) / 'source.json'
        self.snapshot.write_text(json.dumps({'version': 1, 'workspace': str(self.root),
            'files': [{'path': p, 'sha256': hashlib.sha256((self.root / p).read_bytes()).hexdigest()}
                      for p in ('input.txt', 'goals.json')]}))

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], text=True).strip()

    def prepare(self):
        self.assertTrue(callable(getattr(passes, 'prepare_main_only', None)),
                        'missing main-only immutable-source admission')
        return passes.prepare_main_only(self.root, Path(self.temp.name) / 'snapshot',
                                        self.base, self.snapshot, 'T-one', ['input.txt'], ['output.txt'])

    def test_main_only_snapshot_preserves_unrelated_dirty_bytes(self):
        (self.root / 'unrelated.txt').write_text('keep dirty\n')
        manifest = self.prepare()
        self.assertEqual(manifest['mode'], 'main-only')
        self.assertFalse((Path(manifest['snapshot']) / '.git').exists())
        self.assertEqual((Path(manifest['snapshot']) / 'input.txt').read_bytes(), b'exact input\n')
        self.assertEqual((self.root / 'unrelated.txt').read_bytes(), b'keep dirty\n')
        self.assertEqual(self.git('branch', '--show-current'), 'main')

    def test_serialized_lock_covers_worker_lifecycle_and_cleanup(self):
        self.assertTrue(callable(getattr(passes, 'run_main_only', None)), 'missing full-lifecycle writer lock')
        manifest = self.prepare()
        saved = Path(self.temp.name) / 'manifest.json'
        saved.write_text(json.dumps(manifest))
        started = Path(self.temp.name) / 'started'
        script = ('import json,pass_workspace as p; '
                  'm=json.load(open(' + repr(str(saved)) + ')); '
                  'p.run_main_only(m,' + repr([sys.executable, '-c',
                  'from pathlib import Path; import time; Path(' + repr(str(started)) + ').touch(); time.sleep(.8)']) +
                  ',ownership_guard=lambda:None)')
        env = dict(os.environ, PYTHONPATH=str(Path(passes.__file__).parent))
        first = subprocess.Popen([sys.executable, '-c', script], env=env)
        self.addCleanup(lambda: first.kill() if first.poll() is None else None)
        deadline = time.monotonic() + 5
        while not started.exists() and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertTrue(started.exists(), 'worker did not start')
        with self.assertRaisesRegex(ValueError, 'writer already owns'):
            passes.run_main_only(manifest, [sys.executable, '-c', 'pass'], ownership_guard=lambda: None)
        self.assertEqual(first.wait(timeout=5), 0)
        self.assertEqual(passes.run_main_only(manifest, [sys.executable, '-c', 'pass'],
                                            ownership_guard=lambda: None), 0)
        with self.assertRaises(FileNotFoundError):
            passes.run_main_only(manifest, ['/nonexistent-fixture-command'], ownership_guard=lambda: None)
        with self.assertRaises(subprocess.CalledProcessError):
            passes.run_main_only(manifest, [sys.executable, '-c', 'raise SystemExit(7)'],
                                 ownership_guard=lambda: None)
        self.assertEqual(passes.run_main_only(manifest, [sys.executable, '-c', 'pass'],
                                            ownership_guard=lambda: None), 0)

    def test_freshness_snapshot_and_ownership_refusals_preserve_bytes(self):
        manifest = self.prepare()
        before = (self.root / 'input.txt').read_bytes()
        def owned():
            raise ValueError('fixture native resource owner')
        with self.assertRaisesRegex(ValueError, 'native resource owner'):
            passes.run_main_only(manifest, [sys.executable, '-c', 'pass'], ownership_guard=owned)
        (self.root / 'input.txt').write_text('retracted\n')
        with self.assertRaisesRegex(ValueError, 'bytes changed'):
            passes.run_main_only(manifest, [sys.executable, '-c', 'pass'], ownership_guard=lambda: None)
        (self.root / 'input.txt').write_bytes(before)
        snapshot_input = Path(manifest['snapshot']) / 'input.txt'
        snapshot_input.chmod(0o600)
        snapshot_input.write_text('tampered\n')
        with self.assertRaisesRegex(ValueError, 'bytes changed'):
            passes.run_main_only(manifest, [sys.executable, '-c', 'pass'], ownership_guard=lambda: None)
        self.assertEqual((self.root / 'input.txt').read_bytes(), before)

    def test_timeout_cleanup_releases_lock(self):
        manifest = self.prepare()
        with self.assertRaises(subprocess.TimeoutExpired):
            passes.run_main_only(manifest, [sys.executable, '-c', 'import time; time.sleep(10)'],
                                 ownership_guard=lambda: None, timeout=.05)
        self.assertEqual(passes.run_main_only(manifest, [sys.executable, '-c', 'pass'],
                                            ownership_guard=lambda: None), 0)

    def test_cli_main_only_reports_precise_gate_before_reading_manifest(self):
        result = subprocess.run([sys.executable, str(Path(passes.__file__)), '--mode', 'main-only',
                                 '--manifest', '/missing-fixture', '--manifest-sha256', 'a' * 64,
                                 '--workspace', str(self.root), '--', sys.executable, '-c', 'pass'],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn('native dispatcher has no common-repository admission hook', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_native_mode_refuses_before_launch_without_runtime_hook(self):
        self.assertTrue(callable(getattr(passes, 'native_main_only_gate', None)),
                        'missing fail-closed native lifecycle gate')
        with self.assertRaisesRegex(ValueError, 'native dispatcher.*full worker lifecycle'):
            passes.native_main_only_gate()


if __name__ == '__main__':
    unittest.main()
