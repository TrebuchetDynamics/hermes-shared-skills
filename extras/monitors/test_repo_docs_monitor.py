#!/usr/bin/env python3
"""Offline monitor integration tests with disposable Git and Hermes fixtures."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

MONITOR = Path(__file__).with_name('repo_docs_monitor.py').resolve()


class DriftTests(unittest.TestCase):
    def test_root_directory_alias_backticks_use_head_despite_retargeting(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as tmp:
            root = Path(tmp) / 'repo'
            root.mkdir()
            env = {**os.environ, 'HERMES_HOME': str(Path(tmp) / 'hermes'),
                   'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_SYSTEM': os.devnull}

            def git(*args):
                subprocess.run(['git', *args], cwd=root, env=env, check=True, capture_output=True)

            git('init', '-q')
            (root / 'docs').mkdir()
            (root / 'docs/guide.md').write_text('Guide\n')
            (root / 'guide.md').write_text('Root guide\n')
            aliases = {'docs-link': 'docs', 'alias': 'docs-link', 'root-link': '.',
                       'absolute-link': str(root / 'docs')}
            for name, target in aliases.items():
                (root / name).symlink_to(target, target_is_directory=True)
            (root / 'file-link').symlink_to('docs/guide.md')
            (root / 'README.md').write_text(
                ''.join(f'`{name}/guide.md`\n`{name}/missing.md`\n' for name in aliases)
                + '`file-link/missing.md`\n')
            git('add', '.')
            git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                '-c', 'commit.gpgsign=false', 'commit', '-qm', 'fixture')

            def snapshot():
                return subprocess.run([sys.executable, str(MONITOR)], cwd=root, env=env,
                                      check=True, capture_output=True, text=True).stdout

            before = snapshot()
            self.assertIn(f'drift {len(aliases)}\n', before)
            for name in aliases:
                self.assertIn(f'  README.md: path {name}/missing.md\n', before)
                self.assertNotIn(f'  README.md: path {name}/guide.md\n', before)
            self.assertNotIn('  README.md: path file-link/missing.md\n', before)

            # Both breaking existing paths and supplying missing paths in the
            # working tree must leave committed alias classification unchanged.
            (root / 'replacement').mkdir()
            (root / 'replacement/missing.md').write_text('Uncommitted replacement\n')
            for name in aliases:
                (root / name).unlink()
                (root / name).symlink_to('replacement', target_is_directory=True)
            (root / 'file-link').unlink()
            (root / 'file-link').symlink_to('replacement', target_is_directory=True)
            self.assertEqual(snapshot(), before)

    def test_committed_directory_symlink_ignores_worktree_retargeting(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as tmp:
            root = Path(tmp) / 'repo'
            root.mkdir()
            env = {**os.environ, 'HERMES_HOME': str(Path(tmp) / 'hermes'),
                   'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_SYSTEM': os.devnull}

            def git(*args):
                subprocess.run(['git', *args], cwd=root, env=env, check=True, capture_output=True)

            git('init', '-q')
            (root / 'docs').mkdir()
            (root / 'docs/guide.md').write_text('Guide\n')
            (root / 'docs/nested').mkdir()
            (root / 'docs/nested/anchor').write_text('Retains committed directory\n')
            (root / 'docs-link').symlink_to('docs', target_is_directory=True)
            (root / 'docs/relative-link').symlink_to('../docs', target_is_directory=True)
            (root / 'nested-link').symlink_to('docs/nested', target_is_directory=True)
            (root / 'alias').symlink_to('docs-link', target_is_directory=True)
            (root / 'file-link').symlink_to('docs/guide.md')
            (root / 'absolute-link').symlink_to(root / 'docs', target_is_directory=True)
            targets = ['docs-link/guide.md', 'docs-link', 'docs/relative-link/guide.md',
                       'nested-link/../guide.md', 'alias/guide.md', 'file-link',
                       'absolute-link/guide.md']
            (root / 'README.md').write_text(''.join(f'[guide]({target})\n' for target in targets)
                                           + '`docs/relative-link/guide.md`\n')
            git('add', '.')
            git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                '-c', 'commit.gpgsign=false', 'commit', '-qm', 'fixture')

            def snapshot():
                return subprocess.run([sys.executable, str(MONITOR)], cwd=root, env=env,
                                      check=True, capture_output=True, text=True).stdout

            before = snapshot()
            self.assertIn('drift 0\n', before)
            (root / 'docs-link').unlink()
            (root / 'docs-link').symlink_to('missing', target_is_directory=True)
            self.assertEqual(snapshot(), before)

    def test_committed_broken_cyclic_and_deep_symlinks_remain_drift(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as tmp:
            root = Path(tmp) / 'repo'
            root.mkdir()
            env = {**os.environ, 'HERMES_HOME': str(Path(tmp) / 'hermes'),
                   'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_SYSTEM': os.devnull}

            def git(*args):
                subprocess.run(['git', *args], cwd=root, env=env, check=True, capture_output=True)

            git('init', '-q')
            (root / 'guide.md').write_text('Guide\n')
            links = {'broken': 'missing', 'cycle-a': 'cycle-b', 'cycle-b': 'cycle-a',
                     'escape': '../guide.md'}
            links.update({f'deep-{i}': f'deep-{i + 1}' for i in range(41)})
            links['deep-41'] = 'guide.md'
            for name, target in links.items():
                (root / name).symlink_to(target)
            targets = ['broken', 'broken/guide.md', 'cycle-a', 'cycle-a/guide.md',
                       'deep-0', 'escape']
            (root / 'README.md').write_text(''.join(f'[link]({target})\n' for target in targets))
            git('add', '.')
            git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                '-c', 'commit.gpgsign=false', 'commit', '-qm', 'fixture')

            def snapshot():
                return subprocess.run([sys.executable, str(MONITOR)], cwd=root, env=env,
                                      check=True, capture_output=True, text=True, timeout=10).stdout

            before = snapshot()
            self.assertIn(f'drift {len(targets)}\n', before)
            for target in targets:
                self.assertIn(f'  README.md: link {target}\n', before)
            # Working-tree repairs cannot conceal committed broken/cyclic links.
            for name in links:
                (root / name).unlink()
                (root / name).symlink_to('guide.md')
            (root / 'missing').mkdir()
            (root / 'missing/guide.md').write_text('Uncommitted guide\n')
            self.assertEqual(snapshot(), before)

    def test_uncommitted_source_deletion_does_not_change_drift(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as tmp:
            root = Path(tmp) / 'repo'
            root.mkdir()
            env = {**os.environ, 'HERMES_HOME': str(Path(tmp) / 'hermes'),
                   'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_SYSTEM': os.devnull}

            def git(*args):
                subprocess.run(['git', *args], cwd=root, env=env, check=True, capture_output=True)

            git('init', '-q')
            (root / 'README.md').write_text('[module](src/module.py)\n`src/module.py`\n')
            (root / 'src').mkdir()
            (root / 'src/module.py').write_text('# committed source\n')
            (root / 'src/anchor.py').write_text('# retains tracked source directory\n')
            git('add', '.')
            git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                '-c', 'commit.gpgsign=false', 'commit', '-qm', 'fixture')

            def snapshot():
                return subprocess.run([sys.executable, str(MONITOR)], cwd=root, env=env,
                                      check=True, capture_output=True, text=True).stdout

            before = snapshot()
            self.assertIn('drift 0\n', before)
            (root / 'src/module.py').unlink()
            self.assertEqual(snapshot(), before)

            # A committed deletion is a real drift event; recreating the file
            # without a commit must not conceal that event again.
            git('add', '-u')
            git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                '-c', 'commit.gpgsign=false', 'commit', '-qm', 'remove source')
            removed = snapshot()
            self.assertIn('drift 2\n', removed)
            (root / 'src/module.py').write_text('# uncommitted replacement\n')
            self.assertEqual(snapshot(), removed)


if __name__ == '__main__':
    unittest.main()
