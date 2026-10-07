#!/usr/bin/env python3
"""Offline tests for the merge train's agent-branch phase, using throwaway repos and a fake kanban."""
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sh(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


class BranchPhase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.home = self.tmp / 'hermes'
        self.repo = self.tmp / 'proj'
        origin = self.tmp / 'origin.git'
        sh('git', 'init', '-q', '--bare', '-b', 'main', str(origin))
        sh('git', 'init', '-q', '-b', 'main', str(self.repo))
        for k, v in (('user.email', 't@t'), ('user.name', 't')):
            sh('git', 'config', k, v, cwd=self.repo)
        (self.repo / '.hermes').mkdir()
        (self.repo / '.hermes' / 'merge-train.json').write_text('{"gate": ["! grep -rq BAD src"]}')
        (self.repo / 'src').mkdir()
        for n in 'abcd':
            (self.repo / 'src' / f'{n}.py').write_text(f'{n} = 0\n')
        sh('git', 'add', '-A', cwd=self.repo)
        sh('git', 'commit', '-qm', 'init', cwd=self.repo)
        sh('git', 'remote', 'add', 'origin', str(origin), cwd=self.repo)
        sh('git', 'push', '-q', '-u', 'origin', 'main', cwd=self.repo)
        prof = self.home / 'profiles' / 'p'
        prof.mkdir(parents=True)
        (prof / 'config.yaml').write_text(f'terminal:\n  cwd: {self.repo}\n')
        db = sqlite3.connect(self.home / 'kanban.db')
        db.execute('CREATE TABLE tasks (id TEXT PRIMARY KEY, status TEXT)')
        db.executemany('INSERT INTO tasks VALUES (?, ?)',
                       [('t_good', 'done'), ('t_bad', 'done'), ('t_live', 'running'), ('t_dirty', 'done')])
        db.commit()

    def branch(self, task, path, text):
        sh('git', 'switch', '-q', '-c', f'agent/p/{task}', 'main', cwd=self.repo)
        (self.repo / path).write_text(text)
        sh('git', 'commit', '-qam', task, cwd=self.repo)
        sh('git', 'switch', '-q', 'main', cwd=self.repo)

    def run_train(self):
        env = dict(os.environ, HERMES_HOME=str(self.home))
        return subprocess.run([sys.executable, str(HERE / 'merge_train.py'), 'run'], env=env,
                              capture_output=True, text=True, timeout=300)

    def test_merges_done_branches_and_isolates_failures(self):
        self.branch('t_good', 'src/a.py', 'a = 1\n')
        self.branch('t_bad', 'src/b.py', 'BAD\n')
        self.branch('t_live', 'src/c.py', 'c = 1\n')
        self.branch('t_dirty', 'src/d.py', 'd = 1\n')
        (self.repo / 'src' / 'd.py').write_text('d = 2  # uncommitted owner work\n')
        old = os.stat(self.repo / 'src' / 'd.py').st_mtime - 3600
        os.utime(self.repo / 'src' / 'd.py', (old, old))  # old enough for the worktree phase
        out = self.run_train()
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn('1 merged', out.stdout)
        self.assertIn('agent/p/t_bad', out.stdout)
        self.assertIn('1 card not done', out.stdout)
        self.assertIn('1 overlaps uncommitted worktree files', out.stdout)
        main = sh('git', 'rev-parse', 'origin/main', cwd=self.repo)
        self.assertEqual(sh('git', 'show', f'{main}:src/a.py', cwd=self.repo), 'a = 1')
        self.assertEqual(sh('git', 'show', f'{main}:src/b.py', cwd=self.repo), 'b = 0')
        self.assertEqual(sh('git', 'show', f'{main}:src/d.py', cwd=self.repo), 'd = 2  # uncommitted owner work')
        self.assertEqual(sh('git', 'merge-base', '--is-ancestor', 'agent/p/t_good', main, cwd=self.repo), '')
        # The shared worktree shows the merged file as current, not reverted.
        self.assertEqual((self.repo / 'src' / 'a.py').read_text(), 'a = 1\n')
        self.assertEqual(sh('git', 'status', '--porcelain', cwd=self.repo), '')



class FailureComparison(unittest.TestCase):
    def test_only_new_failures_block_when_main_is_red(self):
        sys.path.insert(0, str(HERE))
        import merge_train as m
        self.assertFalse(m.new_failure(1, 'FAILED t.py::a\n', 1, 'FAILED t.py::a\n'))
        self.assertTrue(m.new_failure(1, 'FAILED t.py::a\nFAILED t.py::b\n', 1, 'FAILED t.py::a\n'))
        self.assertTrue(m.new_failure(1, 'anything', 0, ''))
        self.assertFalse(m.new_failure(0, '', 1, 'FAILED t.py::a'))
        self.assertTrue(m.new_failure(1, 'test x::y ... FAILED\n', 1, 'test x::z ... FAILED\n'))

if __name__ == '__main__':
    unittest.main()
