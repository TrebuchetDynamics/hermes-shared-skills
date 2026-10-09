"""Offline installer regressions; all profile writes stay in temporary fixtures."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
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
                    'extras/monitors/autogoal_gate.py',
                    'extras/maintenance/scratch_cleanup.py',
                    'extras/maintenance/merge_train_daily.py',
                    'extras/maintenance/question_relay.py'):
            p = self.repo / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('print("fixture target")\n')

    def install(self, repo=None, dry=False, profiles=('default',), active_home=None):
        env = dict(os.environ, HOME=str(self.root), HERMES_HOME=str(active_home or self.home), INSTALL_ARGS=json.dumps({
            'repo': str(repo or self.repo), 'profiles': profiles, 'dry_run': dry}))
        env.pop('HERMES_PROFILE', None)
        code = f'import sys, runpy; sys.path.insert(0, {str(AGENT)!r}); sys.path.insert(0, {self.dependencies!r}); '
        if profiles is None:
            # Hermes maps ANY home below the platform ~/.hermes to that fleet's
            # root. Isolate HOME too, and fail closed before any real discovery.
            code += ('from hermes_cli.profiles import _get_default_hermes_home; '
                     f'assert str(_get_default_hermes_home().resolve()) == {str(self.home.resolve())!r}, '
                     '"Fixture escaped its isolated Hermes root"; ')
        code += f'runpy.run_path({str(REPO / "extras/install/install_helper.py")!r}, run_name="__main__")'
        result = subprocess.run([sys.executable, '-I', '-c', code], env=env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def shell_install(self, repo_name='shell-repo', agent_name='agent', selection=('default',), sync=False, dry=False):
        repo = self.root / repo_name
        repo.mkdir()
        shutil.copy2(REPO / 'install.sh', repo / 'install.sh')
        (repo / 'extras/install').mkdir(parents=True)
        shutil.copy2(REPO / 'extras/install/install_helper.py', repo / 'extras/install/install_helper.py')
        if sync:
            shutil.copy2(REPO / 'extras/install/sync_repo.py', repo / 'extras/install/sync_repo.py')
            def git(cwd, *arguments):
                result = subprocess.run(['git', '-C', str(cwd), *arguments], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            git(repo, 'init', '-b', 'main')
            git(repo, 'config', 'user.name', 'Fixture')
            git(repo, 'config', 'user.email', 'fixture@example.invalid')
            git(repo, 'add', '.')
            git(repo, 'commit', '-m', 'installer')
            upstream = self.root / 'upstream'
            git(self.root, 'clone', str(repo), str(upstream))
            git(repo, 'remote', 'add', 'origin', str(upstream))
            git(repo, 'fetch', 'origin')
            git(repo, 'branch', '--set-upstream-to=origin/main')
            if not dry:
                (repo / 'extras/install/install_helper.py').write_text('raise SystemExit("stale helper executed")\n')
        agent = self.root / agent_name
        agent.mkdir()
        (agent / 'hermes_bootstrap.py').write_text(
            f'import sys; sys.path.insert(0, {self.dependencies!r})\n')
        (agent / 'pm').mkdir()
        (agent / 'pm/__init__.py').write_text('')
        (agent / 'pm/environments.py').write_text(
            f'import sys\ndef activate_dependencies(root): sys.path.insert(0, {self.dependencies!r})\n')
        (agent / 'hermes_cli').mkdir()
        (agent / 'hermes_cli/__init__.py').write_text('')
        (agent / 'hermes_cli/profiles.py').write_text(
            'import os\nfrom pathlib import Path\n'
            'def _get_default_hermes_home(): return Path(os.environ["HERMES_HOME"])\n'
            'def list_profile_names(): return ["default", "alpha", "beta"]\n')
        runtime = [sys.executable, '-I', '-c',
                   f'import sys; sys.path.insert(0, {str(agent)!r}); import hermes_bootstrap']
        bin_dir = self.root / 'bin'
        bin_dir.mkdir()
        fake = bin_dir / 'hermes'
        fake.write_text('#!/usr/bin/env python3\nimport json, os, sys\n'
                        f'sys.path.insert(0, {self.dependencies!r})\n'
                        'from pathlib import Path\nfrom ruamel.yaml import YAML\n'
                        'if sys.argv[1:] == ["--print-runtime-command"]:\n'
                        f'    print({json.dumps(runtime)!r})\n'
                        'elif sys.argv[1:3] == ["config", "set"]:\n'
                        '    path = Path(os.environ["HERMES_HOME"]) / "config.yaml"\n'
                        '    yaml = YAML(); data = yaml.load(path.read_text()); node = data\n'
                        '    parts = sys.argv[3].split(".")\n'
                        '    for key in parts[:-1]: node = node.setdefault(key, {})\n'
                        '    node[parts[-1]] = json.loads(sys.argv[4])\n'
                        '    with path.open("w") as f: yaml.dump(data, f)\n'
                        '    with (path.parent / "config-calls").open("a") as f: f.write(sys.argv[3] + "\\n")\n'
                        'else: raise SystemExit("unsupported fixture command")\n')
        fake.chmod(0o755)
        env = dict(os.environ, HOME=str(self.root), HERMES_HOME=str(self.home),
                   PATH=str(bin_dir) + os.pathsep + os.environ['PATH'])
        command = ['bash', str(repo / 'install.sh')]
        if not sync:
            command += ['--skip-sync']
        if selection is not None:
            command += ['--profiles', ','.join(selection)]
        if dry:
            command += ['--dry-run']
            before = {str(p): p.read_bytes() for base in (repo, self.home)
                      for p in base.rglob('*') if p.is_file()}
        result = subprocess.run(command, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        if dry:
            after = {str(p): p.read_bytes() for base in (repo, self.home)
                     for p in base.rglob('*') if p.is_file()}
            self.assertEqual(before, after)
        else:
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

    def test_real_native_discovery_from_named_home_skips_tombstones_and_ghosts(self):
        for name in ('alpha', 'deleted'):
            ph = self.home / 'profiles' / name
            ph.mkdir(parents=True)
            (ph / 'config.yaml').write_text('model: fixture-model\nskills: {}\n')
            (ph / 'SOUL.md').write_text('# Keep identity\n')
            (ph / 'cron').mkdir()
            (ph / 'cron/jobs.json').write_text('[]')
        (self.home / 'profiles/.deleted').mkdir()
        (self.home / 'profiles/.deleted/deleted').write_text('fixture tombstone')
        (self.home / 'profiles/ghost/logs').mkdir(parents=True)
        alpha = self.home / 'profiles/alpha'
        self.install(profiles=None, active_home=alpha)
        self.assertTrue((self.home / 'scripts/repo_docs_monitor.py').exists())
        self.assertTrue((alpha / 'scripts/repo_docs_monitor.py').exists())
        self.assertFalse((self.home / 'profiles/deleted/scripts').exists())
        self.assertFalse((self.home / 'profiles/ghost/config.yaml').exists())
        self.assertEqual((alpha / 'SOUL.md').read_text(), '# Keep identity\n')
        self.assertEqual((alpha / 'cron/jobs.json').read_text(), '[]')
        from ruamel.yaml import YAML
        cfg = YAML(typ='safe').load((alpha / 'config.yaml').read_text())
        self.assertEqual(cfg['model'], 'fixture-model')
        self.assertNotIn('approvals', cfg)
        self.assertNotIn('disabled', cfg['skills'])
        self.assertEqual(cfg['skills']['external_dirs'], [str(self.repo)])

    def test_shell_default_discovers_all_native_profiles(self):
        for name in ('alpha', 'beta'):
            ph = self.home / 'profiles' / name
            ph.mkdir(parents=True)
            (ph / 'config.yaml').write_text('skills: {}\n')
        self.shell_install(selection=None, sync=True)
        self.assertEqual((self.home / 'config-calls').read_text(), 'skills.external_dirs\n')
        for name in ('alpha', 'beta'):
            self.assertTrue((self.home / 'profiles' / name / 'scripts/repo_docs_monitor.py').exists())

    def test_shell_dry_run_preserves_git_and_profiles(self):
        result = self.shell_install(selection=None, sync=True, dry=True)
        self.assertIn('no Git writes', result.stdout)
        self.assertIn('(dry run)', result.stdout)
        self.assertFalse((self.root / '.hermes/private-records').exists())

    def test_shell_explicit_selection_does_not_touch_other_profiles(self):
        ph = self.home / 'profiles/alpha'
        ph.mkdir(parents=True)
        (ph / 'config.yaml').write_text('skills: {}\n')
        self.shell_install()
        self.assertFalse((ph / 'scripts').exists())

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
