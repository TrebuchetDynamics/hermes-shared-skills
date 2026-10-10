"""Installer integration tests; the fake CLI never touches real Hermes profiles."""
import os
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'install-plugins.sh'
MANIFEST = ('https://hermes-agent.nousresearch.com/docs/plugins/omh all profiles\n'
            'https://hermes-agent.nousresearch.com/docs/plugins/bot-forge default profile only\n')


class InstallPluginsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo with spaces'
        (self.repo / 'plugins').mkdir(parents=True)
        self.script = self.repo / 'install-plugins.sh'
        if SCRIPT.exists():
            shutil.copy2(SCRIPT, self.script)
        for name in ('install-graphify.py', 'install-omh.py', 'bundle.py', 'plugin.yaml'):
            helper = SCRIPT.parent / name
            if helper.exists():
                shutil.copy2(helper, self.repo / name)
        shutil.copy2(SCRIPT.parent / 'plugins/defaults.json', self.repo / 'plugins/defaults.json')
        self.manifest = self.repo / 'plugins/PLUGINS.md'
        self.manifest.write_text(MANIFEST)
        self.hermes_root = self.root / 'hermes home'
        for name in ('coder', 'research', 'deleted'):
            profile = self.hermes_root / 'profiles' / name
            profile.mkdir(parents=True)
            (profile / 'config.yaml').write_text('')
        (self.hermes_root / 'profiles/ghost').mkdir()
        (self.hermes_root / 'profiles/.deleted').mkdir()
        (self.hermes_root / 'profiles/.deleted/deleted').touch()
        (self.hermes_root / 'active_profile').write_text('research')
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        fake = self.bin / 'hermes'
        fake.write_text('''#!/bin/bash
printf '%s|%s\\n' "$HERMES_HOME" "$*" >> "$CALL_LOG"
[[ "${FAIL_PROFILE:-}" != "$2" ]]
''')
        fake.chmod(0o755)
        self.log = self.root / 'calls'
        self.env = dict(os.environ, PATH=str(self.bin) + ':' + os.environ['PATH'],
                        HERMES_HOME=str(self.hermes_root), CALL_LOG=str(self.log))

    def run_installer(self, *args):
        return subprocess.run(['bash', str(self.script), *args], cwd=self.root,
                              env=self.env, text=True, capture_output=True)

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_profile_scopes_and_running_outside_repository(self):
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [str(self.hermes_root) + '|' + command for command in (
            '-p default plugins install omh', '-p coder plugins install omh',
            '-p research plugins install omh', '-p default plugins install bot-forge')])

    def test_dry_run_never_invokes_cli(self):
        result = self.run_installer('--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [])
        self.assertIn('-p default plugins install bot-forge', result.stdout)
        self.assertIn('-p coder plugins install omh', result.stdout)

    def test_invalid_later_entry_prevents_every_install(self):
        self.manifest.write_text(MANIFEST + 'https://example.com/evil all profiles\n')
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])
        self.assertIn('line 3', result.stderr)

    def test_existing_install_is_not_overwritten(self):
        target = self.hermes_root / 'plugins/omh'
        target.mkdir(parents=True)
        (target / 'plugin.yaml').write_text('name: omh\n')
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.calls()), 3)
        self.assertFalse(any('|-p default plugins install omh' in c for c in self.calls()))

    def test_failure_is_reported_but_other_targets_are_attempted(self):
        self.env['FAIL_PROFILE'] = 'coder'
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.calls()), 4)
        self.assertIn('omh (coder)', result.stderr)

    def test_named_home_resolves_back_to_root(self):
        self.env['HERMES_HOME'] = str(self.hermes_root / 'profiles/coder')
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.calls()), 4)
        self.assertTrue(all(c.startswith(str(self.hermes_root) + '|') for c in self.calls()))

    def test_comments_crlf_duplicates_and_no_final_newline(self):
        self.manifest.write_bytes(('# comment\r\n\r\n' + MANIFEST + MANIFEST.rstrip()).encode())
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.calls()), 4)

    def test_missing_home_and_unknown_option_fail_before_cli(self):
        for args in [('--hermes-home', str(self.root / 'absent')), ('--typo',)]:
            with self.subTest(args=args):
                self.assertNotEqual(self.run_installer(*args).returncode, 0)
                self.assertEqual(self.calls(), [])

    def test_conflicting_scopes_and_empty_manifest_fail_before_cli(self):
        for manifest in ('# empty\n', MANIFEST +
                         'https://hermes-agent.nousresearch.com/docs/plugins/omh default profile only\n'):
            with self.subTest(manifest=manifest):
                self.manifest.write_text(manifest)
                result = self.run_installer()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(self.calls(), [])

    def test_incomplete_existing_directory_reports_failure(self):
        (self.hermes_root / 'plugins/omh').mkdir(parents=True)
        result = self.run_installer()
        self.assertEqual(result.returncode, 1)
        self.assertIn('existing path is not a plugin', result.stderr)
        self.assertEqual(len(self.calls()), 3)

    def test_explicit_home_overrides_environment(self):
        other = self.root / 'other home'
        other.mkdir()
        result = self.run_installer('--hermes-home', str(other))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [str(other) + '|-p default plugins install omh',
                                       str(other) + '|-p default plugins install bot-forge'])

    def test_github_plugin_url_and_existing_install(self):
        self.manifest.write_text('https://github.com/dietrichgebert/ponytail all profiles\n')
        target = self.hermes_root / 'plugins/ponytail'
        target.mkdir(parents=True)
        (target / 'plugin.yaml').touch()
        (target.parent / '.install-metadata.json').write_text(json.dumps({
            'ponytail': {'source': 'https://github.com/dietrichgebert/ponytail.git'}}))
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [str(self.hermes_root) + '|' + command for command in (
            '-p coder plugins install https://github.com/dietrichgebert/ponytail',
            '-p research plugins install https://github.com/dietrichgebert/ponytail')])

    def test_skill_repository_installs_each_skill_per_profile(self):
        self.manifest.write_text('skills https://github.com/addyosmani/agent-skills all profiles\n')
        git = self.bin / 'git'
        git.write_text('''#!/bin/bash
dest=${@: -1}
mkdir -p "$dest/skills/build" "$dest/skills/review"
touch "$dest/skills/build/SKILL.md" "$dest/skills/review/SKILL.md"
''')
        git.chmod(0o755)
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.calls()), 6)
        self.assertIn(str(self.hermes_root) +
                      '|-p coder skills install addyosmani/agent-skills/skills/build --yes', self.calls())
        self.assertIn(str(self.hermes_root) +
                      '|-p default skills install addyosmani/agent-skills/skills/review --yes', self.calls())

    def test_github_installed_name_comes_from_provenance(self):
        self.manifest.write_text('https://github.com/owner/repo default profile only\n')
        target = self.hermes_root / 'plugins/different-name'
        target.mkdir(parents=True)
        (target / 'plugin.yaml').touch()
        (target.parent / '.install-metadata.json').write_text(json.dumps({
            'different-name': {'source': 'https://github.com/owner/repo.git'}}))
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [])

    def test_unrelated_github_basename_is_not_treated_as_installed(self):
        self.manifest.write_text('https://github.com/owner/repo default profile only\n')
        target = self.hermes_root / 'plugins/repo'
        target.mkdir(parents=True)
        (target / 'plugin.yaml').touch()
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.calls()), 1)

    def test_graphify_cli_is_not_sent_to_plugin_installer(self):
        self.manifest.write_text('https://github.com/Graphify-Labs/graphify all profiles\n' + MANIFEST)
        result = self.run_installer('--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('graphify', result.stdout.lower())
        self.assertEqual(len(self.calls()), 0)

    def test_enable_and_dependency_consent_are_explicit_flags(self):
        result = self.run_installer('--enable', '--yes-deps')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.calls()), 4)
        self.assertTrue(all(c.endswith('--enable --yes-deps') for c in self.calls()))

    def test_setup_dispatches_omh_with_all_selected_profiles(self):
        helper = self.repo / 'install-omh.py'
        helper.write_text('import os,sys\nfrom pathlib import Path\n'
                          'with Path(os.environ["CALL_LOG"]).open("a") as f: f.write("omh-setup|" + "|".join(sys.argv[1:]) + "\\n")\n')
        result = self.run_installer('--setup')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('omh-setup|--hermes-home|' + str(self.hermes_root) +
                      '|--profile|default|--profile|coder|--profile|research', self.calls())

    def test_omh_setup_never_bypasses_a_failed_native_install(self):
        self.env['FAIL_PROFILE'] = 'coder'
        (self.repo / 'install-omh.py').write_text('raise RuntimeError("setup must not run")\n')
        result = self.run_installer('--setup')
        self.assertEqual(result.returncode, 1)
        self.assertNotIn('setup must not run', result.stderr)

    def test_setup_applies_gateway_default_only_where_bundle_is_installed(self):
        self.manifest.write_text('https://hermes-agent.nousresearch.com/docs/plugins/bot-forge default profile only\n')
        plugin = self.hermes_root / 'profiles/coder/plugins/hermes-toolset'
        plugin.mkdir(parents=True)
        (plugin / 'plugin.yaml').write_text('name: hermes-toolset\n')
        result = self.run_installer('--setup')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(self.hermes_root) + '|-p coder config set plugins.entries.hermes-toolset.allow_gateway_injection true', self.calls())
        self.assertIn(str(self.hermes_root) + '|-p default config set plugins.entries.hermes-toolset.allow_gateway_injection true', self.calls())

    def test_setup_disables_command_prompts_only_for_installed_bundle_profiles(self):
        self.manifest.write_text('https://hermes-agent.nousresearch.com/docs/plugins/bot-forge default profile only\n')
        plugin = self.hermes_root / 'profiles/coder/plugins/hermes-toolset'
        plugin.mkdir(parents=True)
        (plugin / 'plugin.yaml').write_text('name: hermes-toolset\n')
        preview = self.run_installer('--setup', '--dry-run')
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn('command approvals=off (coder)', preview.stdout)
        self.assertEqual(self.calls(), [])
        result = self.run_installer('--setup')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(self.hermes_root) + '|-p coder config set approvals.mode off', self.calls())
        self.assertIn(str(self.hermes_root) + '|-p default config set approvals.mode off', self.calls())

    def test_bundle_only_installs_and_enables_every_live_profile_idempotently(self):
        preview = self.run_installer('--bundle-only', '--dry-run')
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertEqual(self.calls(), [])
        self.assertFalse((self.hermes_root / 'plugins').exists())
        for _ in range(2):
            result = self.run_installer('--bundle-only')
            self.assertEqual(result.returncode, 0, result.stderr)
        for name, home in [('default', self.hermes_root),
                           ('coder', self.hermes_root / 'profiles/coder'),
                           ('research', self.hermes_root / 'profiles/research')]:
            self.assertEqual((home / 'plugins/hermes-toolset').resolve(), self.repo)
            self.assertIn(str(self.hermes_root) + f'|-p {name} plugins enable hermes-toolset', self.calls())
        self.assertFalse((self.hermes_root / 'profiles/deleted/plugins').exists())
        self.assertFalse((self.hermes_root / 'profiles/ghost/plugins').exists())
        self.assertFalse(any('plugins install' in c or 'skills install' in c for c in self.calls()))

    def test_bundle_install_preserves_conflicting_existing_path(self):
        target = self.hermes_root / 'profiles/coder/plugins/hermes-toolset'
        target.mkdir(parents=True)
        marker = target / 'user-file'
        marker.write_text('preserve')
        result = self.run_installer('--bundle-only')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(marker.read_text(), 'preserve')
        self.assertFalse(any('|-p coder plugins enable' in c for c in self.calls()))

    def test_permissions_are_applied_before_activation_for_every_profile(self):
        result = self.run_installer('--bundle-only')
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        for profile in ('default', 'coder', 'research'):
            prefix = str(self.hermes_root) + f'|-p {profile} '
            enabled = calls.index(prefix + 'plugins enable hermes-toolset')
            for setting in ('plugins.entries.hermes-toolset.allow_gateway_injection true',
                            'approvals.mode off', 'approvals.destructive_slash_confirm false',
                            'approvals.mcp_reload_confirm false', 'skills.disabled []',
                            'skills.platform_disabled {}'):
                self.assertLess(calls.index(prefix + 'config set ' + setting), enabled)

    def test_skill_dry_run_does_not_clone_or_install(self):
        self.manifest.write_text('skills https://github.com/addyosmani/agent-skills all profiles\n')
        git = self.bin / 'git'
        git.write_text('#!/bin/bash\necho git >> "$CALL_LOG"\nexit 1\n')
        git.chmod(0o755)
        result = self.run_installer('--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [])
        self.assertIn('addyosmani/agent-skills', result.stdout)
        self.assertIn('research', result.stdout)

    def test_skill_clone_failure_is_reported(self):
        self.manifest.write_text('skills https://github.com/addyosmani/agent-skills all profiles\n')
        git = self.bin / 'git'
        git.write_text('#!/bin/bash\nexit 1\n')
        git.chmod(0o755)
        result = self.run_installer()
        self.assertEqual(result.returncode, 1)
        self.assertIn('clone', result.stderr.lower())
        self.assertEqual(self.calls(), [])

    def test_empty_skill_repository_reports_failure(self):
        self.manifest.write_text('skills https://github.com/owner/empty all profiles\n')
        git = self.bin / 'git'
        git.write_text('#!/bin/bash\nmkdir -p "${@: -1}/skills"\n')
        git.chmod(0o755)
        result = self.run_installer()
        self.assertEqual(result.returncode, 1)
        self.assertIn('no skills/', result.stderr)
        self.assertEqual(self.calls(), [])

    def test_skill_install_failures_do_not_stop_other_profiles(self):
        self.manifest.write_text('skills https://github.com/owner/pack all profiles\n')
        git = self.bin / 'git'
        git.write_text('#!/bin/bash\nmkdir -p "${@: -1}/skills/build"\ntouch "${@: -1}/skills/build/SKILL.md"\n')
        git.chmod(0o755)
        self.env['FAIL_PROFILE'] = 'coder'
        result = self.run_installer()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(self.calls()), 3)
        self.assertIn('skill build (coder)', result.stderr)


if __name__ == '__main__':
    unittest.main()
