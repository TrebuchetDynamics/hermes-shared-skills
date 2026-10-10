"""Real local Git fixtures; no provider, remote or native dispatch proof."""
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

class PassWorkspaceTests(unittest.TestCase):
    def setUp(self):
        (Path.home() / '.hermes/cache/scratch').mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=Path.home() / '.hermes/cache/scratch')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'source'
        self.root.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@local')
        (self.root / 'owned.py').write_text('base\n')
        self.git('add', 'owned.py'); self.git('commit', '-qm', 'base')
        self.base = self.git('rev-parse', 'HEAD')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], text=True).strip()

    def module(self):
        path = Path(__file__).with_name('pass_workspace.py')
        self.assertTrue(path.exists(), 'Executable isolated pass helper required')
        spec = importlib.util.spec_from_file_location('pass_workspace', path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        return module

    def test_required_sibling_must_be_explicitly_assembled(self):
        self.git('checkout', '-qb', 'sibling')
        (self.root / 'dependency.py').write_text('needed\n')
        self.git('add', 'dependency.py'); self.git('commit', '-qm', 'sibling')
        pin = self.git('rev-parse', 'HEAD')
        self.git('checkout', '--detach', self.base)
        (self.root / 'candidate.py').write_text('selected candidate\n')
        self.git('add', 'candidate.py'); self.git('commit', '-qm', 'candidate')
        candidate = self.git('rev-parse', 'HEAD')
        module = self.module()
        with self.assertRaisesRegex(ValueError, 'required path'):
            module.prepare(self.root, Path(self.tmp.name) / 'missing', self.base, self.base,
                           required_paths=['dependency.py'])
        identity = module.prepare(self.root, Path(self.tmp.name) / 'assembled', self.base,
                                  candidate, {'sibling': pin}, ['dependency.py', 'candidate.py'])
        self.assertEqual((Path(identity['workspace']) / 'dependency.py').read_text(), 'needed\n')
        self.assertEqual((Path(identity['workspace']) / 'candidate.py').read_text(), 'selected candidate\n')
        self.assertTrue(module.candidate_identity.check(identity, identity['workspace']))
        self.git('update-ref', 'refs/heads/sibling', self.base)
        self.assertFalse(module.candidate_identity.check(identity, identity['workspace']))

    def test_worker_start_refuses_retracted_source_before_command_writes(self):
        import hashlib
        module = self.module()
        target = Path(self.tmp.name) / 'pass'
        identity = module.prepare(self.root, target, self.base, self.base)
        manifest = {'source_workspace': str(self.root), 'candidate_identity': identity,
                    'files': [{'path': 'owned.py', 'sha256': hashlib.sha256(b'base\n').hexdigest()}],
                    'ledger_sha256': None}
        (self.root / 'owned.py').write_text('finding retracted\n')
        self.assertTrue(callable(getattr(module, 'run_checked', None)), 'Worker start requires executable guard')
        with self.assertRaisesRegex(ValueError, 'Source changed'):
            module.run_checked(manifest, target, ['python3', '-c', "open('owned.py','w').write('production edit')"])
        self.assertEqual((target / 'owned.py').read_text(), 'base\n')

    def test_worker_start_refuses_clean_checkout_at_different_commit(self):
        import hashlib
        module = self.module()
        target = Path(self.tmp.name) / 'pass'
        identity = module.prepare(self.root, target, self.base, self.base)
        manifest = {'source_workspace': str(self.root), 'candidate_identity': identity,
                    'files': [{'path': 'owned.py', 'sha256': hashlib.sha256(b'base\n').hexdigest()}],
                    'ledger_sha256': None}
        self.git('commit', '--allow-empty', '-qm', 'different candidate')
        other = self.git('rev-parse', 'HEAD')
        subprocess.run(['git', '-C', str(target), 'checkout', '--detach', other], check=True)
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            module.verify(manifest, target)

    def test_worker_guard_allows_fresh_initial_write_but_refuses_workspace_drift(self):
        import hashlib
        module = self.module()
        target = Path(self.tmp.name) / 'pass'
        identity = module.prepare(self.root, target, self.base, self.base)
        manifest = {'source_workspace': str(self.root), 'candidate_identity': identity,
                    'files': [{'path': 'owned.py', 'sha256': hashlib.sha256(b'base\n').hexdigest()},
                              {'path': 'new.py', 'sha256': None}], 'ledger_sha256': None}
        self.assertEqual(module.run_checked(manifest, target, ['python3', '-c',
                         "open('owned.py','w').write('authorized initial write')"]), 0)
        with self.assertRaisesRegex(ValueError, 'workspace changed'):
            module.verify(manifest, target)
        self.assertEqual((self.root / 'owned.py').read_text(), 'base\n')

    def test_ledger_appearance_after_create_refuses_worker_start(self):
        import hashlib
        module = self.module()
        target = Path(self.tmp.name) / 'pass'
        identity = module.prepare(self.root, target, self.base, self.base)
        manifest = {'source_workspace': str(self.root), 'candidate_identity': identity,
                    'files': [{'path': 'owned.py', 'sha256': hashlib.sha256(b'base\n').hexdigest()}],
                    'ledger_sha256': None}
        (self.root / 'goals.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'ledger changed'):
            module.run_checked(manifest, target, ['python3', '-c', "open('owned.py','w').write('wrong')"])
        self.assertEqual((target / 'owned.py').read_text(), 'base\n')

    def test_cli_worker_guard_refuses_manifest_replacement_before_initial_write(self):
        import hashlib
        import json
        import sys
        module = self.module()
        target = Path(self.tmp.name) / 'pass'
        identity = module.prepare(self.root, target, self.base, self.base)
        manifest = {'source_workspace': str(self.root), 'candidate_identity': identity,
                    'files': [{'path': 'owned.py', 'sha256': hashlib.sha256(b'base\n').hexdigest()}],
                    'ledger_sha256': None}
        receipt = Path(self.tmp.name) / 'manifest.json'
        receipt.write_text(json.dumps(manifest))
        digest = hashlib.sha256(receipt.read_bytes()).hexdigest()
        receipt.write_text(receipt.read_text() + '\n')
        result = subprocess.run([sys.executable, str(Path(__file__).with_name('pass_workspace.py')),
                                 '--manifest', str(receipt), '--manifest-sha256', digest,
                                 '--workspace', str(target), '--', sys.executable, '-c',
                                 "open('owned.py','w').write('wrong')"], capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('manifest changed', result.stderr)
        self.assertEqual((target / 'owned.py').read_text(), 'base\n')

    def test_dirty_shared_source_never_becomes_write_workspace(self):
        (self.root / 'owned.py').write_text('foreign dirty\n')
        (self.root / 'foreign.py').write_text('untracked foreign\n')
        index = (self.root / '.git/index').read_bytes()
        target = Path(self.tmp.name) / 'pass'
        identity = self.module().prepare(self.root, target, self.base, self.base)
        self.assertEqual(identity['workspace'], str(target))
        self.assertEqual((target / 'owned.py').read_text(), 'base\n')
        self.assertFalse((target / 'foreign.py').exists())
        (target / 'owned.py').write_text('worker change\n')
        self.assertEqual((self.root / 'owned.py').read_text(), 'foreign dirty\n')
        self.assertEqual((self.root / '.git/index').read_bytes(), index)
