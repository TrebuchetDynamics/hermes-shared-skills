"""Exact candidate identities tested against disposable real Git histories."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git('init', '-q')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        (self.root / 'input').write_text('base')
        self.git('add', '.')
        self.git('commit', '-qm', 'base')
        self.base = self.git('rev-parse', 'HEAD')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], text=True).strip()

    def load(self):
        path = Path(__file__).with_name('candidate_identity.py')
        self.assertTrue(path.exists(), 'candidate identity implementation missing')
        spec = importlib.util.spec_from_file_location('candidate_identity', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_identity_pins_base_tree_and_prerequisite_ref(self):
        module = self.load()
        self.git('branch', 'sibling')
        self.git('branch', 'candidate')
        identity = module.capture(self.root, self.base, 'candidate', {'sibling': self.base})
        self.assertTrue(module.check(identity, self.root))
        self.assertEqual(identity['candidate_tree'], self.git('rev-parse', 'HEAD^{tree}'))
        (self.root / 'input').write_text('next')
        self.git('add', 'input')
        self.git('commit', '-qm', 'next')
        self.git('branch', '-f', 'sibling', 'HEAD')
        self.assertFalse(module.check(identity, self.root))
        with self.assertRaises(ValueError):
            module.capture(self.root, 'HEAD', 'candidate')
        with self.assertRaises(ValueError):
            module.capture(self.root, self.base, 'candidate', tree=self.git('rev-parse', 'HEAD^{tree}'))

    def test_agent_commit_emits_exact_identity_without_touching_shared_state(self):
        import json
        import os
        script = Path(__file__).with_name('agent_commit.sh')
        before_head = self.git('rev-parse', 'HEAD')
        before_index = (self.root / '.git/index').read_bytes()
        (self.root / 'input').write_text('candidate file')
        (self.root / 'unrelated').write_text('other writer')
        result = subprocess.run(['bash', str(script), str(self.root), 'fixture', 'card',
                                 'Fixture only', 'input'], capture_output=True, text=True,
                                env={**os.environ, 'AGENT_COMMIT_JSON': '1'}, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        try:
            identity = json.loads(result.stdout)
        except ValueError:
            self.fail('agent_commit must emit an opt-in exact candidate JSON identity')
        module = self.load()
        self.assertTrue(module.check(identity, self.root))
        self.assertEqual(identity['base_commit'], before_head)
        self.assertEqual(self.git('rev-parse', 'HEAD'), before_head)
        self.assertEqual((self.root / '.git/index').read_bytes(), before_index)
        self.assertEqual((self.root / 'unrelated').read_text(), 'other writer')
        self.assertEqual((self.root / 'input').read_text(), 'candidate file')
        self.assertNotIn('unrelated', self.git('ls-tree', '--name-only', identity['candidate_commit']))

    def test_missing_sibling_rejected_even_with_dirty_union(self):
        module = self.load()
        self.git('checkout', '-qb', 'sibling')
        (self.root / 'sibling').write_text('required')
        self.git('add', 'sibling')
        self.git('commit', '-qm', 'sibling')
        sibling = self.git('rev-parse', 'HEAD')
        self.git('checkout', '-qb', 'candidate', self.base)
        (self.root / 'sibling').write_text('required')  # shared union is not ancestry
        with self.assertRaisesRegex(ValueError, 'prerequisite'):
            module.capture(self.root, self.base, 'candidate', {'refs/heads/sibling': sibling})


if __name__ == '__main__':
    unittest.main()
