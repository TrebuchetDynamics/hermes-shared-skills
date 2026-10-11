"""Exercise setup against temporary profiles; never start a server or model."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class HindsightSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'hermes home'
        self.root.mkdir()
        for name in ('default', 'coder', 'research'):
            home = self.home(name)
            home.mkdir(parents=True, exist_ok=True)
            (home / 'config.yaml').write_text('memory:\n  provider: builtin\n')
            (home / 'plugins/hindsight').mkdir(parents=True)
            (home / 'plugins/hindsight/plugin.yaml').write_text('name: hindsight\n')
        self.connection = Path(self.temp.name) / 'connection.json'
        self.connection.write_text(json.dumps({'mode': 'local_embedded',
            'llm_provider': 'ollama', 'llm_model': 'test-model',
            'llm_base_url': 'http://localhost:11434'}))
        self.bin = Path(self.temp.name) / 'bin'
        self.bin.mkdir()
        fake = self.bin / 'hermes'
        fake.write_text('#!/bin/sh\nprintf "%s|%s\\n" "$HERMES_HOME" "$*" >> "$CALL_LOG"\n')
        fake.chmod(0o755)
        self.calls = Path(self.temp.name) / 'calls'
        self.env = dict(os.environ, PATH=str(self.bin) + ':' + os.environ['PATH'],
                        CALL_LOG=str(self.calls), HOME=str(Path(self.temp.name) / 'user-home'))

    def home(self, name):
        return self.root if name == 'default' else self.root / 'profiles' / name

    def run_setup(self, *args, profiles=('default', 'coder', 'research'), connection=True):
        command = [sys.executable, str(ROOT / 'install-hindsight.py'), '--hermes-home', str(self.root)]
        for name in profiles:
            command += ['--profile', name]
        if connection:
            command += ['--config', str(self.connection)]
        return subprocess.run([*command, *args], env=self.env, capture_output=True, text=True)

    def config(self, name):
        return json.loads((self.home(name) / 'hindsight/config.json').read_text())

    def test_every_profile_has_distinct_persistent_bank_and_embedded_store(self):
        result = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        configs = [self.config(n) for n in ('default', 'coder', 'research')]
        self.assertEqual(len({c['bank_id'] for c in configs}), 3)
        self.assertEqual(len({c['profile'] for c in configs}), 3)
        for cfg in configs:
            self.assertEqual(cfg['bank_id_template'], '')
            self.assertTrue(cfg['auto_recall'] and cfg['auto_retain'])
            self.assertEqual(cfg['memory_mode'], 'hybrid')
        before = {n: (self.home(n) / 'hindsight/config.json').stat().st_mtime_ns
                  for n in ('default', 'coder', 'research')}
        self.assertEqual(self.run_setup(connection=False).returncode, 0)
        for name, stamp in before.items():
            self.assertEqual((self.home(name) / 'hindsight/config.json').stat().st_mtime_ns, stamp)
            self.assertEqual((self.home(name) / 'hindsight/config.json').stat().st_mode & 0o777, 0o600)
        calls = self.calls.read_text()
        for name in before:
            self.assertIn(f'|-p {name} config set memory.provider hindsight', calls)
            self.assertIn(f'|-p {name} config set memory.memory_enabled false', calls)
            self.assertIn(f'|-p {name} config set memory.user_profile_enabled false', calls)

    def test_prepare_and_dry_run_never_activate(self):
        result = self.run_setup('--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / 'hindsight').exists())
        self.assertFalse(self.calls.exists())
        self.assertEqual(self.run_setup('--prepare').returncode, 0)
        self.assertTrue((self.root / 'hindsight/config.json').exists())
        self.assertFalse(self.calls.exists())

    def test_missing_backend_fails_before_any_profile_write(self):
        result = self.run_setup(connection=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--config', result.stderr)
        self.assertFalse((self.root / 'hindsight').exists())
        self.assertFalse(self.calls.exists())

    def test_existing_connections_and_custom_banks_are_preserved(self):
        path = self.home('coder') / 'hindsight/config.json'
        path.parent.mkdir()
        path.write_text(json.dumps({'mode': 'local_external', 'api_url': 'http://localhost:8888',
                                  'bank_id': 'existing-coder', 'recall_budget': 'high'}))
        result = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        cfg = self.config('coder')
        self.assertEqual(cfg['mode'], 'local_external')
        self.assertEqual(cfg['api_url'], 'http://localhost:8888')
        self.assertEqual(cfg['bank_id'], 'existing-coder')
        self.assertEqual(cfg['recall_budget'], 'high')

    def test_existing_implicit_default_bank_and_daemon_keep_their_data(self):
        path = self.home('coder') / 'hindsight/config.json'
        path.parent.mkdir()
        path.write_text(json.dumps({'mode': 'local_embedded', 'llm_provider': 'ollama',
                                   'llm_model': 'test-model'}))
        result = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.config('coder')['bank_id'], 'hermes')
        self.assertEqual(self.config('coder')['profile'], 'hermes')

    def test_conflicting_existing_banks_fail_without_repartitioning_data(self):
        for name in ('coder', 'research'):
            path = self.home(name) / 'hindsight/config.json'
            path.parent.mkdir()
            path.write_text(json.dumps({'mode': 'local_external', 'api_url': 'http://localhost:8888',
                                      'bank_id': 'shared'}))
        result = self.run_setup(profiles=('coder',))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('shared', result.stderr)
        self.assertEqual(self.config('coder')['bank_id'], 'shared')
        self.assertFalse(self.calls.exists())

    def test_embedded_daemon_collision_is_rejected_even_with_distinct_banks(self):
        for name in ('coder', 'research'):
            path = self.home(name) / 'hindsight/config.json'
            path.parent.mkdir()
            path.write_text(json.dumps({'mode': 'local_embedded', 'llm_provider': 'ollama',
                'llm_model': 'test-model', 'bank_id': name, 'profile': 'shared-daemon'}))
        result = self.run_setup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('shared-daemon', result.stderr)
        self.assertFalse((self.root / 'hindsight').exists())

    def test_template_and_cross_bank_recall_cannot_bypass_isolation(self):
        for extra in ({'bank_id_template': 'shared'}, {'recall_additional_banks': ['research']}):
            path = self.home('coder') / 'hindsight/config.json'
            path.parent.mkdir(exist_ok=True)
            path.write_text(json.dumps({'mode': 'cloud', **extra}))
            result = self.run_setup()
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(self.calls.exists())

    def test_unselected_sibling_cannot_route_to_selected_bank(self):
        for extra in ({'bank_id_template': 'selected'}, {'recall_additional_banks': ['selected']}):
            for name, cfg in [('coder', {'bank_id': 'selected'}),
                              ('research', {'bank_id': 'sibling', **extra})]:
                path = self.home(name) / 'hindsight/config.json'
                path.parent.mkdir(exist_ok=True)
                path.write_text(json.dumps({'mode': 'cloud', **cfg}))
            result = self.run_setup(profiles=('coder',))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('research', result.stderr)
            self.assertFalse(self.calls.exists())

    def test_invalid_last_profile_aborts_without_partial_setup(self):
        path = self.home('research') / 'hindsight/config.json'
        path.parent.mkdir()
        path.write_text('{broken')
        result = self.run_setup()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / 'hindsight').exists())
        self.assertEqual(path.read_text(), '{broken')

    def test_deleted_symlinked_or_escaping_profiles_are_refused(self):
        deleted = self.root / 'profiles/.deleted'
        deleted.mkdir()
        (deleted / 'coder').touch()
        for name in ('coder', '../outside', 'absent'):
            result = self.run_setup(profiles=(name,))
            self.assertNotEqual(result.returncode, 0)
        linked = self.root / 'profiles/linked'
        linked.symlink_to(self.home('research'), target_is_directory=True)
        self.assertNotEqual(self.run_setup(profiles=('linked',)).returncode, 0)
        self.assertFalse(self.calls.exists())

    def test_live_sibling_with_shared_config_directory_is_not_skipped(self):
        (self.home('coder') / 'hindsight').mkdir()
        (self.home('research') / 'hindsight').symlink_to(self.home('coder') / 'hindsight')
        result = self.run_setup(profiles=('coder',))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.calls.exists())

    def test_legacy_global_or_profile_env_routing_is_not_silently_replaced(self):
        global_config = Path(self.env['HOME']) / '.hindsight/config.json'
        global_config.parent.mkdir(parents=True)
        global_config.write_text('{"mode":"cloud","bank_id":"old-bank"}')
        result = self.run_setup()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / 'hindsight').exists())
        global_config.unlink()
        (self.home('research') / '.env').write_text('HINDSIGHT_BANK_ID=old-env-bank\n')
        result = self.run_setup(profiles=('coder',))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('research', result.stderr)
        self.assertFalse(self.calls.exists())

    def test_existing_hindsight_selection_without_local_json_requires_migration(self):
        (self.home('coder') / 'config.yaml').write_text('memory:\n  provider: hindsight\n')
        result = self.run_setup()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / 'hindsight').exists())

    def test_secrets_in_template_are_refused_and_not_printed(self):
        self.connection.write_text(json.dumps({'mode': 'cloud', 'api_key': 'private-test-key'}))
        result = self.run_setup()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('private-test-key', result.stdout + result.stderr)
        self.assertFalse((self.root / 'hindsight').exists())


if __name__ == '__main__':
    unittest.main()
