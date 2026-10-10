"""Source/dependency/environment-bound checks, no model or transport."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


class ReceiptTests(unittest.TestCase):
    def load(self):
        path = Path(__file__).with_name('check_receipt.py')
        self.assertTrue(path.is_file(), 'check receipt implementation missing')
        spec = importlib.util.spec_from_file_location('check_receipt', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_runtime_fingerprints_actual_execution_environment(self):
        module = self.load()
        import os
        environment = dict(os.environ, CHECK_EXECUTION_ENV='remapped-value', PWD='/isolated/one')
        first = module.runtime([sys.executable], '/isolated/one', environment)
        changed = dict(environment, CHECK_EXECUTION_ENV='different-value')
        self.assertNotEqual(first['environment_sha256'],
                            module.runtime([sys.executable], '/isolated/one', changed)['environment_sha256'])
        other = dict(environment, PWD='/isolated/two')
        second = module.runtime([sys.executable], '/isolated/two', other)
        self.assertEqual(first['environment_sha256'], second['environment_sha256'])
        self.assertNotEqual(first['execution_environment_sha256'], second['execution_environment_sha256'])

    def test_shared_resource_lock_is_bounded_across_processes(self):
        import subprocess
        import time
        module = self.load()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'input').write_text('fixture')
            lock = root / 'resource.lock'
            ready = root / 'ready'
            holder_code = ('import fcntl,time; from pathlib import Path; '
                           f'f=open({str(lock)!r}, "a"); fcntl.flock(f, fcntl.LOCK_EX); '
                           f'Path({str(ready)!r}).touch(); time.sleep(10)')
            holder = subprocess.Popen([sys.executable, '-c', holder_code])
            try:
                deadline = time.monotonic() + 3
                while not ready.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(ready.exists())
                with self.assertRaisesRegex(ValueError, 'resource lock'):
                    module.execute(root, ['input'], [sys.executable, '-c', 'pass'], 5,
                                   resource_lock=lock, lock_timeout=0.05)
            finally:
                holder.terminate()
                holder.wait(timeout=5)

    def test_backend_environment_and_tool_executable_reject_reuse_without_secret_values(self):
        import os
        from unittest.mock import patch
        module = self.load()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'input').write_text('fixture')
            tool = root / 'tool'
            tool.write_text('#!/bin/sh\nexit 0\n')
            tool.chmod(0o700)
            command = [str(tool)]
            with patch.dict(os.environ, {'CHECK_BACKEND': 'fixture-a', 'TEST_API_TOKEN': 'secret-fixture-value'}):
                receipt = module.execute(root, ['input'], command, 5)
                self.assertNotIn('secret-fixture-value', str(receipt))
                with patch.dict(os.environ, {'CHECK_BACKEND': 'fixture-b'}):
                    self.assertFalse(module.reusable(receipt, root, command))
                tool.write_text('#!/bin/sh\n# changed toolchain\nexit 0\n')
                self.assertFalse(module.reusable(receipt, root, command))

    def test_reuse_cannot_change_declared_input_contract(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'input').write_text('one')
            (root / 'dependency').write_text('two')
            command = [sys.executable, '-c', 'pass']
            receipt = module.execute(root, ['input'], command, 5)
            self.assertFalse(module.reusable(receipt, root, command, paths=['input', 'dependency']))

    def test_reuse_requires_same_source_dependencies_environment_and_command(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('artifact', 'lock', 'environment'):
                (root / name).write_text('original')
            command = [sys.executable, '-c', 'pass']
            receipt = module.execute(root, ['artifact', 'lock', 'environment'], command, 5)
            self.assertTrue(module.reusable(receipt, root, command))
            for name in ('artifact', 'lock', 'environment'):
                (root / name).write_text('changed')
                self.assertFalse(module.reusable(receipt, root, command))
                (root / name).write_text('original')
            self.assertFalse(module.reusable(receipt, root, command + ['different']))
            receipt['runtime']['python'] = 'different runtime'
            self.assertFalse(module.reusable(receipt, root, command))

    def test_cli_round_trip_and_refusal_preserves_receipt(self):
        import json
        import subprocess
        module = self.load()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'input').write_text('fixture')
            receipt = root / 'receipt.json'
            base = [sys.executable, module.__file__, 'run', '--workspace', str(root),
                    '--receipt', str(receipt), '--path', 'input', '--', sys.executable, '-c', 'pass']
            result = subprocess.run(base, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            before = receipt.read_bytes()
            base[2] = 'reuse'
            result = subprocess.run(base, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            (root / 'input').write_text('drift')
            result = subprocess.run(base, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(receipt.read_bytes(), before)

    def test_cli_reuse_cannot_omit_external_input_contract(self):
        import subprocess
        module = self.load()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'input').write_text('fixture')
            (root / 'dependency.lock').write_text('pinned')
            argv = [sys.executable, module.__file__, 'run', '--workspace', str(root),
                    '--receipt', str(root / 'receipt.json'), '--path', 'input',
                    '--external-path', 'dependency.lock', '--', sys.executable, '-c', 'pass']
            result = subprocess.run(argv, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            argv[2] = 'reuse'
            omitted = argv[:9] + argv[11:]
            result = subprocess.run(omitted, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            result = subprocess.run(argv, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_failed_diagnostics_and_command_never_store_credential_values(self):
        import os
        from unittest.mock import patch
        module = self.load()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'input').write_text('fixture')
            with patch.dict(os.environ, {'TEST_API_TOKEN': 'sensitive-fixture-token'}):
                command = [sys.executable, '-c', 'print("sensitive-fixture-token"); raise SystemExit(1)']
                receipt = module.execute(root, ['input'], command, 5)
                self.assertNotIn('sensitive-fixture-token', str(receipt))
                self.assertIn('[REDACTED]', receipt['diagnostic'])

    def test_shell_last_command_success_cannot_mask_failed_check(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'input').write_text('fixture')
            command = ['sh', '-c', 'false; true']
            receipt = module.execute(root, ['input'], command, 5)
            self.assertEqual(receipt['exit_code'], 0)
            self.assertNotEqual(receipt['outcome'], 'passed')
            self.assertFalse(module.reusable(receipt, root, command))
            receipt['outcome'] = 'passed'  # Legacy last-command-only receipt.
            self.assertFalse(module.reusable(receipt, root, command))

    def test_failed_check_retains_diagnostic_without_retry(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'input').write_text('fixture')
            receipt = module.execute(root, ['input'], [sys.executable, '-c',
                                     'print("fixture failure detail"); raise SystemExit(2)'], 5)
            self.assertIn('fixture failure detail', receipt.get('diagnostic', ''))
            self.assertEqual(receipt['attempts'], 1)

    def test_timeout_stops_descendants(self):
        import time
        module = self.load()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'input').write_text('fixture')
            child = 'import time; from pathlib import Path; time.sleep(0.4); Path("escaped").touch()'
            parent = f'import subprocess, sys, time; subprocess.Popen([sys.executable, "-c", {child!r}]); time.sleep(5)'
            receipt = module.execute(root, ['input'], [sys.executable, '-c', parent], 0.15)
            self.assertEqual(receipt['outcome'], 'timeout')
            time.sleep(0.5)
            self.assertFalse((root / 'escaped').exists(), 'timed-out check left a live descendant')

    def test_failure_timeout_and_in_check_drift_cannot_qualify(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'artifact').write_text('original')
            for code, timeout in [('raise SystemExit(1)', 5),
                                  ('import time; time.sleep(5)', 0.05),
                                  ('from pathlib import Path; Path("artifact").write_text("changed")', 5)]:
                command = [sys.executable, '-c', code]
                receipt = module.execute(root, ['artifact'], command, timeout)
                self.assertFalse(module.reusable(receipt, root, command))
                self.assertEqual(receipt['attempts'], 1)
                self.assertIn(receipt['outcome'], ('failed', 'timeout', 'source_changed'))


class CandidateReceiptTests(unittest.TestCase):
    load = ReceiptTests.load

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git('init', '-q')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        (self.root / 'input').write_text('base')
        self.git('add', '.')
        self.git('commit', '-qm', 'base')
        self.base = self.git('rev-parse', 'HEAD')

    def git(self, *args):
        import subprocess
        return subprocess.check_output(['git', '-C', str(self.root), *args], text=True).strip()

    def identity(self):
        import candidate_identity
        self.git('branch', 'candidate')
        return candidate_identity.capture(self.root, self.base, 'candidate')

    def test_external_script_argv_cannot_qualify_clean_candidate(self):
        module = self.load()
        candidate = self.identity()
        with tempfile.TemporaryDirectory() as outside:
            script = Path(outside) / 'helper.py'
            script.write_text('print("augmented local check")\n')
            command = [sys.executable, '-B', str(script)]
            receipt = module.execute(self.root, ['input'], command, 5, candidate=candidate)
            self.assertEqual(receipt['outcome'], 'passed')
            self.assertNotEqual(receipt['qualification'], 'exact_candidate')
            self.assertFalse(module.reusable(receipt, self.root, command, candidate=candidate))

    def test_embedded_shared_checkout_read_cannot_qualify(self):
        module = self.load()
        candidate = self.identity()
        dependency = self.root / 'untracked-dependency'
        dependency.write_text('outside candidate')
        command = [sys.executable, '-c', f'from pathlib import Path; assert Path({str(dependency)!r}).read_text()']
        receipt = module.execute(self.root, ['input'], command, 5, candidate=candidate)
        self.assertNotEqual(receipt['qualification'], 'exact_candidate')
        self.assertFalse(module.reusable(receipt, self.root, command, candidate=candidate))

    def test_new_untracked_dependency_cannot_qualify(self):
        module = self.load()
        candidate = self.identity()
        command = [sys.executable, '-c', 'from pathlib import Path; p=Path("not-in-candidate.py"); p.write_text("VALUE=1"); assert p.read_text()']
        receipt = module.execute(self.root, ['input'], command, 5, candidate=candidate)
        self.assertEqual(receipt['outcome'], 'undeclared_generated_files')
        self.assertFalse(module.reusable(receipt, self.root, command, candidate=candidate))

    def test_declared_generated_output_preserves_only_narrow_evidence(self):
        module = self.load()
        candidate = self.identity()
        command = [sys.executable, '-c', 'from pathlib import Path; Path("report.json").write_text("{}")']
        receipt = module.execute(self.root, ['input'], command, 5, candidate=candidate,
                                 generated_outputs=['report.json'])
        self.assertEqual(receipt['outcome'], 'passed')
        self.assertEqual(receipt['generated_outputs'], ['report.json'])
        self.assertNotEqual(receipt['qualification'], 'exact_candidate')
        self.assertFalse(module.reusable(receipt, self.root, command, candidate=candidate))
        with self.assertRaisesRegex(ValueError, 'output'):
            module.execute(self.root, ['input'], command, 5, candidate=candidate,
                           generated_outputs=['not-in-candidate.py'])

    def test_transient_generated_source_cannot_qualify(self):
        module = self.load()
        candidate = self.identity()
        command = [sys.executable, '-c', 'from pathlib import Path; p=Path("transient.py"); p.write_text("VALUE=1"); assert p.read_text(); p.unlink()']
        receipt = module.execute(self.root, ['input'], command, 5, candidate=candidate)
        self.assertNotEqual(receipt['qualification'], 'exact_candidate')
        self.assertFalse(module.reusable(receipt, self.root, command, candidate=candidate))

    def test_pre_repair_exact_receipts_cannot_be_reused(self):
        module = self.load()
        candidate = self.identity()
        command = [sys.executable, '-c', 'pass']
        receipt = module.execute(self.root, ['input'], command, 5, candidate=candidate)
        receipt.pop('qualification_policy', None)
        self.assertFalse(module.reusable(receipt, self.root, command, candidate=candidate))

    def test_candidate_symlink_to_shared_checkout_is_refused(self):
        module = self.load()
        dependency = self.root / 'untracked-dependency'
        dependency.write_text('outside candidate')
        (self.root / 'linked-input').symlink_to(dependency)
        self.git('add', 'linked-input')
        self.git('commit', '-qm', 'unsafe symlink fixture')
        self.base = self.git('rev-parse', 'HEAD')
        candidate = self.identity()
        with self.assertRaisesRegex(ValueError, 'symlink'):
            module.execute(self.root, ['input'], [sys.executable, '-c', 'pass'], 5,
                           candidate=candidate)

    def test_candidate_ref_drift_and_undeclared_tracked_drift_invalidate(self):
        module = self.load()
        candidate = self.identity()
        command = [sys.executable, '-c', 'pass']
        receipt = module.execute(self.root, ['input'], command, 5, candidate=candidate)
        (self.root / 'input').write_text('next')
        self.git('add', 'input')
        self.git('commit', '-qm', 'next')
        self.git('branch', '-f', 'candidate', 'HEAD')
        self.assertFalse(module.reusable(receipt, self.root, command, candidate=candidate))
        with self.assertRaises(ValueError):
            module.execute(self.root, ['input'], command, 5, candidate=candidate)

    def test_external_dependencies_reject_reuse_and_drift_during_check(self):
        module = self.load()
        candidate = self.identity()
        (self.root / 'external-lock').write_text('one')
        command = [sys.executable, '-c', 'pass']
        receipt = module.execute(self.root, ['input'], command, 5, candidate=candidate,
                                 external_paths=['external-lock'])
        self.assertTrue(module.reusable(receipt, self.root, command, candidate=candidate))
        (self.root / 'external-lock').write_text('two')
        self.assertFalse(module.reusable(receipt, self.root, command, candidate=candidate))

    def test_named_scope_is_preserved_and_scope_changes_reject_reuse(self):
        import inspect
        module = self.load()
        self.assertIn('qualification_scope', inspect.signature(module.execute).parameters)
        candidate = self.identity()
        command = [sys.executable, '-c', 'pass']
        scope = {'platform': 'linux-native', 'backend': 'offline', 'mode': 'fixture',
                 'toolchain': {'python': sys.version}}
        receipt = module.execute(self.root, ['input'], command, 5, candidate=candidate,
                                 qualification_scope=scope)
        self.assertEqual(receipt['qualification_scope'], scope)
        self.assertTrue(module.reusable(receipt, self.root, command, candidate=candidate,
                                        qualification_scope=scope))
        for key, value in [('platform', 'android'), ('backend', 'provider-x'),
                           ('mode', 'live'), ('toolchain', {'python': 'different'})]:
            changed = dict(scope, **{key: value})
            self.assertFalse(module.reusable(receipt, self.root, command, candidate=candidate,
                                             qualification_scope=changed), key)
        with self.assertRaises(ValueError):
            module.execute(self.root, ['input'], command, 5, candidate=candidate,
                           qualification_scope={'platform': 'linux-native'})

    def test_exact_candidate_cli_reports_execution_vs_reuse(self):
        import json
        import subprocess
        module = self.load()
        candidate = self.identity()
        receipt = self.root / 'receipt.json'
        argv = [sys.executable, module.__file__, 'run', '--workspace', str(self.root),
                '--receipt', str(receipt), '--path', 'input', '--base', self.base,
                '--candidate', 'candidate', '--tree', candidate['candidate_tree'],
                '--timeout', '301', '--platform', 'linux-native', '--backend', 'offline',
                '--mode', 'fixture', '--toolchain', 'python=' + sys.version,
                '--', sys.executable, '-c', 'pass']
        result = subprocess.run(argv, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['execution'], 'executed')
        argv[2] = 'reuse'
        result = subprocess.run(argv, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['execution'], 'reused')
        self.assertEqual(report['attempts'], 0)
        self.assertGreaterEqual(report['elapsed_seconds'], 0)

    def test_isolated_head_change_cannot_qualify_even_with_same_tree(self):
        module = self.load()
        candidate = self.identity()
        self.git('commit', '--allow-empty', '-qm', 'empty next')
        next_commit = self.git('rev-parse', 'HEAD')
        receipt = module.execute(self.root, ['input'], ['git', 'checkout', '--detach', next_commit],
                                 5, candidate=candidate)
        self.assertEqual(receipt['outcome'], 'candidate_changed')

    def test_prerequisite_ref_moving_during_check_invalidates_receipt(self):
        import candidate_identity
        module = self.load()
        self.git('branch', 'sibling')
        self.git('branch', 'candidate')
        candidate = candidate_identity.capture(self.root, self.base, 'candidate', {'sibling': self.base})
        self.git('commit', '--allow-empty', '-qm', 'next sibling')
        next_commit = self.git('rev-parse', 'HEAD')
        receipt = module.execute(self.root, ['input'], ['git', '-C', str(self.root), 'branch', '-f',
                                 'sibling', next_commit], 5, candidate=candidate)
        self.assertEqual(receipt['outcome'], 'candidate_changed')

    def test_absolute_workspace_script_executes_candidate_copy(self):
        module = self.load()
        script = self.root / 'runner.py'
        script.write_text('from pathlib import Path\nassert Path("input").read_text() == "base"\n')
        self.git('add', 'runner.py')
        self.git('commit', '-qm', 'runner')
        self.base = self.git('rev-parse', 'HEAD')
        candidate = self.identity()
        script.write_text('raise SystemExit(7)\n')
        command = [sys.executable, str(script)]
        receipt = module.execute(self.root, ['input', 'runner.py'], command, 5, candidate=candidate)
        self.assertEqual(receipt['outcome'], 'passed')
        self.assertTrue(module.reusable(receipt, self.root, command, candidate=candidate))

    def test_candidate_environment_cannot_redirect_git_index_or_python_imports_to_shared_tree(self):
        import os
        from unittest.mock import patch
        module = self.load()
        (self.root / 'fixture_module.py').write_text('VALUE = "base"\n')
        self.git('add', 'fixture_module.py')
        self.git('commit', '-qm', 'module')
        self.base = self.git('rev-parse', 'HEAD')
        candidate = self.identity()
        (self.root / 'fixture_module.py').write_text('VALUE = "dirty"\n')
        # No implicit cache-output allowance: prevent bytecode output explicitly.
        command = [sys.executable, '-B', '-c', 'import os,fixture_module; assert "GIT_INDEX_FILE" not in os.environ; assert fixture_module.VALUE == "base"']
        before_index = (self.root / '.git/index').read_bytes()
        with patch.dict(os.environ, {'GIT_INDEX_FILE': str(self.root / '.git/index'),
                                    'PYTHONPATH': str(self.root)}):
            receipt = module.execute(self.root, ['input'], command, 5, candidate=candidate)
        self.assertEqual(receipt['outcome'], 'passed')
        self.assertEqual((self.root / '.git/index').read_bytes(), before_index)

    def test_exact_reuse_revalidates_candidate_input_fingerprints(self):
        module = self.load()
        candidate = self.identity()
        command = [sys.executable, '-c', 'pass']
        receipt = module.execute(self.root, ['input'], command, 5, candidate=candidate)
        receipt['before']['files'][0]['sha256'] = '0' * 64
        receipt['after']['files'][0]['sha256'] = '0' * 64
        self.assertFalse(module.reusable(receipt, self.root, command, candidate=candidate))

    def test_undeclared_tracked_candidate_mutation_invalidates_check(self):
        module = self.load()
        (self.root / 'other-source').write_text('original')
        self.git('add', 'other-source')
        self.git('commit', '-qm', 'other source')
        self.base = self.git('rev-parse', 'HEAD')
        candidate = self.identity()
        command = [sys.executable, '-c', 'from pathlib import Path; Path("other-source").write_text("changed")']
        receipt = module.execute(self.root, ['input'], command, 5, candidate=candidate)
        self.assertEqual(receipt['outcome'], 'source_changed')
        self.assertFalse(module.reusable(receipt, self.root, command, candidate=candidate))
        self.assertEqual((self.root / 'other-source').read_text(), 'original')

    def test_external_dependency_drift_during_check_invalidates_receipt(self):
        module = self.load()
        candidate = self.identity()
        external = self.root / 'external-lock'
        external.write_text('original')
        command = [sys.executable, '-c', f'from pathlib import Path; Path({str(external)!r}).write_text("changed")']
        receipt = module.execute(self.root, ['input'], command, 5, candidate=candidate,
                                 external_paths=['external-lock'])
        self.assertEqual(receipt['outcome'], 'source_changed')

    def test_exact_candidate_executes_in_isolation_not_dirty_union(self):
        module = self.load()
        candidate = self.identity()
        (self.root / 'input').write_text('dirty unrelated union')
        command = [sys.executable, '-c', 'from pathlib import Path; assert Path("input").read_text() == "base"']
        receipt = module.execute(self.root, ['input'], command, 301, candidate=candidate)
        self.assertEqual(receipt['outcome'], 'passed')
        self.assertEqual(receipt['qualification'], 'exact_candidate')
        self.assertEqual(receipt['candidate'], candidate)
        self.assertTrue(module.reusable(receipt, self.root, command, candidate=candidate))
        (self.root / 'receipt-only.json').write_text('bookkeeping')
        self.assertTrue(module.reusable(receipt, self.root, command, candidate=candidate))
        self.assertEqual((self.root / 'input').read_text(), 'dirty unrelated union')


if __name__ == '__main__':
    unittest.main()
