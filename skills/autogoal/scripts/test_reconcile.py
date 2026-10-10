"""Read-only reconciliation regressions: never launch workers or messages."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_delivery_state import EvidenceFixture, SCRATCH

spec = importlib.util.spec_from_file_location('reconcile', Path(__file__).with_name('reconcile.py'))
m = importlib.util.module_from_spec(spec) if spec else None
if spec and spec.loader and Path(spec.origin).exists():
    spec.loader.exec_module(m)
else:
    m = None

class ReconcileTests(unittest.TestCase):
    def test_completed_card_supersedes_ready_creation_receipt(self):
        self.assertIsNotNone(m, 'Missing read-only reconciliation helper')
        with tempfile.TemporaryDirectory(dir=SCRATCH) as directory:
            home = Path(directory)
            (home / 'autogoal').mkdir()
            (home / 'autogoal/goal-handoff.json').write_text(json.dumps({'task_id':'t_fixture','status':'ready'}))
            snapshot = {'task':{'id':'t_fixture','assignee':'fixture','status':'done'},'runs':[{'id':5,'profile':'fixture','outcome':'completed','summary':'five controls passed','metadata':{'report':'/evidence/report.md'}}],'events':[{'kind':'completed','created_at':123}]}
            with patch.object(m, 'run', return_value=json.dumps(snapshot)) as cli:
                result = m.reconcile(['hermes','-p','fixture'], home, 'fixture')
            self.assertEqual(result['status'], 'done')
            self.assertEqual(result['summary'], 'five controls passed')
            self.assertEqual(result['run_id'], 5)
            self.assertTrue(result['worker_observed'])
            self.assertEqual(result['run_ownership'], 'current_profile')
            self.assertEqual(result['metadata']['report'], '/evidence/report.md')
            self.assertEqual(cli.call_args.args[1:], ('kanban','--board','default','show','t_fixture','--json'))
            self.assertEqual(json.loads((home/'autogoal/goal-handoff.json').read_text())['status'], 'ready')

    def test_wrong_card_readback_is_rejected(self):
        snapshot = {'task': {'id': 't_other', 'assignee': 'fixture', 'status': 'done'},
                    'runs': [], 'events': []}
        with patch.object(m, 'run', return_value=json.dumps(snapshot)):
            with self.assertRaisesRegex(ValueError, 'task ID'):
                m.reconcile(['hermes', '-p', 'fixture'], Path('.'), 'fixture', 't_fixture')

    def test_unknown_snapshot_shapes_fail_with_schema_error(self):
        valid_task = {'id': 't_fixture', 'assignee': 'fixture', 'status': 'done'}
        cases = [[], None, 'text', {'task': []},
                 {'task': valid_task, 'runs': {}},
                 {'task': valid_task, 'runs': ['not a run']},
                 {'task': valid_task, 'events': {}},
                 {'task': valid_task, 'runs': [{'id': 'not numeric'}]},
                 {'task': {'id': 't_fixture', 'assignee': 'fixture'}}]
        for snapshot in cases:
            with self.subTest(snapshot=snapshot):
                with patch.object(m, 'run', return_value=json.dumps(snapshot)):
                    with self.assertRaisesRegex(ValueError, 'schema'):
                        m.reconcile(['hermes', '-p', 'fixture'], Path('.'), 'fixture', 't_fixture')

    def test_unknown_receipt_shapes_are_rejected_before_cli(self):
        for receipt in ([], None, 'text', {}, {'task_id': 12}, {'task_id': ''}):
            with self.subTest(receipt=receipt), tempfile.TemporaryDirectory(dir=SCRATCH) as directory:
                home = Path(directory)
                (home / 'autogoal').mkdir()
                path = home / 'autogoal/goal-handoff.json'
                original = json.dumps(receipt)
                path.write_text(original)
                with patch.object(m, 'run') as cli:
                    with self.assertRaisesRegex(ValueError, 'receipt schema'):
                        m.reconcile(['hermes', '-p', 'fixture'], home, 'fixture')
                    cli.assert_not_called()
                self.assertEqual(path.read_text(), original)

    def test_explicit_nested_current_handoff_is_read_without_rewriting(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as directory:
            home = Path(directory)
            (home / 'autogoal').mkdir()
            path = home / 'autogoal/goal-handoff.json'
            original = json.dumps({'task_id': None, 'current_handoff': {'task_id': 't_fixture'}})
            path.write_text(original)
            snapshot = {'task': {'id': 't_fixture', 'assignee': 'fixture', 'status': 'ready'},
                        'runs': [], 'events': []}
            with patch.object(m, 'run', return_value=json.dumps(snapshot)):
                result = m.reconcile(['hermes', '-p', 'fixture'], home, 'fixture')
            self.assertEqual(result['task_id'], 't_fixture')
            self.assertFalse(result['worker_observed'])
            self.assertEqual(path.read_text(), original)

    def test_wrong_card_run_is_rejected(self):
        snapshot = {'task': {'id': 't_fixture', 'assignee': 'fixture', 'status': 'ready'},
                    'runs': [{'id': 9, 'task_id': 't_other', 'profile': 'fixture'}]}
        with patch.object(m, 'run', return_value=json.dumps(snapshot)):
            with self.assertRaisesRegex(ValueError, 'run task ID'):
                m.reconcile(['hermes', '-p', 'fixture'], Path('.'), 'fixture', 't_fixture')

    def test_prior_or_unknown_run_owner_is_not_current_worker_evidence(self):
        for owner, ownership in [('previous-owner', 'other_profile'), (None, 'unknown')]:
            with self.subTest(owner=owner):
                record = {'id': 9, 'outcome': 'completed'}
                if owner is not None:
                    record['profile'] = owner
                snapshot = {'task': {'id': 't_fixture', 'assignee': 'fixture', 'status': 'ready'},
                            'runs': [record]}
                with patch.object(m, 'run', return_value=json.dumps(snapshot)):
                    result = m.reconcile(['hermes', '-p', 'fixture'], Path('.'), 'fixture', 't_fixture')
                self.assertFalse(result['worker_observed'])
                self.assertTrue(result['card_run_observed'])
                self.assertEqual(result['run_profile'], owner)
                self.assertEqual(result['run_ownership'], ownership)

    def test_foreign_or_unknown_run_delivery_evidence_is_not_current_profile_delivery(self):
        with EvidenceFixture() as f:
            evidence = f.integrated()
            for owner in ('previous-owner', None, 'fixture'):
                record = {'id': 9, 'metadata': {'delivery_evidence': evidence}}
                if owner is not None:
                    record['profile'] = owner
                snapshot = {'task': {'id': 't_fixture', 'assignee': 'fixture', 'status': 'done'},
                            'runs': [record]}
                with self.subTest(owner=owner), patch.object(m, 'run', return_value=json.dumps(snapshot)):
                    result = m.reconcile(['hermes', '-p', 'fixture'], f.repo, 'fixture', 't_fixture', f.repo)
                    self.assertEqual(result['delivery']['delivered'], owner == 'fixture')
                    self.assertFalse(result['delivery']['milestone_complete'])
                    self.assertEqual(result['task_id'], 't_fixture')
                    self.assertEqual(result['run_id'], 9)
                    self.assertEqual(result['board_id'], 'default')
                    if owner != 'fixture':
                        self.assertEqual(result['delivery']['state'], 'unknown')
                        self.assertNotIn('merged', result['human_report'])

    def test_reviewed_card_remains_unknown_without_structured_delivery_evidence(self):
        snapshot = {'task': {'id': 't_fixture', 'assignee': 'fixture', 'status': 'reviewed'},
                    'runs': [{'id': 7, 'profile': 'fixture', 'outcome': 'completed',
                              'summary': 'reviewed and merged'}]}
        with patch.object(m, 'run', return_value=json.dumps(snapshot)):
            result = m.reconcile(['hermes', '-p', 'fixture'], Path('.'), 'fixture', 't_fixture')
        self.assertEqual(result['delivery']['state'], 'unknown')
        self.assertFalse(result['delivery']['milestone_complete'])
        self.assertNotIn('merged', result['human_report'])
        self.assertEqual(result['board_id'], 'default')

    def test_repeated_cli_reconciliation_suppresses_only_human_report(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory(dir=SCRATCH) as directory, EvidenceFixture() as f:
            home = Path(directory)
            (home/'autogoal').mkdir()
            receipt = home/'autogoal/goal-handoff.json'
            receipt.write_text(json.dumps({'task_id': 't_fixture'}))
            original = receipt.read_text()
            snapshot = {'task': {'id': 't_fixture', 'assignee': 'fixture', 'status': 'done'},
                        'runs': [{'id': 7, 'profile': 'fixture', 'metadata': {
                            'delivery_evidence': {'candidate': f.identity,
                                                  'implementation': {'artifacts': ['a.py']}}}}]}
            outputs = []
            with patch.object(m, 'run', return_value=json.dumps(snapshot)) as cli, \
                 patch.object(m, 'profile_home', return_value=home), \
                 patch('sys.argv', ['reconcile.py', '--profile', 'fixture', '--repo', str(f.repo)]):
                for _ in range(2):
                    buffer = io.StringIO()
                    with contextlib.redirect_stdout(buffer):
                        m.main()
                    outputs.append(json.loads(buffer.getvalue()))
                self.assertEqual(cli.call_count, 2, 'Reporting cache must never skip live readback')
            self.assertEqual(outputs[0]['delivery']['state'], 'implemented')
            self.assertIsNotNone(outputs[0]['human_report'])
            self.assertIsNone(outputs[1]['human_report'])
            self.assertTrue(outputs[1]['selection_required'])
            self.assertNotIn('discovery_required', outputs[1], 'Reconcile cannot decide backlog eligibility')
            self.assertEqual(outputs[0]['task_id'], outputs[1]['task_id'])
            self.assertEqual(outputs[0]['board_id'], outputs[1]['board_id'])
            self.assertEqual(receipt.read_text(), original)

if __name__ == '__main__':
    unittest.main()
