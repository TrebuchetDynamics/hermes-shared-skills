"""Offline integration coverage for the Graphify profile adapter."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'install-graphify.py'
GRAPHIFY = '''import os, sys
from pathlib import Path
assert sys.argv[1:] == ['install', '--platform', 'hermes', '--project']
assert os.environ['HOME'] == os.environ['EXPECTED_HOME']
if os.environ.get('FAIL_GRAPHIFY'):
    sys.exit(12)
skill = Path('.hermes/skills/graphify')
(skill / 'references').mkdir(parents=True)
(skill / 'SKILL.md').write_text('Graphify skill')
(skill / 'references/usage.md').write_text('Usage reference')
Path('AGENTS.md').write_text('Generated staging instructions')
'''


class InstallGraphifyTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.home = self.root / 'hermes'
        (self.home / 'profiles/coder').mkdir(parents=True)
        (self.home / 'profiles/coder/config.yaml').touch()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.env = dict(os.environ, PATH=str(self.bin), EXPECTED_HOME=os.environ['HOME'])
        self.command('graphify', GRAPHIFY)

    def command(self, name, body):
        path = self.bin / name
        path.write_text(f'#!{sys.executable}\n' + body)
        path.chmod(0o755)
        return path

    def run_adapter(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), '--hermes-home', str(self.home),
                               *args], cwd=self.root, env=self.env, capture_output=True, text=True)

    def test_installs_complete_tree_in_selected_profiles_only(self):
        result = self.run_adapter('--profile', 'default', '--profile', 'coder')
        self.assertEqual(result.returncode, 0, result.stderr)
        for home in (self.home, self.home / 'profiles/coder'):
            self.assertEqual((home / 'skills/graphify/SKILL.md').read_text(), 'Graphify skill')
            self.assertEqual((home / 'skills/graphify/references/usage.md').read_text(), 'Usage reference')
            self.assertEqual([p.name for p in (home / 'skills').iterdir()], ['graphify'])
        self.assertFalse((self.root / 'AGENTS.md').exists())

    def test_dry_run_has_no_mutations_or_subprocesses(self):
        self.command('graphify', "raise RuntimeError('must not execute')")
        before = sorted(str(p) for p in self.root.rglob('*'))
        result = self.run_adapter('--profile', 'default', '--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('graphify', result.stdout)
        self.assertEqual(before, sorted(str(p) for p in self.root.rglob('*')))

    def test_existing_skill_is_not_overwritten(self):
        target = self.home / 'skills/graphify'
        target.mkdir(parents=True)
        (target / 'SKILL.md').write_text('Local edits')
        self.command('graphify', "raise RuntimeError('generation is unnecessary')")
        result = self.run_adapter('--profile', 'default')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((target / 'SKILL.md').read_text(), 'Local edits')

    def test_uv_install_discovers_bin_outside_path(self):
        (self.bin / 'graphify').unlink()
        tool_bin = self.root / 'tool-bin'
        self.env['UV_TOOL_BIN_DIR'] = str(tool_bin)
        self.env['GRAPHIFY_FIXTURE'] = GRAPHIFY
        self.command('uv', '''import os, sys
from pathlib import Path
bin_dir = Path(os.environ['UV_TOOL_BIN_DIR'])
if sys.argv[1:] == ['tool', 'install', 'graphifyy']:
    bin_dir.mkdir()
    executable = bin_dir / 'graphify'
    executable.write_text('#!' + sys.executable + '\\n' + os.environ['GRAPHIFY_FIXTURE'])
    executable.chmod(0o755)
elif sys.argv[1:] == ['tool', 'dir', '--bin']:
    print(bin_dir)
else:
    sys.exit(13)
''')
        result = self.run_adapter('--profile', 'coder')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.home / 'profiles/coder/skills/graphify/SKILL.md').exists())
        self.assertFalse((self.home / 'skills').exists())
        self.assertIn(str(tool_bin), result.stdout)

    def test_unusable_existing_destinations_fail_without_overwriting(self):
        for kind in ('file', 'dangling-link', 'missing-skill', 'skill-directory'):
            with self.subTest(kind=kind):
                self.home = self.root / kind
                (self.home / 'profiles/coder').mkdir(parents=True)
                (self.home / 'profiles/coder/config.yaml').touch()
                target = self.home / 'skills/graphify'
                target.parent.mkdir()
                if kind == 'file':
                    target.write_text('Keep this file')
                elif kind == 'dangling-link':
                    target.symlink_to(self.root / 'missing')
                else:
                    target.mkdir()
                    (target / 'local.txt').write_text('Keep local contents')
                    if kind == 'skill-directory':
                        (target / 'SKILL.md').mkdir()
                for extra in ((), ('--dry-run',)):
                    result = self.run_adapter('--profile', 'default', '--profile', 'coder', *extra)
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn('SKILL.md', result.stderr)
                    self.assertFalse((self.home / 'profiles/coder/skills').exists())
                if kind == 'file':
                    self.assertEqual(target.read_text(), 'Keep this file')
                    target.unlink()
                elif kind == 'dangling-link':
                    self.assertEqual(target.readlink(), self.root / 'missing')
                    target.unlink()
                else:
                    self.assertEqual((target / 'local.txt').read_text(), 'Keep local contents')
                    (target / 'local.txt').unlink()
                    if kind == 'skill-directory':
                        (target / 'SKILL.md').rmdir()
                    target.rmdir()

    def test_invalid_profile_is_rejected_before_any_install(self):
        for profile in ('../escape', 'missing', '.', '/tmp'):
            with self.subTest(profile=profile):
                result = self.run_adapter('--profile', 'default', '--profile', profile)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.home / 'skills').exists())

    def test_symlinked_skills_root_is_rejected(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (self.home / 'skills').symlink_to(outside, target_is_directory=True)
        result = self.run_adapter('--profile', 'default')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])

    def test_failed_generation_leaves_no_partial_skill(self):
        self.env['FAIL_GRAPHIFY'] = '1'
        result = self.run_adapter('--profile', 'default')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.home / 'skills/graphify').exists())
        self.assertIn('12', result.stderr)

    def test_missing_cli_and_uv_has_useful_error(self):
        (self.bin / 'graphify').unlink()
        result = self.run_adapter('--profile', 'default')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('uv', result.stderr)


if __name__ == '__main__':
    unittest.main()
