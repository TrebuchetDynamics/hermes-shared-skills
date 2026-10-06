#!/usr/bin/env python3
"""Offline regression tests for the shared skill catalog validator."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_skills import validate_catalog


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def skill(self, text, name='sample'):
        path = self.root / name / 'SKILL.md'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def test_valid_catalog(self):
        self.skill('---\nname: sample\ndescription: "Audit a repository: verify findings."\nplatforms: [linux]\n---\n# Workflow\nRun checks.\n')
        self.assertEqual(validate_catalog(self.root), [])

    def test_yaml_mapping_description_is_rejected(self):
        self.skill('---\nname: sample\ndescription: {unexpected: mapping}\n---\nBody\n')
        self.assertTrue(any('description' in e for e in validate_catalog(self.root)))

    def test_description_over_catalog_budget_is_rejected(self):
        self.skill('---\nname: sample\ndescription: ' + 'x' * 61 + '\n---\nBody\n')
        self.assertTrue(any('description' in e for e in validate_catalog(self.root)))

    def test_wrong_directory_name_is_rejected(self):
        self.skill('---\nname: other\ndescription: Useful workflow.\n---\nBody\n')
        self.assertTrue(any('directory' in e for e in validate_catalog(self.root)))

    def test_missing_body_is_rejected(self):
        self.skill('---\nname: sample\ndescription: Useful workflow.\n---\n')
        self.assertTrue(any('body' in e for e in validate_catalog(self.root)))

    def test_duplicate_yaml_keys_are_rejected(self):
        self.skill('---\nname: sample\nname: other\ndescription: Useful workflow.\n---\nBody\n')
        self.assertTrue(any('YAML' in e for e in validate_catalog(self.root)))

    def test_invalid_platform_is_rejected(self):
        self.skill('---\nname: sample\ndescription: Useful workflow.\nplatforms: [unknown]\n---\nBody\n')
        self.assertTrue(any('platforms' in e for e in validate_catalog(self.root)))

    def test_empty_catalog_is_not_success(self):
        self.assertTrue(any('No first-party skills' in e for e in validate_catalog(self.root)))

    def test_hidden_catalog_is_out_of_scope(self):
        self.skill('---\nname: sample\ndescription: Useful workflow.\n---\nBody\n')
        self.skill('not a skill', name='.hidden')
        self.assertEqual(validate_catalog(self.root), [])

    def test_symlinked_catalog_is_out_of_scope(self):
        self.skill('---\nname: sample\ndescription: Useful workflow.\n---\nBody\n')
        with tempfile.TemporaryDirectory() as outside:
            (Path(outside) / 'SKILL.md').write_text('not a skill')
            (self.root / 'external').symlink_to(outside, target_is_directory=True)
            self.assertEqual(validate_catalog(self.root), [])

    def test_vendor_catalog_is_out_of_scope(self):
        self.skill('---\nname: sample\ndescription: Useful workflow.\n---\nBody\n')
        vendor = self.root / 'vendor' / 'source' / 'broken'
        vendor.mkdir(parents=True)
        (vendor / 'SKILL.md').write_text('not a skill', encoding='utf-8')
        self.assertEqual(validate_catalog(self.root), [])


if __name__ == '__main__':
    unittest.main()
