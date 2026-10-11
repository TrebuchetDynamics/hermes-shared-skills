"""Read-only consumer checks and clerical repair, using real isolated Git ledgers."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('goals.py')


class HandoffReconciliationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        self.plan = self.repo / 'SPEC.md'
        self.plan.write_text('# Slice\n\nStatus: Accepted (implementation only)\n\n'
                             'Approval evidence: fixture owner approved this slice.\n')
        self.todo = self.repo / 'TODO.md'
        self.body = ('# TODO\n\n## Now\n\n- [ ] T1: Verify startup\n'
                     '  Goal: G1\n  Scope: startup check\n'
                     '  Acceptance: startup check passes\n  Dependencies: None\n'
                     '  Ownership: fixture owner\n  Sources: [Slice](SPEC.md#slice)\n')
        self.todo.write_text(self.body)
        (self.repo / 'goals.json').write_text(json.dumps({
            'version': 1,
            'goals': [{'id': 'G1', 'title': 'Startup works', 'source': 'SPEC.md#slice',
                       'status': 'unmet', 'priority': 1, 'tasks': ['T1']}],
            'tasks': [{'id': 'T1', 'goal': 'G1', 'title': 'Verify startup',
                       'status': 'open', 'section': 'Now'}]}))
        subprocess.run([sys.executable, str(SCRIPT), 'fmt', str(self.repo)],
                       check=True, capture_output=True)

    def check(self):
        before = {p.name: p.read_bytes() for p in self.repo.iterdir() if p.is_file()}
        result = subprocess.run([sys.executable, str(SCRIPT), 'backlog-check',
                                 str(self.repo), '--plan', 'SPEC.md#slice', '--tasks', 'T1'],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.repo.iterdir() if p.is_file()})
        return result.returncode, json.loads(result.stdout)

    def test_missing_status_does_not_hide_missing_task_contract(self):
        self.todo.write_text('# TODO\n\n## Now\n')
        code, receipt = self.check()
        self.assertEqual(code, 1)
        self.assertEqual(receipt['state'], 'draft_saved')
        self.assertIn('plan section lacks explicit Status: Accepted', receipt['reasons'])
        self.assertIn('T1: missing or duplicate task body', receipt['reasons'])

    def test_clerical_repair_makes_same_slice_ready_without_claiming_it(self):
        self.assertEqual(self.check()[0], 1)
        ledger = (self.repo / 'goals.json').read_bytes()
        self.plan.write_text(self.plan.read_text().replace(
            'Status: Accepted (implementation only)', 'Status: Accepted\n\nScope: implementation only'))
        code, receipt = self.check()
        self.assertEqual((code, receipt['state']), (0, 'ready_for_autogoal'))
        self.assertEqual(receipt['eligible_task_ids'], ['T1'])
        self.assertEqual(ledger, (self.repo / 'goals.json').read_bytes())
        self.assertEqual(receipt, self.check()[1])

    def test_proposed_plan_stays_draft_even_with_complete_eligible_backlog(self):
        self.plan.write_text('# Slice\n\nStatus: Proposed\n')
        code, receipt = self.check()
        self.assertEqual((code, receipt['state']), (1, 'draft_saved'))
        self.assertIn('plan section lacks explicit Status: Accepted', receipt['reasons'])

    def test_invalid_ledger_is_reported_alongside_missing_status(self):
        (self.repo / 'goals.json').write_text('{bad json')
        code, receipt = self.check()
        self.assertEqual(code, 1)
        self.assertTrue(any(reason.startswith('invalid backlog:') for reason in receipt['reasons']))


if __name__ == '__main__':
    unittest.main()
