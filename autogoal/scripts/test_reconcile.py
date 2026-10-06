"""Read-only reconciliation regressions: never launch workers or messages."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('reconcile', Path(__file__).with_name('reconcile.py'))
m = importlib.util.module_from_spec(spec) if spec else None
if spec and spec.loader and Path(spec.origin).exists():
    spec.loader.exec_module(m)
else:
    m = None

class ReconcileTests(unittest.TestCase):
    def test_completed_card_supersedes_ready_creation_receipt(self):
        self.assertIsNotNone(m, 'Missing read-only reconciliation helper')
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / 'autogoal').mkdir()
            (home / 'autogoal/goal-handoff.json').write_text(json.dumps({'task_id':'t_fixture','status':'ready'}))
            snapshot = {'task':{'id':'t_fixture','assignee':'fixture','status':'done'},'runs':[{'id':5,'outcome':'completed','summary':'five controls passed','metadata':{'report':'/evidence/report.md'}}],'events':[{'kind':'completed','created_at':123}]}
            with patch.object(m, 'run', return_value=json.dumps(snapshot)) as cli:
                result = m.reconcile(['hermes','-p','fixture'], home, 'fixture')
            self.assertEqual(result['status'], 'done')
            self.assertEqual(result['summary'], 'five controls passed')
            self.assertEqual(result['run_id'], 5)
            self.assertEqual(result['metadata']['report'], '/evidence/report.md')
            self.assertEqual(cli.call_args.args[1:], ('kanban','--board','default','show','t_fixture','--json'))
            self.assertEqual(json.loads((home/'autogoal/goal-handoff.json').read_text())['status'], 'ready')

if __name__ == '__main__':
    unittest.main()
