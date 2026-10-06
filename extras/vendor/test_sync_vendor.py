#!/usr/bin/env python3
"""Offline vendor CLI regressions; never fetch or modify the real vendor tree."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('sync_vendor', Path(__file__).with_name('sync_vendor.py'))
assert SPEC is not None and SPEC.loader is not None
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


class PinTests(unittest.TestCase):
    def check_fetch_ref(self, options, expected_ref):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as tmp:
            manifest = Path(tmp) / 'manifest.json'
            manifest.write_text(json.dumps({'sources': [
                {'name': 'fixture', 'repo': 'owner/repo', 'ref': 'old-commit', 'skills': ['skill']}
            ]}))
            refs = []

            def fetch(source, directory):
                refs.append(source.get('ref'))
                return Path(directory), 'new-commit'

            with patch.object(sync, 'MANIFEST', manifest), patch.object(sync, 'fetch', side_effect=fetch), \
                    patch.object(sync, 'install', return_value=['skill']), \
                    patch('sys.argv', ['sync_vendor.py', *options]), contextlib.redirect_stdout(io.StringIO()):
                sync.main()
            self.assertEqual(refs, [expected_ref])
            persisted_ref = 'new-commit' if '--pin' in options and '--dry-run' not in options else 'old-commit'
            self.assertEqual(json.loads(manifest.read_text())['sources'][0]['ref'], persisted_ref)

    def test_pin_fetches_head_instead_of_existing_pin(self):
        self.check_fetch_ref(['--pin'], 'HEAD')

    def test_normal_sync_preserves_existing_pin(self):
        self.check_fetch_ref([], 'old-commit')

    def test_pin_dry_run_fetches_head_without_rewriting_manifest(self):
        self.check_fetch_ref(['--pin', '--dry-run'], 'HEAD')


if __name__ == '__main__':
    unittest.main()
