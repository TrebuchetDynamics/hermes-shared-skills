"""Explicit installed Linux LOCAL FIXTURE composition, never offline discovery."""
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from controller_bridge import FixtureBridge, observe
from native_containment import launch

ROOT = (Path.home() / '.hermes/cache/scratch')
EVIDENCE = ROOT / 'executable-safeguards/controller-bridge'

@unittest.skipUnless(os.environ.get('RUN_CONTROLLER_BRIDGE_LINUX') == '1', 'opt-in installed Linux')
class CompositionTests(unittest.TestCase):
    def _run_egress_composition(self, *, inject_shutdown_request=False):
        import hashlib
        import shutil
        import socket
        import subprocess
        evidence = ROOT / 'executable-safeguards/worker-egress'
        import uuid
        evidence = evidence / ('run-' + uuid.uuid4().hex)
        evidence.mkdir(parents=True, exist_ok=True)
        sources = [Path(__file__).resolve(), Path(__file__).with_name('native_containment.py'),
                   Path(__file__).with_name('controller_bridge.py'),
                   Path(__file__).with_name('budget_controller.py')]
        def hashes():
            return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
        pre = hashes()
        (evidence / 'source-pre.json').write_text(json.dumps(pre, indent=2))
        for path in sources:
            shutil.copyfile(path, evidence / ('source-pre-' + path.name))
        observer_script = '''import json,os,select,socket,sys,time
listeners=[]; endpoints=[]; missing=[]; controls=[]; requests=[]
for family,address,name in ((socket.AF_INET,'127.0.0.1','ipv4'),(socket.AF_INET6,'::1','ipv6')):
 for kind,label in ((socket.SOCK_STREAM,'tcp_host'),(socket.SOCK_DGRAM,'udp_host'),(socket.SOCK_DGRAM,'dns_host')):
  cell=name+'_'+label
  s=None
  try:
   s=socket.socket(family,kind);s.bind((address,0))
   if kind==socket.SOCK_STREAM:s.listen(8)
  except OSError as exc:
   if s is not None:s.close()
   if name!='ipv6':raise
   missing.append(dict(cell=cell,status='capability_missing',errno=exc.errno,qualified=False));continue
  endpoint=dict(cell=cell,family=family,kind=kind,address=address,port=s.getsockname()[1])
  endpoints.append(endpoint);listeners.append((s,endpoint))
print(json.dumps(dict(pid=os.getpid(),endpoints=endpoints,missing=missing)),flush=True)
deadline=time.monotonic()+15; announced=False; stopping=False
while time.monotonic()<deadline:
 ready,_,_=select.select(([] if stopping else [sys.stdin])+[s for s,e in listeners],[],[],.1)
 if not stopping and sys.stdin in ready:
  sys.stdin.readline();stopping=True;deadline=min(deadline,time.monotonic()+.25)
 for s,e in listeners:
  if s not in ready:continue
  if e['kind']==socket.SOCK_STREAM:
   c,peer=s.accept();c.settimeout(.25)
   try:data=c.recv(256)
   except OSError:data=b''
   c.close()
  else:data,peer=s.recvfrom(256)
  row=dict(cell=e['cell'],data_hex=data.hex(),peer=list(peer),observer_pid=os.getpid())
  (controls if data==('control:'+e['cell']).encode() else requests).append(row)
 if not announced and len(controls)==len(endpoints):
  print(json.dumps(dict(positive_controls=controls)),flush=True);announced=True
for s,e in listeners:s.close()
print(json.dumps(dict(pid=os.getpid(),controls=controls,worker_requests=requests,missing=missing,listeners_closed=True)),flush=True)
'''
        worker_script = '''import errno,json,os,socket,subprocess,sys,time
from pathlib import Path
endpoints=json.loads(sys.argv[1]); actor=sys.argv[2]
os.environ.update(NO_PROXY='*',no_proxy='*',HTTP_PROXY='http://127.0.0.1:9',HTTPS_PROXY='http://127.0.0.1:9',ALL_PROXY='socks5://127.0.0.1:9')
attempts=[]
targets=endpoints+[dict(cell=family+'_'+kind+'_documentation',family=af,kind=typ,address=address,port=9) for family,af,address in (('ipv4',socket.AF_INET,'192.0.2.1'),('ipv6',socket.AF_INET6,'2001:db8::1')) for kind,typ in (('tcp',socket.SOCK_STREAM),('udp',socket.SOCK_DGRAM))]
for e in targets:
 row=dict(e,actor=actor,qualified=False)
 s=None
 try:
  s=socket.socket(e['family'],e['kind']);s.settimeout(.2)
  if e['kind']==socket.SOCK_STREAM:s.connect((e['address'],e['port']));s.sendall(('worker:'+actor).encode())
  else:
   payload=(b'\\x12\\x34\\x01\\x00\\x00\\x01\\x00\\x00\\x00\\x00\\x00\\x00\\x06egress\\x07invalid\\x00\\x00\\x01\\x00\\x01' if 'dns_' in e['cell'] else ('worker:'+actor).encode())
   s.connect((e['address'],e['port']))
   row['sent_bytes']=s.send(payload)
   row['denial_stage']='receive_after_send'
   row['response_hex']=s.recv(256).hex()
  row.update(status='escaped',errno=None)
 except OSError as exc:
  missing=s is None and e['family']==socket.AF_INET6 and exc.errno in (errno.EAFNOSUPPORT,errno.EPROTONOSUPPORT)
  row.update(status='capability_missing' if missing else 'denied',errno=exc.errno,error=str(exc),qualified=not missing)
 finally:
  if s is not None:s.close()
 attempts.append(row)
try:
 value=socket.getaddrinfo('egress.invalid',443)
 attempts.append(dict(cell='dns_resolver',status='escaped',errno=None,result=repr(value),qualified=False))
except socket.gaierror as exc:
 attempts.append(dict(cell='dns_resolver',status='denied',errno=exc.errno,error=str(exc),qualified=True,mechanism='resolver failure; raw DNS kernel probes separate'))
record=dict(actor=actor,pid=os.getpid(),attempts=attempts,environment=dict(os.environ),namespaces={n:os.readlink('/proc/self/ns/'+n) for n in ('user','pid','net','mnt')},cgroup=Path('/proc/self/cgroup').read_text())
status=dict(line.split(':',1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
forbidden=(HOST_HOME,'/home/sandbox/.hermes','/home/sandbox/.aws','/home/sandbox/.ssh','/run/user','/run/dbus','/var/run/docker.sock','/run/docker.sock','/sys/fs/cgroup','/etc/resolv.conf','/proc/1/root' + HOST_HOME,'/usr/bin/nsenter','/usr/bin/unshare','/usr/bin/bwrap','/usr/bin/ip','/usr/bin/docker')
manager=subprocess.run(['/usr/bin/systemctl','--user','show'],capture_output=True,text=True,timeout=1)
record['inspection']=dict(forbidden_paths={p:os.path.exists(p) for p in forbidden},cap_eff=status['CapEff'].strip(),no_new_privs=status['NoNewPrivs'].strip(),mountinfo=Path('/proc/self/mountinfo').read_text(),manager_returncode=manager.returncode,manager_stderr=manager.stderr)
Path('/job/'+actor+'.json').write_text(json.dumps(record))
if actor=='child':
 time.sleep(.3)
else:
 child=subprocess.Popen(['/usr/bin/python3.12','-I','-c',SCRIPT,sys.argv[1],'child'])
 child_rc=child.wait(timeout=2)
 child_record=json.loads(Path('/job/child.json').read_text());record['child_returncode']=child_rc
 s=socket.socket(socket.AF_UNIX);s.settimeout(1);s.connect('/controller.sock')
 s.sendall(b'{"request_id":"egress","model":"fixture","payload":"x","max_output":1}\\n')
 record['controller_response']=json.loads(s.recv(4096));s.close()
 Path('/job/worker.json').write_text(json.dumps(record))
 print(json.dumps(dict(worker=record,child=child_record)),flush=True)
'''
        worker_script = worker_script.replace('HOST_HOME', repr(str(Path.home())))
        worker_script = worker_script.replace('SCRIPT', repr(worker_script))
        result = {'source_pre': pre, 'probes': {}, 'stderr': '', 'host': {}, 'controller': {},
                  'artifact_directory': str(evidence), 'kernel_pid_readback': [],
                  'shutdown_probe': inject_shutdown_request}
        observer = None
        thread = None
        server = None
        monitor = None
        monitor_stop = threading.Event()
        with tempfile.TemporaryDirectory(prefix='we-', dir=ROOT) as tmp:
            directory = Path(tmp); job = directory / 'job'; job.mkdir()
            try:
                observer = subprocess.Popen(['/usr/bin/python3.12', '-I', '-c', observer_script],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, start_new_session=True)
                assert observer.stdout is not None
                # Readiness is bounded; no guessed sleep or listener port.
                import select
                if not select.select([observer.stdout], [], [], 3)[0]:
                    raise RuntimeError('host observer readiness timeout')
                ready = json.loads(observer.stdout.readline())
                result['observer'] = ready; result['endpoints'] = ready['endpoints']
                for endpoint in ready['endpoints']:
                    with socket.socket(endpoint['family'], endpoint['kind']) as client:
                        client.settimeout(.5)
                        address = (endpoint['address'], endpoint['port'])
                        payload = ('control:' + endpoint['cell']).encode()
                        if endpoint['kind'] == socket.SOCK_STREAM:
                            client.connect(address); client.sendall(payload)
                        else:
                            client.sendto(payload, address)
                if not select.select([observer.stdout], [], [], 3)[0]:
                    raise RuntimeError('host positive controls timeout')
                result['positive_control'] = json.loads(observer.stdout.readline())
                server = FixtureBridge(directory, max_accepts=1, lifetime=8)
                thread = threading.Thread(target=server.serve); thread.start()
                def register(observation):
                    nonlocal monitor
                    if server.register(observation) is not True:
                        return False
                    def readback():
                        from native_containment import cgroup_pids
                        import time
                        seen = set()
                        group = Path('/sys/fs/cgroup' + observation['control_group'])
                        deadline = time.monotonic() + 12
                        while not monitor_stop.is_set() and time.monotonic() < deadline:
                            for pid in cgroup_pids(group):
                                try:
                                    identity = observe(pid)
                                    key = (pid, identity['starttime'])
                                    if key in seen: continue
                                    status = Path(f'/proc/{pid}/status').read_text()
                                    namespace_pid = int(next(line.split()[-1] for line in status.splitlines() if line.startswith('NSpid:')))
                                    namespaces = {n:os.readlink(f'/proc/{pid}/ns/{n}') for n in ('user','pid','net','mnt')}
                                    # Recheck exact identity after the proc reads.
                                    if observe(pid) != identity: continue
                                    result['kernel_pid_readback'].append(dict(identity,namespace_pid=namespace_pid,namespaces=namespaces))
                                    seen.add(key)
                                except (OSError, StopIteration, ValueError): continue
                            monitor_stop.wait(.01)
                    monitor = threading.Thread(target=readback); monitor.start()
                    return True
                receipt = launch(['/usr/bin/python3.12', '-I', '-c', worker_script,
                    json.dumps(ready['endpoints']), 'worker'], job,
                    receipt_path=evidence / 'matrix-worker-receipt.json', runtime_sec=5,
                    controller_socket=server.socket_path, before_release=register)
                result['worker_receipt'] = receipt
            except Exception as exc:
                result.setdefault('errors', {})['execution'] = type(exc).__name__
            finally:
                result.setdefault('errors', {})
                result['qualified'] = False
                result['controller']['ledger'] = None
                def persist():
                    (evidence / 'matrix-manifest.json').write_text(json.dumps(result, indent=2))
                def failure(name, exc):
                    result['errors'][name] = type(exc).__name__
                try:
                    # Durable fail-closed envelope and raw process files precede any
                    # fallible final observation. No unknown count becomes zero.
                    persist()
                    for name in ('stdout', 'stderr', 'worker.json', 'child.json'):
                        path = job / name
                        try:
                            if path.exists():
                                shutil.copyfile(path, evidence / ('matrix-' + name))
                        except Exception as exc:
                            failure('copy_' + name, exc)
                    monitor_stop.set()
                    if monitor is not None: monitor.join(1)
                    result['monitor_thread_exited'] = monitor is None or not monitor.is_alive()
                    if thread is not None:
                        assert server is not None
                        thread.join(10)
                        result['controller'] = dict(controller_identity=None,
                            registration=server.registration, receipts=server.receipts,
                            effects=server.effects, ledger=None, thread_exited=not thread.is_alive(),
                            socket_absent=not server.socket_path.exists())
                        try:
                            shutil.copyfile(server.ledger_path, evidence / 'matrix-ledger.sqlite')
                        except Exception as exc:
                            failure('copy_ledger', exc)
                    persist()
                except Exception as exc:
                    failure('finalization', exc)
                finally:
                    if observer is not None:
                        try:
                            if inject_shutdown_request:
                                import signal
                                # Only our exact live child is stopped. Queue socket and
                                # shutdown input together to reproduce the drain race.
                                os.kill(observer.pid, signal.SIGSTOP)
                                try:
                                    endpoint = next(e for e in result['endpoints'] if e['cell'] == 'ipv4_udp_host')
                                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                                        client.sendto(b'shutdown-probe', (endpoint['address'], endpoint['port']))
                                    assert observer.stdin is not None
                                    observer.stdin.write('\n'); observer.stdin.flush()
                                finally:
                                    os.kill(observer.pid, signal.SIGCONT)
                                output, errors = observer.communicate(timeout=3)
                            else:
                                output, errors = observer.communicate('\n', timeout=3)
                            (evidence / 'matrix-observer-stdout').write_text(output)
                            (evidence / 'matrix-observer-stderr').write_text(errors)
                            result['observer_stderr'] = errors
                            result['host'] = json.loads(output.strip()) if output.strip() else None
                            if result['host'] is None:
                                raise ValueError('missing observer final observation')
                        except Exception as exc:
                            result['host'] = None
                            failure('host', exc)
                            if isinstance(exc, subprocess.TimeoutExpired):
                                result['observer_timeout'] = True
                        finally:
                            # Kill only this unreaped Popen child, never a discovered
                            # PID/group. wait/communicate have finite escalation bounds.
                            try:
                                if observer.poll() is None:
                                    observer.terminate()
                                output, errors = observer.communicate(timeout=1)
                            except subprocess.TimeoutExpired:
                                observer.kill()
                                output, errors = observer.communicate(timeout=1)
                            (evidence / 'matrix-observer-stdout').write_text(output)
                            (evidence / 'matrix-observer-stderr').write_text(errors)
                            result['observer_returncode'] = observer.returncode
                            result['observer_reaped'] = observer.poll() is not None
                if thread is not None:
                    try:
                        with sqlite3.connect(server.ledger_path) as db:
                            rows = db.execute('select reservation,attempts,state from requests').fetchall()
                        result['controller']['ledger'] = [list(row) for row in rows]
                    except Exception as exc:
                        failure('ledger', exc)
                    try:
                        result['controller']['controller_identity'] = observe(os.getpid())
                    except Exception as exc:
                        failure('controller_identity', exc)
                for name in ('stderr', 'worker.json', 'child.json'):
                    path = evidence / ('matrix-' + name)
                    if path.exists():
                        if name == 'stderr': result['stderr'] = path.read_text()
                        if name.endswith('.json'): result['probes'][name[:-5]] = json.loads(path.read_text())
                result['source_post'] = None
                try:
                    result['source_post'] = hashes()
                except Exception as exc:
                    failure('source_post', exc)
                result['final_observations_complete'] = (not result['errors']
                    and result['source_post'] == result['source_pre']
                    and result.get('observer_reaped') is True
                    and result.get('observer_returncode') == 0
                    and result['monitor_thread_exited'] is True
                    and result['controller'].get('thread_exited') is True
                    and result['controller'].get('socket_absent') is True
                    and result['controller'].get('ledger') == [[3, 1, 'done']]
                    and result.get('host', {}).get('worker_requests') == []
                    and result.get('worker_receipt', {}).get('cleanup', {}).get('status') == 'VERIFIED'
                    and result.get('worker_receipt', {}).get('returncode') == 0)
                persist()
        result['fixture_directory_absent'] = not directory.exists()
        (evidence / 'matrix-manifest.json').write_text(json.dumps(result, indent=2))
        return result

    def test_host_observer_drains_pending_requests_before_cleanup(self):
        result = self._run_egress_composition(inject_shutdown_request=True)
        self.assertEqual(len(result['host']['worker_requests']), 1)
        self.assertEqual(bytes.fromhex(result['host']['worker_requests'][0]['data_hex']), b'shutdown-probe')
        self.assertTrue(result['observer_reaped'])
        self.assertEqual(result['observer_returncode'], 0)

    def test_real_namespace_mount_and_descendant_readback(self):
        result = self._run_egress_composition()
        self.assertEqual(result['source_pre'], result['source_post'])
        self.assertTrue(result['observer_reaped'])
        self.assertEqual(result['observer_returncode'], 0)
        self.assertTrue(result['host']['listeners_closed'])
        self.assertTrue(result['monitor_thread_exited'])
        self.assertTrue(result['fixture_directory_absent'])
        for actor in ('worker', 'child'):
            record = result['probes'][actor]
            inspection = record['inspection']
            self.assertFalse(any(inspection['forbidden_paths'].values()), inspection)
            self.assertEqual(inspection['cap_eff'], '0000000000000000')
            self.assertEqual(inspection['no_new_privs'], '1')
            self.assertNotEqual(inspection['manager_returncode'], 0)
            self.assertTrue(inspection['mountinfo'])
            self.assertEqual(record['namespaces'], result['worker_receipt']['namespace_observation']['namespaces'])
            matches = [p for p in result['kernel_pid_readback']
                       if p['namespace_pid'] == record['pid'] and p['namespaces'] == record['namespaces']]
            self.assertTrue(matches, (actor, record['pid'], result['kernel_pid_readback']))
            self.assertTrue(all(p['cgroup'] == result['worker_receipt']['control_group'] for p in matches))
        self.assertEqual(result['probes']['worker']['child_returncode'], 0)

    def test_real_worker_child_egress_denial_with_controller_effect(self):
        result = self._run_egress_composition()
        self.assertEqual(result['worker_receipt']['execution_status'], 'EXITED')
        self.assertEqual(result['worker_receipt']['returncode'], 0, result['stderr'])
        self.assertEqual(result['worker_receipt']['cleanup']['status'], 'VERIFIED')
        self.assertEqual(result['host']['worker_requests'], [])
        self.assertEqual(len(result['host']['controls']), len(result['endpoints']))
        self.assertEqual(result['controller']['ledger'], [[3, 1, 'done']])
        self.assertEqual(result['controller']['effects'],
                         [{'reservation_before_effect': 3, 'state_before_effect': 'uncertain'}])
        self.assertEqual(result['controller']['receipts'][0]['state'], 'done')
        self.assertEqual(result['controller']['receipts'][0]['peer']['cgroup'],
                         result['worker_receipt']['control_group'])
        self.assertTrue(result['controller']['thread_exited'])
        self.assertTrue(result['controller']['socket_absent'])
        for actor in ('worker', 'child'):
            probes = result['probes'][actor]
            self.assertEqual(probes['environment']['NO_PROXY'], '*')
            self.assertEqual(probes['environment']['no_proxy'], '*')
            for name in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY'):
                self.assertIn('127.0.0.1:9', probes['environment'][name])
            self.assertEqual({p['cell'] for p in probes['attempts']},
                             {e['cell'] for e in result['endpoints']} |
                             {'ipv4_tcp_documentation', 'ipv4_udp_documentation',
                              'ipv6_tcp_documentation', 'ipv6_udp_documentation', 'dns_resolver'})
            for attempt in probes['attempts']:
                if attempt['status'] == 'capability_missing':
                    self.assertTrue(attempt['cell'].startswith('ipv6_'))
                    self.assertFalse(attempt['qualified'])
                    continue
                self.assertEqual(attempt['status'], 'denied', attempt)
                self.assertIsInstance(attempt['errno'], int, attempt)
                self.assertTrue(attempt['qualified'])

    def test_adversarial_boundary_replay_capacity_disconnect_and_isolation(self):
        import socket
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='cb-',dir=ROOT) as tmp:
            directory=Path(tmp);job=directory/'job';job.mkdir()
            (directory/'sentinel').write_text('local fixture sentinel')
            server=FixtureBridge(directory,max_accepts=8,lifetime=8)
            thread=threading.Thread(target=server.serve);thread.start()
            outside=[]
            def register(observation):
                if server.register(observation) is not True:
                    return False
                for extra in ({},{'subject':'forged','pid':os.getpid(),'cgroup':observation['control_group']}):
                    with socket.socket(socket.AF_UNIX) as s:
                        s.settimeout(1);s.connect(str(server.socket_path))
                        s.sendall(json.dumps(dict(request_id='outside',model='fixture',payload='x',max_output=1,**extra)).encode()+b'\n')
                        outside.append(json.loads(s.recv(4096)))
                with sqlite3.connect(server.ledger_path) as db:
                    return db.execute('select count(*) from requests').fetchone()[0]==0 and server.effects==[]
            script='''import socket,json,os,subprocess
assert not os.path.exists(HOST_LEDGER) and not os.path.exists(HOST_SECRET)
assert not os.path.exists('/run/user') and not os.path.exists('/run/dbus')
assert subprocess.run(['/usr/bin/systemctl','--user','show'],capture_output=True,timeout=1).returncode!=0
assert all(line.split(':')[0].strip()=='lo' for line in open('/proc/net/dev').read().splitlines()[2:])
def call(request,drop=False):
 s=socket.socket(socket.AF_UNIX);s.settimeout(1);s.connect('/controller.sock');s.sendall(json.dumps(request).encode()+b'\\n')
 if drop:s.close();return
 r=json.loads(s.recv(4096));s.close();return r
r=dict(request_id='one',model='fixture',payload='x',max_output=1)
assert call(r)['state']=='done'
assert call(r)['reason']=='duplicate'
assert call(dict(r,subject='forged'))['reason']=='protocol'
assert call(dict(r,request_id='unknown',model='unknown'))['reason']=='validation'
assert call(dict(r,request_id='cap',max_output=1000))['reason']=='capacity'
call(dict(r,request_id='drop'),True)
'''.replace('HOST_LEDGER',repr(str(server.ledger_path))).replace('HOST_SECRET',repr(str(directory/'sentinel')))
            try:
                receipt=launch(['/usr/bin/python3.12','-I','-c',script],job,receipt_path=EVIDENCE/'adversarial-worker.json',runtime_sec=5,controller_socket=server.socket_path,before_release=register)
            finally:
                thread.join(10)
            with sqlite3.connect(server.ledger_path) as db:
                rows=db.execute('select reservation,attempts,state from requests').fetchall()
            (EVIDENCE/'adversarial-controller.json').write_text(json.dumps(dict(controller_identity=observe(os.getpid()),limits={'max_accepts':server.max_accepts,'lifetime':server.lifetime,'frame_bytes':4096,'client_deadline_sec':.25},registration=server.registration,receipts=server.receipts,effects=server.effects,ledger=rows,outside=outside,thread_exited=not thread.is_alive(),socket_absent=not server.socket_path.exists()),indent=2))
            self.assertEqual(receipt['execution_status'],'EXITED',receipt.get('error'))
            self.assertEqual(receipt['returncode'],0,(job/'stderr').read_text())
            self.assertEqual(outside,[{'state':'refused','reason':'authorization'}]*2)
            self.assertEqual(rows,[(3,1,'done')]*2)
            self.assertEqual(len(server.effects),2)
            self.assertFalse(thread.is_alive());self.assertFalse(server.socket_path.exists())
            self.assertEqual(receipt['cleanup']['status'],'VERIFIED')
            import shutil
            shutil.copyfile(server.ledger_path,EVIDENCE/'adversarial-ledger.sqlite')

    def test_uncertainty_is_durable_and_replay_not_forwarded(self):
        with tempfile.TemporaryDirectory(prefix='cb-',dir=ROOT) as tmp:
            directory=Path(tmp);job=directory/'job';job.mkdir()
            server=FixtureBridge(directory,max_accepts=2,lifetime=8,fixture_outcome='uncertain')
            thread=threading.Thread(target=server.serve);thread.start()
            script='''import socket,json
for reason in (None,'duplicate'):
 s=socket.socket(socket.AF_UNIX);s.settimeout(1);s.connect('/controller.sock')
 s.sendall(b'{"request_id":"uncertain","model":"fixture","payload":"x","max_output":1}\\n')
 r=json.loads(s.recv(4096));s.close();assert r['uncertain'] is True and r['reason']==reason,r
'''
            try:
                receipt=launch(['/usr/bin/python3.12','-I','-c',script],job,receipt_path=EVIDENCE/'uncertainty-worker.json',runtime_sec=5,controller_socket=server.socket_path,before_release=server.register)
            finally:thread.join(10)
            with sqlite3.connect(server.ledger_path) as db:
                rows=db.execute('select reservation,attempts,state from requests').fetchall()
            (EVIDENCE/'uncertainty-controller.json').write_text(json.dumps(dict(controller_identity=observe(os.getpid()),limits={'max_accepts':server.max_accepts,'lifetime':server.lifetime,'frame_bytes':4096,'client_deadline_sec':.25},receipts=server.receipts,registration=server.registration,ledger=rows,effects=server.effects,thread_exited=not thread.is_alive(),socket_absent=not server.socket_path.exists()),indent=2))
            self.assertEqual(receipt['execution_status'],'EXITED',receipt.get('error'))
            self.assertEqual(receipt['returncode'],0,(job/'stderr').read_text())
            self.assertEqual(rows,[(3,1,'uncertain')]);self.assertEqual(len(server.effects),1)
            self.assertEqual(receipt['cleanup']['status'],'VERIFIED')
            self.assertFalse(thread.is_alive());self.assertFalse(server.socket_path.exists())
            import shutil
            shutil.copyfile(server.ledger_path,EVIDENCE/'uncertainty-ledger.sqlite')

    def test_durable_fixture_through_isolated_socket(self):
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='cb-', dir=ROOT) as tmp:
            directory = Path(tmp)
            job = directory / 'job'
            job.mkdir()
            server = FixtureBridge(directory, max_accepts=1, lifetime=8)
            thread = threading.Thread(target=server.serve)
            thread.start()
            script = '''import json,socket
s=socket.socket(socket.AF_UNIX);s.settimeout(1);s.connect('/controller.sock')
s.sendall(b'{"request_id":"one","model":"fixture","payload":"x","max_output":1}\\n')
r=json.loads(s.recv(4096));assert r['state']=='done',r
'''
            try:
                receipt = launch(['/usr/bin/python3.12','-I','-c',script],job,
                    receipt_path=EVIDENCE/'composition-worker.json',runtime_sec=5,
                    controller_socket=server.socket_path,before_release=server.register)
            finally:
                thread.join(10)
            (EVIDENCE/'composition-controller.json').write_text(json.dumps({
                'controller_identity':observe(os.getpid()),
                'limits':{'max_accepts':server.max_accepts,'lifetime':server.lifetime,'frame_bytes':4096,'client_deadline_sec':.25},
                'registration':getattr(server,'registration',None), 'receipts':server.receipts,
                'socket_absent':not server.socket_path.exists(), 'thread_exited':not thread.is_alive()},indent=2))
            self.assertFalse(thread.is_alive())
            self.assertEqual(receipt['execution_status'], 'EXITED', receipt.get('error'))
            self.assertEqual(receipt['returncode'],0,(job/'stderr').read_text())
            self.assertEqual(receipt['cleanup']['status'],'VERIFIED')
            self.assertFalse(server.socket_path.exists())
            with sqlite3.connect(server.ledger_path) as db:
                self.assertEqual(db.execute('select reservation,attempts,state from requests').fetchall(),[(3,1,'done')])
            self.assertEqual(server.effects,[{'reservation_before_effect':3,'state_before_effect':'uncertain'}])
            import shutil
            shutil.copyfile(server.ledger_path,EVIDENCE/'composition-ledger.sqlite')

if __name__ == '__main__':
    unittest.main()
