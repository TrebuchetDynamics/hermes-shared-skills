#!/usr/bin/env python3
"""Test offline discovery without running model-backed or vendored checks."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check import discover_tests


class DiscoveryTests(unittest.TestCase):
    def test_discovers_all_first_party_suites_and_excludes_live_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            offline = ['fleet-status/scripts/test_status.py', 'extras/vendor/test_sync_vendor.py',
                       'scripts/test_check.py', 'autogoal/scripts/test_picker_policy.py',
                       'autogoal/scripts/test_native_containment.py',
                       'autogoal/scripts/test_controller_bridge.py']
            excluded = ['repo-docs/scripts/test_goal_gap_regression.py',
                        'hard-blockers/scripts/test_repo_docs.py',
                        'autogoal/scripts/test_native_lifecycle_controls.py',
                        'autogoal/scripts/test_native_containment_linux.py',
                        'autogoal/scripts/test_controller_bridge_linux.py',
                        'vendor/upstream/test_foreign.py', '.git/test_hidden.py']
            for name in offline + excluded:
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('# fixture\n')
            self.assertEqual([str(p.relative_to(root)) for p in discover_tests(root)], sorted(offline))

    def test_context_invalid_python_fails_syntax_gate(self):
        import contextlib
        import io
        from unittest.mock import patch
        import check
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'sample').mkdir()
            (root / 'sample/SKILL.md').write_text('---\nname: sample\ndescription: Useful workflow.\n---\nBody\n')
            (root / 'test_good.py').write_text('print("fixture test passed")\n')
            helper = root / 'helper.py'
            for source in ['return 1\n', 'break\n', 'await f()\n']:
                with self.subTest(source=source):
                    helper.write_text(source)
                    with patch.object(check, 'ROOT', root), contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(check.main(), 1)

    def test_symlinked_external_tests_are_not_executed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'repo'
            root.mkdir()
            outside = Path(tmp) / 'test_outside.py'
            outside.write_text('raise RuntimeError("should not run")\n')
            (root / 'test_link.py').symlink_to(outside)
            self.assertEqual(discover_tests(root), [])


if __name__ == '__main__':
    unittest.main()
