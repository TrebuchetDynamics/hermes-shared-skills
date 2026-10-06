import importlib.util
from pathlib import Path
import tempfile
import unittest
import os

os.environ.setdefault('TMPDIR', os.path.join(os.environ.get('HERMES_HOME') or os.path.expanduser('~/.hermes'), 'cache/scratch'))


class CollectorTest(unittest.TestCase):
    def load(self):
        path = Path(__file__).with_name('collect.py')
        self.assertTrue(path.exists(), 'file-derived fleet blocker collector is not implemented')
        spec = importlib.util.spec_from_file_location('collect', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_empty_canonical_file_yields_no_invented_user_actions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'BLOCKERS.md').write_text('# BLOCKERS\n\nThis file contains only hard blockers that require user action.\n\n## Active\n\nNone.\n\n## Resolved\n\nNone.\n')
            result = self.load().collect([{'repository': 'fixture', 'root': str(root)}])
            self.assertEqual(result['recorded_active'], [])
            self.assertEqual(result['issues'], [])
            self.assertEqual(result['coverage']['read'], 1)
            self.assertFalse(result['semantic_verification_performed'])


    def test_only_active_entries_are_collected_with_exact_actions(self):
        text = '''# BLOCKERS

This file contains only hard blockers that require user action.

## Active

### BLK-20261005-001 — Choose persistence

- Status: ACTIVE
- Category: USER_DECISION
- Owner: user
- Task/Card: t_fixture
- Blocked scope: Persistence implementation only
- Why blocked: Accepted requirements do not select a backend.
- Evidence: PRD.md and adr/persistence.md
- User action required: Choose SQLite or PostgreSQL.
- Resume condition: The selection is recorded.
- Created: 2026-10-05T00:00:00Z
- Last checked: 2026-10-05T00:00:00Z

## Resolved

### BLK-20261004-001 — Tool installed

- Status: RESOLVED
- Category: USER_INPUT
- Resolved: 2026-10-05T00:00:00Z
- Resolution: Required artifact provided.
- Evidence: receipt.json
'''
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / 'BLOCKERS.md'
            path.write_text(text)
            before = path.read_bytes()
            result = self.load().collect([{'repository': 'fixture', 'root': str(root)}])
            self.assertEqual(len(result['recorded_active']), 1)
            entry = result['recorded_active'][0]
            self.assertEqual(entry['id'], 'BLK-20261005-001')
            self.assertEqual(entry['category'], 'USER_DECISION')
            self.assertEqual(entry['user_action_required'], 'Choose SQLite or PostgreSQL.')
            self.assertEqual(entry['consequence_of_waiting'], 'Persistence implementation only')
            self.assertEqual(entry['verification'], 'REQUIRES_REEVALUATION')
            self.assertEqual(result['issues'], [])
            self.assertEqual(path.read_bytes(), before)


    def test_optional_impact_is_preserved_without_attesting_validity(self):
        text = '''# BLOCKERS

## Active

### BLK-20261005-001 — Choose feature path
- Status: ACTIVE
- Category: USER_DECISION
- Impact: SCOPE_BLOCKING
- Owner: user
- Task/Card: t_fixture
- Blocked scope: One feature only
- Why blocked: No selected path.
- Evidence: PRD.md
- User action required: Choose path A or B.
- Resume condition: Choice recorded.
- Created: 2026-10-05T00:00:00Z
- Last checked: 2026-10-05T00:00:00Z

## Resolved

None.
'''
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'BLOCKERS.md'
            path.write_text(text)
            before = path.read_bytes()
            result = self.load().collect([{'repository': 'fixture', 'root': folder}])
            self.assertEqual(result['recorded_active'][0].get('impact'), 'SCOPE_BLOCKING')
            self.assertEqual(result['issues'], [])
            self.assertFalse(result['semantic_verification_performed'])
            self.assertEqual(path.read_bytes(), before)

    def test_invalid_optional_impact_is_rejected(self):
        text = '''# BLOCKERS

## Active

### BLK-20261005-001 — Choose feature path
- Status: ACTIVE
- Category: USER_DECISION
- Impact: IMPORTANT
- Owner: user
- Task/Card: t_fixture
- Blocked scope: Feature
- Why blocked: No selected path.
- Evidence: PRD.md
- User action required: Choose path A or B.
- Resume condition: Choice recorded.
- Created: 2026-10-05T00:00:00Z
- Last checked: 2026-10-05T00:00:00Z

## Resolved

None.
'''
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'BLOCKERS.md'
            path.write_text(text)
            result = self.load().collect([{'repository': 'fixture', 'root': folder}])
            self.assertEqual(result['recorded_active'], [])
            self.assertTrue(any('invalid impact' in item['issue'] for item in result['issues']))

    def test_ordinary_todo_content_is_not_silently_reported_as_empty(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'BLOCKERS.md').write_text('# BLOCKERS\n\n## Active\n\n- Fix failing tests\n\n## Resolved\n\nNone.\n')
            result = self.load().collect([{'repository': 'fixture', 'root': str(root)}])
            self.assertEqual(result['recorded_active'], [])
            self.assertTrue(result['issues'])

    def test_unavailable_file_is_unknown_not_empty_success(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.load().collect([{'repository': 'missing', 'root': folder}])
            self.assertEqual(result['coverage']['read'], 0)
            self.assertTrue(result['issues'])

    def test_duplicate_ids_and_invalid_category_are_rejected(self):
        text = '# BLOCKERS\n\n## Active\n\n### BLK-20261005-001 — First\n- Status: ACTIVE\n- Category: BUG\n\n### BLK-20261005-001 — Duplicate\n- Status: ACTIVE\n- Category: BUG\n\n## Resolved\n\nNone.\n'
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'BLOCKERS.md').write_text(text)
            result = self.load().collect([{'repository': 'fixture', 'root': str(root)}])
            self.assertEqual(result['recorded_active'], [])
            issues = ' '.join(item['issue'] for item in result['issues'])
            self.assertIn('duplicate blocker ID', issues)
            self.assertIn('invalid hard-blocker category', issues)
            self.assertIn('missing', issues)


    def test_duplicate_fields_are_entry_local_defects(self):
        active = '''### BLK-20261005-001 — Choose persistence
- Status: ACTIVE
- Category: USER_DECISION
- Owner: user
- Task/Card: t_fixture
- Blocked scope: Persistence
- Why blocked: No backend selected.
- Evidence: PRD.md
- User action required: Choose SQLite or PostgreSQL.
- Resume condition: Decision recorded.
- Created: 2026-10-05T00:00:00Z
- Last checked: 2026-10-05T00:00:00Z
'''
        resolved = '''### BLK-20261004-001 — Historical record
- Status: RESOLVED
- Category: USER_INPUT
- Resolved: 2026-10-05T00:00:00Z
- Resolution: Artifact supplied.
- Evidence: receipt.json
'''
        second = active.replace('BLK-20261005-001', 'BLK-20261005-002')
        for section in ['Active', 'Resolved']:
            with self.subTest(section=section), tempfile.TemporaryDirectory() as folder:
                text = '# BLOCKERS\n\n## Active\n' + active
                if section == 'Active':
                    text += '- Evidence: duplicate.md\n'
                text += second + '\n## Resolved\n' + resolved
                if section == 'Resolved':
                    text += '- Evidence: duplicate.md\n'
                (Path(folder) / 'BLOCKERS.md').write_text(text)
                result = self.load().collect([{'repository': 'fixture', 'root': folder}])
                expected = ['BLK-20261005-002'] if section == 'Active' else ['BLK-20261005-001', 'BLK-20261005-002']
                self.assertEqual([entry['id'] for entry in result['recorded_active']], expected)
                self.assertTrue(any('duplicate field' in issue['issue'] for issue in result['issues']))

    def test_invalid_resolved_history_does_not_hide_valid_active_entries(self):
        text = '''# BLOCKERS

## Active

### BLK-20261005-001 — Choose persistence

- Status: ACTIVE
- Category: USER_DECISION
- Owner: user
- Task/Card: N/A
- Blocked scope: Persistence
- Why blocked: No accepted backend decision.
- Evidence: PRD.md
- User action required: Choose SQLite or PostgreSQL.
- Resume condition: Decision recorded.
- Created: 2026-10-05T00:00:00Z
- Last checked: 2026-10-05T00:00:00Z

## Resolved

### BLK-20261004-001 — Historical malformed record

- Status: RESOLVED
- Category: USER_INPUT (extra explanation)
- Resolution: Artifact supplied.
- Evidence: receipt.json
'''
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'BLOCKERS.md').write_text(text)
            result = self.load().collect([{'repository': 'fixture', 'root': str(root)}])
            self.assertEqual(len(result['recorded_active']), 1)
            self.assertEqual(result['recorded_active'][0]['id'], 'BLK-20261005-001')
            self.assertTrue(result['issues'])


if __name__ == '__main__':
    unittest.main()
