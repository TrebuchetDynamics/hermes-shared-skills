"""Exercise the combined installer without installing real skills or plugins."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'install.sh'


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo with spaces'
        self.repo.mkdir()
        self.script = self.repo / 'install.sh'
        if SCRIPT.exists():
            shutil.copy2(SCRIPT, self.script)
        self.log = self.root / 'calls'
        self.env = dict(os.environ, CALL_LOG=str(self.log))
        for name, status in [('skills', 'SKILLS_EXIT'), ('plugins', 'PLUGINS_EXIT')]:
            child = self.repo / f'install-{name}.sh'
            child.write_text(f'''#!/usr/bin/env bash
printf '%s\\n' '{name}' "$@" >> "$CALL_LOG"
exit "${{{status}:-0}}"
''')
            child.chmod(0o755)

    def run_installer(self, *args):
        return subprocess.run(['bash', str(self.script), *args], cwd=self.root,
                              env=self.env, text=True, capture_output=True)

    def test_runs_in_order_and_preserves_arguments_from_other_directory(self):
        result = self.run_installer('--dry-run', '--hermes-home', '/tmp/home with spaces')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.log.read_text().splitlines(), [
            'skills', '--dry-run', '--hermes-home', '/tmp/home with spaces',
            'plugins', '--dry-run', '--hermes-home', '/tmp/home with spaces'])

    def test_either_failure_returns_nonzero_and_both_are_attempted(self):
        for variable in ('SKILLS_EXIT', 'PLUGINS_EXIT'):
            with self.subTest(variable=variable):
                self.env[variable] = '7'
                result = self.run_installer()
                self.assertEqual(result.returncode, 1)
                self.assertEqual(self.log.read_text().splitlines()[-2:], ['skills', 'plugins'])
                self.assertIn('7', result.stderr)
                del self.env[variable]

    def test_missing_child_fails_before_running_either(self):
        (self.repo / 'install-plugins.sh').unlink()
        result = self.run_installer()
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.log.exists())
        self.assertIn('install-plugins.sh', result.stderr)


if __name__ == '__main__':
    unittest.main()
