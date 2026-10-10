"""Offline bundle portability checks; these do not launch a native/model worker."""
import importlib.util
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WorkflowContractTests(unittest.TestCase):
    def test_active_bundled_markdown_links_resolve(self):
        for source in (ROOT / 'skills').rglob('*.md'):
            # Vendored upstream provenance retains its original relative links.
            if 'accepted-plan-support' in source.parts:
                continue
            for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', source.read_text()):
                if '://' in target or target.startswith('#'):
                    continue
                with self.subTest(source=source, target=target):
                    self.assertTrue((source.parent / target.split('#')[0]).exists())

    def test_active_docs_do_not_assume_shared_skills_install(self):
        for folder in ('autogoal', 'repo-docs', 'git-commit-push'):
            for source in (ROOT / 'skills' / folder).rglob('*.md'):
                with self.subTest(source=source):
                    self.assertNotIn('~/.hermes/shared-skills/', source.read_text())

    def test_generated_ledger_commands_run_from_install_path_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix='toolset install ') as directory:
            installed = Path(directory) / 'bundle with spaces'
            shutil.copytree(ROOT / 'skills', installed / 'skills')
            script = installed / 'skills/autogoal/scripts/start_goal.py'
            spec = importlib.util.spec_from_file_location('portable_start_goal', script)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            body = module.build_task_body('Objective: portability fixture')
            self.assertNotIn('~/.hermes/shared-skills/', body)
            commands = [text for text in re.findall(r'`([^`]+)`', body)
                        if 'goals.py' in text]
            self.assertEqual(len(commands), 3)
            repo = Path(directory) / 'consumer with spaces'
            repo.mkdir()
            (repo / 'goals.json').write_text(json.dumps({
                'version': 1,
                'goals': [{'id': 'G', 'title': 'Portable helper', 'source': 'README.md',
                           'status': 'unmet', 'tasks': ['T'], 'priority': 1}],
                'tasks': [{'id': 'T', 'goal': 'G', 'title': 'Check portability',
                           'status': 'open', 'section': 'Now'}]}))
            replacements = {'<repo>': str(repo), '<TASK>': 'T', '<GOAL>': 'G',
                            '<exact command>': 'offline fixture check', 'pass|fail': 'pass'}
            for command in commands:
                argv = shlex.split(command)
                self.assertEqual(Path(argv[1]), installed / 'skills/repo-docs/scripts/goals.py')
                result = subprocess.run(argv[:2] + ['--help'], cwd=directory,
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('backlog-check', result.stdout)
                result = subprocess.run([replacements.get(arg, arg) for arg in argv],
                                        cwd=directory, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
            ledger = json.loads((repo / 'goals.json').read_text())
            self.assertEqual(ledger['tasks'][0]['status'], 'done')
            self.assertIn('Goal coverage', (repo / 'TODO.md').read_text())


if __name__ == '__main__':
    unittest.main()
