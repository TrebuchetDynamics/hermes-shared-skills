"""Offline real-ledger lifecycle; review receipts are simulated, no model/native runs."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GOALS = ROOT / 'skills/repo-docs/scripts/goals.py'


def worker_module():
    spec = importlib.util.spec_from_file_location('cycle_start_goal',
        ROOT / 'skills/autogoal/scripts/start_goal.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CycleGuidanceTests(unittest.TestCase):
    def test_cycle_routes_available_skills_and_preserves_authority(self):
        policy = ROOT / 'skills/shared/ENGINEERING-CYCLE.md'
        self.assertTrue(policy.is_file(), 'missing shared engineering cycle')
        text = policy.read_text()
        for requirement in ('interview-me', 'spec-driven-development', 'documentation-and-adrs',
                            'planning-and-task-breakdown', 'incremental-implementation',
                            'test-driven-development', 'code-review-and-quality',
                            'skills/.hub/lock.json', 'systematic-debugging',
                            '--ledger-mode proposal --integration-owner',
                            'tasks/todo.md', 'review acceptance', 'NOT_CHECKED'):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, text)
        for path in ('repo-docs/SKILL.md', 'autogoal/SKILL.md',
                     'autogoal/references/whole-spec-execution.md'):
            self.assertIn('ENGINEERING-CYCLE.md', (ROOT / 'skills' / path).read_text())

    def test_workers_receive_autonomous_decisions_and_skill_application_contract(self):
        module = worker_module()
        for kwargs in ({}, {'ledger_mode': 'proposal', 'integration_owner': 'fixture-owner'}):
            body = module.build_task_body('Objective: fixture', **kwargs)
            for phrase in ('Decide routine reversible choices yourself',
                           'Skill application:', 'trigger, verified skill path, decision/artifact, check/result',
                           'planning-and-task-breakdown', 'constraint-driven-development',
                           'incremental-implementation', 'code-review-and-quality',
                           'git-workflow-and-versioning'):
                self.assertIn(phrase, body)
            self.assertNotIn('Questions (no reply = defaults apply)', body)
            self.assertIn('Mandatory completion gate:', body)
            self.assertIn('required review acceptance', body)

    def test_autonomy_does_not_turn_missing_intent_into_approval(self):
        core = (ROOT / 'skills/autogoal/SKILL.md').read_text()
        self.assertNotIn('proceed on the recommended reading', core)
        self.assertIn('continue only independent authorized work', core)
        self.assertIn('Silence never grants', core)
        cycle = (ROOT / 'skills/shared/ENGINEERING-CYCLE.md').read_text()
        for skill in ('api-and-interface-design', 'deprecation-and-migration',
                      'ci-cd-and-automation', 'observability-and-instrumentation',
                      'frontend-ui-engineering', 'context-engineering', 'code-simplification'):
            self.assertIn(skill, cycle)

    def test_worker_body_links_cycle_and_gates_direct_closure_on_review(self):
        module = worker_module()
        body = module.build_task_body('Objective: fixture')
        self.assertIn(str(ROOT / 'skills/shared/ENGINEERING-CYCLE.md'), body)
        self.assertLess(body.index('Ledger closure precondition:'),
                        body.index('task <repo> <TASK> done'))
        self.assertIn('required review acceptance', body)
        self.assertIn('update scoped documentation', body)
        proposal = module.build_task_body('Objective: fixture', ledger_mode='proposal',
                                          integration_owner='fixture-owner')
        self.assertIn('fixture-owner', proposal)
        self.assertIn('required review acceptance', proposal)
        self.assertNotIn('task <repo> <TASK> done', proposal)


class LedgerCycleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='offline engineering cycle ')
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        initialized = subprocess.run(['git', 'init', str(self.repo)],
                                     capture_output=True, text=True, timeout=10)
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        data = {'version': 1, 'goals': [], 'tasks': []}
        for number in (1, 2):
            data['goals'].append({'id': f'G{number}', 'title': f'Artifact {number}',
                'source': 'SPEC.md#accepted', 'status': 'unmet', 'priority': number,
                'tasks': [f'T{number}'], 'depends_on': ['G1'] if number == 2 else []})
            data['tasks'].append({'id': f'T{number}', 'goal': f'G{number}',
                'title': f'Write artifact {number}', 'status': 'open', 'section': 'Now',
                'depends_on': ['T1'] if number == 2 else []})
        (self.repo / 'goals.json').write_text(json.dumps(data))
        (self.repo / 'SPEC.md').write_text('# Accepted\n\nStatus: Accepted\n\nWrite two artifacts in order.\n')
        self.bodies = {}
        for number, content in ((1, 'first'), (2, 'second')):
            dependencies = 'T1, G1' if number == 2 else 'None'
            self.bodies[f'T{number}'] = (
                f'- [ ] T{number}: Write artifact {number}\n'
                f'  Goal: G{number}\n  Scope: artifact{number}.txt\n'
                f'  Acceptance: artifact contains {content} followed by a newline\n'
                f'  Dependencies: {dependencies}\n'
                '  Ownership: fixture integration owner; no live workers\n'
                '  Sources: [Accepted spec](SPEC.md#accepted)\n\n')
        (self.repo / 'TODO.md').write_text('# TODO\n\n## Now\n\n' + ''.join(self.bodies.values()))
        self.cli('fmt')

    def cli(self, command, *args, expected=0):
        result = subprocess.run([sys.executable, str(GOALS), command, str(self.repo), *args],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result.stdout

    def data(self):
        return json.loads((self.repo / 'goals.json').read_text())

    def goal_status(self, goal):
        return next(g['status'] for g in self.data()['goals'] if g['id'] == goal)

    def picks(self):
        return [row['task']['id'] for row in json.loads(self.cli('next', '--json'))]

    def evidence(self, goal, kind, result, ref='offline fixture receipt'):
        self.cli('evidence', goal, '--kind', kind, '--ref', ref, '--result', result)

    def test_completion_without_executed_pass_cannot_promote_goal(self):
        self.cli('task', 'T1', 'done')
        self.evidence('G1', 'inspection', 'pass')
        self.assertEqual(self.goal_status('G1'), 'unmet')
        self.assertNotIn('T2', self.picks())
        self.evidence('G1', 'executed', 'fail')
        self.assertEqual(self.goal_status('G1'), 'unmet')
        self.assertNotIn('T2', self.picks())
        self.assertIn('unmet goal has no open task', self.cli('validate', expected=1))

    def test_two_tasks_require_owner_closure_then_advance_and_render_stably(self):
        self.assertEqual(self.picks(), ['T1'])
        ready = json.loads(self.cli('backlog-check', '--plan', 'SPEC.md#accepted', '--tasks', 'T1'))
        self.assertEqual(ready['state'], 'ready_for_autogoal')
        for number, content in ((1, 'first'), (2, 'second')):
            task, goal = f'T{number}', f'G{number}'
            self.cli('task', task, 'in_progress')
            check = [sys.executable, '-c',
                f'from pathlib import Path; assert Path("artifact{number}.txt").read_text() == "{content}\\n"']
            red = subprocess.run(check, cwd=self.repo, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(red.returncode, 0)
            (self.repo / f'artifact{number}.txt').write_text(content + '\n')
            green = subprocess.run(check, cwd=self.repo, capture_output=True, text=True, timeout=10)
            self.assertEqual(green.returncode, 0, green.stderr)
            receipt = json.dumps(check)
            self.evidence(goal, 'executed', 'pass', receipt)
            # Passing checks cannot promote while the task is still owned/in progress.
            self.assertEqual(self.goal_status(goal), 'unmet')
            # Review is simulated owner evidence, not a goals.py runtime review gate.
            review = {'task': task, 'status': 'pending', 'check': receipt, 'fixture': True}
            (self.repo / 'fixture-review.json').write_text(json.dumps(review))
            if number == 1:
                self.assertNotIn('T2', self.picks())
            review['status'] = 'accepted'
            (self.repo / 'fixture-review.json').write_text(json.dumps(review))
            self.assertEqual(json.loads((self.repo / 'fixture-review.json').read_text())['status'], 'accepted')
            # Only the simulated integration owner applies canonical closure.
            self.cli('task', task, 'done')
            self.evidence(goal, 'executed', 'pass', receipt)
            self.assertEqual(self.goal_status(goal), 'met')
            # Simulate the owner's narrow documentation reconciliation, not model behavior.
            todo = self.repo / 'TODO.md'
            text = todo.read_text().replace(self.bodies[task], '', 1)
            if '## Done\n' not in text:
                text += '\n## Done\n\n'
            completed = self.bodies[task].replace('- [ ]', '- [x]', 1)
            todo.write_text(text + completed)
            self.assertNotIn(self.bodies[task], todo.read_text())
            self.assertIn(completed, todo.read_text().split('## Done\n', 1)[1])
            self.cli('validate')
            self.cli('render')
            if number == 1:
                ready = json.loads(self.cli('backlog-check', '--plan', 'SPEC.md#accepted', '--tasks', 'T2'))
                self.assertEqual(ready['state'], 'ready_for_autogoal')
            self.assertEqual(self.picks(), ['T2'] if number == 1 else [])
        first = {name: (self.repo / name).read_bytes() for name in ('goals.json', 'TODO.md')}
        self.cli('fmt')
        self.cli('render')
        self.assertEqual(first, {name: (self.repo / name).read_bytes() for name in first})
        todo = (self.repo / 'TODO.md').read_text()
        self.assertNotIn('- [ ]', todo)
        for body in self.bodies.values():
            self.assertIn(body.replace('- [ ]', '- [x]', 1), todo.split('## Done\n', 1)[1])
        self.assertFalse((self.repo / 'tasks/todo.md').exists())


if __name__ == '__main__':
    unittest.main()
