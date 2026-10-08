"""Composed picker/dispatch/worker/reconcile fixture, not a native worker run."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import start_goal
import source_freshness
import reconcile
import check_receipt

ROOT = Path(__file__).resolve().parents[2]


class PipelineTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='pipeline-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.home = self.root / 'home'
        self.home.mkdir()
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        ledger = {'version': 1, 'goals': [{'id': 'G', 'title': 'Fixture output',
                  'source': 'README.md', 'status': 'unmet', 'tasks': ['T'], 'priority': 1}],
                  'tasks': [{'id': 'T', 'goal': 'G', 'title': 'Create artifact',
                             'status': 'open', 'section': 'Now'}]}
        (self.repo / 'goals.json').write_text(json.dumps(ledger))
        result = subprocess.run([sys.executable, str(ROOT / 'repo-docs/scripts/goals.py'),
                                 'next', str(self.repo), '--json'], check=True,
                                capture_output=True, text=True, timeout=30)
        self.selected = json.loads(result.stdout)[0]['task']
        self.assertEqual(self.selected['id'], 'T')
        self.contract = self.root / 'contract.txt'
        self.contract.write_text(''.join(f'{key}: fixture {key}\n' for key in start_goal.CONTRACT_FIELDS))
        self.snapshot = self.root / 'snapshot.json'
        self.snapshot.write_text(json.dumps(source_freshness.capture(self.repo, ['goals.json'])))
        self.db = self.root / 'board.db'
        with sqlite3.connect(self.db) as db:
            db.execute('CREATE TABLE tasks (id TEXT, goal_mode INTEGER, goal_max_turns INTEGER)')
        self.tasks, self.runs, self.created = [], [], 0

    def cli(self, prefix, *args):
        if args == ('config', 'get', 'terminal.cwd'):
            return str(self.repo)
        if args == ('profile', 'show', 'fixture'):
            return f'Path: {self.home}'
        if args == ('kanban', 'boards', 'list', '--json'):
            return json.dumps([{'slug': 'default', 'db_path': str(self.db)}])
        self.assertEqual(args[:3], ('kanban', '--board', 'default'))
        if args[3] == 'list':
            return json.dumps(self.tasks)
        if args[3] == 'create':
            self.created += 1
            self.assertEqual(args[args.index('--max-retries') + 1], '3')
            self.assertEqual(args[args.index('--goal-max-turns') + 1], '50')
            self.assertEqual(args[args.index('--completion-contract') + 1], 'local-only')
            task = {'id': 't_fixture', 'title': self.selected['title'], 'assignee': 'fixture',
                    'workspace_kind': 'dir', 'workspace_path': str(self.repo),
                    'completion_contract': 'local-only', 'status': 'ready'}
            self.tasks.append(task)
            with sqlite3.connect(self.db) as db:
                db.execute('INSERT INTO tasks VALUES (?, ?, ?)', ('t_fixture', 1, 50))
            return json.dumps(task)
        if args[3] == 'show':
            self.assertEqual(args[4], 't_fixture')
            return json.dumps({'task': self.tasks[0], 'runs': self.runs})
        raise AssertionError(args)

    def dispatch(self):
        argv = ['start_goal.py', '--profile', 'fixture', '--workspace', str(self.repo),
                '--title', self.selected['title'], '--contract-file', str(self.contract),
                '--source-snapshot', str(self.snapshot)]
        with patch.object(start_goal, 'run', side_effect=self.cli), \
                patch.object(sys, 'argv', argv), patch.dict(os.environ, {}, clear=True), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            start_goal.main()
        return json.loads(output.getvalue())

    def test_selected_task_executes_and_fixture_review_acknowledges_exact_candidate(self):
        first = self.dispatch()
        self.assertEqual(first['outcome'], 'handed_off')
        self.assertEqual(self.dispatch()['outcome'], 'already_owned')
        self.assertEqual(self.created, 1)
        artifact = self.repo / 'artifact.txt'
        # Explicit fixture worker: a real bounded subprocess, no LLM or native scheduler.
        subprocess.run([sys.executable, '-c',
                        'from pathlib import Path; Path("artifact.txt").write_text("portable\\n")'],
                       cwd=self.repo, check=True, timeout=30)
        command = [sys.executable, '-c',
                   'from pathlib import Path; assert Path("artifact.txt").read_text() == "portable\\n"']
        (self.repo / 'dependencies.lock').write_text('fixture uses Python stdlib only\n')
        (self.repo / 'environment.json').write_text(json.dumps({'backend': 'fixture', 'python': sys.version}))
        checked = check_receipt.execute(self.repo, ['artifact.txt', 'dependencies.lock', 'environment.json'], command, 30)
        self.assertTrue(check_receipt.reusable(checked, self.repo, command))
        receipt = {'task': self.selected['id'], 'candidate_sha256': hashlib.sha256(artifact.read_bytes()).hexdigest(),
                   'check': checked, 'boundary': 'fixture review only'}
        # The fake review sink acknowledges precisely this candidate and receipt.
        self.tasks[0]['status'] = 'review'
        self.runs.append({'id': 1, 'task_id': 't_fixture', 'profile': 'fixture',
                          'outcome': 'review', 'metadata': {'review_ack': receipt}})
        with patch.object(reconcile, 'run', side_effect=self.cli):
            observed = reconcile.reconcile(['hermes', '-p', 'fixture'], self.home, 'fixture')
        self.assertTrue(observed['worker_observed'])
        self.assertEqual(observed['status'], 'review')
        self.assertEqual(observed['metadata']['review_ack'], receipt)
        self.assertEqual(self.dispatch()['outcome'], 'already_owned')
        self.assertEqual(self.created, 1)

    def test_source_drift_refuses_new_dispatch(self):
        (self.repo / 'goals.json').write_text('{}')
        with self.assertRaisesRegex(SystemExit, 'Source changed'):
            self.dispatch()
        self.assertEqual(self.created, 0)
        self.assertEqual(self.tasks, [])

    def test_timeout_preserves_original_card_for_reconciliation(self):
        self.dispatch()
        original = (self.home / 'autogoal/goal-handoff.json').read_bytes()
        with patch.object(reconcile, 'run', side_effect=subprocess.TimeoutExpired(['hermes'], 30)):
            with self.assertRaises(subprocess.TimeoutExpired):
                reconcile.reconcile(['hermes'], self.home, 'fixture')
        self.assertEqual((self.home / 'autogoal/goal-handoff.json').read_bytes(), original)
        self.assertEqual(self.dispatch()['outcome'], 'already_owned')
        self.assertEqual(self.created, 1)


if __name__ == '__main__':
    unittest.main()
