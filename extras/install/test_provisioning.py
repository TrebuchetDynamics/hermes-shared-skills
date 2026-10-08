"""Real shell composition with a fake Hermes boundary; no live profiles or jobs."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import test_install

ROOT = Path(__file__).resolve().parents[2]
FAKE = r'''
import json, os, sys
from pathlib import Path
from ruamel.yaml import YAML
yaml = YAML()
root = Path(os.environ['HERMES_HOME'])
state = Path(os.environ['FIXTURE_STATE'])
data = json.loads(state.read_text())
original = json.loads(state.read_text())
a = sys.argv[1:]
profile = 'default'
if a[:1] == ['-p']:
    profile, a = a[1], a[2:]
home = root if profile == 'default' else root / 'profiles' / profile
if a == ['--print-runtime-command']:
    print(os.environ['FIXTURE_RUNTIME'])
elif a == ['profile', 'list']:
    print('\n'.join(sorted(data['profiles'])))
elif a[:2] == ['profile', 'create']:
    name = a[2]
    if name in data['profiles']:
        raise SystemExit('duplicate profile')
    target = root / 'profiles' / name
    target.mkdir(parents=True)
    (target / 'config.yaml').write_text('# project identity\nmodel: fixture-model\nskills: {}\n')
    (target / 'SOUL.md').write_text('# Project identity\nKeep this.\n')
    data['profiles'].append(name)
elif a[:2] == ['config', 'set']:
    cfg = home / 'config.yaml'
    content = yaml.load(cfg.read_text())
    node = content
    parts = a[2].split('.')
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = a[3]
    with cfg.open('w') as stream:
        yaml.dump(content, stream)
elif a == ['cron', 'list']:
    for job in data['jobs'].get(profile, []):
        print(job['id'])
        print('  ' + job['args'][job['args'].index('--name') + 1])
elif a[:2] == ['cron', 'create']:
    jobs = data['jobs'].setdefault(profile, [])
    jobs.append({'id': f'{len(jobs)+1:012x}', 'args': a})
else:
    raise SystemExit('Unexpected fake CLI call: ' + repr(a))
if data != original:
    state.write_text(json.dumps(data, sort_keys=True))
'''


class ProvisioningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reuse only dependency discovery; never instantiate its test cases.
        test_install.InstallTests.setUpClass()
        cls.dependencies = test_install.InstallTests.dependencies

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='provisioning-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo with spaces'
        self.repo.mkdir()
        for name in ('bootstrap.sh', 'install.sh'):
            shutil.copy2(ROOT / name, self.repo / name)
        for name in ('install', 'cron', 'soul', 'monitors', 'maintenance'):
            shutil.copytree(ROOT / 'extras' / name, self.repo / 'extras' / name,
                            ignore=shutil.ignore_patterns('__pycache__'))
        self.home = self.root / 'home'
        self.home.mkdir()
        (self.home / 'config.yaml').write_text('# retain comment\nmodel: fixture-model\nskills: {}\n')
        (self.home / 'SOUL.md').write_text('# Personal identity\nKeep this.\n')
        self.workspace = self.root / 'project workspace'
        self.workspace.mkdir()
        self.state = self.root / 'state.json'
        self.state.write_text(json.dumps({'profiles': [], 'jobs': {}}))
        agent = self.root / 'fake agent'
        agent.mkdir()
        (agent / 'hermes_bootstrap.py').write_text(
            f'import sys; sys.path.insert(0, {self.dependencies!r})\n')
        runtime = [sys.executable, '-I', '-c',
                   f'import sys; sys.path.insert(0, {str(agent)!r}); import hermes_bootstrap']
        binary = self.root / 'bin'
        binary.mkdir()
        fake = binary / 'hermes'
        fake.write_text(f'#!{sys.executable}\nimport sys\nsys.path.insert(0, {self.dependencies!r})\n' + FAKE)
        fake.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.root), HERMES_HOME=str(self.home),
                        PATH=str(binary) + os.pathsep + os.environ['PATH'],
                        FIXTURE_STATE=str(self.state), FIXTURE_RUNTIME=json.dumps(runtime))
        self.env.pop('HERMES_PROFILE', None)

    def run_script(self, name, *args):
        result = subprocess.run(['bash', str(self.repo / name), *args], env=self.env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def snapshot(self):
        return {str(p.relative_to(self.home)): p.read_bytes()
                for p in self.home.rglob('*') if p.is_file()}

    def config(self, home):
        from ruamel.yaml import YAML
        return YAML(typ='safe').load((home / 'config.yaml').read_text())

    def assert_wired(self, home, project=False):
        cfg = self.config(home)
        self.assertEqual(cfg['skills']['external_dirs'], [str(self.repo)])
        self.assertEqual(cfg['model'], 'fixture-model')
        self.assertEqual(cfg['approvals']['mode'], 'off')
        self.assertFalse(cfg['security']['protected_instruction_files'])
        self.assertIn('Keep this.', (home / 'SOUL.md').read_text())
        wrappers = {'repo_docs_monitor.py', 'autogoal_gate.py', 'autogoal_monitor.py', 'question_relay.py'}
        if not project:
            wrappers |= {'scratch_cleanup.py', 'merge_train_daily.py'}
        self.assertEqual({p.name for p in (home / 'scripts').iterdir()}, wrappers)
        # Execute only generated wrapper glue; intercept dispatch so monitors never run.
        from unittest.mock import patch
        for name in wrappers:
            directory = 'monitors' if name in {
                'repo_docs_monitor.py', 'autogoal_gate.py', 'autogoal_monitor.py'
            } else 'maintenance'
            target = str(self.repo / 'extras' / directory / name)
            body = (home / 'scripts' / name).read_text()
            old_argv = sys.argv[:]
            try:
                with patch('runpy.run_path') as dispatch:
                    exec(compile(body, str(home / 'scripts' / name), 'exec'), {})
                    dispatch.assert_called_once_with(target, run_name='__main__')
            finally:
                sys.argv[:] = old_argv
        if project:
            self.assertEqual(cfg['terminal']['cwd'], str(self.workspace))
            self.assertTrue({'fleet-status', 'fleet-blockers', 'fleet-governor'} <= set(cfg['skills']['disabled']))

    def jobs(self, profile):
        return json.loads(self.state.read_text())['jobs'].get(profile, [])

    def test_explicit_relocation_preserves_unrelated_inputs(self):
        self.run_script('install.sh', '--profiles', 'default')
        (self.repo / 'repo-docs').mkdir()
        (self.repo / 'repo-docs/SKILL.md').write_text('# shared fixture\n')
        from ruamel.yaml import YAML
        yaml = YAML()
        cfg = self.config(self.home)
        unrelated = str(self.root / 'independent skills')
        cfg['skills']['external_dirs'].extend([unrelated, unrelated])
        with (self.home / 'config.yaml').open('w') as stream:
            yaml.dump(cfg, stream)
        custom = self.home / 'scripts/question_relay.py'
        custom.write_text('# custom wrapper\n')
        override = self.home / 'skills/repo-docs/SKILL.md'
        override.parent.mkdir(parents=True)
        override.write_text('# local override\n')
        old = self.repo
        self.repo = self.root / 'relocated checkout'
        old.rename(self.repo)
        args = ('--profiles', 'default', '--replace-root', str(old))
        before, state = self.snapshot(), self.state.read_bytes()
        self.run_script('install.sh', *args, '--dry-run')
        self.assertEqual(self.snapshot(), before)
        result = self.run_script('install.sh', *args)
        self.assertEqual(self.config(self.home)['skills']['external_dirs'],
                         [str(self.repo), unrelated, unrelated])
        self.assertIn('shadow', result.stdout.lower())
        self.assertEqual(custom.read_text(), '# custom wrapper\n')
        self.assertEqual(override.read_text(), '# local override\n')
        self.assertEqual(self.config(self.home)['model'], 'fixture-model')
        self.assertEqual((self.home / 'SOUL.md').read_bytes(), before['SOUL.md'])
        self.assertEqual(self.state.read_bytes(), state)
        body = (self.home / 'scripts/repo_docs_monitor.py').read_text()
        self.assertIn(str(self.repo), body)
        self.assertNotIn(str(old), body)
        after = self.snapshot()
        self.run_script('install.sh', *args)
        self.assertEqual(self.snapshot(), after)

    def test_customized_profile_adoption_options_are_additive(self):
        project = self.home / 'profiles/demo'
        project.mkdir(parents=True)
        (project / 'config.yaml').write_text(
            '# custom comment\nmodel: fixture-model\ncustom: retain\n'
            'skills:\n  disabled: [my-private-skill]\n'
            'platforms:\n  telegram:\n    extra:\n      command_menu:\n        priority: [personal]\n')
        (project / 'SOUL.md').write_text('# Existing identity\nKeep this.\n')
        (project / '.env').write_text('FIXTURE_ONLY=retain\n')
        self.state.write_text(json.dumps({'profiles': ['demo'], 'jobs': {'demo': [
            {'id': 'abc123abc123', 'args': ['cron', 'create', '* * * * *', 'fixture', '--name', 'unrelated-job']} ]}}))
        before = self.snapshot()
        self.run_script('extras/install/new_profile.sh', 'demo', str(self.workspace), '--no-cron')
        cfg = self.config(project)
        self.assertEqual(cfg['custom'], 'retain')
        self.assertIn('# custom comment', (project / 'config.yaml').read_text())
        self.assertEqual((project / '.env').read_bytes(), before['profiles/demo/.env'])
        expected_prune = {line.strip() for line in (self.repo / 'extras/install/disabled-skills.txt').read_text().splitlines()
                          if line.strip() and not line.lstrip().startswith('#')}
        self.assertEqual(set(cfg['skills']['disabled']), expected_prune | {
            'my-private-skill', 'fleet-governor', 'fleet-status', 'fleet-blockers'})
        self.assertEqual(cfg['platforms']['telegram']['extra']['command_menu']['priority'],
                         ['personal', 'repo_docs', 'autogoal', 'grill_me', 'lgtm', 'git_commit_push', 'git_pull_merge', 'impeccable'])
        soul = (project / 'SOUL.md').read_text()
        for snippet in (self.repo / 'extras/soul').glob('*.md'):
            if snippet.name != 'README.md':
                self.assertEqual(soul.count(snippet.read_text().strip()), 1)
        self.assertEqual(len(self.jobs('demo')), 1)
        self.assertEqual({k: v for k, v in self.snapshot().items() if not k.startswith('profiles/demo/')},
                         {k: v for k, v in before.items() if not k.startswith('profiles/demo/')})
        after, state = self.snapshot(), self.state.read_bytes()
        self.run_script('extras/install/new_profile.sh', 'demo', str(self.workspace), '--no-cron')
        self.assertEqual(self.snapshot(), after)
        self.assertEqual(self.state.read_bytes(), state)

    def test_profile_escape_is_rejected_before_any_mutation(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (outside / 'config.yaml').write_text('model: outside\n')
        before = self.snapshot()
        for name in ('../../outside', str(outside)):
            result = subprocess.run(['bash', str(self.repo / 'install.sh'), '--profiles',
                                     'default,' + name], env=self.env,
                                    capture_output=True, text=True, timeout=30)
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertEqual(self.snapshot(), before)
            self.assertEqual((outside / 'config.yaml').read_text(), 'model: outside\n')

    def test_symlinked_config_outside_profile_is_not_written(self):
        outside = self.root / 'outside.yaml'
        outside.write_text('model: outside\n')
        (self.home / 'config.yaml').unlink()
        (self.home / 'config.yaml').symlink_to(outside)
        result = subprocess.run(['bash', str(self.repo / 'install.sh'), '--profiles', 'default'],
                                env=self.env, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(outside.read_text(), 'model: outside\n')
        self.assertFalse((self.home / 'scripts').exists())

    def test_default_bootstrap_twice(self):
        self.run_script('bootstrap.sh', '--no-vendor')
        self.assert_wired(self.home)
        self.assertEqual([job['args'] for job in self.jobs('default')], [
            ['cron', 'create', '30 3 * * *', '--name', 'merge-train-daily', '--script',
             'merge_train_daily.py', '--no-agent', '--deliver', 'local'],
            ['cron', 'create', '17 4 * * 0', '--name', 'scratch-cleanup-weekly', '--script',
             'scratch_cleanup.py', '--no-agent', '--deliver', 'local']])
        before, state = self.snapshot(), self.state.read_bytes()
        self.run_script('bootstrap.sh', '--no-vendor')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.state.read_bytes(), state)

    def test_project_create_then_adopt_twice(self):
        default = self.snapshot()
        args = ('demo', str(self.workspace), '--deliver', 'local')
        self.run_script('extras/install/new_profile.sh', *args)
        project = self.home / 'profiles/demo'
        self.assert_wired(project, project=True)
        outside_project = {key: value for key, value in self.snapshot().items()
                           if not key.startswith('profiles/demo/')}
        self.assertEqual(outside_project, default)
        self.assertEqual(self.jobs('default'), [])
        self.assertEqual(json.loads(self.state.read_text())['profiles'], ['demo'])
        jobs = self.jobs('demo')
        self.assertEqual(len(jobs), 2)
        docs, auto = [j['args'] for j in jobs]
        for job, monitor in [(docs, 'repo_docs_monitor.py'), (auto, 'autogoal_gate.py')]:
            self.assertEqual(job[job.index('--workdir')+1], str(self.workspace))
            self.assertEqual(job[job.index('--monitor-script')+1], monitor)
            self.assertEqual(job[job.index('--deliver')+1], 'local')
        self.assertIn('--continuity', auto)
        self.assertIn(jobs[0]['id'], auto[3])
        self.assertNotIn('{repo_docs_job_id}', auto[3])
        before, state = self.snapshot(), self.state.read_bytes()
        self.run_script('extras/install/new_profile.sh', *args)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.state.read_bytes(), state)

    def test_dry_runs_preserve_profiles_and_jobs(self):
        before, state = self.snapshot(), self.state.read_bytes()
        self.run_script('bootstrap.sh', '--no-vendor', '--dry-run')
        self.run_script('extras/install/new_profile.sh', 'demo', str(self.workspace), '--dry-run')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.state.read_bytes(), state)

    def test_no_cron_options(self):
        self.run_script('bootstrap.sh', '--no-vendor', '--no-cleanup-cron')
        self.run_script('extras/install/new_profile.sh', 'demo', str(self.workspace), '--no-cron')
        self.assertEqual(json.loads(self.state.read_text())['jobs'], {})
        self.assert_wired(self.home)
        self.assert_wired(self.home / 'profiles/demo', project=True)

    def test_negative_control_rejects_default_profile_contamination(self):
        script = self.repo / 'extras/install/new_profile.sh'
        script.write_text(script.read_text() + '\nmkdir -p "$HERMES_HOME/scripts"\n'
                          + 'touch "$HERMES_HOME/scripts/unexpected.py"\n')
        with self.assertRaises(AssertionError):
            self.test_project_create_then_adopt_twice()

    def test_negative_control_rejects_wrong_wrapper_target(self):
        self.run_script('bootstrap.sh', '--no-vendor')
        wrapper = self.home / 'scripts/repo_docs_monitor.py'
        wrapper.write_text(wrapper.read_text().replace(
            f'runpy.run_path({str(self.repo / "extras/monitors/repo_docs_monitor.py")!r}',
            "runpy.run_path('/wrong/target.py'"))
        with self.assertRaises(AssertionError):
            self.assert_wired(self.home)

    def test_negative_control_detects_disconnected_installer(self):
        # Mutate only the fixture copy. A shell-only job test would miss this defect.
        (self.repo / 'install.sh').write_text('#!/usr/bin/env bash\nexit 0\n')
        self.run_script('bootstrap.sh', '--no-vendor')
        with self.assertRaises((AssertionError, KeyError)):
            self.assert_wired(self.home)


if __name__ == '__main__':
    unittest.main()
