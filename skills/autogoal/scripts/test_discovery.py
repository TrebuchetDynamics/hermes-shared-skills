"""Offline regressions for read-only project-source discovery."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('discover', Path(__file__).with_name('discover_sources.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class DiscoveryTests(unittest.TestCase):
    def discover(self, files, **kwargs):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in files:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('# Fixture\n')
            return {x['path'] for x in m.discover(root, **kwargs)['candidates']}

    def test_readmes_do_not_crowd_out_plans_and_engineering_docs(self):
        important = {'README.md', 'docs/plans/next-feature.md', 'docs/architecture/service-boundaries.md', 'docs/runbooks/first-run.md'}
        files = list(important) + [f'components/c{i:02d}/README.md' for i in range(60)]
        self.assertTrue(important <= self.discover(files, limit=10))

    def test_explicit_upstream_exclusion(self):
        self.assertEqual(self.discover(['hermes-agent/ROADMAP.md', 'docs/plans/client-port.md'], exclude=['hermes-agent']), {'docs/plans/client-port.md'})

    def test_roadmap_without_backlog(self):
        self.assertEqual(self.discover(['ROADMAP.md']), {'ROADMAP.md'})

    def test_nested_todo(self):
        self.assertEqual(self.discover(['component/docs/TODO.md']), {'component/docs/TODO.md'})

    def test_empty_repository(self):
        self.assertEqual(self.discover([]), set())

    def test_dependency_pruning(self):
        self.assertEqual(self.discover(['node_modules/x/TODO.md', 'docs/plans/current.md']), {'docs/plans/current.md'})

    def test_exclusion_cannot_escape_root(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                m.discover(root, exclude=['../elsewhere'])

if __name__ == '__main__':
    unittest.main()
