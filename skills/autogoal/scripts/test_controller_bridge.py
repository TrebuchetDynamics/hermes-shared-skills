"""Offline local fixture bridge controls; no installed sandbox required."""
import json
import os
from pathlib import Path
import socket
import sqlite3
import tempfile
import threading
import unittest
import controller_bridge as bridge

ROOT = Path.home() / '.hermes/cache/scratch'
ROOT.mkdir(parents=True, exist_ok=True)

class BridgeTests(unittest.TestCase):
    def test_forwarding_connections_closed_on_every_exit(self):
        from unittest.mock import patch
        real_connect = sqlite3.connect
        for outcome in ('done', 'uncertain', 'missing', 'query_error'):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory(prefix='cb-', dir=ROOT) as tmp:
                server = bridge.FixtureBridge(Path(tmp), max_accepts=1, lifetime=.05,
                    fixture_outcome='uncertain' if outcome == 'uncertain' else 'done')
                connections = []

                class TrackedConnection(sqlite3.Connection):
                    close_calls = 0

                    def close(self):
                        self.close_calls += 1
                        super().close()

                    def execute(self, sql, *args, **kwargs):
                        if outcome == 'query_error' and sql.startswith('select reservation,state'):
                            raise sqlite3.OperationalError('injected forwarding read failure')
                        return super().execute(sql, *args, **kwargs)

                def connect(*args, **kwargs):
                    db = real_connect(*args, factory=TrackedConnection, **kwargs)
                    connections.append(db)  # Keep alive: GC cannot hide a leaked handle.
                    return db

                request = dict(request_id='close-test', subject='/test.service',
                               model='fixture', payload='x', max_output=1)
                try:
                    with patch('sqlite3.connect', side_effect=connect):
                        if outcome == 'missing':
                            with self.assertRaisesRegex(ValueError, 'missing durable reservation'):
                                server.forward_fixture(request)
                        else:
                            result = server.budget.submit(request, server)
                            self.assertEqual(result['state'], 'done' if outcome == 'done' else 'uncertain')
                            self.assertEqual(result['reservation'], 3)
                            self.assertEqual(result['attempts'], 1)
                        self.assertTrue(connections)
                        for db in connections:
                            self.assertEqual(db.close_calls, 1, 'connection was not explicitly closed')
                            with self.assertRaises(sqlite3.ProgrammingError):
                                db.execute('SELECT 1')
                    self.assertEqual(len(server.effects), int(outcome in ('done', 'uncertain')))
                    if server.effects:
                        self.assertEqual(server.effects[0],
                            {'reservation_before_effect': 3, 'state_before_effect': 'uncertain'})
                    db = real_connect(server.ledger_path)
                    try:
                        self.assertEqual(db.execute('select reservation,state from requests').fetchall(),
                            [] if outcome == 'missing' else [(3, 'done' if outcome == 'done' else 'uncertain')])
                    finally:
                        db.close()
                finally:
                    for db in connections:
                        if not db.close_calls:
                            db.close()
                    server.listener.close()
                    server.socket_path.unlink()

    def test_oversized_unix_path_refuses_before_ledger_creation(self):
        with tempfile.TemporaryDirectory(prefix='cb-',dir=ROOT) as tmp:
            private=Path(tmp)/('p'*80);private.mkdir(mode=0o700)
            with self.assertRaises(ValueError):bridge.FixtureBridge(private)
            self.assertEqual(list(private.iterdir()),[])

    def test_private_directory_and_ledger_symlinks_refused(self):
        with tempfile.TemporaryDirectory(prefix='cb-',dir=ROOT) as tmp:
            root=Path(tmp);private=root/'private';private.mkdir(mode=0o700)
            alias=root/'alias';alias.symlink_to(private,target_is_directory=True)
            with self.assertRaises(ValueError):bridge.FixtureBridge(alias)
            (private/'ledger.sqlite').symlink_to(root/'outside')
            with self.assertRaises(ValueError):bridge.FixtureBridge(private)
            self.assertFalse((root/'outside').exists())
            self.assertFalse((private/'controller.sock').exists())

    def test_deep_json_refuses_without_server_crash(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(prefix='cb-', dir=ROOT) as tmp:
            server=bridge.FixtureBridge(Path(tmp),max_accepts=1,lifetime=1)
            with patch.object(server,'authorized',return_value=bridge.observe(os.getpid())):
                thread=threading.Thread(target=server.serve);thread.start()
                with socket.socket(socket.AF_UNIX) as client:
                    client.settimeout(1);client.connect(str(server.socket_path))
                    client.sendall(b'['*1500+b']'*1500+b'\n')
                    received=client.recv(4096)
                thread.join(2)
            self.assertEqual(received,b'{"state": "refused", "reason": "protocol"}\n')
            self.assertFalse(server.socket_path.exists())
            self.assertEqual(server.effects,[])

    def test_fixed_fixture_failure_retains_uncertain_reservation(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(prefix='cb-', dir=ROOT) as tmp:
            server = bridge.FixtureBridge(Path(tmp),max_accepts=1,lifetime=.1,fixture_outcome='uncertain')
            server.registration = {'cgroup':'/test.service'}
            left,right = socket.socketpair()
            try:
                right.sendall(b'{"request_id":"a","model":"fixture","payload":"x","max_output":1}\n')
                with patch.object(server,'authorized',return_value=bridge.observe(os.getpid())):
                    result,_ = server.handle(left,os.getpid(),os.getuid())
                self.assertEqual(result['state'],'uncertain')
                with sqlite3.connect(server.ledger_path) as db:
                    self.assertEqual(db.execute('select reservation,state from requests').fetchall(),[(3,'uncertain')])
            finally:
                left.close();right.close();server.serve()

    def test_slow_drip_has_absolute_client_deadline(self):
        import time
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(prefix='cb-', dir=ROOT) as tmp:
            server = bridge.FixtureBridge(Path(tmp), max_accepts=1, lifetime=1)
            peer = bridge.observe(os.getpid())
            thread = threading.Thread(target=server.serve)
            with patch.object(server,'authorized',return_value=peer):
                start = time.monotonic()
                thread.start()
                with socket.socket(socket.AF_UNIX) as client:
                    client.connect(str(server.socket_path))
                    for _ in range(8):
                        try:
                            client.sendall(b' ')
                        except OSError:
                            break
                        time.sleep(.06)
                thread.join(2)
                self.assertLess(time.monotonic()-start,.45)
            self.assertFalse(thread.is_alive())
            self.assertEqual(server.receipts[0]['reason'],'protocol')
            self.assertEqual(server.effects,[])

    def test_invalid_server_bounds_refused_before_socket_creation(self):
        with tempfile.TemporaryDirectory(prefix='cb-', dir=ROOT) as tmp:
            for kw in ({'max_accepts':0},{'max_accepts':257},{'max_accepts':True}, {'lifetime':float('inf')},{'lifetime':0},{'lifetime':31}):
                with self.subTest(kw=kw), self.assertRaises(ValueError):
                    bridge.FixtureBridge(Path(tmp), **kw)
            self.assertEqual(list(Path(tmp).iterdir()),[])

    def test_strict_protocol_rejections_do_not_reserve(self):
        from unittest.mock import patch
        cases = [b'{"request_id":"a","request_id":"b","model":"fixture","payload":"x","max_output":1}\n',
                 b'{"request_id":"a","model":"fixture","payload":"x","max_output":true}\n',
                 b'{"request_id":"a","model":"fixture","payload":"x","max_output":1,"subject":"forged"}\n',
                 b'[]\n', b'{}\n{}\n', b'x'*4097+b'\n']
        with tempfile.TemporaryDirectory(prefix='cb-', dir=ROOT) as tmp:
            server = bridge.FixtureBridge(Path(tmp), max_accepts=1, lifetime=.1)
            server.registration = {'cgroup':'/test.service'}
            peer = bridge.observe(os.getpid())
            try:
                with patch.object(server, 'authorized', return_value=peer):
                    for raw in cases:
                        with self.subTest(raw_length=len(raw)):
                            left,right = socket.socketpair()
                            try:
                                right.sendall(raw)
                                left.settimeout(.1)
                                with self.assertRaises(ValueError):
                                    server.handle(left,os.getpid(),os.getuid())
                            finally:
                                left.close();right.close()
                with sqlite3.connect(server.ledger_path) as db:
                    self.assertEqual(db.execute('select count(*) from requests').fetchone()[0],0)
            finally:
                server.serve()

    def test_kernel_identity_current_starttime(self):
        peer = bridge.observe(os.getpid())
        self.assertEqual(peer['pid'], os.getpid())
        self.assertEqual(peer['uid'], os.getuid())
        self.assertTrue(peer['starttime'].isdigit())
        self.assertTrue(peer['cgroup'].startswith('/'))

    def test_registration_refuses_unknown_and_outside_service(self):
        with tempfile.TemporaryDirectory(prefix='cb-', dir=ROOT) as tmp:
            server = bridge.FixtureBridge(Path(tmp), max_accepts=1, lifetime=.1)
            for observation in ({}, {'unit':'forged.service', 'control_group':'/', 'namespace_host_pids':[os.getpid()]},
                                {'unit':'native-containment-'+'0'*32+'.service', 'control_group':'/unknown', 'namespace_host_pids':[os.getpid()]}):
                self.assertIs(server.register(observation), False)
            server.serve()
            self.assertFalse(server.socket_path.exists())

    def test_outside_peer_refused_without_reservation(self):
        with tempfile.TemporaryDirectory(prefix='cb-', dir=ROOT) as tmp:
            server = bridge.FixtureBridge(Path(tmp), max_accepts=1, lifetime=1)
            thread = threading.Thread(target=server.serve)
            thread.start()
            with socket.socket(socket.AF_UNIX) as client:
                client.connect(str(server.socket_path))
                try:
                    client.sendall(b'{"request_id":"a","model":"fixture","payload":"secret","max_output":1}\n')
                except BrokenPipeError:
                    pass  # Authorization may refuse before reading any request.
                response = json.loads(client.recv(4096))
            thread.join(2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(response, {'state':'refused','reason':'authorization'})
            with sqlite3.connect(server.ledger_path) as db:
                self.assertEqual(db.execute('select count(*) from requests').fetchone()[0], 0)
            self.assertFalse(server.socket_path.exists())
            self.assertEqual(server.receipts[0]['uid'], os.getuid())
            self.assertEqual(server.receipts[0]['kernel_identity'], bridge.observe(os.getpid()))
            self.assertNotIn('secret', json.dumps(server.receipts))

if __name__ == '__main__':
    unittest.main()
