#!/usr/bin/env python3
"""Bounded local containment slice. NOT a native/model execution acceptance gate.

Only installed Python/true/systemctl fixtures are admitted. No fallback, providers,
network dispatch, budget approval, or lifecycle-gate mutation. Trusted root-owned
runtime and cooperative host pathname ownership are prerequisites; this is not a
reviewed arbitrary-hostile-code sandbox. Receipts are launcher observations, not
worker-produced native acceptance evidence.
"""
from pathlib import Path
import json
import math
import os
import re
import stat
import subprocess
import time
import uuid

SCRATCH_ROOT = (Path.home() / '.hermes/cache/scratch')
BINARIES = ('/usr/bin/python3.12', '/usr/bin/true', '/usr/bin/systemctl')
STDLIB = '/usr/lib/python3.12'
LIBRARY_ROOT = Path('/usr/lib/x86_64-linux-gnu')
SONAMES = ('libm.so.6', 'libz.so.1', 'libexpat.so.1', 'libc.so.6',
           'libcap.so.2', 'liblz4.so.1', 'libselinux.so.1', 'liblzma.so.5',
           'libzstd.so.1', 'libblkid.so.1', 'libgcrypt.so.20', 'libmount.so.1',
           'libcrypto.so.3', 'libpcre2-8.so.0', 'libgpg-error.so.0',
           'ld-linux-x86-64.so.2')


def runtime_manifest():
    # Mount stdlib entries, not its root: distribution sitecustomize/config links
    # can point into host /etc or unrelated libraries. They are never admitted.
    packages = {'encodings', 'json', 'collections', 're', 'importlib', 'lib-dynload', 'urllib'}
    stdlib = {str(p): str(p) for p in sorted(Path(STDLIB).iterdir())
              if not p.is_symlink() and ((p.is_file() and p.suffix == '.py'
                  and p.name != 'sitecustomize.py') or p.name in packages)}
    libraries = {}
    for name in SONAMES:
        source = (LIBRARY_ROOT / name).resolve()
        if source.parent != LIBRARY_ROOT:
            raise ValueError('library symlink escapes fixed runtime root')
        libraries[str(source)] = '/lib/x86_64-linux-gnu/' + name
    libraries[str(LIBRARY_ROOT / 'ld-linux-x86-64.so.2')] = '/lib64/ld-linux-x86-64.so.2'
    return {**{p: p for p in BINARIES}, **stdlib, **libraries}


def clean_path(value):
    text = os.fspath(value)
    if not text.startswith('/') or os.path.normpath(text) != text:
        raise ValueError('absolute canonical lexical path required')
    path = Path(text)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('symlink path refused')
    return path


def build_plan(argv, scratch, *, runtime_mounts, runtime_sec=2, memory_bytes=134217728,
               tasks=16, cpu_percent=100, controller_socket=None):
    for value, low, high in ((runtime_sec, .1, 5), (memory_bytes, 16777216, 536870912),
                             (tasks, 4, 64), (cpu_percent, 1, 100)):
        if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError('invalid hard resource bound')
    if type(memory_bytes) is not int or type(tasks) is not int:
        raise ValueError('memory and task bounds must be integral')
    scratch = clean_path(scratch)
    if SCRATCH_ROOT not in scratch.parents or not scratch.is_dir():
        raise ValueError('job must be an existing dedicated directory below scratch root')
    if controller_socket is not None:
        controller_socket = clean_path(controller_socket)
        if controller_socket == scratch or scratch in controller_socket.parents:
            raise ValueError('controller socket must be outside worker scratch')
        try:
            socket_stat = controller_socket.stat()
        except OSError as exc:
            raise ValueError('controller socket unavailable') from exc
        if not stat.S_ISSOCK(socket_stat.st_mode) or socket_stat.st_uid != os.getuid():
            raise ValueError('controller socket must be a caller-owned Unix socket')
    if not argv or argv[0] not in BINARIES or any(not isinstance(x, str) or '\0' in x for x in argv):
        raise ValueError('only explicit local Python/true/systemctl fixtures are allowed')
    manifest = runtime_manifest()
    for mount in runtime_mounts:
        if str(clean_path(mount)) not in manifest:
            raise ValueError('non-allowlisted runtime mount refused')
    controls = {'RuntimeMaxSec': runtime_sec, 'TimeoutStopSec': 1,
                'MemoryMax': memory_bytes, 'TasksMax': tasks,
                'CPUQuota': f'{cpu_percent}%', 'KillMode': 'control-group',
                'NoNewPrivileges': 'yes', 'RemainAfterExit': 'yes'}
    sandbox = ['/usr/bin/bwrap', '--unshare-user', '--unshare-pid', '--unshare-net',
               '--unshare-ipc', '--unshare-uts', '--die-with-parent', '--new-session',
               '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/run',
               '--tmpfs', '/home', '--dir', '/home/sandbox', '--clearenv',
               '--setenv', 'HOME', '/home/sandbox', '--setenv', 'PATH', '/usr/bin',
               '--setenv', 'LANG', 'C', '--bind', str(scratch), '/job', '--chdir', '/job']
    for mount in runtime_mounts:
        sandbox += ['--ro-bind', str(mount), manifest[str(mount)]]
    if controller_socket is not None:
        sandbox += ['--ro-bind', str(controller_socket), '/controller.sock']
    sandbox += ['--', *argv]
    return {'sandbox_argv': sandbox, 'configured_controls': controls,
            'live_model_execution': 'NOT_RUN'}


def command(args):
    uid = os.getuid()
    env = {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'XDG_RUNTIME_DIR': f'/run/user/{uid}',
           'DBUS_SESSION_BUS_ADDRESS': f'unix:path=/run/user/{uid}/bus'}
    return subprocess.run(args, capture_output=True, text=True, env=env, timeout=3)


def unit_state(unit):
    result = command(['/usr/bin/systemctl', '--user', 'show', unit])
    if result.returncode:
        raise RuntimeError('cannot observe exact service unit: ' + result.stderr.strip())
    return dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)


def seconds(text):
    matches = re.findall(r'([\d.]+)(min|ms|us|s)', text)
    if not matches or ''.join(a + b for a, b in matches) != text.replace(' ', ''):
        raise RuntimeError('unrecognized systemd duration: ' + text)
    return sum(float(a) * {'min': 60, 's': 1, 'ms': .001, 'us': .000001}[b] for a, b in matches)


def cgroup_pids(path):
    if path is None or not path.exists():
        return []
    pids = set()
    for entry in path.rglob('cgroup.procs'):
        try:
            pids.update(int(p) for p in entry.read_text().split())
        except FileNotFoundError:
            # Exact owned group may disappear between enumeration and read.
            continue
    return sorted(pids)


def host_pid_identity(pid):
    try:
        # Starttime distinguishes recycled host PIDs. Never use namespace worker PIDs.
        stat = Path(f'/proc/{pid}/stat').read_text()
        return stat[stat.rfind(')') + 2:].split()[19]
    except FileNotFoundError:
        return None


def trusted_runtime(mounts):
    for source in mounts:
        path = clean_path(source)
        entries = (path, *path.rglob('*')) if path.is_dir() else (path,)
        for entry in entries:
            if entry.is_symlink():
                if path not in entry.resolve().parents:
                    raise ValueError('escaping runtime symlink refused')
            stat = entry.stat()
            if stat.st_uid != 0 or stat.st_mode & 0o022:
                raise ValueError('runtime is not root-owned and non-writable')


GATE = '''import json, os, sys, time
from pathlib import Path
nonce, target = sys.argv[1], json.loads(sys.argv[2])
ready = {'namespaces': {n: os.readlink('/proc/self/ns/' + n) for n in ('user','pid','net','mnt')},
         'environment': dict(os.environ), 'home_entries': os.listdir(os.environ['HOME']),
         'manager_paths_present': os.path.exists('/run/user') or os.path.exists('/run/dbus')}
Path('/job/.ready-' + nonce).write_text(json.dumps(ready))
while not Path('/job/.release-' + nonce).exists(): time.sleep(.01)
os.execv(target[0], target)
'''


def launch(argv, scratch, *, receipt_path, runtime_sec=2, memory_bytes=134217728,
           tasks=16, cpu_percent=100, cancel_event=None, controller_socket=None,
           before_release=None):
    """Run one <=5s disposable user service; persist an honest observation receipt.

    The target is released only after manager, kernel cgroup and namespace checks.
    RemainAfterExit retains the exact unit for observation; launcher stops it on
    successful leader exit as well as failures. RuntimeMaxSec is the independent
    manager-side deadline if the launcher dies.

    Optional controller_socket is a canonical caller-owned Unix socket outside
    the worker job, bound read-only at /controller.sock. It requires the paired
    trusted before_release(observation) callback: after verification and before
    release, observation contains unit, control_group and namespace_host_pids.
    Only an exact True return authorizes release; exceptions refuse and clean up.
    The trusted callback must be bounded by its caller; it is not worker input.
    """
    started = time.monotonic()
    receipt_path = clean_path(receipt_path)
    if SCRATCH_ROOT not in receipt_path.parents:
        raise ValueError('receipt must remain under scratch root')
    nonce = uuid.uuid4().hex
    unit = 'native-containment-' + nonce + '.service'
    receipt = {'unit': unit, 'argv': list(argv), 'control_group': None,
               'configured_controls': {}, 'verified_controls': {}, 'observed_host_pids': [],
               'execution_status': 'NOT_RUN', 'returncode': None, 'live_model_execution': 'NOT_RUN',
               'cancellation': {'requested': False, 'acknowledged': False},
               'cleanup': {'unit_absent': False, 'cgroup_empty': False,
                           'cgroup_absent': False, 'observed_host_pids_absent': False}, 'started_unix': time.time()}
    dispatched = False
    cgroup = None
    identities = {}
    observations = {}

    def observe_pids():
        for pid in cgroup_pids(cgroup):
            identity = host_pid_identity(pid)
            if identity is None:
                continue
            identities.setdefault(pid, identity)
            if pid in observations:
                continue
            try:
                status = Path(f'/proc/{pid}/status').read_text()
                nspid = next(line.split()[1:] for line in status.splitlines() if line.startswith('NSpid:'))
                observations[pid] = {'host_pid': pid, 'starttime': identity,
                    'namespace_pid': int(nspid[-1]), 'isolated_pid_namespace':
                    os.readlink(f'/proc/{pid}/ns/pid') != os.readlink('/proc/self/ns/pid'),
                    'control_group': receipt['control_group'],
                    'observed_elapsed_sec': time.monotonic() - started}
            except (FileNotFoundError, StopIteration):
                continue

    def cancellation_requested():
        if cancel_event is None or not cancel_event.is_set():
            return False
        receipt['execution_status'] = 'CANCELLED'
        receipt['cancellation'].update(requested=True, actor='caller', reason='cancel-event',
            requested_elapsed_sec=time.monotonic() - started)
        return True

    try:
        if cancellation_requested():
            return receipt
        if (controller_socket is None) != (before_release is None) or (
                before_release is not None and not callable(before_release)):
            raise ValueError('controller socket and callable before_release must be paired')
        scratch = clean_path(scratch)
        if scratch in receipt_path.parents or receipt_path == scratch:
            raise ValueError('receipt cannot be placed in worker-writable job')
        mounts = list(runtime_manifest())
        plan = build_plan(argv, scratch, runtime_mounts=mounts, runtime_sec=runtime_sec,
                          memory_bytes=memory_bytes, tasks=tasks, cpu_percent=cpu_percent,
                          controller_socket=controller_socket)
        receipt.update(plan)
        if list(scratch.iterdir()) or scratch.stat().st_uid != os.getuid():
            raise ValueError('job must be empty and owned by caller')
        scratch_identity = (scratch.stat().st_dev, scratch.stat().st_ino)
        trusted_runtime(mounts)
        for tool in ('/usr/bin/systemd-run', '/usr/bin/systemctl', '/usr/bin/bwrap'):
            trusted_runtime([tool])
            if not os.access(tool, os.X_OK):
                raise RuntimeError('required installed control unavailable: ' + tool)
        if not Path('/sys/fs/cgroup/cgroup.controllers').is_file():
            raise RuntimeError('cgroup v2 unavailable')
        manager = command(['/usr/bin/systemctl', '--user', 'show', '--property=Version'])
        if manager.returncode:
            raise RuntimeError('user manager unavailable')
        gate_argv = ['/usr/bin/python3.12', '-I', '-c', GATE, nonce, json.dumps(argv)]
        sandbox = build_plan(gate_argv, scratch, runtime_mounts=mounts, runtime_sec=runtime_sec,
                             memory_bytes=memory_bytes, tasks=tasks, cpu_percent=cpu_percent,
                             controller_socket=controller_socket)['sandbox_argv']
        receipt['sandbox_argv'] = sandbox
        dispatch = ['/usr/bin/systemd-run', '--user', '--unit=' + unit, '--service-type=exec']
        for name, value in plan['configured_controls'].items():
            dispatch += ['--property=' + name + '=' + str(value)]
        dispatch += ['--property=StandardOutput=file:' + str(scratch / 'stdout'),
                     '--property=StandardError=file:' + str(scratch / 'stderr'), '--', *sandbox]
        receipt['dispatch_argv'] = dispatch
        dispatched = True  # cleanup even if the client's acknowledgement is lost
        result = command(dispatch)
        receipt['dispatch_returncode'] = result.returncode
        if result.returncode:
            raise RuntimeError('service dispatch refused: ' + result.stderr.strip())
        ready_path = scratch / ('.ready-' + nonce)
        deadline = started + runtime_sec + 3
        while not ready_path.exists():
            if cancellation_requested():
                return receipt
            state = unit_state(unit)
            if state.get('ActiveState') in ('failed', 'inactive') or time.monotonic() >= deadline:
                raise RuntimeError('namespace bootstrap did not become ready')
            time.sleep(.02)
        clean_path(scratch)
        if scratch_identity != (scratch.stat().st_dev, scratch.stat().st_ino):
            raise RuntimeError('job pathname changed during dispatch')
        state = unit_state(unit)
        group = state.get('ControlGroup', '')
        if not group.startswith('/') or Path(group).name != unit or '..' in Path(group).parts:
            raise RuntimeError('exact owned service cgroup unavailable')
        receipt['control_group'] = group
        cgroup = Path('/sys/fs/cgroup' + group)
        kernel = {name: (cgroup / name).read_text().strip() for name in ('memory.max', 'pids.max', 'cpu.max')}
        checks = {
            'RuntimeMaxSec': seconds(state['RuntimeMaxUSec']) == runtime_sec,
            'TimeoutStopSec': seconds(state['TimeoutStopUSec']) == 1,
            'KillMode': state['KillMode'] == 'control-group',
            'NoNewPrivileges': state['NoNewPrivileges'] == 'yes',
            'RemainAfterExit': state['RemainAfterExit'] == 'yes',
            'MemoryMax': state['MemoryMax'] == str(memory_bytes) == kernel['memory.max'],
            'TasksMax': state['TasksMax'] == str(tasks) == kernel['pids.max'],
            'CPUQuota': seconds(state['CPUQuotaPerSecUSec']) == cpu_percent / 100,
        }
        quota, period = kernel['cpu.max'].split()
        checks['cpu.max'] = quota != 'max' and int(quota) / int(period) <= cpu_percent / 100
        receipt['manager_properties'] = {k: state[k] for k in ('RuntimeMaxUSec', 'TimeoutStopUSec',
            'KillMode', 'NoNewPrivileges', 'RemainAfterExit', 'MemoryMax', 'TasksMax', 'CPUQuotaPerSecUSec')}
        receipt['kernel_controls'] = kernel
        ready = json.loads(clean_path(ready_path).read_text())
        pids = cgroup_pids(cgroup)
        namespace_host_pids = []
        for pid in pids:
            try:
                observed = {n: os.readlink(f'/proc/{pid}/ns/{n}') for n in ('user', 'pid', 'net', 'mnt')}
                if observed == ready['namespaces']:
                    namespace_host_pids.append(pid)
            except FileNotFoundError:
                continue
        checks['namespace_host_pid_observed'] = bool(namespace_host_pids)
        checks['namespaces_distinct_from_host'] = all(ready['namespaces'][n] != os.readlink('/proc/self/ns/' + n)
                                                     for n in ('user', 'pid', 'net', 'mnt'))
        checks['empty_home'] = ready['home_entries'] == []
        checks['manager_bus_unmounted'] = ready['manager_paths_present'] is False
        checks['cleared_environment'] = ready['environment'] == {
            'HOME': '/home/sandbox', 'PATH': '/usr/bin', 'LANG': 'C', 'PWD': '/job'}
        receipt['namespace_observation'] = ready
        receipt['namespace_host_pids'] = namespace_host_pids
        receipt['verified_controls'] = checks
        if not all(checks.values()):
            raise RuntimeError('required controls could not be verified')
        observe_pids()
        if cancellation_requested():
            return receipt
        if before_release is not None:
            if before_release({'unit': unit, 'control_group': group,
                               'namespace_host_pids': list(namespace_host_pids)}) is not True:
                raise RuntimeError('trusted before_release registration refused')
            if cancellation_requested():
                return receipt
        (scratch / ('.release-' + nonce)).write_text('release')
        receipt['execution_status'] = 'RUNNING'
        receipt['released_elapsed_sec'] = time.monotonic() - started
        while time.monotonic() < deadline:
            observe_pids()
            if cancel_event is not None and cancel_event.is_set():
                receipt['execution_status'] = 'CANCELLED'
                receipt['cancellation'].update(requested=True, actor='caller', reason='cancel-event',
                    requested_elapsed_sec=time.monotonic() - started)
                break
            state = unit_state(unit)
            if state.get('SubState') == 'exited' or state.get('ActiveState') in ('failed', 'inactive'):
                receipt['service_result'] = state.get('Result')
                receipt['exec_main_code'] = int(state.get('ExecMainCode', '0'))
                receipt['exec_main_status'] = int(state.get('ExecMainStatus', '0'))
                receipt['returncode'] = (receipt['exec_main_status'] if receipt['exec_main_code'] == 1
                    else -receipt['exec_main_status'] if receipt['exec_main_code'] in (2, 3) else None)
                receipt['execution_status'] = 'TIMED_OUT' if state.get('Result') == 'timeout' else 'EXITED'
                if receipt['execution_status'] == 'TIMED_OUT':
                    receipt['cancellation'].update(requested=True, actor='systemd', reason='RuntimeMaxSec')
                break
            time.sleep(.02)
        else:
            receipt['execution_status'] = 'CANCELLED'
            receipt['cancellation']['requested'] = True
    except Exception as exc:
        receipt['error'] = str(exc)
        receipt['execution_status'] = 'ERROR' if receipt['execution_status'] == 'RUNNING' else 'REFUSED'
    finally:
        cleanup_started = time.monotonic()
        receipt['cleanup']['trigger'] = {
            'EXITED': 'leader-exit', 'TIMED_OUT': 'runtime-deadline',
            'CANCELLED': 'launcher-deadline'}.get(receipt['execution_status'], 'refusal-or-error')
        if dispatched:
            try:
                if cgroup is None:
                    state = unit_state(unit)
                    group = state.get('ControlGroup', '')
                    if group.startswith('/') and Path(group).name == unit and '..' not in Path(group).parts:
                        receipt['control_group'] = group
                        cgroup = Path('/sys/fs/cgroup' + group)
                observe_pids()
            except Exception as exc:
                receipt['cleanup']['error'] = str(exc)
            # Observation is best-effort; never let it suppress exact-unit stop.
            for action, field in (('stop', 'stop_returncode'), ('reset-failed', 'reset_failed_returncode')):
                try:
                    result = command(['/usr/bin/systemctl', '--user', action, unit])
                    receipt['cleanup'][field] = result.returncode
                except Exception as exc:
                    receipt['cleanup'][action + '_error'] = str(exc)
            try:
                state = unit_state(unit)
                receipt['cleanup']['unit_load_state'] = state.get('LoadState')
                receipt['cleanup']['unit_absent'] = state.get('LoadState') == 'not-found'
                receipt['cleanup']['cgroup_empty'] = cgroup is not None and not cgroup_pids(cgroup)
                receipt['cleanup']['cgroup_absent'] = cgroup is not None and not cgroup.exists()
                receipt['cleanup']['observed_host_pids_absent'] = all(
                    identity is None or host_pid_identity(pid) != identity for pid, identity in identities.items())

            except Exception as exc:
                receipt['cleanup']['error'] = str(exc)
        receipt['cleanup']['status'] = ('NOT_NEEDED' if not dispatched else
            'VERIFIED' if all(receipt['cleanup'].get(k, False) for k in
                ('unit_absent', 'cgroup_absent', 'cgroup_empty', 'observed_host_pids_absent')) else 'UNVERIFIED')
        if receipt['cancellation']['requested']:
            receipt['cancellation']['acknowledged'] = receipt['cleanup']['status'] == 'VERIFIED'
        receipt['cleanup']['elapsed_sec'] = time.monotonic() - cleanup_started
        receipt['cleanup']['finished_unix'] = time.time()
        receipt['host_pid_observations'] = [v for _, v in sorted(observations.items())]
        receipt['observed_host_pids'] = [{'pid': p, 'starttime': identity} for p, identity in sorted(identities.items())]
        receipt['elapsed_sec'] = time.monotonic() - started
        receipt['finished_unix'] = time.time()
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scratch', required=True, type=Path)
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--runtime-sec', type=float, default=2)
    parser.add_argument('--memory-bytes', type=int, default=134217728)
    parser.add_argument('--tasks', type=int, default=16)
    parser.add_argument('--cpu-percent', type=float, default=100)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    target = args.command[1:] if args.command[:1] == ['--'] else args.command
    result = launch(target, args.scratch, receipt_path=args.receipt, runtime_sec=args.runtime_sec,
                    memory_bytes=args.memory_bytes, tasks=args.tasks, cpu_percent=args.cpu_percent)
    print(json.dumps({'unit': result['unit'], 'execution_status': result['execution_status'],
                      'returncode': result['returncode'], 'cleanup': result['cleanup'],
                      'receipt': str(args.receipt), 'live_model_execution': 'NOT_RUN'}))
    return 0 if (result['execution_status'] == 'EXITED' and result['returncode'] == 0
        and result['cleanup'].get('status') == 'VERIFIED' and all(
            result['cleanup'].get(k) is True for k in
            ('unit_absent', 'cgroup_absent', 'cgroup_empty', 'observed_host_pids_absent'))) else 1


if __name__ == '__main__':
    raise SystemExit(main())
