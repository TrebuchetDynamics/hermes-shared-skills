"""Real Git fixture tests; never synchronize the developer checkout."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
SYNC = REPO / 'extras/install/sync_repo.py'


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.remote = self.root / 'upstream'
        self.remote.mkdir()
        self.git(self.remote, 'init', '-b', 'main')
        self.git(self.remote, 'config', 'user.email', 'fixture@example.invalid')
        self.git(self.remote, 'config', 'user.name', 'Fixture')
        (self.remote / 'tracked').write_text('original\n')
        (self.remote / '.gitignore').write_text('ignored/\n')
        (self.remote / 'install.sh').write_text('#!/bin/bash\nexit 0\n')
        (self.remote / 'extras/install').mkdir(parents=True)
        (self.remote / 'extras/install/install_helper.py').write_text('# fixture\n')
        self.git(self.remote, 'add', '.')
        self.git(self.remote, 'commit', '-m', 'initial')
        self.repo = self.root / 'checkout'
        self.git(self.root, 'clone', str(self.remote), str(self.repo))
        self.git(self.repo, 'config', 'user.email', 'fixture@example.invalid')
        self.git(self.repo, 'config', 'user.name', 'Fixture')
        self.env = dict(os.environ, HOME=str(self.root / 'home'))

    def git(self, path, *args):
        result = subprocess.run(['git', '-C', str(path), *args], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        return result.stdout

    def sync(self, *args):
        return subprocess.run([sys.executable, str(SYNC), str(self.repo), *args],
                              env=self.env, capture_output=True, text=True)

    def advance(self):
        (self.remote / 'tracked').write_text('upstream\n')
        self.git(self.remote, 'commit', '-am', 'update')

    def test_failed_fetch_keeps_head_index_and_working_tree(self):
        (self.repo / 'tracked').write_text('local\n')
        self.git(self.repo, 'add', 'tracked')
        head = self.git(self.repo, 'rev-parse', 'HEAD')
        index = (self.repo / '.git/index').read_bytes()
        self.git(self.repo, 'remote', 'set-url', 'origin', str(self.root / 'missing'))
        result = self.sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git(self.repo, 'rev-parse', 'HEAD'), head)
        self.assertEqual((self.repo / '.git/index').read_bytes(), index)
        self.assertEqual((self.repo / 'tracked').read_text(), 'local\n')
        self.assertFalse((self.root / 'home').exists())

    def test_dry_run_does_not_fetch_or_change_any_files(self):
        self.advance()
        (self.repo / 'tracked').write_text('local\n')
        before = {str(p.relative_to(self.repo)): p.read_bytes()
                  for p in self.repo.rglob('*') if p.is_file()}
        result = self.sync('--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        after = {str(p.relative_to(self.repo)): p.read_bytes()
                 for p in self.repo.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse((self.root / 'home').exists())

    def test_unrelated_ignored_and_untracked_files_survive(self):
        (self.repo / 'ignored').mkdir()
        (self.repo / 'ignored/secret').write_bytes(b'private\0data')
        (self.repo / 'notes').write_text('local notes')
        self.advance()
        result = self.sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.repo / 'ignored/secret').read_bytes(), b'private\0data')
        self.assertEqual((self.repo / 'notes').read_text(), 'local notes')

    def test_local_only_commit_remains_reachable_via_safety_ref(self):
        (self.repo / 'tracked').write_text('local commit\n')
        self.git(self.repo, 'commit', '-am', 'local-only')
        old = self.git(self.repo, 'rev-parse', 'HEAD').strip()
        self.advance()
        result = self.sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        refs = self.git(self.repo, 'for-each-ref', '--format=%(objectname)', 'refs/install-backups')
        self.assertIn(old, refs)
        self.assertEqual(self.git(self.repo, 'rev-parse', 'HEAD'), self.git(self.remote, 'rev-parse', 'HEAD'))

    def test_missing_upstream_fails_closed(self):
        self.git(self.repo, 'config', '--unset', 'branch.main.remote')
        result = self.sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.repo / 'tracked').read_text(), 'original\n')

    def test_untracked_collision_blocks_reset_without_data_loss(self):
        (self.repo / 'new-file').write_text('private local\n')
        (self.remote / 'new-file').write_text('remote tracked\n')
        self.git(self.remote, 'add', 'new-file')
        self.git(self.remote, 'commit', '-m', 'new tracked path')
        head = self.git(self.repo, 'rev-parse', 'HEAD')
        result = self.sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.repo / 'new-file').read_text(), 'private local\n')
        self.assertEqual(self.git(self.repo, 'rev-parse', 'HEAD'), head)

    def test_sync_discards_tracked_edits_with_private_recoverable_backup(self):
        (self.repo / 'tracked').write_text('staged\n')
        self.git(self.repo, 'add', 'tracked')
        (self.repo / 'tracked').write_text('working\n')
        self.advance()
        result = self.sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.repo / 'tracked').read_text(), 'upstream\n')
        backups = list((self.root / 'home/.hermes/private-records/shared-skills/install-backups').iterdir())
        self.assertEqual(len(backups), 1)
        backup = backups[0]
        self.assertEqual(backup.stat().st_mode & 0o777, 0o700)
        self.assertIn(b'staged', (backup / 'index.patch').read_bytes())
        self.assertIn(b'working', (backup / 'worktree.patch').read_bytes())
        self.assertTrue((backup / 'tracked.tar').exists())
        self.assertTrue((backup / 'index').exists())
        state = json.loads((backup / 'state.json').read_text())
        self.git(self.repo, 'reset', '--hard', state['head'])
        self.git(self.repo, 'apply', '--index', str(backup / 'index.patch'))
        self.git(self.repo, 'apply', str(backup / 'worktree.patch'))
        self.assertEqual(self.git(self.repo, 'show', ':tracked'), b'staged\n')
        self.assertEqual((self.repo / 'tracked').read_text(), 'working\n')

    def test_ignored_directory_collision_stops_without_removing_secrets(self):
        (self.repo / 'ignored').mkdir()
        (self.repo / 'ignored/private').write_text('local private')
        (self.remote / 'ignored').write_text('upstream file')
        self.git(self.remote, 'add', '-f', 'ignored')
        self.git(self.remote, 'commit', '-m', 'file replaces ignored directory')
        result = self.sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.repo / 'ignored/private').read_text(), 'local private')

    def test_backup_failure_stops_before_reset(self):
        (self.repo / 'tracked').write_text('local')
        self.advance()
        self.env['HOME'] = str(self.repo)
        head = self.git(self.repo, 'rev-parse', 'HEAD')
        result = self.sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.repo / 'tracked').read_text(), 'local')
        self.assertEqual(self.git(self.repo, 'rev-parse', 'HEAD'), head)


if __name__ == '__main__':
    unittest.main()
