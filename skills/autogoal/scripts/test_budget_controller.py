#!/usr/bin/env python3
"""Hermetic synthetic FIXTURE_UNITS controls; never invokes a provider."""
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from typing import Any
import unittest
import multiprocessing
import hashlib
import queue as queue_module
import time


def source_identities():
    return {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
            for name in ('test_budget_controller.py', 'budget_controller.py', 'controller_bridge.py')}


def ledger_snapshot(path):
    """Read-only committed state; never retains raw request payloads."""
    connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=0.25)
    try:
        connection.row_factory = sqlite3.Row
        return {'requests': [dict(row) for row in connection.execute('SELECT * FROM requests ORDER BY request_id')],
                'meta': [dict(row) for row in connection.execute('SELECT * FROM meta')],
                'user_version': connection.execute('PRAGMA user_version').fetchone()[0]}
    finally:
        connection.close()

HERE = Path(__file__).resolve().parent
SCRATCH = (Path.home() / '.hermes/cache/scratch/executable-safeguards/budget-race')
SCRATCH.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(HERE))


from contextlib import contextmanager


@contextmanager
def fixture_connection(path):
    connection = sqlite3.connect(path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def save_receipts(name, receipts):
    # Unique evidence names preserve previous RED/GREEN run receipts.
    with tempfile.NamedTemporaryFile(mode='w', prefix=name+'-', suffix='.json', dir=SCRATCH, delete=False) as output:
        json.dump(receipts, output, indent=2)
        output.write('\n')
    print(f'FIXTURE_RECEIPTS {output.name}', flush=True)
    return output.name


class Fixture:
    def __init__(self):
        self.calls = []

    def forward_fixture(self, request):
        self.calls.append(request)


def hold_fixture_transaction(db, entered, release):
    """Real SQLite lock; explicit release and hard timeout, no receipt stand-ins."""
    with fixture_connection(db) as connection:
        connection.execute('BEGIN IMMEDIATE')
        entered.set()
        if not release.wait(10):
            raise RuntimeError('fixture transaction release timed out')


def process_fixture(db, request_id, mode, gate, queue, transaction_lock=None, callback_release=None):
    """Spawned, bounded fixture only: real SQLite plus durable local marker."""
    from budget_controller import BudgetController
    class CoordinatedController(BudgetController):
        @contextmanager
        def _connection(inner):
            # Fixture-only scheduling: synchronize transaction entry, not the
            # callback. Real SQLite statements and its 0.25s timeout are intact.
            if not transaction_lock.acquire(timeout=5):
                raise RuntimeError('fixture transaction coordination timed out')
            try:
                with super()._connection() as connection:
                    yield connection
            finally:
                transaction_lock.release()
    controller_type = CoordinatedController if transaction_lock is not None else BudgetController
    controller = controller_type(db, cap=30, catalog={'fixture': (2, 3, 1)}, scope='offline-fixture-v1')
    queue.put('ready')
    if not gate.wait(5):
        raise RuntimeError('fixture start barrier timed out')
    completion_lock = None
    class ProcessFixture:
        def forward_fixture(self, request):
            nonlocal completion_lock
            # Independent physical callback-entry observation, not receipt claims.
            fd = os.open(str(db) + '.attempts', os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                identity = hashlib.sha256(json.dumps(request['request_id']).encode()).hexdigest()
                os.write(fd, (json.dumps(dict(pid=os.getpid(), request_digest=identity)) + '\n').encode())
                os.fsync(fd)
            finally:
                os.close(fd)
            if mode == 'crash-before-effect':
                os._exit(23)
            fd = os.open(str(db) + '.calls', os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                os.write(fd, b'fixture-effect\n')
                os.fsync(fd)
            finally:
                os.close(fd)
            if mode == 'uncertain-concurrent':
                queue.put('uncertain-concurrent-entered')
                if not callback_release.wait(5):
                    raise RuntimeError('fixture callback release timed out')
                queue.put('callback-released')
                raise TimeoutError('fixture uncertain callback')
            if mode == 'completion-lock':
                completion_lock = sqlite3.connect(db, timeout=0.25)
                completion_lock.execute('BEGIN IMMEDIATE')
                queue.put('completion-lock-entered')
                if not callback_release.wait(5):
                    raise RuntimeError('fixture callback release timed out')
                queue.put('callback-released')
            if mode == 'crash-after-effect':
                os._exit(23)
            if mode in ('hang', 'deadline'):
                queue.put('entered')
                gate.clear()
                gate.wait(10)
                raise TimeoutError('fixture deadline')
    request = dict(request_id=request_id, subject='worker1', model='fixture', payload='secret', max_output=2)
    try:
        queue.put(controller.submit(request, ProcessFixture()))
    finally:
        if completion_lock is not None:
            completion_lock.rollback()
            completion_lock.close()


class BudgetTests(unittest.TestCase):
    last_cleanup_evidence: str

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ledger-', dir=SCRATCH)
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / 'ledger.sqlite'

    def controller(self, **overrides):
        from budget_controller import BudgetController
        config = dict(cap=30, catalog={'fixture': (2, 3, 1)}, scope='offline-fixture-v1')
        config.update(overrides)
        return BudgetController(self.db, **config)

    def request(self, **overrides):
        request = dict(request_id='r1', subject='worker1', model='fixture', payload='secret', max_output=2)
        request.update(overrides)
        return request

    def test_fixture_connections_close_after_commit(self):
        self.assertTrue(callable(globals().get('fixture_connection')),
                        'closing fixture connection helper missing')
        with fixture_connection(self.db) as connection:
            connection.execute('CREATE TABLE fixture (value INTEGER)')
            connection.execute('INSERT INTO fixture VALUES (1)')
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute('SELECT 1')
        with fixture_connection(self.db) as reopened:
            self.assertEqual(reopened.execute('SELECT value FROM fixture').fetchone(), (1,))

    def test_invalid_adapter_does_not_claim_forwarding(self):
        from types import SimpleNamespace
        for adapter in (object(), SimpleNamespace(forward_fixture=None)):
            with self.subTest(adapter=type(adapter).__name__):
                request = self.request(request_id='invalid-' + type(adapter).__name__)
                result = self.controller(cap=100).submit(request, adapter)
                self.assertEqual(result['state'], 'uncertain')
                self.assertEqual(result['reservation'], 19)
                self.assertEqual(result['attempts'], 1)
                self.assertFalse(result['forwarded'])
                replay = self.controller(cap=100).submit(request, Fixture())
                self.assertEqual(replay['reason'], 'duplicate')

    def test_reserves_before_local_fixture_forward(self):
        self.assertTrue((HERE / 'budget_controller.py').exists(), 'controller implementation missing')
        controller = self.controller()
        fixture = Fixture()
        class InspectFixture(Fixture):
            def forward_fixture(inner, request):
                with fixture_connection(self.db) as connection:
                    row = connection.execute('SELECT reservation, attempts, state FROM requests').fetchone()
                self.assertEqual(row, (19, 1, 'uncertain'))
                super().forward_fixture(request)
        fixture = InspectFixture()
        receipt = controller.submit(self.request(), fixture)
        self.assertEqual(len(fixture.calls), 1)
        self.assertEqual(receipt['state'], 'done')
        self.assertEqual(receipt['reservation'], 19)
        self.assertEqual(receipt['remaining'], 11)

    def test_exhaustion_refuses_without_forwarding(self):
        controller = self.controller()
        fixture = Fixture()
        controller.submit(self.request(), fixture)
        receipt = controller.submit(self.request(request_id='r2'), fixture)
        self.assertEqual(receipt['state'], 'refused')
        self.assertEqual(receipt['reason'], 'capacity')
        self.assertEqual(len(fixture.calls), 1)
        with fixture_connection(self.db) as connection:
            self.assertEqual(connection.execute('SELECT SUM(reservation) FROM requests').fetchone()[0], 19)

    def test_persistent_identity_never_forwards_twice(self):
        fixture = Fixture()
        self.controller(cap=1000).submit(self.request(), fixture)
        for change in ({}, {'payload': 'changed'}, {'subject': 'other'}, {'model': 'other'}, {'max_output': 3}):
            with self.subTest(change=change):
                try:
                    receipt = self.controller(cap=1000).submit(self.request(**change), fixture)
                except Exception as exc:
                    self.fail(f'expected stable identity refusal, got {type(exc).__name__}')
                self.assertEqual(receipt['state'], 'refused')
                self.assertEqual(receipt['reason'], 'duplicate' if not change else 'identity')
        self.assertEqual(len(fixture.calls), 1)

    def test_untrusted_shapes_and_bounds_refuse_without_forwarding(self):
        controller = self.controller(cap=1000)
        fixture = Fixture()
        requests = [None, [], {}, self.request(model='unknown'), self.request(payload='\ud800'), self.request(payload='x' * 65537)]
        requests += [self.request(**{key: value}) for key in ('request_id', 'subject', 'model', 'payload') for value in (None, True, 1, [], {})]
        requests += [self.request(max_output=value) for value in (True, False, 1.0, -1, 10**30, None)]
        requests += [self.request(**{key: 0}) for key in ('cost', 'price', 'budget', 'refund', 'scope', 'catalog', 'endpoint')]
        requests += [self.request(request_id=''), self.request(subject='x'*257)]
        for request in requests:
            with self.subTest(request_type=type(request).__name__):
                try:
                    receipt = controller.submit(request, fixture)
                except Exception as exc:
                    self.fail(f'expected validation refusal, got {type(exc).__name__}')
                self.assertEqual(receipt['state'], 'refused')
                self.assertEqual(receipt['reason'], 'validation')
        self.assertEqual(fixture.calls, [])
        with fixture_connection(self.db) as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM requests').fetchone()[0], 0)

    def test_trusted_configuration_and_computed_overflow_are_bounded(self):
        from budget_controller import BudgetController
        bad = [dict(cap=x) for x in (True, 1.0, -1, 10**30)]
        bad += [dict(catalog=x) for x in ({}, {'fixture': (True, 3, 1)}, {'fixture': (-1, 3, 1)}, {'fixture': (1, 1)}, {'fixture': (1, 1, 10**30)}, {'fixture': (1.0, 1, 1)})]
        bad += [dict(scope=x) for x in ('', True, 'x'*257)]
        for overrides in bad:
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValueError):
                    self.controller(**overrides)
        fixture = Fixture()
        controller = self.controller(cap=10**12, catalog={'fixture': (10**12, 1, 0)})
        receipt = controller.submit(self.request(), fixture)
        self.assertEqual(receipt['reason'], 'validation')
        self.assertEqual(fixture.calls, [])

    def test_incompatible_config_and_schema_refuse_without_migration(self):
        fixture = Fixture()
        self.controller().submit(self.request(), fixture)
        for change in ({'cap': 1000}, {'scope': 'other'}, {'catalog': {'fixture': (1, 1, 0)}}):
            with self.subTest(change=change):
                before = self.db.read_bytes()
                receipt = self.controller(**change).submit(self.request(request_id='r2'), fixture)
                self.assertEqual(receipt['state'], 'refused')
                self.assertEqual(receipt['reason'], 'state')
                self.assertEqual(self.db.read_bytes(), before)
        for sql in ('CREATE TABLE alien (x)', 'CREATE TRIGGER alien AFTER INSERT ON requests BEGIN SELECT 1; END'):
            with fixture_connection(self.db) as connection:
                connection.execute(sql)
            before = self.db.read_bytes()
            receipt = self.controller().submit(self.request(request_id='r3'), fixture)
            self.assertEqual(receipt['reason'], 'state')
            self.assertEqual(self.db.read_bytes(), before)
        self.assertEqual(len(fixture.calls), 1)
        empty = Path(self.tmp.name) / 'empty.sqlite'
        empty.touch()
        from budget_controller import BudgetController
        receipt = BudgetController(empty, cap=30, catalog={'fixture': (2, 3, 1)}, scope='offline-fixture-v1').submit(self.request(), Fixture())
        self.assertEqual(receipt['reason'], 'state')
        self.assertEqual(empty.read_bytes(), b'')

    def test_malformed_persisted_rows_refuse_before_forwarding(self):
        mutations = [('reservation', value) for value in (-1, 18, 1.5, 10**15, None)]
        mutations += [('attempts', 0), ('attempts', 2), ('state', 'pending'), ('state', None), ('payload_digest', 'bad'), ('subject', ''), ('request_id', ''), ('model', 'unknown')]
        fixture = Fixture()
        for number, (column, value) in enumerate(mutations):
            with self.subTest(column=column, value=value):
                self.db = Path(self.tmp.name) / f'malformed-{number}.sqlite'
                controller = self.controller()
                controller.submit(self.request(), Fixture())
                with fixture_connection(self.db) as connection:
                    connection.execute(f'UPDATE requests SET {column} = ?', (value,))
                before = self.db.read_bytes()
                receipt = controller.submit(self.request(request_id='new'), fixture)
                self.assertEqual(receipt['state'], 'refused')
                self.assertEqual(receipt['reason'], 'state')
                self.assertEqual(self.db.read_bytes(), before)
        self.assertEqual(fixture.calls, [])

    def test_exception_and_timeout_keep_uncertain_exposure_on_restart(self):
        for number, error in enumerate((RuntimeError('private error text'), TimeoutError('private timeout'))):
            with self.subTest(error=type(error).__name__):
                self.db = Path(self.tmp.name) / f'exception-{number}.sqlite'
                class FailingFixture(Fixture):
                    def forward_fixture(inner, request):
                        super().forward_fixture(request)
                        raise error
                fixture = FailingFixture()
                try:
                    receipt = self.controller().submit(self.request(), fixture)
                except Exception as exc:
                    self.fail(f'expected uncertain receipt, got {type(exc).__name__}')
                self.assertEqual(receipt['state'], 'uncertain')
                self.assertEqual(receipt['remaining'], 11)
                self.assertNotIn(str(error), json.dumps(receipt))
                restarted = self.controller()
                self.assertEqual(restarted.submit(self.request(), fixture)['reason'], 'duplicate')
                self.assertEqual(restarted.submit(self.request(request_id='new'), fixture)['reason'], 'capacity')
                self.assertEqual(len(fixture.calls), 1)
                with fixture_connection(self.db) as connection:
                    self.assertEqual(connection.execute('SELECT reservation, attempts, state FROM requests').fetchone(), (19, 1, 'uncertain'))

    def test_redacted_receipts_identify_bound_admission_without_live_capability(self):
        controller = self.controller()
        fixture = Fixture()
        request = self.request(request_id='private-id', subject='private-subject')
        receipt = controller.submit(request, fixture)
        required = {'request_digest', 'payload_digest', 'subject_digest', 'model_digest', 'config_digest', 'scope_digest', 'reservation', 'attempts', 'uncertain', 'remaining', 'cap', 'unit', 'ledger_state', 'forwarded'}
        self.assertTrue(required <= receipt.keys(), 'receipt identity and uncertainty fields missing')
        for key in ('request_digest', 'payload_digest', 'subject_digest', 'model_digest', 'config_digest', 'scope_digest'):
            self.assertRegex(receipt[key], r'^[0-9a-f]{64}$')
        self.assertEqual(receipt['attempts'], 1)
        self.assertFalse(receipt['uncertain'])
        self.assertTrue(receipt['forwarded'])
        self.assertEqual(receipt['unit'], 'FIXTURE_UNITS')
        self.assertEqual(receipt['ledger_state'], 'done')
        duplicate = controller.submit(request, fixture)
        self.assertFalse(duplicate['forwarded'])
        self.assertEqual(duplicate['attempts'], 1)
        self.assertEqual(duplicate['reservation'], 19)
        refused = controller.submit(self.request(request_id='new'), fixture)
        self.assertEqual(refused['attempts'], 0)
        self.assertFalse(refused['forwarded'])
        encoded = json.dumps([receipt, duplicate, refused])
        for value in ('secret', 'private-id', 'private-subject', 'offline-fixture-v1'):
            self.assertNotIn(value, encoded)
            self.assertNotIn(value.encode(), self.db.read_bytes())
        self.assertNotIn('live_capability', receipt)
        save_receipts('receipt-summaries', [receipt, duplicate, refused])

    def run_processes(self, ids, mode='normal', *, coordinated=False, held_transaction=False):
        context = multiprocessing.get_context('spawn')
        gate, queue = context.Event(), context.Queue()
        holder_entered, holder_release = context.Event(), context.Event()
        holder = context.Process(target=hold_fixture_transaction, args=(self.db, holder_entered, holder_release)) if held_transaction else None
        transaction_lock = context.Lock() if coordinated else None
        callback_release = context.Event()
        processes = [context.Process(target=process_fixture, args=(self.db, identity, mode, gate, queue, transaction_lock, callback_release)) for identity in ids]
        pre = source_identities()
        ledger_pre = ledger_snapshot(self.db)
        events, failures = [], []
        started = time.monotonic()
        try:
            if holder is not None:
                holder.start()
                if not holder_entered.wait(5):
                    raise RuntimeError('fixture held transaction entry timed out')
            for process in processes:
                process.start()
            for _ in processes:
                event = queue.get(timeout=5)
                events.append(event)
                if event != 'ready':
                    failures.append('unexpected readiness event')
            gate.set()
            if mode in ('completion-lock', 'uncertain-concurrent'):
                # Keep callback in flight until competing submissions return.
                # Completion-lock also keeps real SQLite held through completion.
                deadline = time.monotonic() + 5
                while (mode + '-entered' not in events or
                       sum(isinstance(event, dict) for event in events) < len(processes) - 1):
                    events.append(queue.get(timeout=max(0.01, deadline - time.monotonic())))
                    if time.monotonic() >= deadline:
                        raise RuntimeError('fixture callback contention timed out')
                callback_release.set()
            if mode in ('hang', 'deadline'):
                event = queue.get(timeout=5)
                events.append(event)
                if event != 'entered':
                    failures.append('missing hang entry')
                if mode == 'hang':
                    processes[0].terminate()
            for process in processes:
                process.join(0.1 if mode == 'deadline' else 5)
                if process.is_alive():
                    failures.append('fixture process exceeded deadline')
        except Exception as exc:
            failures.append(type(exc).__name__)
        finally:
            for process in processes:
                if process.is_alive():
                    process.kill()
                if process.pid is not None:
                    process.join(5)
            holder_release.set()
            if holder is not None and holder.pid is not None:
                holder.join(5)
                if holder.is_alive():
                    failures.append('fixture lock holder exceeded deadline')
                    holder.kill()
                    holder.join(5)
                if holder.exitcode != 0:
                    failures.append('fixture lock holder failed')
            # Children have exited: consume their actual queue messages before
            # reporting failures, asserting outcomes, or deleting the ledger.
            while True:
                try:
                    events.append(queue.get(timeout=0.1))
                except queue_module.Empty:
                    break
            queue.close()
            queue.join_thread()
            receipts = [event for event in events if isinstance(event, dict)]
            marker = Path(str(self.db) + '.calls')
            evidence: dict[str, Any] = dict(receipts=receipts, events=events,
                            exitcodes=[process.exitcode for process in processes],
                            alive=[process.is_alive() for process in processes],
                            processes=[dict(pid=process.pid, request_digest=hashlib.sha256(json.dumps(identity).encode()).hexdigest())
                                       for process, identity in zip(processes, ids)],
                            callback_attempts=None,
                            holder=None if holder is None else dict(pid=holder.pid, exitcode=holder.exitcode,
                                alive=holder.is_alive(), entered=holder_entered.is_set(), release_set=holder_release.is_set()),
                            effects=None, ledger=None, ledger_pre=ledger_pre, source_pre=pre,
                            source_post=None, failures=failures, observation_errors={},
                            mode=mode, coordination='transaction-mutex' if coordinated else 'barrier-only',
                            elapsed=time.monotonic() - started)
            # Persist collected process facts before any fallible final read.
            # None means unknown, never a fabricated valid empty observation.
            self.last_process_evidence = save_receipts('race-evidence', evidence)
            for field, observe in (
                    ('callback_attempts', lambda: [json.loads(line) for line in Path(str(self.db) + '.attempts').read_text().splitlines()]
                     if Path(str(self.db) + '.attempts').exists() else []),
                    ('effects', lambda: marker.read_text().splitlines() if marker.exists() else []),
                    ('ledger', lambda: ledger_snapshot(self.db)),
                    ('source_post', source_identities)):
                try:
                    evidence[field] = observe()
                except Exception as exc:
                    error_type = type(exc).__name__
                    evidence['observation_errors'][field] = error_type
                    failures.append('observation ' + field + ': ' + error_type)
            self.last_process_evidence = save_receipts('race-evidence', evidence)
            database, artifact = self.db, self.last_process_evidence
            def retain_cleanup():
                self.tmp.cleanup()
                self.last_cleanup_evidence = save_receipts('process-cleanup', dict(
                    race_evidence=artifact, ledger_removed=not database.exists(),
                    alive=[process.is_alive() for process in processes],
                    exitcodes=[process.exitcode for process in processes],
                    holder_alive=False if holder is None else holder.is_alive()))
            self.addCleanup(retain_cleanup)
        self.assertEqual(failures, [], f'fixture failure; evidence {self.last_process_evidence}')
        returns_receipts = mode in ('normal', 'completion-lock', 'uncertain-concurrent')
        for process in processes:
            self.assertFalse(process.is_alive(), 'fixture process exceeded deadline')
            self.assertEqual(process.exitcode, 0 if returns_receipts else (-15 if mode == 'hang' else 23))
        self.assertEqual(len(receipts), len(processes) if returns_receipts else 0)
        return receipts

    def assert_final_observation_failure_retains_evidence(self, field, mode):
        from unittest.mock import patch
        probe = BudgetTests('test_real_duplicate_process_race_has_one_fixture_effect')
        probe.setUp()
        database = probe.db
        observed_baselines = []
        real_snapshot = ledger_snapshot
        real_sources = source_identities
        real_read_text = Path.read_text
        calls = 0

        def fail_observation():
            artifact = getattr(probe, 'last_process_evidence', None)
            if artifact is not None:
                observed_baselines.append(json.loads(real_read_text(Path(artifact))))
            raise sqlite3.OperationalError('private observation secret')

        def snapshot(path):
            nonlocal calls
            calls += 1
            return real_snapshot(path) if calls == 1 else fail_observation()

        def sources():
            nonlocal calls
            calls += 1
            return real_sources() if calls == 1 else fail_observation()

        def read_text(path, *args, **kwargs):
            if str(path).endswith('.calls'):
                return fail_observation()
            return real_read_text(path, *args, **kwargs)

        target, replacement = {'ledger': ('ledger_snapshot', snapshot),
                               'source_post': ('source_identities', sources),
                               'effects': ('read_text', read_text)}[field]
        patcher = patch.object(Path, target, replacement) if field == 'effects' else patch(__name__ + '.' + target, replacement)
        try:
            probe.controller()
            with patcher:
                with self.assertRaises(AssertionError):
                    probe.run_processes(['observation'], mode=mode)
            artifact = getattr(probe, 'last_process_evidence', None)
        finally:
            probe.doCleanups()
        self.assertIsNotNone(artifact, 'final observation erased process evidence')
        assert artifact is not None
        evidence = json.loads(Path(artifact).read_text())
        self.assertFalse(database.exists())
        self.assertEqual(evidence['alive'], [False])
        self.assertEqual(evidence['exitcodes'], [0] if mode == 'normal' else [-9])
        self.assertEqual(len(evidence['receipts']), 1 if mode == 'normal' else 0)
        self.assertIn('ready', evidence['events'])
        if mode == 'deadline':
            self.assertIn('entered', evidence['events'])
            self.assertIn('fixture process exceeded deadline', evidence['failures'])
        self.assertLess(evidence['elapsed'], 2)
        self.assertIsNone(evidence[field])
        self.assertEqual(evidence['observation_errors'], {field: 'OperationalError'})
        self.assertIn('observation ' + field + ': OperationalError', evidence['failures'])
        self.assertEqual(evidence['ledger_pre']['requests'], [])
        self.assertEqual(set(evidence['source_pre']), {'test_budget_controller.py', 'budget_controller.py', 'controller_bridge.py'})
        if field != 'effects':
            self.assertEqual(evidence['effects'], ['fixture-effect'])
        if field != 'source_post':
            self.assertEqual(evidence['source_pre'], evidence['source_post'])
        if field != 'ledger':
            row = evidence['ledger']['requests'][0]
            self.assertEqual((row['reservation'], row['attempts'], row['state']),
                             (19, 1, 'done' if mode == 'normal' else 'uncertain'))
        self.assertEqual(len(observed_baselines), 1, 'minimal envelope not persisted before observation')
        baseline = observed_baselines[0]
        for key in ('receipts', 'events', 'exitcodes', 'alive', 'ledger_pre', 'source_pre'):
            self.assertEqual(baseline[key], evidence[key])
        self.assertNotIn('private observation secret', json.dumps(evidence))
        self.assertNotIn('secret', json.dumps(evidence))

    def test_final_snapshot_error_retains_normal_process_evidence(self):
        self.assert_final_observation_failure_retains_evidence('ledger', 'normal')

    def test_final_snapshot_error_preserves_real_deadline_failure(self):
        self.assert_final_observation_failure_retains_evidence('ledger', 'deadline')

    def test_final_effect_read_error_fails_qualification_without_erasing_evidence(self):
        self.assert_final_observation_failure_retains_evidence('effects', 'normal')

    def test_final_source_read_error_fails_qualification_without_erasing_evidence(self):
        self.assert_final_observation_failure_retains_evidence('source_post', 'normal')

    def test_failed_race_evidence_survives_assertion_and_temp_cleanup(self):
        probe = BudgetTests('test_real_duplicate_process_race_has_one_fixture_effect')
        probe.setUp()
        database = probe.db
        try:
            probe.controller()
            receipts = probe.run_processes(['same', 'same', 'same'])
            with self.assertRaises(AssertionError):
                probe.assertEqual(len(receipts), 99, 'deliberate evidence regression')
            artifact = getattr(probe, 'last_process_evidence', None)
        finally:
            probe.doCleanups()
        self.assertIsNotNone(artifact, 'failure-path race evidence was not retained')
        self.assertFalse(database.exists())
        evidence = json.loads(Path(artifact).read_text())
        self.assertEqual(evidence['receipts'], receipts)
        self.assertEqual(evidence['exitcodes'], [0, 0, 0])
        self.assertEqual(evidence['effects'], ['fixture-effect'])
        self.assertEqual(len(evidence['ledger']['requests']), 1)
        self.assertEqual(evidence['ledger']['requests'][0]['reservation'], 19)
        self.assertEqual(evidence['source_pre'], evidence['source_post'])
        self.assertNotIn('secret', json.dumps(evidence))

    def test_process_deadline_retains_failure_artifact_after_finite_cleanup(self):
        probe = BudgetTests('test_real_crash_and_killed_timeout_keep_exposure_without_replay')
        probe.setUp()
        database = probe.db
        try:
            probe.controller()
            with self.assertRaises(AssertionError):
                probe.run_processes(['stalled'], mode='deadline')
            artifact = probe.last_process_evidence
        finally:
            probe.doCleanups()
        evidence = json.loads(Path(artifact).read_text())
        self.assertIn('fixture process exceeded deadline', evidence['failures'])
        self.assertFalse(database.exists())
        self.assertEqual(evidence['alive'], [False])
        self.assertEqual(evidence['exitcodes'], [-9])
        self.assertEqual(evidence['receipts'], [])
        self.assertEqual(evidence['effects'], ['fixture-effect'])
        self.assertLess(evidence['elapsed'], 2)
        row = evidence['ledger']['requests'][0]
        self.assertEqual((row['reservation'], row['attempts'], row['state']), (19, 1, 'uncertain'))
        self.assertEqual(evidence['source_pre'], evidence['source_post'])

    def test_held_transaction_distinguishes_lock_refusal_from_permanent_duplicate(self):
        controller = self.controller()
        fixture = Fixture()
        accepted = controller.submit(self.request(request_id='held'), fixture)
        with fixture_connection(self.db) as lock:
            lock.execute('BEGIN IMMEDIATE')
            receipts = self.run_processes(['held', 'held', 'new'])
        race = json.loads(Path(self.last_process_evidence).read_text())
        restarted = self.controller()
        duplicate = restarted.submit(self.request(request_id='held'), fixture)
        changed = restarted.submit(self.request(request_id='held', payload='changed'), fixture)
        capacity = restarted.submit(self.request(request_id='new'), fixture)
        save_receipts('lock-versus-identity', dict(accepted=accepted, locked=receipts,
                      duplicate=duplicate, changed=changed, capacity=capacity,
                      race_evidence=self.last_process_evidence, ledger=ledger_snapshot(self.db)))
        self.assertIn('ledger_pre', race, 'held-transaction evidence lacks pre-admission snapshot')
        self.assertEqual(race['ledger_pre'], race['ledger'])
        self.assertLess(race['elapsed'], 2)
        self.assertEqual([receipt['reason'] for receipt in receipts], ['lock'] * 3)
        for receipt in receipts:
            self.assertEqual(receipt['state'], 'refused')
            self.assertFalse(receipt['forwarded'])
            self.assertEqual(receipt['attempts'], 0)
            self.assertIsNone(receipt['reservation'])
            self.assertIsNone(receipt['remaining'])
        self.assertEqual(race['effects'], [])
        self.assertEqual(race['ledger']['requests'][0]['reservation'], 19)
        self.assertEqual(duplicate['reason'], 'duplicate')
        self.assertEqual(changed['reason'], 'identity')
        self.assertEqual(duplicate['reservation'], 19)
        self.assertEqual(duplicate['attempts'], 1)
        self.assertFalse(duplicate['forwarded'])
        self.assertEqual(duplicate['remaining'], 11)
        self.assertEqual(capacity['reason'], 'capacity')
        self.assertEqual(len(fixture.calls), 1)

    def test_real_concurrent_sqlite_reservations_never_exceed_cap(self):
        self.controller()
        receipts = self.run_processes(['a', 'b', 'c'])
        self.assertEqual(sum(receipt['forwarded'] for receipt in receipts), 1)
        self.assertEqual(sorted(receipt['state'] for receipt in receipts), ['done', 'refused', 'refused'])
        self.assertEqual(sum(receipt['reason'] == 'capacity' for receipt in receipts), 2)
        with fixture_connection(self.db) as connection:
            self.assertEqual(connection.execute('SELECT SUM(reservation), COUNT(*) FROM requests').fetchone(), (19, 1))
        self.assertEqual(Path(str(self.db)+'.calls').read_text().splitlines(), ['fixture-effect'])
        save_receipts('concurrency-receipts', receipts)

    def test_duplicate_race_records_deterministic_transaction_coordination(self):
        self.test_real_duplicate_process_race_has_one_fixture_effect()
        evidence = json.loads(Path(self.last_process_evidence).read_text())
        self.assertEqual(evidence.get('coordination'), 'transaction-mutex',
                         'duplicate race leaves transaction scheduling uncontrolled')
        self.assertEqual(evidence['exitcodes'], [0, 0, 0])
        self.assertEqual(evidence['source_pre'], evidence['source_post'])

    def test_real_duplicate_process_race_has_one_fixture_effect(self):
        self.controller()
        receipts = self.run_processes(['same', 'same', 'same'], coordinated=True)
        self.assertEqual(sum(receipt['forwarded'] for receipt in receipts), 1)
        self.assertEqual(sum(receipt['reason'] == 'duplicate' for receipt in receipts), 2)
        self.assertEqual(Path(str(self.db)+'.calls').read_text().splitlines(), ['fixture-effect'])

    def test_real_crash_and_killed_timeout_keep_exposure_without_replay(self):
        for number, mode in enumerate(('crash-before-effect', 'crash-after-effect', 'hang')):
            with self.subTest(mode=mode):
                self.db = Path(self.tmp.name) / f'crash-{number}.sqlite'
                self.controller()
                self.run_processes(['crashed'], mode)
                fixture = Fixture()
                controller = self.controller()
                duplicate = controller.submit(self.request(request_id='crashed'), fixture)
                self.assertEqual(duplicate['reason'], 'duplicate')
                self.assertTrue(duplicate['uncertain'])
                self.assertEqual(duplicate['reservation'], 19)
                self.assertEqual(controller.submit(self.request(request_id='new'), fixture)['reason'], 'capacity')
                self.assertEqual(fixture.calls, [])
                marker = Path(str(self.db)+'.calls')
                self.assertEqual(len(marker.read_text().splitlines()) if marker.exists() else 0, 0 if mode == 'crash-before-effect' else 1)
                with fixture_connection(self.db) as connection:
                    self.assertEqual(connection.execute('SELECT reservation, attempts, state FROM requests').fetchone(), (19, 1, 'uncertain'))

    def test_real_sqlite_lock_timeout_refuses_without_forwarding(self):
        import time
        controller = self.controller()
        fixture = Fixture()
        with fixture_connection(self.db) as lock:
            lock.execute('BEGIN IMMEDIATE')
            start = time.monotonic()
            receipt = controller.submit(self.request(), fixture)
            self.assertLess(time.monotonic() - start, 2)
            self.assertEqual(receipt['reason'], 'lock')
            self.assertEqual(receipt['state'], 'refused')
            self.assertFalse(receipt['forwarded'])
        self.assertEqual(fixture.calls, [])
        with fixture_connection(self.db) as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM requests').fetchone()[0], 0)

    def test_controller_configuration_is_immutable_and_copied(self):
        rates = [2, 3, 1]
        catalog = {'fixture': rates}
        controller = self.controller(catalog=catalog)
        rates[0] = 0
        catalog['fixture'] = [0, 0, 0]
        fixture = Fixture()
        self.assertEqual(controller.submit(self.request(), fixture)['reservation'], 19)
        with self.assertRaises(TypeError):
            controller.catalog['fixture'] = (0, 0, 0)
        for attribute, value in (('cap', 1000), ('scope', 'other'), ('catalog', {'fixture': (0, 0, 0)}), ('config_digest', 'fake')):
            with self.subTest(attribute=attribute):
                with self.assertRaises(AttributeError):
                    setattr(controller, attribute, value)

    def test_zero_unit_fixture_ledger_has_bounded_identity_capacity(self):
        import budget_controller
        self.assertTrue(hasattr(budget_controller, 'MAX_REQUESTS'), 'fixture ledger admission bound missing')
        MAX_REQUESTS = budget_controller.MAX_REQUESTS
        controller = self.controller(cap=0, catalog={'fixture': (0, 0, 0)})
        fixture = Fixture()
        self.assertTrue(isinstance(MAX_REQUESTS, int) and 1 <= MAX_REQUESTS <= 256)
        for number in range(MAX_REQUESTS):
            self.assertEqual(controller.submit(self.request(request_id=f'zero-{number}'), fixture)['state'], 'done')
        receipt = controller.submit(self.request(request_id='excess'), fixture)
        self.assertEqual(receipt['reason'], 'capacity')
        self.assertEqual(len(fixture.calls), MAX_REQUESTS)
        self.assertEqual(controller.submit(self.request(request_id='zero-0'), fixture)['reason'], 'duplicate')

    def test_well_shaped_persisted_identity_changes_are_inconsistent(self):
        catalog = {'fixture': (2, 3, 1), 'alternate': (2, 3, 1)}
        for number, (column, value) in enumerate((('payload_digest', '0'*64), ('subject', '0'*64), ('request_id', '0'*64), ('identity_digest', '0'*64), ('model', 'alternate'))):
            with self.subTest(column=column):
                self.db = Path(self.tmp.name) / f'identity-{number}.sqlite'
                controller = self.controller(catalog=catalog)
                controller.submit(self.request(), Fixture())
                with fixture_connection(self.db) as connection:
                    connection.execute(f'UPDATE requests SET {column} = ?', (value,))
                fixture = Fixture()
                receipt = controller.submit(self.request(request_id='new'), fixture)
                self.assertEqual(receipt['reason'], 'state')
                self.assertEqual(fixture.calls, [])

    def test_default_offline_inventory_discovers_this_hermetic_suite(self):
        import importlib.util
        root = HERE.parents[2]
        path = root / 'scripts/check.py'
        spec = importlib.util.spec_from_file_location('offline_check', path)
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        inventory = checker.discover_tests(root)
        self.assertIn(Path(__file__).resolve(), inventory)
        self.assertNotIn(HERE / 'test_native_lifecycle_controls.py', inventory)
        self.assertNotIn(HERE / 'test_native_containment_linux.py', inventory)

    def test_real_completion_lock_failure_is_uncertain_without_refund(self):
        controller = self.controller()
        lock = sqlite3.connect(self.db)
        self.addCleanup(lock.close)
        class CompletionLockFixture(Fixture):
            def forward_fixture(inner, request):
                super().forward_fixture(request)
                lock.execute('BEGIN IMMEDIATE')
        fixture = CompletionLockFixture()
        receipt = controller.submit(self.request(), fixture)
        self.assertEqual(receipt['state'], 'uncertain')
        lock.rollback()
        duplicate = self.controller().submit(self.request(), fixture)
        self.assertTrue(duplicate['uncertain'])
        self.assertEqual(duplicate['reason'], 'duplicate')
        self.assertEqual(receipt['reservation'], 19)
        self.assertEqual(len(fixture.calls), 1)

    def test_foreign_versions_metadata_and_non_sqlite_files_are_preserved(self):
        for number, mutation in enumerate(('PRAGMA user_version = 2', "UPDATE meta SET config = 'bad'", 'INSERT INTO meta SELECT config FROM meta')):
            with self.subTest(mutation=mutation):
                self.db = Path(self.tmp.name) / f'foreign-{number}.sqlite'
                controller = self.controller()
                with fixture_connection(self.db) as connection:
                    connection.execute(mutation)
                before = self.db.read_bytes()
                fixture = Fixture()
                self.assertEqual(controller.submit(self.request(), fixture)['reason'], 'state')
                self.assertEqual(self.db.read_bytes(), before)
                self.assertEqual(fixture.calls, [])
        self.db = Path(self.tmp.name) / 'foreign.bin'
        self.db.write_bytes(b'not sqlite; preserve this fixture')
        controller = self.controller()
        fixture = Fixture()
        self.assertEqual(controller.submit(self.request(), fixture)['reason'], 'state')
        self.assertEqual(self.db.read_bytes(), b'not sqlite; preserve this fixture')
        self.assertEqual(fixture.calls, [])

    def test_utf8_input_and_zero_output_bound_use_exact_fixture_cap(self):
        fixture = Fixture()
        controller = self.controller(cap=5)
        receipt = controller.submit(self.request(payload='é', max_output=0), fixture)
        self.assertEqual(receipt['reservation'], 5)
        self.assertEqual(receipt['remaining'], 0)
        self.assertEqual(len(fixture.calls), 1)
        self.assertEqual(controller.submit(self.request(request_id='new', payload='', max_output=0), fixture)['reason'], 'capacity')
        self.assertEqual(len(fixture.calls), 1)


class UnsynchronizedAdmissionTests(unittest.TestCase):
    """Independent safety contract; never requires a particular race winner."""
    db: Path
    last_process_evidence: str
    last_cleanup_evidence: str
    setUp = BudgetTests.setUp
    controller = BudgetTests.controller
    request = BudgetTests.request
    run_processes = BudgetTests.run_processes

    def assert_admission_safety(self, receipts, *, identity='same', expected_state=None):
        race = json.loads(Path(self.last_process_evidence).read_text())
        fixture = Fixture()
        restarted = self.controller()
        replay = restarted.submit(self.request(request_id=identity), fixture)
        changed = restarted.submit(self.request(request_id=identity, payload='changed'), fixture)
        capacity = restarted.submit(self.request(request_id='new'), fixture)
        after = ledger_snapshot(self.db)
        self.last_safety_evidence = save_receipts('unsynchronized-safety', dict(
            race_evidence=self.last_process_evidence, race=race, replay=replay,
            changed=changed, capacity=capacity, replay_callback_count=len(fixture.calls),
            ledger_after_restart=after, source_post=source_identities()))
        self.assertEqual(race['coordination'], 'barrier-only')
        self.assertEqual(race['source_pre'], race['source_post'])
        self.assertEqual(race['observation_errors'], {})
        self.assertEqual(race['receipts'], receipts)
        self.assertEqual(race['alive'], [False] * len(receipts))
        self.assertEqual(race['exitcodes'], [0] * len(receipts))
        self.assertLessEqual(len(race['effects']), 1, 'physical effect replay')
        self.assertLessEqual(len(race['callback_attempts']), 1, 'callback replay')
        rows = race['ledger']['requests']
        self.assertEqual(len(rows), 1, 'identity must be permanently bound once')
        row = rows[0]
        self.assertEqual((row['reservation'], row['attempts']), (19, 1))
        self.assertIn(row['state'], ('done', 'uncertain'))
        if expected_state is not None:
            self.assertEqual(row['state'], expected_state)
        self.assertLessEqual(sum(item['reservation'] for item in rows), 30)
        self.assertEqual(len(race['callback_attempts']), 1)
        attempt = race['callback_attempts'][0]
        self.assertIn(attempt['pid'], [process['pid'] for process in race['processes']])
        self.assertEqual(attempt['request_digest'], row['request_id'])
        self.assertEqual(sum(receipt['forwarded'] for receipt in receipts), 1)
        for receipt in receipts:
            self.assertEqual(receipt['request_digest'], row['request_id'])
            if receipt['forwarded']:
                self.assertIn(receipt['state'], ('done', 'uncertain'))
                self.assertIsNone(receipt['reason'])
                self.assertEqual((receipt['reservation'], receipt['attempts'], receipt['remaining']), (19, 1, 11))
            else:
                self.assertEqual(receipt['state'], 'refused')
                # Identical requests cannot legitimately differ in identity or
                # capacity after binding; only observed lock/duplicate qualify.
                self.assertIn(receipt['reason'], ('duplicate', 'lock'))
                if receipt['reason'] == 'lock':
                    self.assertEqual(receipt['attempts'], 0)
                    self.assertIsNone(receipt['reservation'])
                    self.assertIsNone(receipt['remaining'])
                else:
                    self.assertEqual((receipt['reservation'], receipt['attempts'], receipt['remaining']), (19, 1, 11))
                self.assertFalse(receipt['forwarded'])
        self.assertEqual(replay['reason'], 'duplicate')
        self.assertFalse(replay['forwarded'])
        self.assertEqual((replay['reservation'], replay['attempts'], replay['remaining']), (19, 1, 11))
        self.assertEqual(replay['uncertain'], row['state'] == 'uncertain')
        self.assertEqual(changed['reason'], 'identity')
        self.assertEqual(capacity['reason'], 'capacity')
        self.assertEqual(fixture.calls, [])
        self.assertEqual(after, race['ledger'], 'restart must not refund or rewrite exposure')

    def test_held_transaction_release_allows_only_unaccepted_retry(self):
        self.controller()
        locked = self.run_processes(['retry', 'retry', 'new'], held_transaction=True)
        race = json.loads(Path(self.last_process_evidence).read_text())
        retry_fixture = Fixture()
        accepted = self.controller().submit(self.request(request_id='retry'), retry_fixture)
        replay = self.controller().submit(self.request(request_id='retry'), retry_fixture)
        capacity = self.controller().submit(self.request(request_id='new'), retry_fixture)
        save_receipts('held-release-safety', dict(race=race, accepted=accepted, replay=replay,
                      capacity=capacity, callback_count=len(retry_fixture.calls), ledger=ledger_snapshot(self.db)))
        self.assertEqual(race['ledger_pre'], race['ledger'])
        self.assertEqual(race['ledger']['requests'], [])
        self.assertEqual(race['effects'], [])
        self.assertEqual(race['callback_attempts'], [])
        self.assertEqual(race['holder']['exitcode'], 0)
        self.assertFalse(race['holder']['alive'])
        self.assertTrue(race['holder']['release_set'])
        for receipt in locked:
            self.assertEqual((receipt['state'], receipt['reason'], receipt['attempts'], receipt['forwarded']),
                             ('refused', 'lock', 0, False))
            self.assertIsNone(receipt['reservation'])
            self.assertIsNone(receipt['remaining'])
        self.assertEqual((accepted['state'], accepted['reservation']), ('done', 19))
        self.assertEqual(replay['reason'], 'duplicate')
        self.assertFalse(replay['forwarded'])
        self.assertEqual(capacity['reason'], 'capacity')
        self.assertEqual(len(retry_fixture.calls), 1)

    def test_completion_transaction_contention_never_refunds_or_replays(self):
        self.controller()
        receipts = self.run_processes(['same', 'same', 'same'], mode='completion-lock')
        self.assert_admission_safety(receipts, expected_state='uncertain')

    def test_uncertain_callback_concurrency_never_refunds_or_replays(self):
        self.controller()
        receipts = self.run_processes(['same', 'same', 'same'], mode='uncertain-concurrent')
        self.assert_admission_safety(receipts, expected_state='uncertain')

    def test_process_cleanup_receipt_survives_ledger_removal(self):
        probe = UnsynchronizedAdmissionTests('test_identical_barrier_race_is_at_most_once_after_restart')
        probe.setUp()
        database = probe.db
        try:
            probe.controller()
            probe.run_processes(['cleanup'])
        finally:
            probe.doCleanups()
        cleanup = json.loads(Path(probe.last_cleanup_evidence).read_text())
        self.assertFalse(database.exists())
        self.assertTrue(cleanup['ledger_removed'])
        self.assertEqual(cleanup['alive'], [False])
        self.assertEqual(cleanup['exitcodes'], [0])

    def test_identical_barrier_race_is_at_most_once_after_restart(self):
        self.controller()
        receipts = self.run_processes(['same', 'same', 'same'])
        self.assert_admission_safety(receipts)


if __name__ == '__main__':
    unittest.main()
