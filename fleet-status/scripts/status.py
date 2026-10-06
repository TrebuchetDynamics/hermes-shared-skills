#!/usr/bin/env python3
"""Read-only fleet collector. No repair commands, secret-file reads or output writes."""
import argparse
import collections
from contextlib import closing
import datetime as dt
import hashlib
import json
import re
import sqlite3
import subprocess
import time
import os
from pathlib import Path
from urllib.parse import quote

EXPECTED = {'goals.max_turns':'50','approvals.mode':'off','agent.verify_on_stop':'true'}
SPECIFIC = ('model.default','model.provider','terminal.cwd')
SHARED = {'autogoal':'planning/autogoal','repo-docs':'engineering/repo-docs','lgtm':'planning/lgtm','grill-me':'grill-me'}
CATEGORIES = ('review/lifecycle','authorization','missing capability/tooling','contract/scope','infrastructure/external dependency','unknown')


def redact(value):
    if isinstance(value,dict):
        return {k:('[REDACTED]' if re.fullmatch(r'(password|secret|api_key|access_token|refresh_token|bot_token)',str(k),re.I) else redact(v)) for k,v in value.items()}
    if isinstance(value,list):return [redact(v) for v in value]
    if not isinstance(value,str):return value
    if value.lstrip().startswith(('{','[')):
        try:return json.dumps(redact(json.loads(value)))
        except ValueError:pass
    value=re.sub(r'(?i)([\"\']?(?:api[_-]?key|password|secret|access[_-]?token|refresh[_-]?token|bot[_-]?token)[\"\']?\s*[=:]\s*)(\"[^\"]*\"|\'[^\']*\'|[^\s,;}]+)',r'\1[REDACTED]',value)
    value=re.sub(r'-----BEGIN [^-]*PRIVATE KEY-----.*?(?:-----END [^-]*PRIVATE KEY-----|$)','[REDACTED PRIVATE KEY]',value,flags=re.S)
    value=re.sub(r'(?i)(authorization\s*:\s*bearer\s+)\S+',r'\1[REDACTED]',value)
    value=re.sub(r'(?i)((?:api[_-]?key|password|secret|access[_-]?token|refresh[_-]?token|bot[_-]?token)\s*[=:]\s*)[\"\']?[^\s,;\"\']+',r'\1[REDACTED]',value)
    value=re.sub(r'(https?://)[^/@\s]+:[^/@\s]+@',r'\1[REDACTED]@',value)
    value=re.sub(r'(?i)([?&](?:token|key|secret|password|api_key)=)[^&#\s]+',r'\1[REDACTED]',value)
    value=re.sub(r'\b(?:sk-|ghp_|github_pat_)[A-Za-z0-9_-]{12,}','[REDACTED]',value)
    value=re.sub(r'\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+','[REDACTED JWT]',value)
    return value


def timestamp(value):
    if isinstance(value,(int,float)):return float(value)
    if not isinstance(value,str):return None
    try:
        parsed=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
        return parsed.timestamp() if parsed.tzinfo else None
    except ValueError:return None


def freshness(value,now,limit):
    epoch=timestamp(value)
    if epoch is None or epoch>now+60:return 'UNKNOWN',None
    age=max(0,now-epoch)
    return ('STALE' if age>limit else 'OBSERVED'),round(age,1)


def classify(text):
    text=(text or '').lower()
    if re.search(r'database unavailable|infrastructure.*(?:down|unavailable)|external dependency.*(?:down|unavailable)|connection refused|service down',text):return 'infrastructure/external dependency'
    if re.search(r'native review|independent review|final review|review.*(?:reject|pending|budget)|judge.*reject|lifecycle.*(?:gate|reject)|review[- ](?:handoff|lane)',text):return 'review/lifecycle'
    if re.search(r'excluded scope|explicitly excluded|resolve ownership/scope|scope.*decision|contract|approved.design|duplicate assignment',text):return 'contract/scope'
    if re.search(r'owner.*(?:approval|decision)|authoriz|permission|human input',text):return 'authorization'
    if re.search(r'database unavailable|infrastructure|external dependency|connection refused|service down',text):return 'infrastructure/external dependency'
    if re.search(r'missing|unavailable|lacks|cannot find|not found|capability|tooling|sdk|chromium|pg_config|skill_manage',text):return 'missing capability/tooling'
    if re.search(r'database|infrastructure|external|network|connection|service down',text):return 'infrastructure/external dependency'
    return 'unknown'


def build_report(raw,now=None,stale_seconds=300,automation_stale_seconds=86400):
    now=time.time() if now is None else now
    profiles=raw.get('profiles',[]);runtime=raw.get('runtime',{})
    rs,age=freshness(runtime.get('observed_at'),now,stale_seconds)
    available=runtime.get('available')
    state=rs if rs!='OBSERVED' else ('AVAILABLE_SHARED_GATEWAY' if available is True else 'UNAVAILABLE' if available is False else 'UNKNOWN')
    board_state,_=freshness(raw.get('observed_at'),now,stale_seconds)
    known=raw.get('boards_known') is True and board_state=='OBSERVED'
    tasks=raw.get('tasks',[]);counts=collections.Counter()
    mapped={'running':'running','ready':'queued','todo':'queued','triage':'queued','scheduled':'queued','changes_requested':'queued','review':'review','blocked':'blocked','done':'done','abandoned':'abandoned','archived':'archived'}
    for task in tasks:counts[mapped.get(task.get('status'),'unknown')]+=1
    full_counts={k:counts[k] for k in ['running','queued','review','blocked','done','abandoned','archived','unknown']}
    blockers=[];actions=[]
    for task in tasks:
        if task.get('status') not in {'blocked','review','changes_requested'} and not (task.get('status')=='triage' and task.get('block_kind') in {'needs_input','capability'}):continue
        text=task.get('summary') or '';category=classify(text) if task.get('status')!='review' else 'review/lifecycle'
        item={'board':task.get('board','UNKNOWN'),'profile':task.get('profile','UNKNOWN'),'card':task.get('id','UNKNOWN'),'category':category,'classification':'INFERRED from attributed last-run summary','reason':redact(text)[:700] or 'UNKNOWN','last_meaningful_action_at':task.get('last_action_at')}
        blockers.append(item)
        if re.search(r'operator|resolve ownership/scope|owner.*(?:decision|approval)|human.*(?:review|approval)|authoriz|permission|product decision|duplicate assignment|cannot claim|please unblock|requires?.*final.*review',text,re.I):
            actions.append({'profile':item['profile'],'board':item['board'],'card':item['card'],'action':'Request operator judgment on same-card review/lifecycle gate; authorization not assumed' if category=='review/lifecycle' else 'Request owner judgment on existing scope/authorization or attribution','why_not_automatic':item['reason']})
    jobs=[];job_unknown=[]
    for profile in profiles:
        if not profile.get('jobs_known'):job_unknown.append(profile['name'])
        for job in profile.get('jobs',[]):
            fs,run_age=freshness(job.get('last_run_at'),now,automation_stale_seconds)
            jobs.append({'profile':profile['name'],'id':job.get('id'),'name':job.get('name'),'enabled':job.get('enabled'),'schedule':job.get('schedule'),'model':job.get('model'),'provider':job.get('provider'),'last_result':job.get('last_status') or 'UNKNOWN','last_run_at':job.get('last_run_at'),'last_run_age_seconds':run_age,'freshness':fs})
    unexpected=[];unknown_config=[];specific=[];variants=collections.defaultdict(list);missing=[];skill_unknown=[]
    for profile in profiles:
        config=profile.get('config',{})
        for key,expected in EXPECTED.items():
            value=config.get(key)
            if value is None or value=='UNKNOWN':unknown_config.append({'profile':profile['name'],'key':key})
            elif str(value).strip().lower()!=expected:unexpected.append({'profile':profile['name'],'key':key,'expected':expected,'observed':value})
        specific.append({'profile':profile['name'],'policy':'Intentional profile-specific allocation; preserved, not normalized','values':{k:config.get(k,'UNKNOWN') for k in SPECIFIC}})
        if not profile.get('skills'):skill_unknown.append(profile['name'])
        for skill in profile.get('skills',[]):
            if skill.get('support_scan')=='PARTIAL' or skill.get('missing_references'):skill_unknown.append(profile['name']+':'+skill['name']+':supporting files incomplete')
            if skill.get('missing'):missing.append({'profile':profile['name'],'name':skill['name']})
            elif skill.get('sha256'):variants[skill['name']].append(dict(skill,profile=profile['name']))
            else:skill_unknown.append(profile['name']+':'+skill['name'])
    divergence=[]
    for name,items in variants.items():
        if len({(x.get('version'),x['sha256'],x.get('support_hash')) for x in items})>1:divergence.append({'name':name,'classification':'UNEXPLAINED; inspect intentional overrides before remediation','copies':items})
    permissions=[dict(p,profile=profile['name']) for profile in profiles for p in profile.get('permissions',[]) if p.get('problem')]
    per_profile=[]
    for profile in profiles:
        owned=[t for t in tasks if t.get('profile')==profile['name']]
        per_profile.append({'profile':profile['name'],'workspace':profile.get('config',{}).get('terminal.cwd','UNKNOWN'),'model':profile.get('config',{}).get('model.default','UNKNOWN'),'provider':profile.get('config',{}).get('model.provider','UNKNOWN'),'running_cards':sum(t.get('status')=='running' for t in owned) if known else None,'blocked_cards':sum(t.get('status')=='blocked' for t in owned) if known else None,'runtime':'Shared gateway observation only; profile transport UNKNOWN'})
    report={'schema':'fleet-status/v1','observed_at':raw.get('observed_at'),'rendered_at':now,'configured_profiles':len(profiles),'profiles':per_profile,
        'runtime':{'state':state,'observed_at':runtime.get('observed_at'),'observation_age_seconds':age,'per_profile_transport':'UNKNOWN','coverage':'Shared gateway process availability; not overall profile health'},
        'work':{'state':'OBSERVED' if known else 'UNKNOWN' if board_state!='STALE' else 'STALE','counts':full_counts if known else None,'partial_counts':None if known else full_counts,'abandoned_detection':'UNKNOWN unless explicitly recorded by a board; no process abandonment audit','coverage':raw.get('boards',[]),'errors':raw.get('board_errors',[])},
        'blockers':{'state':'OBSERVED' if known else 'UNKNOWN','category_counts':dict(collections.Counter(b['category'] for b in blockers)) if known else None,'items':blockers},
        'automations':{'state':'UNKNOWN' if job_unknown else 'OBSERVED','enabled':None if job_unknown else sum(j['enabled'] is True for j in jobs),'disabled':None if job_unknown else sum(j['enabled'] is False for j in jobs),'observed_enabled':sum(j['enabled'] is True for j in jobs),'observed_disabled':sum(j['enabled'] is False for j in jobs),'last_result_failures':None if job_unknown or any(j['last_result']=='UNKNOWN' for j in jobs) else sum(str(j['last_result']).lower() in {'error','failed','failure'} for j in jobs),'known_last_result_failures':sum(str(j['last_result']).lower() in {'error','failed','failure'} for j in jobs),'unknown_profiles':job_unknown,'jobs':jobs,'coverage':'Last recorded results, not complete failure history; silence is not cost-free'},
        'drift':{'unexpected_config':unexpected,'unknown_config':unknown_config,'profile_specific_differences':specific,'skill_divergence':divergence,'missing_skills':missing,'unknown_skill_coverage':skill_unknown,'shared_skill_inventory':dict(variants),'coverage':'Three explicit fleet defaults and four shared families; other config/custom skills UNKNOWN'},
        'security':{'approval_modes':{p['name']:p.get('config',{}).get('approvals.mode','UNKNOWN') for p in profiles},'sensitive_file_permission_problems':permissions,'sensitive_file_metadata':{p['name']:p.get('permissions',[]) for p in profiles},'secret_log_exposure':'UNKNOWN','sandbox_isolation':'UNKNOWN','coverage':'Known sensitive-file metadata only; no secret contents/log scanning; approval bypass is a risk posture, not authorization'},
        'operator_actions':{'state':'OBSERVED' if known and all(b['category']!='unknown' and b['reason']!='UNKNOWN' for b in blockers) else 'UNKNOWN','items':actions,'count':len(actions) if known and all(b['category']!='unknown' and b['reason']!='UNKNOWN' for b in blockers) else None,'coverage':'Known authorization/judgment gates only; technical fixes are not automatically human actions'}}
    return redact(report)


def cli(*args):
    raise ValueError('Collector never invokes Hermes CLI; read commands can migrate state or load secrets')


def skill_inventory(home):
    result=[]
    for name,relative in SHARED.items():
        file=home/'skills'/relative/'SKILL.md'
        if file.is_symlink():result.append({'name':name,'state':'UNKNOWN_UNSAFE_SYMLINK'});continue
        if not file.is_file():result.append({'name':name,'missing':True});continue
        try:
            text=file.read_text();version=re.search(r'^version:\s*(.+)$',text,re.M);base=file.resolve().parent
            support=[];limited=False
            for folder in ['references','assets','scripts','templates']:
                for path in sorted((base/folder).rglob('*')):
                    if not path.is_file() or '__pycache__' in path.parts or path.suffix=='.pyc':continue
                    if path.is_symlink() or not path.resolve().is_relative_to(base) or any(parent.is_symlink() for parent in path.parents if parent!=base and parent.is_relative_to(base)):
                        limited=True;continue
                    if path.name in {'.env','auth.json','credentials.json'} or path.suffix in {'.key','.pem'}:
                        limited=True;continue
                    if len(support)>=200 or path.stat().st_size>1048576:limited=True;continue
                    support.append((str(path.relative_to(base)),hashlib.sha256(path.read_bytes()).hexdigest()))
            missing_refs=[]
            for ref in re.findall(r'\]\(([^)]+)\)',text):
                if '://' in ref or ref.startswith('#'):continue
                rel=ref.split('#')[0]
                if rel and not (base/rel).exists():missing_refs.append(rel)
            result.append({'name':name,'resolved':str(file.resolve()),'version':version.group(1) if version else 'unversioned','sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'support_hash':hashlib.sha256(json.dumps(support).encode()).hexdigest(),'support_file_count':len(support),'support_scan':'PARTIAL' if limited else 'OBSERVED','missing_references':missing_refs})
        except (OSError,UnicodeError):result.append({'name':name,'state':'UNKNOWN'})
    return result


def config_values(path):
    """Parse only simple two-level scalar settings; complex YAML yields UNKNOWN.

    No Hermes imports, defaults, .env expansion, YAML constructors or execution.
    """
    values={key:'UNKNOWN' for key in (*SPECIFIC,*EXPECTED)}
    seen=collections.Counter();section=None;sections=collections.Counter()
    try:
        if path.is_symlink():return values
        for line in path.read_text().splitlines():
            top=re.fullmatch(r'([A-Za-z_][\w-]*):\s*(?:#.*)?',line)
            if top:section=top[1];sections[section]+=1;continue
            if line and not line[0].isspace() and not line.startswith('#'):section=None
            match=re.fullmatch(r'  ([A-Za-z_][\w-]*):\s*(.*?)\s*',line)
            if not match:continue
            key=str(section)+'.'+match[1]
            if key not in values:continue
            seen[key]+=1;value=match[2]
            if value.startswith('"'):
                try:value=json.loads(value)
                except ValueError:value='UNKNOWN'
            elif value.startswith("'") and value.endswith("'"):value=value[1:-1].replace("''", "'")
            else:value=value.split(' #',1)[0].strip()
            if not isinstance(value,str) or not value or value.startswith(('*','&','{','[','|','>')):value='UNKNOWN'
            values[key]=value
        for key in values:
            if seen[key]!=1 or sections[key.split('.')[0]]!=1:values[key]='UNKNOWN'
    except (OSError,UnicodeError):pass
    return values


def runtime_observation(root):
    path=root/'gateway_state.json'
    try:
        if path.is_symlink():return {}
        data=json.loads(path.read_text());pid=data.get('pid')
        alive=None
        if isinstance(pid,int) and pid>0:
            try:os.kill(pid,0);alive=True
            except ProcessLookupError:alive=False
            except (PermissionError,OSError):pass
        return {'observed_at':data.get('updated_at'),'available':alive,'coverage':'State timestamp and PID existence only; process identity and profile transports UNKNOWN'}
    except (OSError,ValueError,TypeError):return {}


def board_paths(root):
    boards=[('default',root/'kanban.db')]
    folder=root/'kanban/boards'
    if folder.is_dir() and not folder.is_symlink():
        boards.extend((p.name,p/'kanban.db') for p in sorted(folder.iterdir()) if p.is_dir() and not p.is_symlink() and re.fullmatch(r'[A-Za-z0-9_-]+',p.name))
    return boards


def collect(root):
    observed=time.time();raw={'observed_at':observed,'runtime':{},'profiles':[],'tasks':[],'boards_known':False,'board_errors':[],'boards':[]}
    homes=[root] if (root/'config.yaml').exists() else []
    if (root/'profiles').is_dir():homes+=sorted(p for p in (root/'profiles').iterdir() if (p/'config.yaml').is_file())
    raw['runtime']=runtime_observation(root)
    for home in homes:
        name='default' if home==root else home.name;row={'name':name,'config':{},'jobs':[],'jobs_known':False,'permissions':[]}
        row['config']=config_values(home/'config.yaml')
        jobs=home/'cron/jobs.json'
        if jobs.is_file():
            try:
                data=json.loads(jobs.read_text());items=data if isinstance(data,list) else data['jobs'];items=list(items.values()) if isinstance(items,dict) else items
                row['jobs']=[{k:j.get(k) for k in ['id','name','enabled','schedule','model','provider','last_status','last_run_at']} for j in items];row['jobs_known']=True
            except (OSError,ValueError,KeyError,TypeError):pass
        # An absent scheduler file is unknown, not proof of zero jobs in all scheduler systems.
        row['skills']=skill_inventory(home)
        for file in ['.env','auth.json']:
            path=home/file
            try:
                if path.is_symlink():row['permissions'].append({'file':file,'state':'UNKNOWN_SYMLINK','problem':True});continue
                if path.exists():
                    mode=path.stat().st_mode&0o777;row['permissions'].append({'file':file,'mode':format(mode,'04o'),'problem':bool(mode&0o077)})
                else:row['permissions'].append({'file':file,'state':'ABSENT; other credential stores UNKNOWN','problem':False})
            except OSError:row['permissions'].append({'file':file,'state':'UNKNOWN','problem':False})
        raw['profiles'].append(row)
    raw['boards_known']=True
    for slug,path in board_paths(root):
        raw['boards'].append({'slug':slug,'observed_at':time.time()})
        try:
            if path.is_symlink() or not path.is_file():raise ValueError('No safe board file')
            wal=Path(str(path)+'-wal')
            if wal.exists() and wal.stat().st_size>0:raise ValueError('Active WAL needs a separate safe snapshot; UNKNOWN')
            uri='file:'+quote(str(path.resolve()))+'?mode=ro&immutable=1'
            with closing(sqlite3.connect(uri,uri=True,timeout=3)) as db:
                db.row_factory=sqlite3.Row
                columns={r[1] for r in db.execute('PRAGMA table_info(tasks)')}
                optional=',block_kind' if 'block_kind' in columns else ''
                for task in db.execute('SELECT id,assignee,status,title,created_at,last_heartbeat_at'+optional+' FROM tasks'):
                    run=db.execute('SELECT summary,error,ended_at FROM task_runs WHERE task_id=? ORDER BY id DESC LIMIT 1',(task['id'],)).fetchone()
                    raw['tasks'].append({'id':task['id'],'board':slug,'profile':task['assignee'],'status':task['status'],'block_kind':task['block_kind'] if 'block_kind' in task.keys() else None,'summary':redact((run['summary'] or run['error'] or '') if run else ''),'last_action_at':run['ended_at'] if run else task['created_at'],'last_heartbeat_at':task['last_heartbeat_at']})
        except (OSError,sqlite3.Error,KeyError,ValueError):
            raw['boards_known']=False;raw['board_errors'].append({'board':slug,'state':'UNKNOWN_READ_FAILED_OR_WAL_UNSAFE'})
    return raw


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stale-seconds',type=int,default=300);p.add_argument('--automation-stale-seconds',type=int,default=86400)
    args=p.parse_args();root=Path(__file__).resolve().parents[4]
    print(json.dumps(build_report(collect(root),stale_seconds=args.stale_seconds,automation_stale_seconds=args.automation_stale_seconds),indent=2))

if __name__=='__main__':main()
