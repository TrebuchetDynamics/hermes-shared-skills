"""Structural policy regression; not a model-behavior or fleet-progress test."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def full_text():
    # Core plus references: phrases may live in either since the v0.22 split.
    return '\n'.join([ROOT.joinpath('SKILL.md').read_text()] + [p.read_text() for p in sorted(ROOT.glob('references/*.md'))])

class PickerPolicyTests(unittest.TestCase):
    def test_exhaustion_requires_new_bounded_evidence_not_scope_expansion(self):
        text=full_text()
        for phrase in ['two consecutive no-selection receipts','DIFFERENT authorized component','not discovery completeness','keep exploration read-only and resource-disjoint','Do not repeat this exploration','Checked scope exhausted','not an enforced runtime guarantee']:
            self.assertIn(phrase,text)
    def test_no_early_exit_and_terminal_results_continue(self):
        text=Path(__file__).resolve().parents[1].joinpath('SKILL.md').read_text()
        for phrase in ['version: 0.23.0', "Ask, don't block", 'Repo-docs runs separately', 'goals.py next', 'never fingerprint-exit', 'On EVERY idle occurrence', 'A completed card is not a stop condition', 'Disable change-only fingerprint monitors', 'autogoal_gate.py', 'CONTINUE selection', 'work_search', 'not a runtime guarantee']:
            self.assertIn(phrase, text)
        for obsolete in ['Step 0 — fast exit', 'return `[SILENT]` immediately', 'Step 0 fast exit bounds']:
            self.assertNotIn(obsolete, text)

    def test_preserves_authority_and_no_busywork(self):
        text=full_text()
        for phrase in ['No exhaustive scan, broad suite, fabricated task','financial/live/scope gates stay','not product acceptance','exactly `[SILENT]`','goal_max_turns: 50','push, deploy, publish, spend money, place trades','agent/<profile>/<card-id>','never\n    push']:
            self.assertIn(phrase,text)

    def test_usable_backlog_takes_short_path_and_worker_owns_whole_outcome(self):
        core = ROOT.joinpath('SKILL.md').read_text()
        handoff = ROOT.joinpath('references/handoff.md').read_text()
        discovery = ROOT.joinpath('references/discovery.md').read_text()
        cron = ROOT.parent.joinpath('extras/cron/autogoal.prompt.md').read_text()
        for text in (core, cron):
            self.assertIn('Reconcile once', text)
            self.assertIn('discovery only when no usable task remains', text)
            self.assertIn('50 turns by default', text)
            self.assertNotIn('or\n   the profile has no `repo-docs` cron job', text)
        self.assertIn('Do not run a repo-docs prepass for a usable backlog task', core)
        self.assertIn('Goal budget rationale:', handoff)
        self.assertIn('--goal-max-turns 100', handoff)
        self.assertIn('Do not split debugging, fixes, tests or review handoff into intermediate cards', handoff)
        self.assertIn('original card and worker session', core)
        self.assertIn('Only when no usable backlog task remains', discovery)

    def test_core_stays_lean_and_points_to_every_reference(self):
        core = ROOT.joinpath('SKILL.md').read_text()
        self.assertLess(len(core.encode()), 16000, 'core SKILL.md must stay lean; move detail to references/')
        for ref in sorted(ROOT.glob('references/*.md')):
            self.assertIn(f'references/{ref.name}', core)

if __name__=='__main__':unittest.main()
