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


if __name__ == '__main__':
    unittest.main()
