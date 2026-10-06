"""Offline installer regressions; all profile writes stay in temporary fixtures."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
AGENT = Path(os.environ.get('HERMES_AGENT_DIR', Path.home() / '.hermes/hermes-agent'))


class InstallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Activate the installed dependency generation without launch preparation:
        # importing hermes_bootstrap can provision tools and rewrite launchers.
        try:
            import ruamel.yaml
        except ImportError:
            sys.path.insert(0, str(AGENT))
            from pm.environments import activate_dependencies
            activate_dependencies(AGENT)
            import ruamel.yaml
        cls.dependencies = str(Path(ruamel.yaml.__file__).parents[2])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / 'fake-home'
        self.home.mkdir()
        (self.home / 'config.yaml').write_text('# retained comment\nskills: {}\n')
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        for rel in ('extras/monitors/repo_docs_monitor.py',
                    'extras/monitors/autogoal_monitor.py',
                    'extras/maintenance/scratch_cleanup.py',
                    'extras/maintenance/merge_train_daily.py'):
            p = self.repo / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('print("fixture target")\n')

    def install(self, repo=None, dry=False):
        env = dict(os.environ, HERMES_HOME=str(self.home), INSTALL_ARGS=json.dumps({
            'repo': str(repo or self.repo), 'profiles': ['default'], 'dry_run': dry}))
        code = (f'import sys, runpy; sys.path.insert(0, {self.dependencies!r}); '
                f'runpy.run_path({str(REPO / "extras/install_helper.py")!r}, run_name="__main__")')
        result = subprocess.run([sys.executable, '-I', '-c', code], env=env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def shell_install(self, repo_name='shell-repo', agent_name='agent'):
        repo = self.root / repo_name
        repo.mkdir()
        shutil.copy2(REPO / 'install.sh', repo / 'install.sh')
        (repo / 'extras').mkdir()
        shutil.copy2(REPO / 'extras/install_helper.py', repo / 'extras/install_helper.py')
        agent = self.root / agent_name
        agent.mkdir()
        (agent / 'hermes_bootstrap.py').write_text(
            f'import sys; sys.path.insert(0, {self.dependencies!r})\n')
        runtime = [sys.executable, '-I', '-c',
                   f'import sys; sys.path.insert(0, {str(agent)!r}); import hermes_bootstrap']
        bin_dir = self.root / 'bin'
        bin_dir.mkdir()
        fake = bin_dir / 'hermes'
        fake.write_text('#!/usr/bin/env python3\nimport json\n'
                        f'print({json.dumps(runtime)!r})\n')
        fake.chmod(0o755)
        env = dict(os.environ, HERMES_HOME=str(self.home),
                   PATH=str(bin_dir) + os.pathsep + os.environ['PATH'])
        result = subprocess.run(['bash', str(repo / 'install.sh'), '--profiles', 'default'],
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.home / 'scripts/repo_docs_monitor.py').exists())
        return result

    def test_legacy_wrapper_refreshes_to_new_location(self):
        scripts = self.home / 'scripts'
        scripts.mkdir()
        wrapper = scripts / 'repo_docs_monitor.py'
        target = self.root / 'missing-old-repo/extras/monitors/repo_docs_monitor.py'
        wrapper.write_text(f'#!/usr/bin/env python3\n# Wrapper: logic lives in {target}\n'
                           'import runpy, sys\nsys.argv[0] = "repo_docs_monitor.py"\n'
                           f'runpy.run_path("{target}", run_name="__main__")\n')
        self.install()
        result = subprocess.run([sys.executable, str(wrapper)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'fixture target\n')

    def test_custom_wrapper_referencing_extras_is_preserved(self):
        scripts = self.home / 'scripts'
        scripts.mkdir()
        wrapper = scripts / 'repo_docs_monitor.py'
        custom = '# custom extras/monitor runner\nprint("custom")\n'
        wrapper.write_text(custom)
        result = self.install()
        self.assertEqual(wrapper.read_text(), custom)
        self.assertIn('keep existing custom', result.stdout)

    def test_customized_managed_wrapper_is_not_overwritten(self):
        self.install()
        wrapper = self.home / 'scripts/repo_docs_monitor.py'
        custom = wrapper.read_text() + 'print("custom behavior")\n'
        wrapper.write_text(custom)
        result = self.install()
        self.assertEqual(wrapper.read_text(), custom)
        self.assertIn('keep existing custom', result.stdout)

    def test_dry_run_relocation_does_not_write_any_profile_files(self):
        self.install()
        before = {str(p.relative_to(self.home)): p.read_bytes()
                  for p in self.home.rglob('*') if p.is_file()}
        relocated = self.root / 'relocated'
        self.repo.rename(relocated)
        result = self.install(relocated, dry=True)
        after = {str(p.relative_to(self.home)): p.read_bytes()
                 for p in self.home.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertIn('write ', result.stdout)
        self.assertIn('(dry run)', result.stdout)

    def test_reinstall_is_idempotent(self):
        self.install()
        before = {str(p): p.stat().st_mtime_ns for p in self.home.rglob('*') if p.is_file()}
        result = self.install()
        after = {str(p): p.stat().st_mtime_ns for p in self.home.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertIn('already up to date', result.stdout)

    def test_shell_install_handles_quoted_agent_runtime_path(self):
        self.shell_install(agent_name='agent\'"back\\slash')

    def test_shell_install_handles_quoted_repository_path(self):
        self.shell_install(repo_name='shell\'"repo\\path')

    def test_managed_wrappers_refresh_after_repository_relocation(self):
        self.install()
        relocated = self.root / 'relocated'
        self.repo.rename(relocated)
        self.install(relocated)
        for wrapper in sorted((self.home / 'scripts').glob('*.py')):
            with self.subTest(wrapper=wrapper.name):
                result = subprocess.run([sys.executable, str(wrapper)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, 'fixture target\n')

    def test_wrapper_executes_with_quotes_and_backslashes_in_repo_path(self):
        exotic = self.root / 'repo\'"back\\slash'
        self.repo.rename(exotic)
        self.install(exotic)
        for wrapper in sorted((self.home / 'scripts').glob('*.py')):
            with self.subTest(wrapper=wrapper.name):
                result = subprocess.run([sys.executable, str(wrapper)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, 'fixture target\n')


if __name__ == '__main__':
    unittest.main()
