"""Privacy redaction uses real temporary Git repositories and CLI processes."""
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name('goals.py')


class RedactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        subprocess.run(['git', 'init', str(self.repo)], check=True, capture_output=True)
        self.data = {'version': 1, 'goals': [{
            'id': 'G', 'title': 'Keep /home/example title', 'source': '/home/example/private/PRD.md#g',
            'status': 'met', 'tasks': ['T1'], 'priority': 1, 'depends_on': [],
            'evidence': [{'kind': 'executed', 'ref': 'python /home/example/private/check.py --flag',
                          'result': 'pass', 'ran_at': '2025-01-01T00:00:00Z'}]}],
            'tasks': [{'id': 'T1', 'goal': 'G', 'title': 'Task', 'status': 'done',
                       'section': 'Done', 'depends_on': []}]}
        (self.repo / 'goals.json').write_text(json.dumps(self.data))
        self.body = b'# TODO\r\n\r\n## Now\r\nUnrelated /home/example text\r\n'
        (self.repo / 'TODO.md').write_bytes(self.body)
        self.mapping = self.base / 'replacements.json'
        self.mapping.write_text(json.dumps({'/home/example/private': '<private-evidence>'}))
        self.archive = self.base / 'archive'

    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                              capture_output=True, text=True, timeout=15)

    def redact(self, *args):
        return self.cli('redact', self.repo, '--replacements-file', self.mapping,
                        '--archive-dir', self.archive, *args)

    def snapshot(self):
        return {n: (self.repo / n).read_bytes() for n in ('goals.json', 'TODO.md')}

    def test_redacts_only_metadata_archives_originals_and_labels_history(self):
        before = self.snapshot()
        result = self.redact()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads((self.repo / 'goals.json').read_text())
        expected = copy.deepcopy(self.data)
        expected['goals'][0]['source'] = '<private-evidence>/PRD.md#g'
        expected['goals'][0]['evidence'][0]['ref'] = 'python <private-evidence>/check.py --flag'
        expected['goals'][0]['evidence'][0]['redacted'] = True
        self.assertEqual(data, expected)
        todo = (self.repo / 'TODO.md').read_bytes()
        self.assertTrue(todo.startswith(self.body))
        self.assertIn(b'redacted historical evidence', todo)
        manifest_path, = self.archive.glob('*/manifest.json')
        manifest = json.loads(manifest_path.read_text())
        for name, blob in before.items():
            self.assertEqual((manifest_path.parent / name).read_bytes(), blob)
            self.assertEqual(manifest['sha256'][name], hashlib.sha256(blob).hexdigest())
        once = self.snapshot()
        self.assertEqual(self.redact().returncode, 0)
        self.assertEqual(self.snapshot(), once)
        self.assertEqual(len(list(self.archive.glob('*/manifest.json'))), 1)

    def test_archive_symlink_cannot_redirect_originals_inside_repository(self):
        token = self.cli('revision', self.repo).stdout.strip()
        self.archive.mkdir()
        (self.archive / token).symlink_to(self.repo, target_is_directory=True)
        before = self.snapshot()
        result = self.redact()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('archive', result.stderr)
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.repo / 'manifest.json').exists())

    def test_placeholder_cannot_reintroduce_private_prefix(self):
        self.mapping.write_text(json.dumps({'/home/example': 'redacted /home/example'}))
        before = self.snapshot()
        result = self.redact()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('placeholder', result.stderr)
        self.assertEqual(before, self.snapshot())

    def test_non_string_source_and_statuses_are_preserved(self):
        self.data['goals'][0]['source'] = {'path': '/home/example/private/PRD.md'}
        self.data['goals'][0]['status'] = 'partial'
        (self.repo / 'goals.json').write_text(json.dumps(self.data))
        result = self.redact()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads((self.repo / 'goals.json').read_text())
        self.assertEqual(data['goals'][0]['source'], self.data['goals'][0]['source'])
        self.assertEqual(data['goals'][0]['status'], 'partial')
        self.assertEqual(data['tasks'], self.data['tasks'])

    def test_expected_revision_refuses_before_archiving_or_writing(self):
        token = self.cli('revision', self.repo).stdout.strip()
        with (self.repo / 'TODO.md').open('ab') as stream:
            stream.write(b'Owner continuation\n')
        before = self.snapshot()
        result = self.redact('--expected-revision', token)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('stale revision', result.stderr)
        self.assertEqual(before, self.snapshot())
        self.assertFalse(self.archive.exists())

    def test_archive_inside_repo_or_symlink_alias_is_refused(self):
        self.archive.symlink_to(self.repo, target_is_directory=True)
        for archive in (self.repo / 'private', self.archive):
            before = self.snapshot()
            result = self.cli('redact', self.repo, '--replacements-file', self.mapping,
                              '--archive-dir', archive)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('outside repository', result.stderr)
            self.assertEqual(before, self.snapshot())

    def test_invalid_mapping_does_not_write_or_archive(self):
        for mapping in ({'relative': '<private>'}, {'/home/example': 42}, [], {}):
            self.mapping.write_text(json.dumps(mapping))
            before = self.snapshot()
            result = self.redact()
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(before, self.snapshot())
            self.assertFalse(self.archive.exists())

    def test_redaction_waits_for_existing_common_git_lock(self):
        import fcntl
        with (self.repo / '.git' / '.repo-docs-goals.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            process = subprocess.Popen([sys.executable, str(SCRIPT), 'redact', str(self.repo),
                '--replacements-file', str(self.mapping), '--archive-dir', str(self.archive)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                with self.assertRaises(subprocess.TimeoutExpired):
                    process.communicate(timeout=0.3)
                self.assertFalse(self.archive.exists())
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
                out, err = process.communicate(timeout=15)
        self.assertEqual(process.returncode, 0, out + err)

    def test_inflight_todo_edit_before_render_is_not_overwritten(self):
        # Inject an uncoordinated edit precisely between ledger replacement and render.
        harness = '''import sys
from pathlib import Path
sys.path.insert(0, sys.argv.pop(1))
import goals
original = goals.render
def edited(repo, data):
    with (Path(repo) / 'TODO.md').open('ab') as stream:
        stream.write(b'Owner continuation\\n')
    return original(repo, data)
goals.render = edited
goals.main()
'''
        result = subprocess.run([sys.executable, '-c', harness, str(SCRIPT.parent),
            'redact', str(self.repo), '--replacements-file', str(self.mapping),
            '--archive-dir', str(self.archive)], capture_output=True, text=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('stale write', result.stderr)
        self.assertEqual((self.repo / 'TODO.md').read_bytes(), self.body + b'Owner continuation\n')
        self.assertTrue(list(self.archive.glob('*/manifest.json')))
        self.assertFalse(list(self.repo.glob('.TODO.md.*')))


if __name__ == '__main__':
    unittest.main()
