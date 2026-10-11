"""Offline role-contract composition; no publication, cards or product access."""
import inspect
import json
from pathlib import Path
import tempfile
import unittest
import start_goal as goal


class WorkerRoles(unittest.TestCase):
    def test_cli_explicit_proposal_validation_without_native_calls(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory(dir=Path.home() / '.hermes/cache/scratch') as directory:
            source = Path(directory)
            contract = source / 'contract.txt'
            contract.write_text(''.join(f'{key}: concrete fixture {key}\n' for key in goal.CONTRACT_FIELDS))
            args = [sys.executable, str(Path(goal.__file__)), '--profile', 'fixture-worker',
                    '--workspace', directory, '--title', 'Fixture', '--contract-file', str(contract),
                    '--validate-only', '--ledger-mode', 'proposal', '--integration-owner', 'fixture-integrator']
            result = subprocess.run(args, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            roles = json.loads(result.stdout)['worker_roles']
            self.assertEqual(roles['ledger_mode'], 'proposal')
            self.assertEqual(roles['integration_owner'], 'fixture-integrator')
            self.assertIsNone(roles['publication_ref'])
            refused = subprocess.run(args[:-2], capture_output=True, text=True, timeout=10)
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn('proposal ledger role requires explicit integration owner', refused.stderr)

    def test_explicit_proposal_mode_removes_worker_ledger_closure(self):
        self.assertIn('ledger_mode', inspect.signature(goal.build_task_body).parameters,
                      'missing explicit worker ledger role')
        body = goal.build_task_body('Fixture contract', ledger_mode='proposal', integration_owner='fixture-integrator')
        self.assertIn('fixture-integrator', body)
        self.assertIn('ledger proposals only', body)
        self.assertNotIn('goals.py task <repo> <TASK> done', body)
        self.assertNotIn('then `goals.py render <repo>`', body)
        self.assertIn('and no push', body)

    def test_default_body_remains_worker_closure_and_no_publication(self):
        body = goal.build_task_body('Fixture contract')
        self.assertIn('goals.py task <repo> <TASK> done', body)
        self.assertIn('and no push', body)

    def test_explicit_ref_publication_requires_bound_owner_authority(self):
        validator = getattr(goal, 'validate_publication_authority', None)
        self.assertTrue(callable(validator), 'missing scoped owner-publication evidence validation')
        with tempfile.TemporaryDirectory(dir=Path.home() / '.hermes/cache/scratch') as directory:
            source = Path(directory)
            authority = {'version': 1, 'workspace': str(source), 'profile': 'fixture-worker',
                         'goal_task': 'T-one', 'contract_sha256': goal.hashlib.sha256(b'Fixture contract').hexdigest(),
                         'remote': 'origin', 'ref': 'refs/heads/agent/fixture-worker/T-one',
                         'owner': 'fixture-integrator', 'evidence_ref': 'fixture://accepted-owner-decision'}
            verified = validator(authority, source, 'fixture-worker', 'T-one', 'Fixture contract')
            body = goal.build_task_body('Fixture contract', ledger_mode='proposal',
                                        integration_owner='fixture-integrator', publication_authority=verified)
            self.assertIn('<receipt-commit-sha>:refs/heads/agent/fixture-worker/T-one', body)
            self.assertNotIn(' HEAD:', body)
            self.assertIn('caller_attestation_not_independent_authorization', body)
            self.assertNotIn('and no push, merge', body)
            self.assertNotIn('goals.py task <repo> <TASK> done', body)
            self.assertIn('no direct main push', body)
            for change in ({'ref': 'refs/heads/main'}, {'profile': 'forged'}, {'remote': '--all'},
                           {'goal_task': 'T-other'}, {'contract_sha256': 'a' * 64}, {'evidence_ref': ''}):
                with self.assertRaises(ValueError):
                    validator(dict(authority, **change), source, 'fixture-worker', 'T-one', 'Fixture contract')


if __name__ == '__main__':
    unittest.main()
