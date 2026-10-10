"""Run the skill installer against temporary repositories and profile homes."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'install-skills.sh'


class InstallSkillsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo with spaces'
        self.skill = self.repo / 'skills/example'
        (self.skill / 'scripts').mkdir(parents=True)
        (self.skill / 'SKILL.md').write_text('---\nname: example\n---\nExample\n')
        (self.skill / 'scripts/run.sh').write_text('#!/bin/sh\nexit 0\n')
        (self.skill / 'scripts/run.sh').chmod(0o755)
        (self.skill / '__pycache__').mkdir()
        (self.skill / '__pycache__/junk.pyc').touch()
        self.script = self.repo / SCRIPT.name
        if SCRIPT.exists():
            shutil.copy2(SCRIPT, self.script)
        self.home = self.root / 'hermes'
        for profile in ('coder', 'deleted'):
            directory = self.home / 'profiles' / profile
            directory.mkdir(parents=True)
            (directory / 'config.yaml').touch()
        (self.home / 'profiles/ghost').mkdir()
        (self.home / 'profiles/.deleted').mkdir()
        (self.home / 'profiles/.deleted/deleted').touch()
        self.env = dict(os.environ, HERMES_HOME=str(self.home))

    def run_installer(self, *args):
        return subprocess.run(['bash', str(self.script), *args], cwd=self.root,
                              env=self.env, text=True, capture_output=True)

    def test_installs_complete_skills_in_all_live_profiles(self):
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        for home in (self.home, self.home / 'profiles/coder'):
            target = home / 'skills/example'
            self.assertEqual((target / 'SKILL.md').read_bytes(), (self.skill / 'SKILL.md').read_bytes())
            self.assertTrue(os.access(target / 'scripts/run.sh', os.X_OK))
            self.assertFalse((target / '__pycache__').exists())
        for name in ('ghost', 'deleted'):
            self.assertFalse((self.home / 'profiles' / name / 'skills').exists())

    def test_dry_run_creates_nothing(self):
        result = self.run_installer('--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('coder', result.stdout)
        self.assertFalse((self.home / 'skills').exists())
        self.assertFalse((self.home / 'profiles/coder/skills').exists())

    def test_existing_edits_are_preserved_on_repeat_install(self):
        self.assertEqual(self.run_installer().returncode, 0)
        target = self.home / 'skills/example/SKILL.md'
        target.write_text('local edits')
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(target.read_text(), 'local edits')
        self.assertIn('2 skipped', result.stdout)

    def test_named_home_and_explicit_root(self):
        self.env['HERMES_HOME'] = str(self.home / 'profiles/coder')
        self.assertEqual(self.run_installer().returncode, 0)
        self.assertTrue((self.home / 'skills/example/SKILL.md').exists())
        other = self.root / 'other'
        other.mkdir()
        self.assertEqual(self.run_installer('--hermes-home', str(other)).returncode, 0)
        self.assertTrue((other / 'skills/example/SKILL.md').exists())

    def test_symlinked_destination_root_is_not_written(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (self.home / 'skills').symlink_to(outside, target_is_directory=True)
        result = self.run_installer()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertTrue((self.home / 'profiles/coder/skills/example/SKILL.md').exists())

    def test_shared_contracts_are_copied_and_existing_edits_preserved(self):
        shared = self.repo / 'skills/shared'
        shared.mkdir()
        for name in ('COMMON-CONTRACT.md', 'PLAN-HANDOFF.md', 'WORKTREE-ISOLATION.md'):
            (shared / name).write_text('Bundled contract\n')
        self.assertEqual(self.run_installer('--dry-run').returncode, 0)
        self.assertFalse((self.home / 'skills').exists())
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        for home in (self.home, self.home / 'profiles/coder'):
            self.assertEqual((home / 'skills/shared/COMMON-CONTRACT.md').read_text(),
                             'Bundled contract\n')
        target = self.home / 'skills/shared/COMMON-CONTRACT.md'
        target.write_text('local contract')
        self.assertEqual(self.run_installer().returncode, 0)
        self.assertEqual(target.read_text(), 'local contract')

    def test_incomplete_shared_support_prevents_partial_install(self):
        (self.repo / 'skills/shared').mkdir()
        result = self.run_installer()
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.home / 'skills').exists())

    def test_invalid_source_prevents_partial_install(self):
        invalid = self.repo / 'skills/broken'
        invalid.mkdir()
        result = self.run_installer()
        self.assertEqual(result.returncode, 1)
        self.assertIn('SKILL.md', result.stderr)
        self.assertFalse((self.home / 'skills').exists())


if __name__ == '__main__':
    unittest.main()
