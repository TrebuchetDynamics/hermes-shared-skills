"""Exercise the offline runner in small copies without importing unsafe tests."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/check.py'


class OfflineCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='offline checker ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'scripts').mkdir()
        self.script = self.root / 'scripts/check.py'
        if SCRIPT.exists():
            shutil.copy2(SCRIPT, self.script)

    def write(self, relative, content):
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return target

    def run_check(self, *args, env=None):
        return subprocess.run([sys.executable, str(self.script), *args],
                              cwd=self.root, env=env, text=True,
                              capture_output=True, timeout=15)

    def test_listing_is_import_free_and_uses_owned_directories(self):
        sentinel = "raise RuntimeError('unsafe import must never run')\n"
        self.write('tests/test_unit.py', sentinel)
        self.write('skills/autogoal/scripts/test_budget_controller.py', sentinel)
        self.write('vendor/examples/test_external.py', sentinel)
        self.write('skills/autogoal/references/vendor/test_external.py', sentinel)
        self.write('skills/repo-docs/scripts/test_goal_gap_regression.py', sentinel)
        self.write('skills/autogoal/scripts/test_native_lifecycle_controls.py', sentinel)
        self.write('tests/integration_plugin.py', sentinel)
        result = self.run_check('--list')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('RUN tests/test_unit.py', result.stdout)
        self.assertIn('RUN skills/autogoal/scripts/test_budget_controller.py', result.stdout)
        self.assertIn('EXCLUDE skills/repo-docs/scripts/test_goal_gap_regression.py [model]', result.stdout)
        self.assertIn('EXCLUDE skills/autogoal/scripts/test_native_lifecycle_controls.py [native]', result.stdout)
        self.assertIn('EXCLUDE tests/integration_plugin.py [integration]', result.stdout)
        self.assertNotIn('test_external.py', result.stdout)
        self.assertNotIn('unsafe import', result.stdout + result.stderr)

    def test_importable_inventory_is_side_effect_free(self):
        self.assertTrue(SCRIPT.is_file(), 'missing offline checker')
        spec = importlib.util.spec_from_file_location('check_inventory', SCRIPT)
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        included = self.write('tests/test_unit.py', "raise RuntimeError('do not import')\n")
        self.assertEqual(checker.discover_tests(self.root), [included])

    def test_runs_real_tests_without_live_flags_or_unsafe_imports(self):
        self.write('tests/test_environment.py', '''import os, unittest
class Check(unittest.TestCase):
    def test_environment(self):
        for name in ('CONTAINMENT_LINUX_TESTS', 'RUN_CONTROLLER_BRIDGE_LINUX', 'HERMES_NATIVE_HANDOFF_TEST'):
            self.assertNotIn(name, os.environ)
''')
        self.write('skills/repo-docs/scripts/test_goal_gap_regression.py',
                   "raise RuntimeError('live model imported')\n")
        env = dict(os.environ, CONTAINMENT_LINUX_TESTS='1', RUN_CONTROLLER_BRIDGE_LINUX='1',
                   HERMES_NATIVE_HANDOFF_TEST='1')
        result = self.run_check(env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Ran 1 test', result.stdout + result.stderr)
        self.assertIn('1 test directories passed', result.stdout)
        self.assertNotIn('live model imported', result.stdout + result.stderr)

    def test_failure_propagates_but_other_directory_still_runs(self):
        self.write('tests/test_failure.py', '''import unittest
class Check(unittest.TestCase):
    def test_failure(self): self.fail('deliberate regression')
''')
        self.write('skills/repo-docs/scripts/test_marker.py', '''from pathlib import Path
import unittest
class Check(unittest.TestCase):
    def test_marker(self): Path('checked').write_text('yes')
''')
        result = self.run_check()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('deliberate regression', result.stdout + result.stderr)
        self.assertTrue((self.root / 'skills/repo-docs/scripts/checked').is_file())

    def test_timeout_is_a_failure_not_a_skip(self):
        self.write('tests/test_hang.py', 'import time; time.sleep(3)\n')
        result = self.run_check('--timeout', '0.1')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('TIMEOUT', result.stdout)


if __name__ == '__main__':
    unittest.main()
