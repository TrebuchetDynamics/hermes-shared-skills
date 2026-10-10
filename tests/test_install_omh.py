"""Offline OMH setup adapter integration tests."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'install-omh.py'
SOURCE = 'git+https://github.com/rlaope/oh-my-hermes.git@021e5c63d976b4e0faf9cfc7d608701d98fe1722'
FAKE = '''import json, os, sys
with open(os.environ['CALL_LOG'], 'a') as log:
    log.write(json.dumps(sys.argv[1:]) + '\\n')
if os.environ.get('FAIL_COMMAND') in sys.argv[1:]:
    sys.exit(9)
if 'doctor' in sys.argv:
    print(json.dumps({'ok': not bool(os.environ.get('BAD_DOCTOR'))}))
else:
    print(json.dumps({'ok': True, 'steps': {'hermes_profiles':
        [{'status': 'failed', 'error': 'broken'}] if os.environ.get('BAD_PROFILE') else []}}))
'''


class InstallOmhTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.repo = self.root / 'repo'
        (self.repo / 'plugins').mkdir(parents=True)
        shutil.copy2(SCRIPT, self.repo / SCRIPT.name)
        self.defaults = self.repo / 'plugins/defaults.json'
        self.defaults.write_text(json.dumps({'omh': {'full': True, 'memory_mode': 'preserve',
                                                    'tui': False, 'menubar': False, 'source': SOURCE}}))
        self.home = self.root / 'hermes'
        self.home.mkdir()
        (self.home / 'config.yaml').write_text('model:\n  default: existing\n')
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.log = self.root / 'calls'
        self.env = dict(os.environ, PATH=str(self.bin), CALL_LOG=str(self.log))
        self.env.pop('OMH_HOME', None)
        self.command('omh', FAKE)
        self.command('hermes', "import json, os, sys\nfrom pathlib import Path\np=Path(os.environ['CALL_LOG']+'.bindings')\nwith p.open('a') as f: f.write(json.dumps([os.environ.get('HERMES_HOME'), *sys.argv[1:]])+'\\n')\n")

    def command(self, name, body):
        path = self.bin / name
        path.write_text(f'#!{sys.executable}\n' + body)
        path.chmod(0o755)
        return path

    def run_helper(self, *args):
        return subprocess.run([sys.executable, str(self.repo / SCRIPT.name),
                               '--hermes-home', str(self.home), *args],
                              env=self.env, text=True, capture_output=True)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_preserves_unset_memory_and_runs_doctor(self):
        result = self.run_helper('--profile', 'default')
        self.assertEqual(result.returncode, 0, result.stderr)
        setup, doctor = self.calls()
        self.assertIn('--no-interactive', setup)
        self.assertIn('--no-omh-tui', setup)
        self.assertIn('--no-menubar', setup)
        self.assertEqual(setup[setup.index('--memory-mode') + 1], 'off')
        self.assertIn('doctor', doctor)
        self.assertNotIn('--force', setup)

    def test_successful_named_setup_binds_plugin_to_created_store(self):
        child = self.home / 'profiles/coder'
        child.mkdir(parents=True)
        (child / 'config.yaml').touch()
        result = self.run_helper('--profile', 'coder')
        self.assertEqual(result.returncode, 0, result.stderr)
        bindings = Path(str(self.log) + '.bindings')
        self.assertTrue(bindings.is_file(), 'setup must bind the Hermes plugin to its store')
        self.assertEqual(json.loads(bindings.read_text()), [str(self.home), '-p', 'coder',
            'config', 'set', 'plugins.entries.omh.settings.omh_home', str(child / 'omh')])

    def test_preserves_foreign_provider(self):
        (self.home / 'config.yaml').write_text('memory:\n  provider: holographic # existing\n')
        result = self.run_helper('--profile', 'default')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('off', self.calls()[0])

    def test_plugin_comments_do_not_hide_enabled_list_from_omh(self):
        config = self.home / 'config.yaml'
        config.write_text('plugins:\n  clone_timeout_seconds: 300\n'
                          '# Model settings\n  enabled:\n    - hermes-toolset\n'
                          'model:\n  provider: openai-codex\n')
        self.command('omh', '''import json, sys
from pathlib import Path
p = Path(sys.argv[sys.argv.index('--hermes-home') + 1]) / 'config.yaml'
text = p.read_text()
if 'setup' in sys.argv:
    section = text.split('plugins:\\n', 1)[1]
    visible = []
    for line in section.splitlines():
        if line.strip() and not line.startswith(' '): break
        visible.append(line)
    if '  enabled:' not in visible:
        p.write_text(text.replace('plugins:\\n', 'plugins:\\n  enabled:\\n    - omh\\n'))
print(json.dumps({'ok': True}))
''')
        result = self.run_helper('--profile', 'default')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(config.read_text().count('  enabled:'), 1)
        self.assertIn('    - hermes-toolset', config.read_text())
        self.assertIn('  provider: openai-codex', config.read_text())
        self.assertIn('# Model settings', config.read_text())

    def test_preserves_existing_omh_store_and_explicit_mode(self):
        store = self.root / 'existing store'
        store.mkdir()
        (store / 'setup-profile.json').write_text(json.dumps({'memory_policy': {
            'mode': 'review-first', 'mode_source': 'explicit'}}))
        (self.home / 'config.yaml').write_text(
            f'memory:\n  provider: omh\nplugins:\n  entries:\n    omh:\n      settings:\n        omh_home: "{store}"\n')
        result = self.run_helper('--profile', 'default')
        self.assertEqual(result.returncode, 0, result.stderr)
        setup = self.calls()[0]
        self.assertEqual(setup[setup.index('--omh-home') + 1], str(store))
        self.assertIn('review-first', setup)

    def test_dry_run_does_not_run_commands_or_write(self):
        self.command('omh', 'raise RuntimeError("must not run")')
        before = sorted(str(p) for p in self.root.rglob('*'))
        result = self.run_helper('--profile', 'default', '--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, sorted(str(p) for p in self.root.rglob('*')))

    def test_preserves_exported_store_and_memory_policy(self):
        store = self.root / 'exported store'
        store.mkdir()
        (store / 'setup-profile.json').write_text(json.dumps({'memory_policy': {
            'mode': 'review-first', 'mode_source': 'explicit'}}))
        (self.home / 'config.yaml').write_text('memory:\n  provider: omh\n')
        self.env['OMH_HOME'] = str(store)
        result = self.run_helper('--profile', 'default')
        self.assertEqual(result.returncode, 0, result.stderr)
        setup = self.calls()[0]
        self.assertEqual(setup[setup.index('--omh-home') + 1], str(store))
        self.assertEqual(setup[setup.index('--memory-mode') + 1], 'review-first')

    def test_configured_store_takes_precedence_over_exported_store(self):
        store = self.root / 'configured store'
        store.mkdir()
        (store / 'setup-profile.json').write_text(json.dumps({'memory_policy': {
            'mode': 'review-first', 'mode_source': 'explicit'}}))
        (self.home / 'config.yaml').write_text(
            f'memory:\n  provider: omh\nplugins:\n  entries:\n    omh:\n      settings:\n        omh_home: "{store}"\n')
        self.env['OMH_HOME'] = str(self.root / 'unrelated store')
        result = self.run_helper('--profile', 'default')
        self.assertEqual(result.returncode, 0, result.stderr)
        setup = self.calls()[0]
        self.assertEqual(setup[setup.index('--omh-home') + 1], str(store))
        self.assertIn('review-first', setup)

    def test_root_refuses_to_touch_unselected_child(self):
        child = self.home / 'profiles/coder'
        child.mkdir(parents=True)
        (child / 'config.yaml').touch()
        result = self.run_helper('--profile', 'default')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())

    def test_all_profiles_runs_children_first(self):
        child = self.home / 'profiles/coder'
        child.mkdir(parents=True)
        (child / 'config.yaml').touch()
        result = self.run_helper('--profile', 'default', '--profile', 'coder')
        self.assertEqual(result.returncode, 0, result.stderr)
        setups = [call for call in self.calls() if 'setup' in call]
        self.assertEqual(setups[0][1], str(child))
        self.assertEqual(setups[1][1], str(self.home))

    def test_mixed_memory_modes_refused_before_any_setup(self):
        child = self.home / 'profiles/coder'
        child.mkdir(parents=True)
        (child / 'config.yaml').write_text('memory:\n  provider: omh\n')
        (child / '.env').write_text(f'OMH_HOME="{child / "omh"}"\n')
        result = self.run_helper('--profile', 'default', '--profile', 'coder')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('different child memory modes', result.stderr)
        self.assertFalse(self.log.exists())

    def test_legacy_default_follows_upstream_auto_safe(self):
        store = self.root / 'store'
        store.mkdir()
        (store / 'setup-profile.json').write_text('{"memory_mode":"review-first"}')
        (self.home / 'config.yaml').write_text('memory:\n  provider: omh\n')
        (self.home / '.env').write_text(f'OMH_HOME="{store}"\n')
        self.env['OMH_HOME'] = str(self.root / 'unrelated exported store')
        result = self.run_helper('--profile', 'default')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('auto-safe', self.calls()[0])
        self.assertIn(str(store), self.calls()[0])

    def test_noncanonical_memory_mapping_refused(self):
        (self.home / 'config.yaml').write_text('memory: {provider: holographic}\n')
        result = self.run_helper('--profile', 'default')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())

    def test_failures_propagate(self):
        for variable, value in [('FAIL_COMMAND', 'setup'), ('BAD_DOCTOR', '1'), ('BAD_PROFILE', '1')]:
            with self.subTest(variable=variable):
                self.env[variable] = value
                result = self.run_helper('--profile', 'default')
                self.assertNotEqual(result.returncode, 0)
                del self.env[variable]

    def test_invalid_defaults_and_profile_fail_before_subprocess(self):
        self.defaults.write_text('{"omh":{"full":"yes"}}')
        result = self.run_helper('--profile', '../outside')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())

    def test_uv_install_then_find_tool_bin(self):
        (self.bin / 'omh').unlink()
        target = self.root / 'uv bin'
        target.mkdir()
        executable = target / 'omh'
        executable.write_text(f'#!{sys.executable}\n' + FAKE)
        executable.chmod(0o755)
        self.command('uv', f'''import json, os, sys
with open(os.environ['CALL_LOG'], 'a') as log:
    log.write(json.dumps(sys.argv[1:]) + '\\n')
if sys.argv[1:] == ['tool', 'dir', '--bin']:
    print({str(target)!r})
elif sys.argv[1:] != ['tool', 'install', {SOURCE!r}]:
    sys.exit(3)
''')
        result = self.run_helper('--profile', 'default')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls()[0], ['tool', 'install', SOURCE])


if __name__ == '__main__':
    unittest.main()
