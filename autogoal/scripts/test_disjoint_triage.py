#!/usr/bin/env python3
"""Regression for explicit governor disjoint-terminal-triage routing."""
import importlib.util
from pathlib import Path
import unittest
spec = importlib.util.spec_from_file_location('start_goal', Path(__file__).with_name('start_goal.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class DisjointTriageTests(unittest.TestCase):
    def setUp(self):
        self.task = {'id':'t_original','status':'triage','assignee':'wing','title':'Original dismissal',
                     'workspace_kind':'dir','workspace_path':'/workspace'}
        self.runs = [{'status':'blocked','ended_at':123}]
        self.claim = {'current_run_id':None,'worker_pid':None}
    def validate(self, task=None, runs=None, claim=None, title='New navigation'):
        return m.validate_disjoint_triage(task or self.task, self.runs if runs is None else runs,
                                         self.claim if claim is None else claim, 'wing', title, '/workspace')
    def test_triage_blocks_only_its_own_slice(self):
        self.assertIsNone(m.existing_task([self.task], 'wing','New navigation','/workspace'))
        self.assertEqual(m.existing_task([self.task], 'wing','Original dismissal','/workspace'), self.task)
    def test_scheduled_backoff_blocks_only_its_own_slice(self):
        parked={**self.task,'status':'scheduled'}
        self.assertIsNone(m.existing_task([parked], 'wing','New navigation','/workspace'))
        self.assertEqual(m.existing_task([parked], 'wing','Original dismissal','/workspace'), parked)
    def test_explicit_terminal_exception(self):
        tid = self.validate()
        self.assertIsNone(m.existing_task([self.task], 'wing','New navigation','/workspace',{tid}))
    def test_same_title_not_replaced(self):
        with self.assertRaises(ValueError): self.validate(title='Original dismissal')
        self.assertEqual(m.existing_task([self.task], 'wing','Original dismissal','/workspace',{'t_original'}), self.task)
    def test_claim_and_pid_rejected(self):
        for field in self.claim:
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.validate(claim={**self.claim,field:12})
    def test_unrun_or_live_run_rejected(self):
        for runs in [[],[{'status':'running','ended_at':None}],[{'status':'blocked','ended_at':None}],[{'status':'done','ended_at':123}]]:
            with self.subTest(runs=runs), self.assertRaises(ValueError): self.validate(runs=runs)
    def test_wrong_scope_or_state_rejected(self):
        for key,value in [('status','running'),('status','ready'),('assignee','arenaton'),('workspace_path','/another'),('workspace_kind','worktree')]:
            with self.subTest(key=key,value=value), self.assertRaises(ValueError):
                self.validate(task={**self.task,key:value})
    def test_other_active_owner_still_blocks(self):
        other={**self.task,'id':'t_live','status':'running','assignee':'other'}
        self.assertEqual(m.existing_task([self.task,other], 'wing','New navigation','/workspace',{'t_original'}),other)
    def test_blocked_duplicate_still_blocks(self):
        duplicate={**self.task,'id':'t_blocked','status':'blocked','title':'New navigation'}
        self.assertEqual(m.existing_task([self.task,duplicate], 'wing','New navigation','/workspace',{'t_original'}),duplicate)

if __name__ == '__main__': unittest.main()
