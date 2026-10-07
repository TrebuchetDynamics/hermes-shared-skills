#!/usr/bin/env python3
"""Offline contract for the pinned, Hermes-adapted implement-spec import."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('sync_vendor', HERE / 'sync_vendor.py')
assert SPEC is not None and SPEC.loader is not None
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


class ImplementSpecTests(unittest.TestCase):
    def test_pinned_import_preserves_upstream_and_adds_safety_overlay(self):
        sources = json.loads((HERE / 'manifest.json').read_text())['sources']
        source = next(s for s in sources if s['name'] == 'mattpocock')
        self.assertIn('skills/engineering/implement-spec', source['skills'])
        self.assertEqual(source['ref'], '6fd947921b935b7e1e69293a200400f0fdd5c15f')
        self.assertEqual(source['license'], 'MIT')
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as tmp:
            root = Path(tmp)
            upstream = root / 'upstream'
            skill = upstream / 'skills/engineering/implement-spec'
            skill.mkdir(parents=True)
            text = ('---\nname: implement-spec\ndescription: "Implement a ticket graph."\n'
                    'disable-model-invocation: true\n---\n\nUpstream fixture.\n')
            (skill / 'SKILL.md').write_text(text)
            (upstream / 'LICENSE').write_text('MIT fixture attribution\n')
            fixture_source = {**source, 'skills': ['skills/engineering/implement-spec']}
            with patch.object(sync, 'VENDOR', root / 'vendor'), \
                    patch.object(sync, 'bundled_names', return_value=set()):
                installed = sync.install(fixture_source, upstream, source['ref'], False)
            self.assertEqual(installed, ['implement-spec'])
            out = root / 'vendor/mattpocock'
            adapted = (out / 'implement-spec/SKILL.md').read_text()
            self.assertTrue(adapted.startswith(text))
            for rule in ['Explicit invocation only', 'git worktree', 'Never reset',
                         'test-driven-development', 'native review',
                         'No automatic push', 'user-facing result']:
                self.assertIn(rule, adapted)
            self.assertEqual((out / 'LICENSE').read_text(), 'MIT fixture attribution\n')
            self.assertIn(source['ref'], (out / 'UPSTREAM.md').read_text())


if __name__ == '__main__':
    unittest.main()
