"""Offline readiness and transcription harness tests, not audio acceptance."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class LocalSTTTests(unittest.TestCase):
    def load(self):
        path = Path(__file__).with_name('local_stt.py')
        self.assertTrue(path.is_file(), 'offline local STT readiness helper missing')
        spec = importlib.util.spec_from_file_location('local_stt', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_absent_prerequisites_are_not_ready(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as tmp, patch.object(module.importlib.util, 'find_spec', return_value=None):
            report = module.readiness(Path(tmp))
            self.assertFalse(report['ready'])
            self.assertIn('faster_whisper', report['missing'])
            self.assertIn('model.bin', report['missing'])
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_complete_files_are_only_readiness_not_recognition(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in module.MODEL_FILES:
                (root / name).write_text('fixture')
            with patch.object(module.importlib.util, 'find_spec', return_value=object()):
                report = module.readiness(root)
            self.assertTrue(report['ready'])
            self.assertEqual(report['transcription'], 'NOT_RUN')
            (root / 'model.bin').write_bytes(b'')
            with patch.object(module.importlib.util, 'find_spec', return_value=object()):
                self.assertFalse(module.readiness(root)['ready'])

    def test_local_smoke_enforces_offline_and_checks_phrase(self):
        import socket
        import types
        module = self.load()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in module.MODEL_FILES:
                (root / name).write_text('fixture')
            audio = root / 'synthetic.wav'
            audio.write_bytes(b'fixture audio boundary')
            class Model:
                def __init__(inner, path, **kwargs):
                    self.assertEqual(path, str(root))
                    self.assertTrue(kwargs['local_files_only'])
                    self.assertEqual(kwargs['device'], 'cpu')
                    with self.assertRaisesRegex(RuntimeError, 'Network disabled'):
                        socket.create_connection(('example.invalid', 80))
                def transcribe(inner, path, **kwargs):
                    self.assertEqual(path, str(audio))
                    return [types.SimpleNamespace(text='Hello, portable tools!')], None
            args = ['--model-dir', str(root), '--audio', str(audio), '--transcribe',
                    '--non-sensitive', '--expect', 'hello portable tools']
            with patch.object(module.importlib.util, 'find_spec', return_value=object()), \
                    patch.dict('sys.modules', faster_whisper=types.SimpleNamespace(WhisperModel=Model)), \
                    patch.dict(module.os.environ), patch.object(socket.socket, 'connect'), \
                    patch.object(socket.socket, 'connect_ex'), patch.object(socket, 'create_connection'):
                self.assertEqual(module.main(args), 0)
                self.assertEqual(module.main(args[:-1] + ['not spoken']), 1)

    def test_audio_requires_explicit_opt_in_and_expected_phrase(self):
        module = self.load()
        for extra in [[], ['--transcribe'], ['--transcribe', '--expect', 'hello']]:
            with self.assertRaises(SystemExit) as caught:
                module.main(['--model-dir', '/absent', '--audio', '/absent.wav'] + extra)
            self.assertNotEqual(caught.exception.code, 0)


if __name__ == '__main__':
    unittest.main()
