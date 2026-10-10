"""Offline fixture ledgers; external CLI mocks are not native-run evidence."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('admission_start', Path(__file__).with_name('start_goal.py'))
assert spec is not None and spec.loader is not None
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
fspec = importlib.util.spec_from_file_location('fresh', Path(__file__).with_name('source_freshness.py'))
assert fspec is not None and fspec.loader is not None
fresh = importlib.util.module_from_spec(fspec)
fspec.loader.exec_module(fresh)


class AdmissionFixtures(unittest.TestCase):
    def setUp(self):
        (Path.home() / '.hermes/cache/scratch').mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=Path.home() / '.hermes/cache/scratch')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ledger = {'version': 1, 'primary_milestone': 'G1', 'goals': [
            {'id': g, 'title': g, 'source': 'spec.md', 'status': 'unmet', 'tasks': [], 'depends_on': [], 'priority': 1}
            for g in ['G1', 'G2']], 'tasks': [
            {'id': t, 'title': t, 'goal': g, 'status': 'open', 'section': 'Next', 'depends_on': deps}
            for t, g, deps in [('T1', 'G1', []), ('T2', 'G1', []), ('T3', 'G1', ['T1']), ('T4', 'G2', [])]]}
        self.write_ledger()
        (self.root / 'spec.md').write_text('fixture source')
        self.snapshot = self.root / 'snapshot.json'
        self.snapshot.write_text(json.dumps(fresh.capture(self.root, ['goals.json', 'spec.md'])))
        self.contract = self.root / 'contract.txt'
        self.contract.write_text(''.join(f'{k}: fixture {k}\n' for k in m.CONTRACT_FIELDS))

    def write_ledger(self):
        (self.root / 'goals.json').write_text(json.dumps(self.ledger))

    def invoke(self, *extra):
        argv = ['start_goal.py', '--profile', 'fixture', '--workspace', str(self.root), '--title', 'Fixture',
                '--contract-file', str(self.contract), '--source-snapshot', str(self.snapshot), '--validate-only', *extra]
        output = io.StringIO()
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        with patch('sys.argv', argv), patch.dict(m.os.environ, {}, clear=True), patch.object(m, 'run') as cli, contextlib.redirect_stdout(output):
            m.main()
            cli.assert_not_called()
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})
        return json.loads(output.getvalue())

    def dispatch(self, *extra, mutate=None, live=False, created_at: str | int="2026-10-08T16:00:00Z", create_existing=False, during_assembly=None):
        import sqlite3
        import subprocess
        subprocess.run(['git', '-C', str(self.root), 'init', '-q'], check=True)
        subprocess.run(['git', '-C', str(self.root), 'add', 'goals.json', 'spec.md'], check=True)
        subprocess.run(['git', '-C', str(self.root), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@local',
                        'commit', '--allow-empty', '-qm', 'fixture admission source'], check=True)
        base = subprocess.check_output(['git', '-C', str(self.root), 'rev-parse', 'HEAD'], text=True).strip()
        pass_temp = tempfile.TemporaryDirectory(dir=Path.home() / '.hermes/cache/scratch')
        self.addCleanup(pass_temp.cleanup)
        home = self.root / 'home'
        home.mkdir(exist_ok=True)
        db_path = self.root / 'fixture-board.db'
        with sqlite3.connect(db_path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS tasks (id TEXT, goal_mode INTEGER, goal_max_turns INTEGER)')
            db.execute('INSERT INTO tasks VALUES (?, ?, ?)', ('fixture_card', 1, 50))
        task = {'id': 'fixture_card', 'assignee': 'fixture', 'title': 'Fixture', 'status': 'ready',
                'workspace_kind': 'dir', 'workspace_path': str(self.root), 'completion_contract': 'local-only',
                'board_id': 'fixture_board', 'created_at': created_at}
        self.creates = 0
        def cli(prefix, *args):
            if args == ('config', 'get', 'terminal.cwd'): return str(self.root)
            if args == ('profile', 'show', 'fixture'): return 'Path: ' + str(home)
            if args == ('kanban', 'boards', 'list', '--json'):
                if mutate: mutate()
                return json.dumps([{'slug': 'default', 'id': 'fixture_board', 'db_path': str(db_path)}])
            if args[3] == 'list': return json.dumps([task] if live else [])
            if args[3] == 'show': return json.dumps({'task': task})
            if args[3] == 'create':
                self.creates += 1
                if not create_existing:
                    task['workspace_path'] = args[args.index('--workspace') + 1].removeprefix('dir:')
                self.created_body = args[args.index('--body') + 1]
                return json.dumps(task)
            raise AssertionError(args)
        argv = ['start_goal.py', '--profile', 'fixture', '--workspace', str(self.root), '--title', 'Fixture',
                '--contract-file', str(self.contract), '--source-snapshot', str(self.snapshot),
                '--base', base, '--pass-root', pass_temp.name, *extra]
        actual_run = subprocess.run
        def local_git(*args, **kwargs):
            result = actual_run(*args, **kwargs)
            if during_assembly and 'worktree' in args[0] and 'add' in args[0]:
                during_assembly()
            return result
        with patch('sys.argv', argv), patch.dict(m.os.environ, {}, clear=True), patch.object(m, 'run', side_effect=cli), \
                patch.object(subprocess, 'run', side_effect=local_git), contextlib.redirect_stdout(io.StringIO()) as output:
            m.main()
        return json.loads(output.getvalue())

    def test_source_retraction_during_assembly_refuses_before_native_create(self):
        def retract():
            (self.root / 'spec.md').write_text('finding retracted by owner')
        with self.assertRaisesRegex(SystemExit, 'Source changed'):
            self.dispatch('--goal-task', 'T1', during_assembly=retract)
        self.assertEqual(self.creates, 0)
        self.assertEqual((self.root / 'spec.md').read_text(), 'finding retracted by owner')

    def test_legacy_new_shared_checkout_dispatch_has_explicit_migration_refusal(self):
        with self.assertRaisesRegex(SystemExit, 'require --base'):
            self.dispatch('--goal-task', 'T1', '--base', '')
        self.assertEqual(self.creates, 0)

    def test_snapshot_replacement_during_native_lookup_is_not_silent_refresh(self):
        def mutate():
            self.snapshot.write_text(self.snapshot.read_text() + '\n')
        with self.assertRaisesRegex(SystemExit, 'snapshot changed'):
            self.dispatch('--goal-task', 'T1', mutate=mutate)
        self.assertEqual(self.creates, 0)

    def test_concurrent_native_create_preserves_original_card_and_legacy_workspace(self):
        journal = self.root / 'home/autogoal'
        journal.mkdir(parents=True)
        original = b'{"task_id":"fixture_card","note":"original receipt"}\n'
        (journal / 'goal-handoff.json').write_bytes(original)
        result = self.dispatch('--goal-task', 'T1', create_existing=True)
        self.assertEqual(result['outcome'], 'already_owned')
        self.assertEqual(result['task_id'], 'fixture_card')
        self.assertEqual((journal / 'goal-handoff.json').read_bytes(), original)
        self.assertEqual(result['goal_max_turns'], 50)

    def test_new_native_card_uses_actual_isolated_workspace_and_guard(self):
        result = self.dispatch('--goal-task', 'T1')
        self.assertNotEqual(result['workspace'], str(self.root), 'New native cards cannot write shared checkout')
        workspace = Path(result['workspace'])
        self.assertTrue((workspace / '.git').is_file())
        self.assertEqual((workspace / 'spec.md').read_text(), 'fixture source')
        self.assertEqual(result['source_workspace'], str(self.root))
        self.assertEqual(result['pass_manifest']['ledger_sha256'], result['ledger_sha256'])
        self.assertIn('pass_workspace.py', self.created_body)
        self.assertIn('--manifest', self.created_body)

    def test_live_card_reconciles_before_admission_and_never_creates_escape(self):
        result = self.dispatch(live=True)
        self.assertEqual(result['outcome'], 'already_owned')
        self.assertEqual(self.creates, 0)

    def test_real_create_path_enforces_focus_and_receipt_identity(self):
        with self.assertRaisesRegex(SystemExit, '--goal-task'):
            self.dispatch()
        self.assertEqual(self.creates, 0)
        result = self.dispatch('--goal-task', 'T1')
        self.assertEqual(result['goal_task'], 'T1')
        self.assertEqual(result['milestone'], 'G1')
        self.assertEqual(result['board_id'], 'fixture_board')
        self.assertEqual(result['created_at'], '2026-10-08T16:00:00Z')
        self.assertIsNone(result['fallback'])

    def test_native_epoch_creation_time_becomes_utc(self):
        result = self.dispatch('--goal-task', 'T1', created_at=1791475200)
        from datetime import datetime, timezone
        self.assertEqual(result['created_at'], datetime.fromtimestamp(1791475200, timezone.utc).isoformat().replace('+00:00', 'Z'))

    def test_focus_evidence_must_include_fresh_ledger(self):
        self.snapshot.write_text(json.dumps(fresh.capture(self.root, ['spec.md'])))
        with self.assertRaisesRegex(SystemExit, 'ledger'):
            self.invoke('--goal-task', 'T1')
        self.snapshot.write_text(json.dumps(fresh.capture(self.root, ['goals.json', 'spec.md'])))
        self.ledger['tasks'][0]['depends_on'] = ['T2']
        self.write_ledger()
        with self.assertRaisesRegex(SystemExit, 'Source changed'):
            self.invoke('--goal-task', 'T1')

    def test_final_focus_dependency_race_is_refused_without_create(self):
        def mutate():
            self.ledger['primary_milestone'] = 'G2'
            self.ledger['tasks'][0]['depends_on'] = ['T2']
            self.write_ledger()
        with self.assertRaisesRegex(SystemExit, 'Source changed'):
            self.dispatch('--goal-task', 'T1', mutate=mutate)
        self.assertEqual(self.creates, 0)

    def test_explicit_reprioritization_is_structured_and_bound(self):
        value = self.fallback()
        value.pop('reasons')
        value['reprioritization'] = {'actor': 'fixture owner', 'reason': 'fixture priority decision', 'evidence_ref': 'fixture:decision'}
        fallback = self.root / 'fallback.json'
        fallback.write_text(json.dumps(value))
        result = self.invoke('--goal-task', 'T4', '--fallback-file', str(fallback))
        self.assertEqual(result['admission']['fallback'], value)
        value['reprioritization'].pop('actor')
        fallback.write_text(json.dumps(value))
        with self.assertRaises(SystemExit):
            self.invoke('--goal-task', 'T4', '--fallback-file', str(fallback))

    def test_focus_requires_explicit_task_even_validate_only(self):
        with self.assertRaisesRegex(SystemExit, '--goal-task'):
            self.invoke()

    def fallback(self):
        return {'version': 1, 'workspace': str(self.root), 'primary_milestone': 'G1', 'goal_task': 'T4',
                'ledger_sha256': m.hashlib.sha256((self.root / 'goals.json').read_bytes()).hexdigest(),
                'source_snapshot_sha256': m.hashlib.sha256(self.snapshot.read_bytes()).hexdigest(),
                'reasons': [{'task_id': t, 'kind': 'ownership', 'reason': 'fixture owner holds slice',
                             'evidence_ref': 'fixture:owner-readback'} for t in ['T1', 'T2']]}

    def test_fallback_dispatch_records_complete_attestation(self):
        value = self.fallback()
        value['reasons'][0]['kind'] = 'authority'
        value['reasons'][1]['kind'] = 'environment'
        fallback = self.root / 'fallback.json'
        fallback.write_text(json.dumps(value))
        result = self.dispatch('--goal-task', 'T4', '--fallback-file', str(fallback))
        saved = json.loads((self.root / 'home/autogoal/goal-handoff.json').read_text())
        self.assertEqual(result['fallback'], value)
        self.assertEqual(saved, result)
        self.assertEqual(result['goal_task'], 'T4')
        self.assertEqual(result['milestone'], 'G1')
        self.assertEqual(result['fallback_validation'], 'caller_attestation_not_truth_verified')

    def test_complete_fallback_is_explicit_caller_attestation(self):
        fallback = self.root / 'fallback.json'
        fallback.write_text(json.dumps(self.fallback()))
        result = self.invoke('--goal-task', 'T4', '--fallback-file', str(fallback))
        self.assertEqual(result['admission']['fallback']['reasons'], self.fallback()['reasons'])
        self.assertEqual(result['admission']['fallback_validation'], 'caller_attestation_not_truth_verified')
        for invalid in ['arbitrary prose', {**self.fallback(), 'reasons': self.fallback()['reasons'][:1]},
                        {**self.fallback(), 'workspace': '/wrong'}, {**self.fallback(), 'ledger_sha256': '0' * 64}]:
            with self.subTest(invalid=invalid), self.assertRaises(SystemExit):
                fallback.write_text(invalid if isinstance(invalid, str) else json.dumps(invalid))
                self.invoke('--goal-task', 'T4', '--fallback-file', str(fallback))

    def test_unrelated_dispatch_requires_structured_fallback(self):
        with self.assertRaisesRegex(SystemExit, 'fallback'):
            self.invoke('--goal-task', 'T4')

    def test_explicit_identity_requires_dependency_ready_eligible_task(self):
        result = self.invoke('--goal-task', 'T1')
        self.assertEqual(result['admission']['goal_task'], 'T1')
        self.assertEqual(result['admission']['milestone'], 'G1')
        for task in ['MISSING', 'T3']:
            with self.subTest(task=task), self.assertRaisesRegex(SystemExit, 'eligible'):
                self.invoke('--goal-task', task)


if __name__ == '__main__':
    unittest.main()
