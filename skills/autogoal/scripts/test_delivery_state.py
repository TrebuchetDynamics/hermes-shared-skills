"""Real isolated Git/helper evidence; no native board or provider execution."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path
import candidate_identity
import check_receipt
import delivery_state as m

SCRATCH = (Path.home() / '.hermes/cache/scratch/executable-safeguards/state-repair')
SCRATCH.mkdir(parents=True, exist_ok=True)


class EvidenceFixture:
    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.repo = Path(self.temp.name)
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.base = self.commit('base\n')
        self.git('update-ref', 'refs/heads/main', self.base)
        self.commit_id = self.commit('candidate\n', self.base)
        self.git('update-ref', 'refs/heads/candidate', self.commit_id)
        self.identity = candidate_identity.capture(self.repo, self.base, 'refs/heads/candidate')
        self.command = [sys.executable, '-c', 'from pathlib import Path; assert Path("a.py").read_text() == "candidate\\n"']
        self.scope = {'platform': 'linux', 'backend': 'offline', 'mode': 'fixture',
                      'toolchain': {'python': sys.version}}
        self.receipt = self.execute()
        self.evidence = {'candidate': self.identity, 'implementation': {'artifacts': ['a.py']},
                         'qualification': {'candidate': self.identity, 'required_checks': ['unit'],
                                           'checks': [self.check()]}}
        return self

    def git(self, *args, text=None):
        import subprocess
        return subprocess.check_output(['git', '-c', 'core.hooksPath=/dev/null', '-C', str(self.repo), *args], input=text, text=True, stderr=subprocess.PIPE).strip()

    def commit(self, text, parent=None):
        blob = self.git('hash-object', '-w', '--stdin', text=text)
        tree = self.git('mktree', text=f'100644 blob {blob}\ta.py\n')
        return self.git('commit-tree', tree, *(['-p', parent] if parent else []), text=text)

    def execute(self, command=None, scope=None):
        return check_receipt.execute(self.repo, ['a.py'], command or self.command, 10,
                                     candidate=self.identity, qualification_scope=scope or self.scope,
                                     external_paths=[])

    def check(self):
        return {'name': 'unit', 'command': self.command, 'paths': ['a.py'], 'external_paths': [],
                'qualification_scope': self.scope, 'receipt': self.receipt,
                'platform': 'linux', 'backend': 'offline', 'mode': 'fixture', 'result': 'passed'}

    def integrated(self):
        self.git('update-ref', 'refs/heads/main', self.commit_id)
        self.evidence['integration'] = {'candidate': self.identity, 'action': 'merge', 'before': self.base,
            'after': self.commit_id, 'target': 'refs/heads/main', 'provenance': {
                'source': 'protected_pr', 'id': 'fixture-pr-1', 'observed': True, 'protected': True,
                'required_checks': 'passed', 'head': self.commit_id, 'merge_commit': self.commit_id}}
        return self.evidence

    def __exit__(self, *args):
        self.temp.cleanup()


class DeliveryStateTests(unittest.TestCase):
    def test_required_runner_checks_cannot_be_omitted_or_replaced_by_app_pass(self):
        with EvidenceFixture() as f:
            qualification = f.evidence['qualification']
            qualification['required_checks'] = ['unit', 'preservation', 'runner']
            self.assertFalse(m.evaluate(f.evidence, f.repo)['qualified'])
            for name in ('preservation', 'runner'):
                check = copy.deepcopy(f.check())
                check['name'] = name
                qualification['checks'].append(check)
            self.assertTrue(m.evaluate(f.evidence, f.repo)['qualified'])
            failed = [sys.executable, '-c', 'raise SystemExit(1)']
            runner = qualification['checks'][-1]
            runner.update(command=failed, receipt=f.execute(failed))
            self.assertFalse(m.evaluate(f.integrated(), f.repo)['delivered'])
            runner.update(command=f.command, receipt=f.receipt)
            for required in (None, [], ['unit', 'unit'], ['unit', 'missing']):
                qualification['required_checks'] = required
                self.assertFalse(m.evaluate(f.evidence, f.repo)['qualified'], required)
            qualification['required_checks'] = ['unit', 'preservation', 'runner']
            qualification['checks'][-1]['name'] = 'unit'
            self.assertFalse(m.evaluate(f.evidence, f.repo)['qualified'])

    def test_assertions_without_helper_receipt_cannot_qualify(self):
        with EvidenceFixture() as f:
            del f.evidence['qualification']['checks'][0]['receipt']
            self.assertEqual(m.evaluate(f.evidence, f.repo)['state'], 'implemented')

    def test_validated_receipt_is_only_scope_authority(self):
        with EvidenceFixture() as f:
            check = f.evidence['qualification']['checks'][0]
            check.update(platform='invented', backend='provider-x', mode='live', result='passed')
            result = m.evaluate(f.evidence, f.repo)
            self.assertEqual(result['qualification_scope'], ['unit: linux/offline (fixture)'])
            f.evidence['required_mode'] = 'live'
            self.assertFalse(m.evaluate(f.evidence, f.repo)['qualified'])

    def test_failed_and_stale_receipts_cannot_qualify(self):
        with EvidenceFixture() as f:
            check = f.evidence['qualification']['checks'][0]
            command = [sys.executable, '-c', 'raise SystemExit(1)']
            check.update(command=command, receipt=f.execute(command))
            self.assertFalse(m.evaluate(f.evidence, f.repo)['qualified'])
            check.update(command=f.command, receipt=f.receipt)
            f.git('update-ref', 'refs/heads/candidate', f.base)
            self.assertFalse(m.evaluate(f.evidence, f.repo)['qualified'])

    def test_each_check_requires_explicit_inputs_and_exact_passed_receipt(self):
        with EvidenceFixture() as f:
            self.assertTrue(m.evaluate(f.evidence, f.repo)['qualified'])
            for field in ('name', 'command', 'paths', 'external_paths', 'qualification_scope', 'receipt'):
                bad = copy.deepcopy(f.evidence)
                del bad['qualification']['checks'][0][field]
                self.assertFalse(m.evaluate(bad, f.repo)['qualified'], field)
            for field, value in [('version', 1), ('qualification', 'shared_tree_declared_inputs_only'),
                                 ('outcome', 'failed'), ('candidate', {}), ('qualification_scope', None)]:
                bad = copy.deepcopy(f.evidence)
                bad['qualification']['checks'][0]['receipt'][field] = value
                self.assertFalse(m.evaluate(bad, f.repo)['qualified'], field)
            bad = copy.deepcopy(f.evidence)
            bad['qualification']['checks'][0]['qualification_scope'] = None
            self.assertFalse(m.evaluate(bad, f.repo)['qualified'])

    def test_missing_or_wrong_repo_cannot_claim_implementation_or_qualification(self):
        with EvidenceFixture() as f:
            self.assertEqual(m.evaluate(f.evidence)['state'], 'unknown')
            self.assertEqual(m.evaluate(f.evidence, f.repo/'missing')['state'], 'unknown')
            self.assertEqual(m.evaluate({'candidate': f.identity}, f.repo)['state'], 'unknown')
            self.assertEqual(m.evaluate(f.evidence, f.repo)['candidate'], f.identity)

    def test_delivered_slice_never_closes_full_milestone(self):
        with EvidenceFixture() as f:
            result = m.evaluate(f.integrated(), f.repo)
            self.assertEqual(result['state'], 'delivered')
            self.assertFalse(result['milestone_complete'])

    def test_live_scope_and_all_check_inputs_are_bound_to_helper_execution(self):
        with EvidenceFixture() as f:
            scope = dict(f.scope, mode='live', backend='local-process')
            receipt = f.execute(scope=scope)
            check = f.evidence['qualification']['checks'][0]
            check.update(qualification_scope=scope, receipt=receipt)
            f.evidence['required_mode'] = 'live'
            self.assertEqual(m.evaluate(f.evidence, f.repo)['qualification_scope'],
                             ['unit: linux/local-process (live)'])
            for field, value in [('command', [sys.executable, '-c', 'pass']),
                                 ('paths', []), ('external_paths', ['not-declared']),
                                 ('qualification_scope', f.scope)]:
                bad = copy.deepcopy(f.evidence)
                bad['qualification']['checks'][0][field] = value
                self.assertFalse(m.evaluate(bad, f.repo)['qualified'], field)
            f.evidence['qualification']['checks'].append({'name': 'invented', 'mode': 'live', 'result': 'passed'})
            self.assertFalse(m.evaluate(f.evidence, f.repo)['qualified'])

    def test_external_dependency_drift_invalidates_delivery_qualification(self):
        with EvidenceFixture() as f:
            external = f.repo/'dependency.txt'
            external.write_text('before\n')
            receipt = check_receipt.execute(f.repo, ['a.py'], f.command, 10, candidate=f.identity,
                                            qualification_scope=f.scope, external_paths=['dependency.txt'])
            f.evidence['qualification']['checks'][0].update(receipt=receipt, external_paths=['dependency.txt'])
            self.assertTrue(m.evaluate(f.evidence, f.repo)['qualified'])
            external.write_text('after\n')
            self.assertFalse(m.evaluate(f.evidence, f.repo)['qualified'])

    def test_integration_gaps_and_noop_synchronization_remain_undelivered(self):
        with EvidenceFixture() as f:
            self.assertEqual(m.evaluate(f.evidence, f.repo)['state'], 'qualified')
            f.integrated()
            for field in ('candidate', 'action', 'before', 'after', 'target', 'provenance'):
                bad = copy.deepcopy(f.evidence)
                del bad['integration'][field]
                self.assertFalse(m.evaluate(bad, f.repo)['delivered'], field)
            for field in ('source', 'id', 'observed', 'protected', 'required_checks', 'head', 'merge_commit'):
                bad = copy.deepcopy(f.evidence)
                del bad['integration']['provenance'][field]
                self.assertFalse(m.evaluate(bad, f.repo)['delivered'], field)
            f.evidence['integration'].update(action='synchronize', before=f.commit_id)
            result = m.evaluate(f.evidence, f.repo)
            self.assertEqual(result['integration'], 'already synchronized')
            self.assertFalse(result['delivered'])
            self.assertNotIn('merged', result['progress'])


if __name__ == '__main__':
    unittest.main()
