"""Primary milestone regression tests; only temporary fixture ledgers are written."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import goals

SCRIPT = Path(__file__).with_name('goals.py')


def sample():
    return {
        'version': 1,
        'goals': [
            {'id': 'M1', 'title': 'Primary milestone', 'source': 'PRD.md#m1',
             'status': 'unmet', 'priority': 99, 'tasks': ['FOCUS']},
            {'id': 'M2', 'title': 'Other milestone', 'source': 'PRD.md#m2',
             'status': 'partial', 'priority': 1, 'tasks': ['OTHER']},
        ],
        'tasks': [
            {'id': 'FOCUS', 'goal': 'M1', 'title': 'Focused next slice',
             'status': 'open', 'section': 'Next'},
            {'id': 'OTHER', 'goal': 'M2', 'title': 'Unrelated now slice',
             'status': 'open', 'section': 'Now'},
        ],
    }


class MilestoneFocusTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.repo = Path(self.directory.name)
        self.ledger = self.repo / 'goals.json'
        goals.dump(self.repo, sample())

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)

    def test_cli_focus_roundtrip_survives_fmt_and_task_mutations(self):
        result = self.run_cli('focus', str(self.repo), 'M1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.ledger.read_text())['primary_milestone'], 'M1')
        self.assertEqual(self.run_cli('validate', str(self.repo)).stdout.strip(), 'ok')
        self.assertEqual(self.run_cli('fmt', str(self.repo)).returncode, 0)
        first = self.ledger.read_bytes()
        self.assertEqual(self.run_cli('fmt', str(self.repo)).returncode, 0)
        self.assertEqual(first, self.ledger.read_bytes())
        self.assertTrue(self.run_cli('next', str(self.repo)).stdout.startswith('FOCUS'))
        picks = json.loads(self.run_cli('next', str(self.repo), '--json').stdout)
        self.assertEqual([p['task']['id'] for p in picks], ['FOCUS', 'OTHER'])
        self.assertEqual(self.run_cli('task', str(self.repo), 'OTHER', 'in_progress').returncode, 0)
        self.assertEqual(json.loads(self.ledger.read_text())['primary_milestone'], 'M1')

    def test_focus_json_query_is_read_only_before_and_after_setting(self):
        for expected in (None, 'M1'):
            if expected:
                self.assertEqual(self.run_cli('focus', str(self.repo), expected).returncode, 0)
            first = self.ledger.read_bytes()
            result = self.run_cli('focus', str(self.repo), '--json')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), {'primary_milestone': expected})
            self.assertEqual(first, self.ledger.read_bytes())
        self.assertEqual(self.run_cli('focus', str(self.repo), 'M1', '--json').returncode, 2)
        self.assertEqual(self.run_cli('focus', str(self.repo), '--clear', '--json').returncode, 2)
        self.assertEqual(first, self.ledger.read_bytes())

    def test_unknown_cli_focus_is_rejected_without_rewriting_ledger(self):
        first = self.ledger.read_bytes()
        result = self.run_cli('focus', str(self.repo), 'MISSING')
        self.assertEqual(result.returncode, 1)
        self.assertIn('unknown goal MISSING', result.stderr)
        self.assertEqual(first, self.ledger.read_bytes())

    def test_validate_rejects_unknown_or_malformed_focus(self):
        for focus in ('MISSING', '', 7, [], {}):
            with self.subTest(focus=focus):
                data = sample()
                data['primary_milestone'] = focus
                self.assertTrue(any('primary_milestone' in err for err in goals.errors(data)))

    def test_clear_focus_restores_legacy_selection_and_is_idempotent(self):
        self.assertEqual(self.run_cli('focus', str(self.repo), 'M1').returncode, 0)
        result = self.run_cli('focus', str(self.repo), '--clear')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('primary_milestone', json.loads(self.ledger.read_text()))
        self.assertTrue(self.run_cli('next', str(self.repo)).stdout.startswith('OTHER'))
        first = self.ledger.read_bytes()
        self.assertEqual(self.run_cli('focus', str(self.repo), '--clear').returncode, 0)
        self.assertEqual(first, self.ledger.read_bytes())
        self.assertEqual(self.run_cli('focus', str(self.repo)).returncode, 2)
        self.assertEqual(self.run_cli('focus', str(self.repo), 'M1', '--clear').returncode, 2)
        self.assertEqual(first, self.ledger.read_bytes())

    def test_legacy_ledger_keeps_shape_and_section_priority_status_order(self):
        data = goals.normalize(sample())
        self.assertEqual(set(data), {'version', 'goals', 'tasks'})
        self.assertEqual(goals.errors(data), [])
        self.assertEqual(self.picks(copy.deepcopy(data)), ['OTHER', 'FOCUS'])
        data['tasks'][0]['section'] = 'Next'
        self.assertEqual(self.picks(copy.deepcopy(data)), ['OTHER', 'FOCUS'])
        for goal in data['goals']:
            goal['priority'] = 1
        self.assertEqual(self.picks(copy.deepcopy(data)), ['OTHER', 'FOCUS'])
        self.assertNotIn('primary_milestone', json.loads(self.ledger.read_text()))

    def test_focus_respects_task_and_goal_dependencies_before_falling_back(self):
        for kind in ('task', 'goal'):
            with self.subTest(kind=kind):
                data = sample()
                data['primary_milestone'] = 'M1'
                if kind == 'task':
                    data['tasks'][0]['depends_on'] = ['OTHER']
                else:
                    data['goals'][0]['depends_on'] = ['M2']
                self.assertEqual(self.picks(copy.deepcopy(data)), ['OTHER'])
                if kind == 'task':
                    data['tasks'][1]['status'] = 'done'
                else:
                    data['goals'][1]['status'] = 'met'
                    data['goals'][1]['evidence'] = [
                        {'kind': 'executed', 'ref': 'test milestone', 'result': 'pass'}]
                self.assertEqual(self.picks(copy.deepcopy(data)), ['FOCUS'])

    def test_focus_does_not_admit_done_decision_or_met_work(self):
        for reason in ('done', 'decision', 'met'):
            with self.subTest(reason=reason):
                data = sample()
                data['primary_milestone'] = 'M1'
                if reason == 'done':
                    data['tasks'][0]['status'] = 'done'
                elif reason == 'decision':
                    data['tasks'][0]['section'] = 'Needs decision'
                else:
                    data['goals'][0]['status'] = 'met'
                    data['goals'][0]['evidence'] = [
                        {'kind': 'executed', 'ref': 'test milestone', 'result': 'pass'}]
                self.assertEqual(self.picks(data), ['OTHER'])

    def test_all_focused_tasks_precede_all_fallback_tasks(self):
        data = sample()
        data['primary_milestone'] = 'M1'
        data['tasks'].extend([
            {'id': 'FOCUS-NOW', 'goal': 'M1', 'title': 'Focused now',
             'status': 'open', 'section': 'Now'},
            {'id': 'OTHER-NEXT', 'goal': 'M2', 'title': 'Fallback next',
             'status': 'open', 'section': 'Next'},
        ])
        self.assertEqual(self.picks(data), ['FOCUS-NOW', 'FOCUS', 'OTHER', 'OTHER-NEXT'])

    def picks(self, data):
        return [t['id'] for t, _ in goals.eligible(goals.normalize(data))]

    def test_focused_next_beats_unrelated_now_without_changing_priorities(self):
        data = sample()
        data['primary_milestone'] = 'M1'
        self.assertEqual(self.picks(data), ['FOCUS', 'OTHER'])
        self.assertEqual({g['id']: g['priority'] for g in data['goals']}, {'M1': 99, 'M2': 1})


if __name__ == '__main__':
    unittest.main()
