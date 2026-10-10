"""Bounded LOCAL FIXTURE bridge. Not a live/native/provider capability.

Cooperative host path/cgroup administration is required. The controller lives
outside the disposable worker service. Only a fixed synthetic effect is exposed.
"""
import json
import os
from pathlib import Path
import socket
import struct
import time
from budget_controller import BudgetController


def observe(pid):
    stat = Path(f'/proc/{pid}/stat').read_text()
    start = stat[stat.rfind(')') + 2:].split()[19]
    status = Path(f'/proc/{pid}/status').read_text()
    uid = int(next(line.split()[1] for line in status.splitlines() if line.startswith('Uid:')))
    groups = Path(f'/proc/{pid}/cgroup').read_text().splitlines()
    if len(groups) != 1 or not groups[0].startswith('0::/'):
        raise ValueError('unknown cgroup observation')
    again = Path(f'/proc/{pid}/stat').read_text()
    if again[again.rfind(')') + 2:].split()[19] != start:
        raise ValueError('pid changed')
    return dict(pid=pid, uid=uid, starttime=start, cgroup=groups[0][3:])


class FixtureBridge:
    def __init__(self, directory, *, max_accepts=16, lifetime=10, fixture_outcome='done'):
        if type(fixture_outcome) is not str or fixture_outcome not in ('done','uncertain'):
            raise ValueError('unknown local fixture outcome')
        self.fixture_outcome = fixture_outcome
        import math
        if type(max_accepts) is not int or not 1 <= max_accepts <= 256 or type(lifetime) not in (int,float) or not math.isfinite(lifetime) or not .05 <= lifetime <= 30:
            raise ValueError('invalid finite server bounds')
        from native_containment import clean_path, SCRATCH_ROOT
        self.directory = clean_path(directory)
        if SCRATCH_ROOT not in self.directory.parents or not self.directory.is_dir() or self.directory.stat().st_uid != os.getuid() or self.directory.stat().st_mode & 0o077:
            raise ValueError('private caller-owned scratch directory required')
        self.socket_path = self.directory / 'controller.sock'
        if len(os.fsencode(self.socket_path)) > 107:
            raise ValueError('Unix socket path exceeds Linux bound')
        self.ledger_path = clean_path(self.directory / 'ledger.sqlite')
        if self.socket_path.exists() or self.socket_path.is_symlink():
            raise ValueError('socket already exists')
        if self.ledger_path.exists() and (not self.ledger_path.is_file() or self.ledger_path.stat().st_uid != os.getuid() or self.ledger_path.stat().st_mode & 0o077):
            raise ValueError('private ledger required')
        self.budget = BudgetController(self.ledger_path, cap=32,
            catalog={'fixture': (1, 1, 1)}, scope='local-controller-fixture')
        self.receipts = []
        self.effects = []
        self.registration = None
        self.max_accepts = max_accepts
        self.lifetime = lifetime
        self.listener = socket.socket(socket.AF_UNIX)
        self.listener.bind(str(self.socket_path))
        os.chmod(self.socket_path, 0o600)
        self.listener.listen(1)

    def register(self, observation):
        # Never trust worker assertions: re-read manager and kernel identities.
        from native_containment import unit_state
        import re
        self.registration = None
        try:
            if type(observation) is not dict or set(observation) != {'unit', 'control_group', 'namespace_host_pids'}:
                return False
            unit, group, pids = (observation[k] for k in ('unit', 'control_group', 'namespace_host_pids'))
            if type(unit) is not str or not re.fullmatch(r'native-containment-[0-9a-f]{32}\.service', unit):
                return False
            if type(group) is not str or not group.startswith('/') or Path(group).name != unit or '..' in Path(group).parts:
                return False
            if type(pids) is not list or not pids or any(type(p) is not int or p <= 0 for p in pids):
                return False
            if unit_state(unit).get('ControlGroup') != group:
                return False
            peers = [observe(p) for p in pids]
            if observe(os.getpid())['cgroup'] == group or any(p['uid'] != os.getuid() or p['cgroup'] != group for p in peers):
                return False
            self.registration = {'unit': unit, 'cgroup': group, 'uid': os.getuid(), 'peers': peers}
            return True
        except (OSError, ValueError, RuntimeError, KeyError):
            return False

    def authorized(self, pid, uid):
        try:
            peer = observe(pid)
            if self.registration is None or uid != self.registration['uid'] or peer['uid'] != uid or peer['cgroup'] != self.registration['cgroup']:
                return None
            original = next((p for p in self.registration['peers'] if p['pid'] == pid), None)
            if original is not None and original['starttime'] != peer['starttime']:
                return None
            return peer
        except (OSError, ValueError, StopIteration):
            return None

    def forward_fixture(self, request):
        # Fixed bounded local effect only. No caller-supplied adapter or destination.
        import sqlite3
        import hashlib
        digest = hashlib.sha256(json.dumps(request['request_id'], separators=(',', ':')).encode()).hexdigest()
        db = sqlite3.connect(self.ledger_path, timeout=.25)
        try:
            with db:
                row = db.execute('select reservation,state from requests where request_id=?', (digest,)).fetchone()
        finally:
            db.close()
        if row is None or row[1] != 'uncertain':
            raise ValueError('missing durable reservation')
        self.effects.append({'reservation_before_effect': row[0], 'state_before_effect': row[1]})
        if self.fixture_outcome == 'uncertain':
            raise RuntimeError('fixed local fixture uncertainty')

    def handle(self, client, pid, uid):
        peer = self.authorized(pid, uid)
        if peer is None:
            return {'state':'refused', 'reason':'authorization'}, None
        raw = bytearray()
        frame_deadline = time.monotonic() + min(.25, client.gettimeout() or .25)
        while not raw.endswith(b'\n') and len(raw) <= 4096:
            remaining = frame_deadline - time.monotonic()
            if remaining <= 0:
                raise ValueError('deadline')
            client.settimeout(remaining)
            chunk = client.recv(min(4097-len(raw), 1024))
            if not chunk:
                raise ValueError('incomplete frame')
            raw.extend(chunk)
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError('duplicate')
                result[key] = value
            return result
        if len(raw) > 4096 or raw.count(b'\n') != 1 or not raw.endswith(b'\n'):
            raise ValueError('frame')
        request = json.loads(raw.decode('utf-8'), object_pairs_hook=unique,
                             parse_constant=lambda _: (_ for _ in ()).throw(ValueError('constant')))
        if type(request) is not dict or set(request) != {'request_id','model','payload','max_output'}:
            raise ValueError('schema')
        if any(type(request[k]) is not str for k in ('request_id','model','payload')) or type(request['max_output']) is not int:
            raise ValueError('type')
        if not all(1 <= len(request[k]) <= 256 for k in ('request_id','model')) or not 0 <= request['max_output'] <= 1000000:
            raise ValueError('bounds')
        request['payload'].encode('utf-8')
        if self.authorized(pid, uid) != peer:
            return {'state':'refused', 'reason':'authorization'}, peer
        request['subject'] = self.registration['cgroup']
        receipt = self.budget.submit(request, self)
        return {k:receipt[k] for k in ('state','reason','reservation','attempts','uncertain')}, peer

    def serve(self):
        deadline = time.monotonic() + self.lifetime
        try:
            for _ in range(self.max_accepts):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self.listener.settimeout(remaining)
                try:
                    client, _ = self.listener.accept()
                except socket.timeout:
                    break
                with client:
                    client.settimeout(min(.25, max(.001, deadline-time.monotonic())))
                    pid, uid, gid = struct.unpack('3i', client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                    try:
                        response, peer = self.handle(client, pid, uid)
                    except (OSError, ValueError, UnicodeError):
                        response, peer = {'state':'refused', 'reason':'protocol'}, None
                    try:
                        kernel_identity = observe(pid)
                    except (OSError, ValueError, StopIteration):
                        kernel_identity = None
                    self.receipts.append(dict(pid=pid, uid=uid, gid=gid, peer=peer,
                        kernel_identity=kernel_identity, **response))
                    try:
                        client.sendall(json.dumps(response).encode() + b'\n')
                    except OSError:
                        self.receipts[-1]['delivery'] = 'unknown'
        finally:
            self.listener.close()
            self.socket_path.unlink()
