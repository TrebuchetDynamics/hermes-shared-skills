"""Archive policy checks; no models, network, live profiles or project migrations."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ArchivePolicyTests(unittest.TestCase):
    def test_skill_and_cron_share_the_archive_contract(self):
        policy = ROOT / 'repo-docs/references/todo-archive.md'
        self.assertTrue(policy.is_file(), 'Missing live-backlog/archive contract')
        text = policy.read_text()
        for requirement in ('todo.archive.md', 'docs/TODO-archive.md',
                            'verbatim', 'goals.json', 'Audit', 'append-only',
                            'dated pass-notes', 'multiplicity'):
            self.assertIn(requirement, text)
        skill = (ROOT / 'repo-docs/SKILL.md').read_text()
        cron = (ROOT / 'extras/cron/repo-docs.prompt.md').read_text()
        self.assertIn('references/todo-archive.md', skill)
        self.assertIn('archive', cron)
        self.assertIn('dated pass-notes', cron)


    def test_goal_helpers_preserve_archive_and_ignore_historical_queue(self):
        script = ROOT / 'repo-docs/scripts/goals.py'
        for name in ('todo.archive.md', 'docs/TODO-archive.md'):
            with self.subTest(archive=name), tempfile.TemporaryDirectory() as directory:
                repo = Path(directory)
                archive = repo / name
                archive.parent.mkdir(parents=True, exist_ok=True)
                history = b'# History\r\n\r\n## Now - historical\r\n- [ ] OLD-9: old note, never queue\r\n\r\n## Done\r\n- [x] DONE-1\r\n  receipt: fixture gate passed\r\n'
                archive.write_bytes(history)
                live = '- [ ] LIVE-1: keep this open task\n  acceptance: preserve the complete continuation\n'
                (repo / 'TODO.md').write_text('# TODO\n\n[History](' + name + ')\n\n## Goal coverage\n\nold\n\n## Now\n\n' + live)
                data = {'version': 1, 'goals': [
                    {'id': 'FINISHED', 'title': 'Historical fixture', 'source': 'PRD.md#done',
                     'status': 'met', 'tasks': ['DONE-1'], 'priority': 1,
                     'evidence': [{'kind': 'executed', 'ref': 'fixture gate', 'result': 'pass'}]},
                    {'id': 'OPEN', 'title': 'Live fixture', 'source': 'PRD.md#open',
                     'status': 'unmet', 'tasks': ['LIVE-1'], 'priority': 2}],
                    'tasks': [
                        {'id': 'DONE-1', 'goal': 'FINISHED', 'title': 'Finished', 'status': 'done', 'section': 'Done'},
                        {'id': 'LIVE-1', 'goal': 'OPEN', 'title': 'Open', 'status': 'open', 'section': 'Now'}]}
                (repo / 'goals.json').write_text(json.dumps(data))
                def run(command, *args):
                    result = subprocess.run([sys.executable, str(script), command, str(repo), *args], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    return result.stdout
                run('fmt')
                self.assertEqual(run('validate').strip(), 'ok')
                run('render')
                self.assertEqual(archive.read_bytes(), history)
                self.assertIn(live, (repo / 'TODO.md').read_text())
                self.assertEqual([p['task']['id'] for p in json.loads(run('next', '--json'))], ['LIVE-1'])
                stable = {p: p.read_bytes() for p in (archive, repo / 'TODO.md', repo / 'goals.json')}
                run('fmt'); run('validate'); run('render')
                self.assertEqual(stable, {p: p.read_bytes() for p in stable})
                ledger = json.loads((repo / 'goals.json').read_text())
                self.assertEqual(next(t for t in ledger['tasks'] if t['id'] == 'DONE-1')['status'], 'done')
                self.assertEqual(ledger['goals'][0]['evidence'][0]['ref'], 'fixture gate')


if __name__ == '__main__':
    unittest.main()
