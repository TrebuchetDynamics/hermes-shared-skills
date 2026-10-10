"""Offline CLI-boundary regressions; no real cards/messages are created."""
import importlib.util
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('start_goal', Path(__file__).with_name('start_goal.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class HandoffTests(unittest.TestCase):
    def test_progress_contract_requires_concrete_fields(self):
        validator = getattr(m, 'validate_contract', None)
        self.assertTrue(callable(validator), 'Handoff needs a structured contract preflight')
        with self.assertRaisesRegex(ValueError, 'Project payoff'):
            validator('Objective: Fix cancellation\nScope: src/client.py\nVerification: focused test\nSource: accepted issue\n')
        text = ('Objective: Fix cancellation\nScope: src/client.py and tests/test_client.py\n'
                'Verification: pytest tests/test_client.py, confirm failure before fix\n'
                'Source: accepted lifecycle contract\nProject payoff: prevent requests surviving owner disposal\n'
                'Current evidence: src/client.py:31 misses cancellation on disposal\n'
                'Expected change: cancel owned request and retain lifecycle regression\n'
                'Acceptance: disposal cancels one request; normal completion unchanged\n'
                'Stop conditions: complete after passing focused regression, or block on conflicting ownership\n'
                'Repo-docs pass: Maintain; lifecycle contract and TODO checked against src/client.py; no doc drift\n')
        self.assertEqual(validator(text)['Expected change'], 'cancel owned request and retain lifecycle regression')
    def test_invalid_contract_stops_before_any_cli_call(self):
        with tempfile.TemporaryDirectory() as directory:
            contract = Path(directory) / 'contract.txt'
            contract.write_text('Objective: another generic audit\n')
            argv = ['start_goal.py', '--profile', 'fixture', '--workspace', directory,
                    '--title', 'Unspecified task', '--contract-file', str(contract)]
            with patch('sys.argv', argv), patch.dict(m.os.environ, {}, clear=True), \
                    patch.object(m, 'run', return_value=directory) as cli:
                with self.assertRaisesRegex(SystemExit, 'Missing or empty contract field: Scope'):
                    m.main()
                cli.assert_not_called()

    def test_new_handoff_requires_repo_docs_pass_record(self):
        text = ''.join(f'{key}: concrete {key}\n' for key in m.CONTRACT_FIELDS
                       if key != 'Repo-docs pass')
        with self.assertRaisesRegex(ValueError, 'Missing or empty contract field: Repo-docs pass'):
            m.validate_contract(text)
        recorded = text + 'Repo-docs pass: Maintain; README and TODO checked against src/client.py; profile-local journal receipt\n'
        self.assertIn('Maintain', m.validate_contract(recorded)['Repo-docs pass'])

    def test_dispatch_requires_unchanged_source_snapshot(self):
        preflight=getattr(m,'require_fresh_sources',None)
        self.assertTrue(callable(preflight),'Dispatch needs source-freshness preflight')
        with tempfile.TemporaryDirectory() as directory:
            r=Path(directory)
            with self.assertRaisesRegex(ValueError,'Source snapshot required'):
                preflight(None,r)
            source=r/'client.py';source.write_text('pending fix\n')
            digest=m.hashlib.sha256(source.read_bytes()).hexdigest()
            snapshot=r/'snapshot.json';snapshot.write_text(json.dumps({'version':1,'workspace':str(r.resolve()),'files':[{'path':'client.py','sha256':digest}]}))
            self.assertTrue(preflight(snapshot,r)['fresh'])
            source.write_text('completed by another owner\n')
            with self.assertRaisesRegex(ValueError,'Source changed since selection'):
                preflight(snapshot,r)

    def test_main_stale_snapshot_never_creates_card(self):
        with tempfile.TemporaryDirectory() as directory:
            r=Path(directory);source=r/'client.py';source.write_text('pending\n')
            snapshot=r/'snapshot.json';snapshot.write_text(json.dumps({'version':1,'workspace':str(r.resolve()),'files':[{'path':'client.py','sha256':m.hashlib.sha256(source.read_bytes()).hexdigest()}]}))
            source.write_text('already repaired\n')
            contract=r/'contract.txt';contract.write_text(''.join(f'{key}: concrete {key}\n' for key in m.CONTRACT_FIELDS))
            argv=['start_goal.py','--profile','fixture','--workspace',directory,'--title','Repair','--contract-file',str(contract),'--source-snapshot',str(snapshot)]
            def cli(prefix,*args):
                if args[:3]==('config','get','terminal.cwd'):return directory
                if args[:2]==('profile','show'):return 'Path: '+directory
                if 'list' in args:return '[]'
                raise AssertionError('Unexpected CLI mutation: '+repr(args))
            with patch('sys.argv',argv),patch.dict(m.os.environ,{},clear=True),patch.object(m,'run',side_effect=cli) as calls:
                with self.assertRaisesRegex(SystemExit,'Source changed since selection'):m.main()
                self.assertFalse(any('create' in call.args for call in calls.call_args_list))

    def test_duplicate_field_is_not_silently_overwritten(self):
        text = ''.join(f'{key}: concrete {key}\n' for key in m.CONTRACT_FIELDS)
        with self.assertRaisesRegex(ValueError, 'Duplicate contract field: Scope'):
            m.validate_contract(text + 'Scope: expanded beyond original boundaries\n')

    def test_empty_fields_and_inline_labels_do_not_pass(self):
        text = ''.join(f'{key}: concrete {key}\n' for key in m.CONTRACT_FIELDS)
        with self.assertRaisesRegex(ValueError, 'Missing or empty contract field: Acceptance'):
            m.validate_contract(text.replace('Acceptance: concrete Acceptance', 'Acceptance:'))
        with self.assertRaisesRegex(ValueError, 'Missing or empty contract field: Acceptance'):
            m.validate_contract(text.replace('Acceptance: concrete Acceptance', 'A paragraph mentions Acceptance: without a field'))

    def test_worker_body_makes_completion_evidence_explicit(self):
        builder = getattr(m, 'build_task_body', None)
        self.assertTrue(callable(builder), 'Native goal judge needs an evidence-bearing completion contract')
        text = ''.join(f'{key}: concrete {key}\n' for key in m.CONTRACT_FIELDS)
        body = builder(text)
        self.assertIn('Before calling kanban_complete', body)
        self.assertIn('Acceptance evidence:', body)
        self.assertIn('NOT_CHECKED', body)
        self.assertIn('50-turn budget', body)
        self.assertTrue(body.startswith(m.REVIEW_DOD + '\n\n' + text))
        self.assertIn('NOT part of this goal', body)

    def test_worker_owns_debug_fix_test_review_without_intermediate_cards(self):
        body = m.build_task_body('Objective: implement scoped repair\n', 100)
        self.assertIn('Own debugging, fixes, focused tests and review handoff on this card', body)
        self.assertIn('5 consecutive attempts without new evidence', body)
        self.assertIn('Stop at acceptance; do not burn unused turns', body)
        self.assertIn('One native review lane', body)
        self.assertIn('100-turn budget', body)

    def test_worker_checks_changed_dependency_delivery_boundary(self):
        body = m.build_task_body('Objective: add shared CLI error serializer\n')
        self.assertIn('Trace changed imports to their runtime delivery boundary', body)
        self.assertIn('checkout tests do not prove packaged execution', body)
        self.assertIn('image build/run/deployment NOT_CHECKED', body)
        self.assertIn('explicit scope excludes packaging edits', body)

    def test_review_handoff_is_not_circular_completion_requirement(self):
        body = m.build_task_body('Objective: implement scoped repair\n')
        self.assertIn('Review handoff finishes this worker card, not the product milestone', body)
        self.assertIn('pending review is not a missing implementation criterion', body)
        self.assertIn('never invent approval', body)
        self.assertIn('preserve exact receipts and original card', body)
        self.assertIn('Only the authorized review lane can approve closure', body)

    def test_circular_entry_retries_once_without_waiving_review(self):
        body = m.build_task_body('Objective: implement scoped repair\n')
        self.assertIn('one corrected review request', body)
        self.assertIn('citing the card Definition of done', body)
        self.assertNotIn('administrative review-entry assessment', body)
        self.assertNotIn('stop for operator resolution', body)
        self.assertIn('never invent approval, force a live claim, replace the card, waive review', body)
        self.assertIn('preserve exact receipts and original card', body)

    def test_validate_only_is_real_preflight_without_cli_or_journal_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            contract = Path(directory) / 'contract.txt'
            contract.write_text(''.join(f'{key}: concrete {key}\n' for key in m.CONTRACT_FIELDS))
            argv = ['start_goal.py', '--profile', 'fixture', '--workspace', directory,
                    '--title', 'Fixture', '--contract-file', str(contract), '--validate-only']
            output = io.StringIO()
            with patch('sys.argv', argv), patch.dict(m.os.environ, {}, clear=True), \
                    patch.object(m, 'run') as cli, contextlib.redirect_stdout(output):
                try:
                    m.main()
                except SystemExit as error:
                    self.fail(f'Validation-only unexpectedly exited: {error}')
                cli.assert_not_called()
            self.assertEqual(json.loads(output.getvalue())['outcome'], 'contract_validated')
            self.assertFalse(json.loads(output.getvalue())['factual_validation'])
            self.assertEqual(list(Path(directory).iterdir()), [contract])

    def test_subscribes_and_reads_back_passive_profile_route(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / '.env').write_text('TELEGRAM_HOME_CHANNEL=12345\n')
            subscriptions = []
            def cli(prefix, *args):
                if 'notify-subscribe' in args:
                    subscriptions.append({'task_id': 't_fixture', 'platform': 'telegram', 'chat_id': '12345', 'notifier_profile': 'fixture', 'delivery_mode': 'notify'})
                    return 'Subscribed'
                if 'notify-list' in args:
                    return json.dumps(subscriptions)
                raise AssertionError(args)
            with patch.object(m, 'run', side_effect=cli):
                result = m.ensure_notification(['hermes', '-p', 'fixture'], 't_fixture', home, 'fixture')
            self.assertEqual(result['delivery_mode'], 'notify')
            self.assertEqual(result['notifier_profile'], 'fixture')

    def test_no_home_preserves_local_only(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(m, 'run') as cli:
            self.assertIsNone(m.ensure_notification(['hermes'], 't_fixture', Path(directory), 'default'))
            cli.assert_not_called()

    def test_notification_readback_failure_is_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / '.env').write_text('TELEGRAM_HOME_CHANNEL=12345\n')
            with patch.object(m, 'run', side_effect=['Subscribed', '[]']):
                with self.assertRaisesRegex(RuntimeError, 'notification subscription was not verified'):
                    m.ensure_notification(['hermes'], 't_fixture', home, 'fixture')

    def test_blocked_same_title_survives_contract_wording_changes(self):
        task = {'id': 't_blocked', 'assignee': 'fixture', 'status': 'blocked', 'title': 'Selected slice'}
        self.assertEqual(m.existing_task([task], 'fixture', 'Selected slice'), task)
        self.assertIsNone(m.existing_task([task], 'fixture', 'Disjoint slice'))

    def test_profile_home_uses_cli_path_not_launch_home(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(m, 'run', return_value='Profile: fixture\nPath:    ' + directory + '\n'):
                self.assertEqual(m.profile_home(['hermes', '-p', 'fixture']), Path(directory).resolve())

    def test_receipt_survives_notification_failure_preserves_previous(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = Path(directory)
            previous = {'task_id': 't_old', 'status': 'ready'}
            (journal / 'goal-handoff.json').write_text(json.dumps(previous))
            receipt = {'task_id': 't_new', 'status': 'ready'}
            with patch.object(m, 'ensure_notification', side_effect=RuntimeError('delivery unavailable')):
                result = m.record_handoff(['hermes'], journal, journal.parent, 'fixture', receipt)
            self.assertEqual(result['outcome'], 'notification_blocked')
            saved = json.loads((journal / 'goal-handoff.json').read_text())
            self.assertEqual(saved['task_id'], 't_new')
            self.assertIn('delivery unavailable', saved['notification_error'])
            self.assertEqual(json.loads((journal / 'handoffs/t_old.json').read_text()), previous)

    def test_dated_history_conserves_exact_original_bytes_and_board_identity(self):
        (Path.home() / '.hermes/cache/scratch').mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=Path.home() / '.hermes/cache/scratch') as directory:
            journal = Path(directory)
            old = {'task_id': 'same_card', 'board_id': 'board_a', 'created_at': '2026-10-07T12:00:00Z', 'note': 'original'}
            raw = json.dumps(old, separators=(',', ':')) + '\n\n'
            (journal / 'goal-handoff.json').write_text(raw)
            new = {**old, 'board_id': 'board_b', 'created_at': '2026-10-08T12:00:00Z', 'note': 'next'}
            m.save_receipt(journal, new)
            dated = list((journal / 'handoffs').glob('2026-10-07*.json'))
            self.assertEqual(len(dated), 1)
            self.assertEqual(dated[0].read_text(), raw)
            # Reusing a native ID on a different board must not overwrite either original.
            first_files = {p.name: p.read_bytes() for p in (journal / 'handoffs').iterdir()}
            m.save_receipt(journal, {'task_id': 'third', 'board_id': 'board_a', 'created_at': '2026-10-09T12:00:00Z'})
            for name, content in first_files.items():
                self.assertEqual((journal / 'handoffs' / name).read_bytes(), content)
            archived = [json.loads(p.read_text()) for p in (journal / 'handoffs').glob('2026-*.json')]
            self.assertIn(old, archived)
            self.assertIn(new, archived)

    def test_same_workspace_other_profile_blocks_handoff(self):
        task = {'id': 't_other', 'assignee': 'other', 'status': 'running', 'workspace_kind': 'dir', 'workspace_path': '/project'}
        self.assertEqual(m.existing_task([task], 'fixture', 'Other slice', '/project'), task)
        self.assertIsNone(m.existing_task([task], 'fixture', 'Other slice', '/disjoint'))

    def test_running_task_wins_over_new_slice(self):
        task = {'id': 't_live', 'assignee': 'fixture', 'status': 'running', 'title': 'Existing slice'}
        self.assertEqual(m.existing_task([task], 'fixture', 'Other slice'), task)
        self.assertIsNone(m.existing_task([task], 'other-profile', 'Other slice'))

if __name__ == '__main__':
    unittest.main()
