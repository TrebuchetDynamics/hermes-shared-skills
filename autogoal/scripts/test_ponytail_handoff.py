"""Offline simplicity selection; no worker, model or board dispatch."""
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location('start_goal', Path(__file__).with_name('start_goal.py'))
assert SPEC is not None and SPEC.loader is not None
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class PonytailHandoffTests(unittest.TestCase):
    def test_implementation_handoff_selects_ponytail_without_waiving_gates(self):
        contract = 'Objective: scoped implementation\nAcceptance: retain required checks'
        body = m.build_task_body(contract)
        self.assertIn(contract, body)
        self.assertIn('Before solution design or implementation, load `ponytail`', body)
        self.assertIn('test-driven-development', body)
        self.assertIn('never waive safety, acceptance criteria or required checks', body)
        self.assertNotIn('load `ponytail-review`', body)
        self.assertIn('no push, merge, deploy', body)
        guide = (Path(__file__).parents[1] / 'references/handoff.md').read_text()
        self.assertIn('Before solution design or implementation, load `ponytail`', guide)
        self.assertIn('native-tool handoffs', guide)


if __name__ == '__main__':
    unittest.main()
