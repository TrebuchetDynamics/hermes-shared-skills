import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

FILE = Path(__file__).with_name('status.py')

class StatusTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(FILE.exists(), 'Missing read-only fleet collector')
        spec = importlib.util.spec_from_file_location('fleet_status', FILE)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.raw = {'observed_at': 1000, 'runtime': {'observed_at':1000,'available':True},
                    'profiles':[{'name':'one','config':{'model.default':'model-a','model.provider':'provider-a','terminal.cwd':'/repo-a','goals.max_turns':'50','approvals.mode':'off','agent.verify_on_stop':'true'},
                                 'jobs':[], 'jobs_known':True,'skills':[], 'permissions':[]}],
                    'boards_known':True,'tasks':[],'board_errors':[]}
    def report(self):
        return self.m.build_report(self.raw, now=1000)
    def test_excluded_shared_shell_is_scope_not_network(self):
        self.raw['tasks']=[{'id':'focus','profile':'one','status':'blocked','summary':'Reproduced editor to Tools to Connections focus transition. Correct repair requires the explicitly excluded shared-shell traversal boundary; resolve ownership/scope before proceeding.'}]
        report=self.report()
        self.assertEqual(report['blockers']['items'][0]['category'],'contract/scope')
        self.assertEqual(report['operator_actions']['items'][0]['card'],'focus')

    def test_typed_block_loop_triage_is_operator_gate(self):
        self.raw['tasks']=[{'id':'loop','profile':'one','status':'triage','block_kind':'needs_input','summary':'Operator decision: circular native review entry rejected'}]
        report=self.report()
        self.assertEqual(len(report['blockers']['items']),1)
        self.assertEqual(report['operator_actions']['items'][0]['card'],'loop')
    def test_ordinary_triage_not_invented_blocker(self):
        self.raw['tasks']=[{'id':'new','profile':'one','status':'triage','summary':'New task awaiting specification'}]
        self.assertEqual(self.report()['blockers']['items'],[])

    def test_archived_is_not_blocked_done_or_abandoned(self):
        self.raw['tasks']=[{'id':'old','profile':'one','status':'archived'}]
        counts=self.report()['work']['counts']
        self.assertEqual(counts['archived'],1)
        for state in ['blocked','done','abandoned','unknown']:self.assertEqual(counts[state],0)

    def test_ambiguous_config_is_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'config.yaml'
            p.write_text('goals:\n  max_turns: 50\n  max_turns: 20\n')
            self.assertEqual(self.m.config_values(p)['goals.max_turns'],'UNKNOWN')
    def test_active_wal_not_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'config.yaml').write_text('goals:\n  max_turns: 50\n')
            (root/'kanban.db').write_bytes(b'fixture');(root/'kanban.db-wal').write_bytes(b'pending fixture')
            raw=self.m.collect(root)
            self.assertFalse(raw['boards_known'])
            self.assertIsNone(self.m.build_report(raw)['work']['counts'])
    def test_unknown_blocker_does_not_claim_zero_actions(self):
        self.raw['tasks']=[{'id':'t1','profile':'one','status':'blocked'}]
        self.assertIsNone(self.report()['operator_actions']['count'])
    def test_historical_final_review_not_current_blocker(self):
        self.assertEqual(self.m.classify('Final review approved; database unavailable'),'infrastructure/external dependency')

    def test_json_string_redaction(self):
        self.assertNotIn('FIXTURE_ONLY_SECRET',self.m.redact('{"api_key": "FIXTURE_ONLY_SECRET"}'))
        text='log: {"password": "secret with spaces"}'
        self.assertNotIn('secret with spaces',self.m.redact(text))
    def test_private_key_redacted_before_truncation(self):
        self.raw['tasks']=[{'id':'t1','profile':'one','status':'blocked','summary':'-----BEGIN PRIVATE KEY-----\n'+'fixture-material'*100+'\n-----END PRIVATE KEY-----'}]
        self.assertNotIn('fixture-material',json.dumps(self.report()))
    def test_owner_approval_action(self):
        self.raw['tasks']=[{'id':'t1','profile':'one','status':'blocked','summary':'owner approval required'}]
        self.assertEqual(self.report()['operator_actions']['count'],1)
    def test_automated_review_not_human_action(self):
        self.raw['tasks']=[{'id':'t1','profile':'one','status':'review','summary':'Automated reviewer queued'}]
        self.assertEqual(self.report()['operator_actions']['count'],0)
    def test_past_review_not_current_blocker(self):
        self.assertEqual(self.m.classify('Review completed; database unavailable'),'infrastructure/external dependency')
    def test_supporting_symlink_never_read(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);skill=root/'skills/engineering/repo-docs';(skill/'references').mkdir(parents=True)
            (skill/'SKILL.md').write_text('---\nname: repo-docs\nversion: 1\n---\ntext')
            secret=root/'.env';secret.write_text('MUST_NOT_READ=fixture')
            (skill/'references/leak.md').symlink_to(secret)
            original=Path.read_bytes
            def guard(p):
                if p.resolve()==secret.resolve():raise AssertionError('Symlink secret target read')
                return original(p)
            with patch.object(Path,'read_bytes',guard):
                items=self.m.skill_inventory(root)
            entry=next(x for x in items if x['name']=='repo-docs')
            self.assertEqual(entry['support_scan'],'PARTIAL')

    def test_available_gateway_does_not_hide_blocked_work(self):
        self.raw['tasks']=[{'id':'t1','profile':'one','status':'blocked','summary':'missing Chromium; tooling unavailable'}]
        result=self.report()
        self.assertEqual(result['runtime']['state'],'AVAILABLE_SHARED_GATEWAY')
        self.assertEqual(result['work']['counts']['blocked'],1)
        self.assertNotIn('healthy',json.dumps(result).lower())
    def test_stale_observation(self):
        self.raw['runtime']['observed_at']=1
        self.assertEqual(self.report()['runtime']['state'],'STALE')
    def test_missing_evidence_is_unknown(self):
        self.raw['runtime']={};self.raw['boards_known']=False
        result=self.report()
        self.assertEqual(result['runtime']['state'],'UNKNOWN')
        self.assertIsNone(result['work']['counts'])
        self.assertEqual(result['operator_actions']['state'],'UNKNOWN')
    def test_intentional_config_difference(self):
        other=dict(self.raw['profiles'][0]);other['name']='two';other['config']=dict(other['config'],**{'model.default':'model-b','terminal.cwd':'/repo-b'})
        self.raw['profiles'].append(other)
        result=self.report()['drift']
        self.assertEqual(result['unexpected_config'],[])
        self.assertTrue(result['profile_specific_differences'])
    def test_accidental_skill_divergence(self):
        self.raw['profiles'][0]['skills']=[{'name':'repo-docs','sha256':'a','support_hash':'x','version':'1'}]
        other=dict(self.raw['profiles'][0]);other['name']='two';other['skills']=[{'name':'repo-docs','sha256':'b','support_hash':'x','version':'1'}];self.raw['profiles'].append(other)
        self.assertIn('repo-docs',[x['name'] for x in self.report()['drift']['skill_divergence']])
    def test_failed_automation(self):
        self.raw['profiles'][0]['jobs']=[{'id':'j1','enabled':True,'last_status':'error','last_run_at':999}]
        self.assertEqual(self.report()['automations']['last_result_failures'],1)
    def test_sensitive_value_redaction(self):
        text='api_key=fixture-secret password: hunter-fixture Authorization: Bearer ABC.fixture.token https://user:pass@example.org/?token=QUERYSECRET sk-ABCDEFGHIJK1234567890'
        redacted=self.m.redact(text)
        for value in ['fixture-secret','hunter-fixture','ABC.fixture.token','user:pass','QUERYSECRET','sk-ABCDEFGHIJK1234567890']:self.assertNotIn(value,redacted)
    def test_zero_operator_actions(self):
        self.assertEqual(self.report()['operator_actions'],{'state':'OBSERVED','items':[],'count':0,'coverage':'Known authorization/judgment gates only; technical fixes are not automatically human actions'})
    def test_same_card_review_action(self):
        self.raw['tasks']=[{'id':'t1','profile':'one','board':'default','status':'blocked','summary':'Native review entry rejected; operator resolution needed on original card'}]
        item=self.report()['operator_actions']['items'][0]
        self.assertEqual(item['card'],'t1');self.assertIn('same-card',item['action']);self.assertTrue(item['why_not_automatic'])
    def test_unknown_automation_run(self):
        self.raw['profiles'][0]['jobs']=[{'id':'j1','enabled':True}]
        self.assertEqual(self.report()['automations']['jobs'][0]['freshness'],'UNKNOWN')
    def test_config_missing_is_not_no_drift(self):
        self.raw['profiles'][0]['config'].pop('goals.max_turns')
        self.assertTrue(self.report()['drift']['unknown_config'])
    def test_classifies_all_blocker_dimensions(self):
        examples={'review/lifecycle':'native review rejected','authorization':'owner approval required', 'missing capability/tooling':'missing Chromium', 'contract/scope':'excluded scope requires decision', 'infrastructure/external dependency':'database unavailable','unknown':'unclear'}
        for expected,text in examples.items():self.assertEqual(self.m.classify(text),expected)
    def test_secret_permissions_metadata(self):
        self.raw['profiles'][0]['permissions']=[{'file':'.env','mode':'0644','problem':True}]
        self.assertEqual(len(self.report()['security']['sensitive_file_permission_problems']),1)
        self.assertEqual(self.report()['security']['secret_log_exposure'],'UNKNOWN')
    def test_cli_refuses_mutation_before_subprocess(self):
        from unittest.mock import patch
        with patch.object(self.m.subprocess,'run') as run:
            with self.assertRaises(ValueError):self.m.cli('kanban','unblock','t1')
            with self.assertRaises(ValueError):self.m.cli('-p','one','config','set','approvals.mode','off')
            run.assert_not_called()

    def test_unknown_failure_total_is_not_zero(self):
        self.raw['profiles'][0]['jobs_known']=False
        self.assertIsNone(self.report()['automations']['last_result_failures'])

    def test_collector_preserves_fixture_and_does_not_read_secrets(self):
        import sqlite3
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'config.yaml').write_text('model:\n  default: model-a\n  provider: provider-a\nterminal:\n  cwd: /repo-a\ngoals:\n  max_turns: 50\napprovals:\n  mode: off\nagent:\n  verify_on_stop: true\n');(root/'cron').mkdir()
            (root/'cron/jobs.json').write_text('{"jobs": []}')
            (root/'.env').write_text('DO_NOT_READ=fixture-secret\n');(root/'.env').chmod(0o600)
            path=root/'kanban.db'
            from contextlib import closing
            with closing(sqlite3.connect(path)) as db:
                db.execute('CREATE TABLE tasks (id,assignee,status,title,created_at,last_heartbeat_at)')
                db.execute('CREATE TABLE task_runs (id,task_id,summary,error,ended_at)')
                db.execute("INSERT INTO tasks VALUES ('t1','default','blocked','safe',1,1)")
                db.execute("INSERT INTO task_runs VALUES (1,'t1','operator must resolve native review',NULL,2)")
                db.commit()
            before={str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            original=Path.read_text
            def guarded(p,*args,**kwargs):
                if p.name in {'.env','auth.json'}:raise AssertionError('Secret contents read')
                return original(p,*args,**kwargs)
            def query(*args):
                if args==('profile','list'):return 'default model running alias'
                if args==('kanban','boards','list','--json'):return json.dumps([{'slug':'default','db_path':str(path)}])
                if args[:3]==('-p','default','config') and args[3]=='get':return self.raw['profiles'][0]['config'][args[4]]
                raise AssertionError('Unexpected command: '+repr(args))
            with patch.object(self.m.subprocess,'run',side_effect=AssertionError('Subprocess forbidden')),patch.object(Path,'read_text',guarded):
                result=self.m.build_report(self.m.collect(root))
            after={str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            self.assertEqual(before,after)
            self.assertEqual(result['work']['counts']['blocked'],1)
            self.assertNotIn('fixture-secret',json.dumps(result))

    def test_stale_automation(self):
        self.raw['profiles'][0]['jobs']=[{'id':'j1','enabled':True,'last_status':'ok','last_run_at':1}]
        self.assertEqual(self.m.build_report(self.raw,now=1000,automation_stale_seconds=100)['automations']['jobs'][0]['freshness'],'STALE')

if __name__=='__main__':unittest.main()
