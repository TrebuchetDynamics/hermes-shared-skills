#!/usr/bin/env python3
"""Offline policy-contract regressions, not live publication or model behavior proof.

Run: python git-commit-push/scripts/test_delivery_scope.py
The canonical scripts/check.py discovers this standalone unittest suite.
"""
from pathlib import Path
import importlib
import re
import sys
import unittest

SKILL = Path(__file__).resolve().parents[1]
ROOT = SKILL.parent


def normalized(path):
    return re.sub(r'\s+', ' ', path.read_text(encoding='utf-8')).lower()


class DeliveryScopePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = normalized(SKILL / 'SKILL.md')
        cls.reference = normalized(SKILL / 'references/shared-worktree-safety.md')

    def both_require(self, *phrases):
        for label, text in [('skill', self.main), ('reference', self.reference)]:
            for phrase in phrases:
                with self.subTest(document=label, phrase=phrase):
                    self.assertIn(phrase, text)

    def test_completed_cross_agent_work_is_eligible_for_repo_wide_ship(self):
        self.both_require('all eligible changes in requested scope',
                          'take delivery ownership', 'provenance',
                          'candidate-bound verification',
                          'authorship alone never excludes changes or yields no-op')
        self.assertIn('completed cross-agent implementation is eligible', self.main)
        self.assertIn('implementer is someone else or no card exists', self.main)
        self.assertIn('attribute contributors and verification receipts in the commit message', self.main)

    def test_live_writer_and_incomplete_work_remain_excluded(self):
        self.both_require('live writer/lease hunks', 'secrets', 'unapproved',
                          'unfinished', 'verification')
        self.assertIn('hold live writer/lease hunks, incomplete or unverifiable work', self.main)
        self.assertIn('live ownership/leases remain excluded', self.reference)

    def test_stale_only_ledger_is_not_a_restoration_commit(self):
        self.assertIn('a stale-only ledger contains no new work', self.main)
        self.assertIn('do not create a restoration commit', self.main)
        self.assertIn('stale-only copies yield no new commit', self.reference)
        self.both_require('no actual unshipped delta in requested scope',
                          'regardless of author', 'report behind/diverged status separately')

    def test_remote_additions_conserved_in_isolated_reconciliation(self):
        self.both_require('fresh upstream', 'isolated candidate',
                          'preserve newer remote entries', 'never delete remote lines',
                          'supported `goals.py task`/`add-task`/`fmt`/`render`',
                          'anchored prose edits', 'validate and inspect the resulting diff')

    def test_worker_local_only_audit_and_allowlist_do_not_gain_authority(self):
        self.both_require('local-only requests never authorize push',
                          'audit never authorizes git writes')
        self.assertIn('autonomous worker/card without explicit repo-wide authorization remains limited to its owned slice', self.main)
        self.assertIn('a path/topic allowlist stays narrow', self.main)
        self.assertIn('without that authorization, remain within the worker/card or path allowlist', self.reference)

    def test_agent_branch_does_not_equal_requested_target(self):
        self.assertIn('a card-branch commit is not proof it already reached the requested target', self.main)
        self.assertIn('committed on an agent branch does not mean published to the requested target', self.reference)

    def test_authorship_veto_removed_without_weakening_staging_or_preservation(self):
        for text in (self.main, self.reference):
            self.assertNotIn("another writer's uncommitted implementation is not yours to publish", text)
            self.assertNotIn('nothing of yours to commit', text)
            self.assertNotIn('belongs to that card, so exclude it', text)
            self.assertNotIn('when the foreign hunks cannot be separated safely', text)
        self.assertIn('stage explicit paths only', self.main)
        self.assertIn('never `git add -a` / `git add .`', self.main)
        self.assertIn("do not discard, stash, revert, or `git clean` other agents'", self.main)
        self.assertIn('committed is not deployed', self.reference)
        self.assertIn('held/asked, not no-op', self.main)

    def test_canonical_gate_discovers_regression_suite(self):
        sys.path.insert(0, str(ROOT / 'scripts'))
        checker = importlib.import_module('check')
        self.assertIn(Path(__file__).resolve(), checker.discover_tests(ROOT))


if __name__ == '__main__':
    unittest.main()
