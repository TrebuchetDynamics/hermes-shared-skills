"""Offline STT setup regressions; never invokes a provider."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

SCRIPT = Path(__file__).with_name('configure_stt.py')


class ConfigureSTTTests(unittest.TestCase):
    def load(self):
        self.assertTrue(SCRIPT.is_file(), 'STT configuration helper is missing')
        spec = importlib.util.spec_from_file_location('configure_stt', SCRIPT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_preview_never_calls_hermes(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / 'config.yaml').write_text('model: untouched\n')
            runner = Mock(side_effect=AssertionError('preview invoked Hermes'))
            self.assertEqual(module.configure(home, 'local', 'base', False, runner), 0)
            runner.assert_not_called()
            self.assertEqual((home / 'config.yaml').read_text(), 'model: untouched\n')

    def test_apply_scopes_cli_and_verifies_each_value(self):
        import json
        from subprocess import CompletedProcess
        module = self.load()
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / 'config.yaml').write_text('model: untouched\n')
            saved = {}
            def run(command, **kwargs):
                self.assertEqual(kwargs['env']['HERMES_HOME'], str(home))
                self.assertNotIn('HERMES_PROFILE', kwargs['env'])
                self.assertEqual(kwargs['timeout'], 30)
                self.assertEqual(command[:2], ['hermes', 'config'])
                if command[2] == 'set':
                    self.assertFalse(command[4].startswith('"'), 'Hermes stores quotes literally')
                    saved[command[3]] = (json.loads(command[4]) if command[4] in ('true', 'false') else command[4])
                    return CompletedProcess(command, 0, '', '')
                return CompletedProcess(command, 0, json.dumps(saved[command[3]]), '')
            self.assertEqual(module.configure(home, 'local', 'tiny', True, run), 0)
            self.assertEqual(list(saved), ['stt.provider', 'stt.local.model', 'stt.enabled'])
            self.assertEqual(saved, {'stt.enabled': True, 'stt.provider': 'local', 'stt.local.model': 'tiny'})
            self.assertEqual((home / 'config.yaml').read_text(), 'model: untouched\n')

    def test_failures_stop_without_retry(self):
        import subprocess
        module = self.load()
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            runner = Mock()
            with self.assertRaises(ValueError):
                module.configure(home, 'local', 'base', True, runner)
            runner.assert_not_called()
            (home / 'config.yaml').write_text('{}\n')
            for failure in [subprocess.CalledProcessError(1, ['hermes']),
                            subprocess.TimeoutExpired(['hermes'], 30)]:
                runner = Mock(side_effect=failure)
                with self.assertRaises(type(failure)):
                    module.configure(home, 'local', 'base', True, runner)
                self.assertEqual(runner.call_count, 1)
            runner = Mock(return_value=subprocess.CompletedProcess([], 0, 'null', ''))
            with self.assertRaisesRegex(ValueError, 'Readback mismatch'):
                module.configure(home, 'off', 'base', True, runner)
            self.assertEqual(runner.call_count, 2)
            self.assertEqual(runner.call_args_list[0].args[0][3:], ['stt.enabled', 'false'])

    def test_reject_invalid_provider_before_calls(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'config.yaml').write_text('{}\n')
            runner = Mock()
            with self.assertRaises(ValueError):
                module.configure(tmp, 'typo', 'base', True, runner)
            runner.assert_not_called()


if __name__ == '__main__':
    unittest.main()
