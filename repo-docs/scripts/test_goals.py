"""Unit tests for goals.py (no network, no LLM)."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name('goals.py')


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def sample():
    return {
        'version': 1,
        'goals': [
            {'id': 'GOAL-1', 'title': 'Starts at 0', 'source': 'README.md#intent', 'status': 'met',
             'evidence': [{'kind': 'inspection', 'ref': 'test/counter_test.dart', 'result': 'pass'}],
             'tasks': ['TASK-002'], 'priority': 1},
            {'id': 'GOAL-4', 'title': 'Decrement floors at 0', 'source': 'README.md#intent', 'status': 'unmet',
             'tasks': ['TASK-001'], 'priority': 4},
            {'id': 'GOAL-5', 'title': 'Undo', 'source': 'PRD.md#req-5', 'status': 'unmet',
             'tasks': ['TASK-003'], 'depends_on': ['GOAL-4'], 'priority': 5},
        ],
        'tasks': [
            {'id': 'TASK-001', 'goal': 'GOAL-4', 'title': 'Implement decrement', 'status': 'open', 'section': 'Now'},
            {'id': 'TASK-002', 'goal': 'GOAL-1', 'title': 'Run counter test', 'status': 'open', 'section': 'Now'},
            {'id': 'TASK-003', 'goal': 'GOAL-5', 'title': 'Implement undo', 'status': 'open', 'section': 'Next'},
        ],
    }


class GoalsTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.repo = Path(self.dir.name)
        (self.repo / 'goals.json').write_text(json.dumps(sample()))

    def tearDown(self):
        self.dir.cleanup()

    def data(self):
        return json.loads((self.repo / 'goals.json').read_text())

    def test_met_without_executed_evidence_is_invalid_then_downgraded(self):
        r = run('validate', str(self.repo))
        self.assertEqual(r.returncode, 1)
        self.assertIn('GOAL-1: met without executed+pass evidence', r.stdout)
        run('fmt', str(self.repo))
        self.assertEqual(self.data()['goals'][0]['status'], 'unverified')
        self.assertEqual(run('validate', str(self.repo)).stdout.strip(), 'ok')

    def test_fmt_is_byte_stable(self):
        run('fmt', str(self.repo)); first = (self.repo / 'goals.json').read_bytes()
        run('fmt', str(self.repo)); self.assertEqual(first, (self.repo / 'goals.json').read_bytes())

    def test_next_orders_by_priority_then_status_and_respects_dependencies(self):
        run('fmt', str(self.repo))
        self.assertTrue(run('next', str(self.repo)).stdout.startswith('TASK-002'))  # GOAL-1 priority 1 first
        d = self.data(); d['goals'][0]['priority'] = 9   # demote the unverified goal below GOAL-4 (priority 4)
        (self.repo / 'goals.json').write_text(json.dumps(d))
        self.assertTrue(run('next', str(self.repo)).stdout.startswith('TASK-001'))  # priority beats status
        picks = json.loads(run('next', str(self.repo), '--json').stdout)
        self.assertNotIn('TASK-003', [p['task']['id'] for p in picks])  # GOAL-5 waits for GOAL-4

    def test_executed_pass_promotes_only_when_tasks_done(self):
        run('fmt', str(self.repo))
        self.assertIn('GOAL-1 → unverified', run('evidence', str(self.repo), 'GOAL-1', '--kind', 'executed',
                                                  '--ref', 'flutter test', '--result', 'pass').stdout)
        run('task', str(self.repo), 'TASK-002', 'done')
        self.assertIn('GOAL-1 → met', run('evidence', str(self.repo), 'GOAL-1', '--kind', 'executed',
                                           '--ref', 'flutter test', '--result', 'pass').stdout)
        self.assertEqual(run('validate', str(self.repo)).stdout.strip(), 'ok')
        self.assertIn('GOAL-1 → partial', run('evidence', str(self.repo), 'GOAL-1', '--kind', 'executed',
                                               '--ref', 'flutter test', '--result', 'fail').stdout)

    def test_render_replaces_only_the_marked_block(self):
        run('fmt', str(self.repo))
        (self.repo / 'TODO.md').write_text('# TODO\n\n## Goal coverage\n\nold table\n\n## Now\n\n- [ ] TASK-001\n')
        run('render', str(self.repo)); first = (self.repo / 'TODO.md').read_text()
        self.assertIn('| GOAL-4: Decrement floors at 0 | unmet | — | TASK-001 |', first)
        self.assertIn('## Now\n\n- [ ] TASK-001', first)
        self.assertNotIn('old table', first)
        run('render', str(self.repo)); self.assertEqual(first, (self.repo / 'TODO.md').read_text())

    def test_non_met_goal_without_open_task_is_invalid(self):
        d = sample(); d['tasks'][0]['status'] = 'done'
        (self.repo / 'goals.json').write_text(json.dumps(d))
        self.assertIn('GOAL-4: unmet goal has no open task', run('validate', str(self.repo)).stdout)


if __name__ == '__main__':
    unittest.main()
