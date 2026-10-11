import argparse
import importlib.util
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT / 'bundle.py').exists(), 'Missing bundle integration')
        spec = importlib.util.spec_from_file_location('bundle_test', ROOT / 'bundle.py')
        self.bundle = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.bundle)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'SKILL.md'
        self.path.write_text('skill')
        self.commands = {'ponytail-review': {'plugin': 'ponytail', 'handler': object()}}
        self.skills = ['bot-forge:bot-forge', 'ponytail:ponytail-review', 'hermes-speech:configure-allmodels-speech']
        self.manager = types.SimpleNamespace(
            list_plugin_skill_metadata=lambda: [{'name': n} for n in self.skills],
            find_plugin_skill=lambda n: self.path,
        )
        self.ctx = types.SimpleNamespace(
            register_command=self.register_command,
            get_config=lambda key, default=None: default,
        )
        self.messages = []
        stubs = {
            'hermes_cli.plugins': types.SimpleNamespace(get_plugin_manager=lambda: self.manager,
                                                        get_plugin_commands=lambda: self.commands),
            'hermes_cli.commands': types.SimpleNamespace(resolve_command=lambda n: object() if n == 'help' else None),
        }
        p = patch.dict('sys.modules', stubs)
        p.start()
        self.addCleanup(p.stop)

    def register_command(self, name, handler, description='', args_hint=''):
        self.commands[name] = {'handler': handler, 'plugin': 'hermes-toolset'}

    def invoke(self, ctx, name, path, args, namespace='hermes-toolset'):
        self.messages.append((namespace, name, args))

    def test_imported_skills_get_commands_without_overwriting_native_handlers(self):
        native = self.commands['ponytail-review']['handler']
        self.bundle.register_imported_skills(self.ctx, self.invoke)
        self.assertIs(self.commands['ponytail-review']['handler'], native)
        self.commands['bot-forge']['handler']('make a bot')
        self.assertEqual(self.messages, [('bot-forge', 'bot-forge', 'make a bot')])
        self.assertIn('configure-allmodels-speech', self.commands)

    def test_builtin_collision_uses_plugin_prefix(self):
        self.skills = ['bot-forge:help']
        self.bundle.register_imported_skills(self.ctx, self.invoke)
        self.assertNotIn('help', self.commands)
        self.commands['bot-forge-help']['handler']('details')
        self.assertEqual(self.messages, [('bot-forge', 'help', 'details')])

    def test_long_imported_skill_names_have_stable_telegram_safe_alias(self):
        self.skills = ['bot-forge:' + 'long-name-' * 6]
        first = self.bundle.register_imported_skills(self.ctx, self.invoke)
        name = next(iter(first))
        self.assertLessEqual(len(name), 32)
        self.assertRegex(name, r'^[a-z0-9-]+$')
        self.commands.clear()
        self.assertEqual(first, self.bundle.register_imported_skills(self.ctx, self.invoke))

    def test_unlisted_plugin_skills_are_not_exported(self):
        self.skills = ['other:secret']
        self.assertEqual(self.bundle.register_imported_skills(self.ctx, self.invoke), {})

    def test_setup_runs_bundled_installer_with_explicit_flags_without_shell_interpolation(self):
        args = argparse.Namespace(action='setup', dry_run=True, hermes_home='/tmp/home with spaces', yes_deps=True)
        with patch.object(self.bundle.subprocess, 'run', return_value=types.SimpleNamespace(returncode=7)) as run:
            self.assertEqual(self.bundle.handle_cli(args), 7)
        self.assertEqual(run.call_args.args[0], ['bash', str(ROOT / 'install-plugins.sh'),
                                               '--enable', '--setup', '--dry-run',
                                               '--hermes-home', '/tmp/home with spaces', '--yes-deps'])
        self.assertNotIn('shell', run.call_args.kwargs)

    def test_setup_parser_requires_action_and_supports_doctor(self):
        parser = argparse.ArgumentParser()
        self.bundle.setup_parser(parser)
        args = parser.parse_args(['doctor', '--json'])
        self.assertEqual(args.action, 'doctor')
        self.assertTrue(args.json)

    def test_setup_forwards_hindsight_connection_file(self):
        parser = argparse.ArgumentParser()
        self.bundle.setup_parser(parser)
        args = parser.parse_args(['setup', '--hindsight-config', '/tmp/connection file.json'])
        with patch.object(self.bundle.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0)) as run:
            self.assertEqual(self.bundle.handle_cli(args), 0)
        self.assertEqual(run.call_args.args[0][-2:], ['--hindsight-config', '/tmp/connection file.json'])

    def test_missing_imports_track_partial_install_and_removed_commands(self):
        home = Path(self.tmp.name)
        self.bundle.record_skill_repository(home, 'https://github.com/addyosmani/agent-skills', ['alpha', 'beta'])
        missing, unchecked = self.bundle.missing_skill_imports(home, {'alpha', 'graphify', 'omh-plan'})
        self.assertEqual(missing, ['beta'])
        self.assertEqual(unchecked, [])

    def test_unattempted_skill_repository_is_not_reported_healthy(self):
        missing, unchecked = self.bundle.missing_skill_imports(Path(self.tmp.name), {'graphify', 'omh-plan'})
        self.assertEqual(missing, [])
        self.assertEqual(unchecked, ['https://github.com/addyosmani/agent-skills'])

    def test_named_profiles_require_bot_forge_too(self):
        self.manager.home_path = Path(self.tmp.name) / 'profiles/coder'
        self.manager.discover_and_load = lambda: None
        self.manager.list_plugins = lambda: []
        modules = {
            'hermes_cli.commands_platforms': types.SimpleNamespace(
                telegram_menu_commands=lambda **kw: ([], 0), telegram_menu_max_commands=lambda: 100),
            'agent.skill_commands': types.SimpleNamespace(get_skill_commands=lambda: {}),
        }
        with patch.dict('sys.modules', modules):
            report = self.bundle.inventory()
        self.assertIn('bot-forge', report['missing_plugins'])

    def test_hindsight_category_provider_is_not_reported_as_a_disabled_general_plugin(self):
        self.manager.home_path = Path(self.tmp.name)
        self.manager.discover_and_load = lambda: None
        self.manager.list_plugins = lambda: [{'name': 'hindsight', 'kind': 'exclusive',
            'enabled': False, 'error': 'exclusive plugin — activate via <category>.provider config'}]
        modules = {
            'hermes_cli.commands_platforms': types.SimpleNamespace(
                telegram_menu_commands=lambda **kw: ([], 0), telegram_menu_max_commands=lambda: 100),
            'agent.skill_commands': types.SimpleNamespace(get_skill_commands=lambda: {}),
            'hermes_cli.config': types.SimpleNamespace(load_config_readonly=lambda: {'memory': {'provider': 'hindsight'}}),
            'plugins.memory': types.SimpleNamespace(load_memory_provider=lambda *a, **kw:
                types.SimpleNamespace(is_available=lambda: True)),
        }
        with patch.dict('sys.modules', modules):
            report = self.bundle.inventory()
        self.assertNotIn('hindsight', report['missing_plugins'])
        self.assertIsNone(report['plugins'][0]['error'])
        self.assertTrue(report['plugins'][0]['memory_provider'])

    def report(self):
        return {'plugins': [{'name': 'ponytail', 'version': '5.1.0', 'enabled': True,
                             'tools': 0, 'commands': 6, 'hooks': 2, 'error': None}],
                'plugin_skills': ['ponytail:ponytail', 'ponytail:ponytail-help'],
                'commands': [{'command': 'ponytail', 'telegram': 'ponytail', 'source': 'ponytail'},
                             {'command': 'repo-docs', 'telegram': 'repo_docs', 'source': 'hermes-toolset'}],
                'missing_plugins': [], 'missing_skills': ['blocked-skill'],
                'unchecked_skill_sources': [], 'telegram_menu_hidden': 12}

    def test_default_summary_reports_capabilities_and_gaps_without_command_dump(self):
        with patch.object(self.bundle, 'inventory', return_value=self.report()):
            output = self.bundle.list_commands('')
        self.assertIn('ponytail 5.1.0: loaded', output)
        self.assertIn('0 tools, 6 commands, 2 skills, 2 hooks', output)
        self.assertIn('blocked-skill', output)
        self.assertIn('/toolsets', output)
        self.assertNotIn('/repo-docs', output)

    def test_list_filter_shows_only_matches_and_distinct_telegram_aliases(self):
        with patch.object(self.bundle, 'inventory', return_value=self.report()):
            output = self.bundle.list_commands('list repo-docs')
            ponytail = self.bundle.list_commands('list ponytail')
        self.assertIn('/repo-docs (Telegram: /repo_docs)', output)
        self.assertNotIn('/ponytail —', output)
        self.assertNotIn('/ponytail /ponytail', ponytail)

    def test_summary_distinguishes_failed_disabled_and_missing_plugins(self):
        report = self.report()
        report['plugins'][0]['error'] = 'load failed'
        report['plugins'].append({'name': 'other', 'enabled': False})
        report['missing_plugins'] = ['absent']
        with patch.object(self.bundle, 'inventory', return_value=report):
            output = self.bundle.list_commands('')
        self.assertIn('ponytail 5.1.0: error', output)
        self.assertIn('load failed', output)
        self.assertIn('other: disabled', output)
        self.assertIn('absent', output)


if __name__ == '__main__':
    unittest.main()
