"""Offline tests for autogoal_gate.py (temp fleet root, temp kanban.db)."""
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GATE = Path(__file__).with_name('autogoal_gate.py')


class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.repo = root / 'repo'
        self.repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        prof = root / 'profiles' / 'demo'
        prof.mkdir(parents=True)
        (prof / 'config.yaml').write_text(f'terminal:\n  cwd: {self.repo}\n')
        self.db = sqlite3.connect(root / 'kanban.db')
        self.db.execute('CREATE TABLE tasks (id TEXT, assignee TEXT, status TEXT, current_run_id INTEGER)')
        self.db.execute('CREATE TABLE task_events (id INTEGER PRIMARY KEY, task_id TEXT, kind TEXT)')
        self.db.commit()
        self.env = dict(os.environ, HERMES_HOME=str(prof))

    def tearDown(self):
        self.db.close(); self.tmp.cleanup()

    def gate(self):
        return subprocess.run([sys.executable, str(GATE)], cwd=self.repo, env=self.env, capture_output=True, text=True).stdout

    def test_idle_always_runs(self):
        self.assertTrue(self.gate().startswith('idle demo '))

    def test_busy_is_stable_until_terminal_event(self):
        self.db.execute("INSERT INTO tasks VALUES ('t_1', 'demo', 'running', 7)"); self.db.commit()
        first = self.gate()
        self.assertTrue(first.startswith('busy demo'))
        self.assertEqual(first, self.gate())
        self.db.execute("INSERT INTO task_events (task_id, kind) VALUES ('t_1', 'review_requested')"); self.db.commit()
        self.assertNotEqual(first, self.gate())


if __name__ == '__main__':
    unittest.main()
