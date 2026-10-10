"""Real CLI concurrency and stale-write contracts (temporary local fixtures)."""
import fcntl
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name('goals.py')


def ledger():
    return {'version': 1, 'goals': [{'id': 'G', 'title': 'Outcome', 'source': 'PRD.md#g',
            'status': 'unverified', 'tasks': ['T1', 'T2'], 'evidence': [], 'depends_on': [], 'priority': 1}],
            'tasks': [{'id': t, 'goal': 'G', 'title': t, 'status': 'open', 'section': 'Now',
                       'depends_on': []} for t in ('T1', 'T2')]}


class ConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / 'repo'
        self.repo.mkdir()
        (self.repo / 'goals.json').write_text(json.dumps(ledger()))
        self.body = '# TODO\n\n## Now\n\n- [ ] T1\n  Scope: all lines\n  Acceptance: retained\n\n- [ ] T2\n  Source: PRD.md#g\n'
        (self.repo / 'TODO.md').write_text(self.body)

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                              capture_output=True, text=True, timeout=15)

    def start(self, *args):
        return subprocess.Popen([sys.executable, str(SCRIPT), *map(str, args)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def finish(self, processes):
        for p in processes:
            out, err = p.communicate(timeout=15)
            self.assertEqual(p.returncode, 0, out + err)

    def git(self, *args):
        result = subprocess.run(['git', '-C', str(self.repo), *map(str, args)],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_git_dir_override_cannot_bypass_explicit_repository_lock(self):
        self.git('init')
        other = Path(self.tmp.name) / 'other'
        other.mkdir()
        initialized = subprocess.run(['git', '-C', str(other), 'init'],
                                     capture_output=True, text=True, timeout=15)
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        env = dict(os.environ, GIT_DIR=str(other / '.git'))
        before = (self.repo / 'goals.json').read_bytes()
        with (self.repo / '.git' / '.repo-docs-goals.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            p = subprocess.Popen([sys.executable, str(SCRIPT), 'task', str(self.repo), 'T1', 'done'],
                                 env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                # A completed CLI (success or refusal) is not serialization on B's lock.
                try:
                    out, err = p.communicate(timeout=0.7)
                except subprocess.TimeoutExpired:
                    pass
                else:
                    self.fail(f'CLI finished while target lock held: {p.returncode}: {out}{err}')
                self.assertEqual((self.repo / 'goals.json').read_bytes(), before)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
                out, err = p.communicate(timeout=15)
        self.assertEqual(p.returncode, 0, out + err)
        data = json.loads((self.repo / 'goals.json').read_text())
        self.assertEqual(next(t for t in data['tasks'] if t['id'] == 'T1')['status'], 'done')
        self.assertFalse((other / '.git' / '.repo-docs-goals.lock').exists())

    def test_common_dir_override_cannot_make_linked_worktree_canonical(self):
        self.git('init')
        self.git('add', 'goals.json', 'TODO.md')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'fixture')
        worker = Path(self.tmp.name) / 'worker'
        self.git('worktree', 'add', '-b', 'worker', worker)
        local = Path((worker / '.git').read_text().strip().removeprefix('gitdir: '))
        # Make the overridden common directory a valid Git directory, using real
        # primary objects/refs; clean discovery still identifies a linked checkout.
        for name in ('objects', 'refs'):
            (local / name).symlink_to(self.repo / '.git' / name, target_is_directory=True)
        before = {name: (worker / name).read_bytes() for name in ('goals.json', 'TODO.md')}
        # Force common == local without replacing GIT_DIR, independently of the first fix.
        env = dict(os.environ, GIT_COMMON_DIR=str(local))
        denied = subprocess.run([sys.executable, str(SCRIPT), 'task', str(worker), 'T1', 'done'],
                                env=env, capture_output=True, text=True, timeout=15)
        self.assertNotEqual(denied.returncode, 0, denied.stdout + denied.stderr)
        self.assertIn('canonical', denied.stderr)
        self.assertEqual(before, {name: (worker / name).read_bytes() for name in before})

    def test_git_environment_matrix_uses_real_target_and_preserves_caller_environment(self):
        self.git('init')
        outside = Path(self.tmp.name) / 'outside'
        outside.mkdir()
        self.assertEqual(subprocess.run(['git', '-C', str(outside), 'init'],
                                      capture_output=True, timeout=15).returncode, 0)
        variants = [
            {'GIT_DIR': str(outside / '.git')},
            {'GIT_WORK_TREE': str(outside)},
            {'GIT_COMMON_DIR': str(outside / '.git')},
            {'GIT_INDEX_FILE': str(outside / 'index')},
            {'GIT_OBJECT_DIRECTORY': str(outside / 'missing-objects')},
            {'GIT_ALTERNATE_OBJECT_DIRECTORIES': str(outside / 'missing-alternates')},
            {'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'core.worktree', 'GIT_CONFIG_VALUE_0': str(outside)},
            {'GIT_CONFIG_COUNT': 'invalid', 'GIT_CONFIG_KEY_7': 'unused', 'GIT_CONFIG_VALUE_7': 'unused'},
            {'GIT_CONFIG_PARAMETERS': "'core.worktree=" + str(outside) + "'"},
            {'GIT_CONFIG_SYSTEM': str(outside / 'config'), 'GIT_CONFIG_GLOBAL': str(outside / 'config'),
             'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG': str(outside / 'config')},
            {'GIT_CEILING_DIRECTORIES': str(self.repo.parent), 'GIT_DISCOVERY_ACROSS_FILESYSTEM': '0'},
        ]
        harness = '''import os,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, sys.argv.pop(1))
import goals
before = dict(os.environ)
run = goals.subprocess.run
def observed(*args, **kwargs):
    env = kwargs['env']
    assert not any(k.startswith('GIT_') for k in env), env
    assert env == {k:v for k,v in before.items() if not k.startswith('GIT_')}
    assert env['IDENTITY_SENTINEL'] == 'retained'
    return run(*args, **kwargs)
with patch.object(goals.subprocess, 'run', observed):
    goals.main()
assert dict(os.environ) == before
'''
        for overrides in variants:
            with self.subTest(overrides=overrides):
                env = dict(os.environ, IDENTITY_SENTINEL='retained', **overrides)
                with (self.repo / '.git' / '.repo-docs-goals.lock').open('a') as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX)
                    p = subprocess.Popen([sys.executable, '-c', harness, str(SCRIPT.parent),
                                          'task', str(self.repo), 'T1', 'in_progress'],
                                         env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    try:
                        with self.assertRaises(subprocess.TimeoutExpired):
                            p.communicate(timeout=0.3)
                    finally:
                        fcntl.flock(lock, fcntl.LOCK_UN)
                        out, err = p.communicate(timeout=15)
                self.assertEqual(p.returncode, 0, out + err)

    def test_primary_git_dir_override_cannot_bypass_linked_canonical_refusal(self):
        self.git('init')
        self.git('add', 'goals.json', 'TODO.md')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'fixture')
        worker = Path(self.tmp.name) / 'worker'
        self.git('worktree', 'add', '-b', 'worker', worker)
        before = {name: (worker / name).read_bytes() for name in ('goals.json', 'TODO.md')}
        env = dict(os.environ, GIT_DIR=str(self.repo / '.git'))
        result = subprocess.run([sys.executable, str(SCRIPT), 'task', str(worker), 'T1', 'done'],
                                env=env, capture_output=True, text=True, timeout=15)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('canonical', result.stderr)
        self.assertEqual(before, {name: (worker / name).read_bytes() for name in before})
        # Both source and canonical discovery use the same sanitized identity.
        result = subprocess.run([sys.executable, str(SCRIPT), 'task', str(worker), 'T1', 'done',
                                 '--canonical-repo', str(self.repo)], env=env,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, {name: (worker / name).read_bytes() for name in before})

    def test_linked_worktrees_require_explicit_canonical_target_and_share_lock(self):
        self.git('init')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'add', 'goals.json', 'TODO.md')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'fixture')
        worker = Path(self.tmp.name) / 'worker'
        self.git('worktree', 'add', '-b', 'worker', worker)
        snapshot = (worker / 'goals.json').read_bytes()
        denied = self.cli('task', worker, 'T1', 'done')
        self.assertNotEqual(denied.returncode, 0)
        self.assertIn('canonical', denied.stderr)
        with (self.repo / '.git' / '.repo-docs-goals.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            processes = [self.start('add-task', self.repo, 'T3', '--goal', 'G', '--title', 'Third'),
                         self.start('evidence', worker, 'G', '--kind', 'executed', '--ref', 'worker-check',
                                    '--result', 'pass', '--canonical-repo', self.repo),
                         self.start('render', worker, '--canonical-repo', self.repo)]
            try:
                time.sleep(0.4)
                self.assertTrue(all(p.poll() is None for p in processes), 'worktree bypassed common Git lock')
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
                self.finish(processes)
        data = json.loads((self.repo / 'goals.json').read_text())
        self.assertIn('T3', {t['id'] for t in data['tasks']})
        self.assertEqual(data['goals'][0]['evidence'][0]['ref'], 'worker-check')
        self.assertEqual((worker / 'goals.json').read_bytes(), snapshot)
        self.assertEqual((worker / 'TODO.md').read_text(), self.body)
        self.assertEqual(self.cli('render', self.repo).returncode, 0)
        self.assertTrue((self.repo / 'TODO.md').read_text().startswith(self.body))
        unrelated = Path(self.tmp.name) / 'unrelated'
        unrelated.mkdir()
        denied = self.cli('render', worker, '--canonical-repo', unrelated)
        self.assertNotEqual(denied.returncode, 0)
        self.assertIn('same repository', denied.stderr)

    def test_symlink_alias_serializes_but_symlink_files_and_lock_are_refused(self):
        alias = Path(self.tmp.name) / 'alias'
        alias.symlink_to(self.repo, target_is_directory=True)
        self.assertEqual(self.cli('fmt', alias).returncode, 0)
        for name, command in [('goals.json', 'fmt'), ('TODO.md', 'render'),
                              ('.repo-docs-goals.lock', 'fmt')]:
            path = self.repo / name
            saved = path.read_bytes()
            path.unlink()
            outside = Path(self.tmp.name) / ('outside-' + name)
            outside.write_bytes(saved)
            path.symlink_to(outside)
            result = self.cli(command, alias)
            self.assertNotEqual(result.returncode, 0, name)
            self.assertIn('symlink', result.stderr)
            self.assertTrue(path.is_symlink())
            self.assertEqual(outside.read_bytes(), saved)
            path.unlink()
            path.write_bytes(saved)

    def test_inflight_uncoordinated_edit_is_refused_not_overwritten(self):
        # Pause immediately before the real atomic writer, then edit outside its lock.
        harness = '''import sys,time
from pathlib import Path
sys.path.insert(0, sys.argv.pop(1))
import goals
ready, release = Path(sys.argv.pop(1)), Path(sys.argv.pop(1))
original = goals.atomic_write
def paused(*args, **kwargs):
    ready.touch()
    deadline = time.monotonic() + 10
    while not release.exists():
        if time.monotonic() > deadline: raise TimeoutError('release')
        time.sleep(.01)
    return original(*args, **kwargs)
goals.atomic_write = paused
goals.main()
'''
        for name, command in [('TODO.md', 'render'), ('goals.json', 'fmt')]:
            ready, release = (Path(self.tmp.name) / p for p in ('ready-' + name, 'release-' + name))
            p = subprocess.Popen([sys.executable, '-c', harness, str(SCRIPT.parent), str(ready), str(release),
                                  command, str(self.repo)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                deadline = time.monotonic() + 10
                while not ready.exists() and p.poll() is None and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertTrue(ready.exists(), 'writer did not reach atomic replacement')
                path = self.repo / name
                external = path.read_bytes() + b'\n'
                path.write_bytes(external)
            finally:
                release.touch()
                out, err = p.communicate(timeout=15)
            self.assertNotEqual(p.returncode, 0, out + err)
            self.assertIn('stale write', err)
            self.assertEqual(path.read_bytes(), external)
            self.assertFalse(list(self.repo.glob('.' + name + '.*')))

    def test_render_preserves_exact_complete_entries_outside_coverage(self):
        prefix = b'# TODO\r\n\r\n## Now\r\n- [ ] T1\r\n  Scope: first\r\n  Acceptance: second\r\n'
        suffix = b'\r\n\r\n## Next\r\n- [ ] T2\r\n  Source: PRD.md#g\r\n  Owner: worker\r\n\r\n\r\n'
        path = self.repo / 'TODO.md'
        path.write_bytes(prefix + b'<!-- goals:coverage:begin -->\nold\n<!-- goals:coverage:end -->' + suffix)
        result = self.cli('render', self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        rendered = path.read_bytes()
        self.assertTrue(rendered.startswith(prefix))
        self.assertTrue(rendered.endswith(suffix))
        self.assertEqual(self.cli('render', self.repo).returncode, 0)
        self.assertEqual(path.read_bytes(), rendered)
        path.write_bytes(prefix + suffix)
        self.assertEqual(self.cli('render', self.repo).returncode, 0)
        self.assertTrue(path.read_bytes().startswith(prefix + suffix))

    def test_atomic_replacement_preserves_existing_file_permissions(self):
        for name, command in [('goals.json', 'fmt'), ('TODO.md', 'render')]:
            path = self.repo / name
            path.chmod(0o640)
            result = self.cli(command, self.repo)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(path.stat().st_mode & 0o777, 0o640)

    def test_broken_git_metadata_is_not_treated_as_an_independent_fixture(self):
        (self.repo / '.git').write_text('gitdir: missing-worktree-metadata\n')
        before = (self.repo / 'goals.json').read_bytes()
        result = self.cli('fmt', self.repo)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Git repository identity', result.stderr)
        self.assertEqual((self.repo / 'goals.json').read_bytes(), before)
        self.assertFalse((self.repo / '.repo-docs-goals.lock').exists())

    def test_nongit_fixture_works_without_git_executable(self):
        env = dict(os.environ, PATH='')
        result = subprocess.run([sys.executable, str(SCRIPT), 'fmt', str(self.repo)],
                                env=env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.cli('validate', self.repo).stdout.strip(), 'ok')

    def test_expected_revision_refuses_stale_todo_before_any_write(self):
        token = self.cli('revision', self.repo)
        self.assertEqual(token.returncode, 0, token.stderr)
        revision = token.stdout.strip()
        self.assertRegex(revision, r'^[a-f0-9]{64}$')
        self.assertEqual(self.cli('render', self.repo, '--expected-revision', revision).returncode, 0)
        revision = self.cli('revision', self.repo).stdout.strip()
        (self.repo / 'TODO.md').write_text((self.repo / 'TODO.md').read_text() + '\nOwner continuation\n')
        before = {name: (self.repo / name).read_bytes() for name in ('goals.json', 'TODO.md')}
        for command in [('render',), ('task', 'T1', 'done'),
                        ('evidence', 'G', '--kind', 'inspection', '--ref', 'x', '--result', 'pass')]:
            result = self.cli(command[0], self.repo, *command[1:], '--expected-revision', revision)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('stale revision', result.stderr)
            self.assertEqual(before, {name: (self.repo / name).read_bytes() for name in before})

    def test_parallel_mutations_and_render_wait_for_one_repository_lock(self):
        before = (self.repo / 'goals.json').read_bytes()
        with (self.repo / '.repo-docs-goals.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            processes = [self.start('add-task', self.repo, 'T3', '--goal', 'G', '--title', 'Third'),
                         self.start('evidence', self.repo, 'G', '--kind', 'executed', '--ref', 'check-a', '--result', 'pass'),
                         self.start('task', self.repo, 'T1', 'in_progress'),
                         self.start('render', self.repo)]
            try:
                time.sleep(0.4)
                self.assertTrue(all(p.poll() is None for p in processes), 'CLI bypassed repository lock')
                self.assertEqual((self.repo / 'goals.json').read_bytes(), before)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
                self.finish(processes)
        data = json.loads((self.repo / 'goals.json').read_text())
        self.assertEqual({t['id'] for t in data['tasks']}, {'T1', 'T2', 'T3'})
        self.assertEqual(next(t for t in data['tasks'] if t['id'] == 'T1')['status'], 'in_progress')
        self.assertEqual(data['goals'][0]['evidence'][0]['ref'], 'check-a')
        self.assertEqual(self.cli('render', self.repo).returncode, 0)
        todo = (self.repo / 'TODO.md').read_text()
        self.assertTrue(todo.startswith(self.body))
        self.assertIn('T3', todo)


if __name__ == '__main__':
    unittest.main()
