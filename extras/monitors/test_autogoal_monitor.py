#!/usr/bin/env python3
"""Offline fleet snapshot regressions using an isolated Hermes home."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('autogoal_monitor', Path(__file__).with_name('autogoal_monitor.py'))
assert SPEC is not None and SPEC.loader is not None
monitor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(monitor)


class FleetTests(unittest.TestCase):
    def test_default_only_home_does_not_require_profiles_directory(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as home, \
                patch.dict(os.environ, {'HERMES_HOME': home}), patch.object(monitor, 'cards', return_value=[]):
            snapshot = monitor.fleet_snapshot()
            self.assertEqual(len(snapshot), 1)
            self.assertTrue(snapshot[0].startswith('bucket '))

    def test_only_visible_configured_profiles_are_scanned(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as home, \
                patch.dict(os.environ, {'HERMES_HOME': home}), patch.object(monitor, 'cards', return_value=[]):
            profiles = Path(home) / 'profiles'
            for name in ('.deleted', 'not-a-profile', 'project'):
                (profiles / name).mkdir(parents=True)
            (profiles / '.deleted/config.yaml').write_text('terminal:\n  cwd: /unused\n')
            workspace = Path(home) / 'workspace'
            workspace.mkdir()
            (workspace / 'BLOCKERS.md').write_text('fixture blocker')
            (profiles / 'project/config.yaml').write_text(f'terminal:\n  cwd: {workspace}\n')
            snapshot = monitor.fleet_snapshot()
            self.assertEqual(snapshot[1:], [f'blockers project {monitor.fhash(workspace / "BLOCKERS.md")}'])


if __name__ == '__main__':
    unittest.main()
