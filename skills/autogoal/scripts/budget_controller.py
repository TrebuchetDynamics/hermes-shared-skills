"""Private synthetic FIXTURE_UNITS admission, not native or monetary enforcement.

Trusted callers own the catalog, cap, private ledger and local forward_fixture
adapter. Tariff tuple = (per UTF-8 input byte, per bounded output unit, fixed).
This bound describes only the synthetic fixture; it is NOT provider pricing.
No backend, transport authentication or live capability is supplied here.
The fixture ledger has at most 256 permanent identities. Caller/process controls
own adapter deadlines; this API is admission logic, not runtime containment.

submit() reserves durably before a single local call. 'attempts' means durable
attempt authorization, including a crash before invocation. Uncertainty consumes
capacity permanently. 'remaining' is an admission-transaction snapshot, not a
promise of current capacity after concurrent submissions. Receipt digests redact
contents, not cryptographically anonymize low-entropy identifiers. The ledger
must remain controller-private: malicious ledger deletion/rollback is outside
this API's trust boundary. Existing incompatible ledgers are never migrated.
"""
from contextlib import contextmanager
import hashlib
import json
import os
import sqlite3
from types import MappingProxyType
from typing import Any

MAX_UNITS = 10**12
MAX_REQUESTS = 256
SCHEMA = (
    'CREATE TABLE meta (config TEXT NOT NULL)',
    'CREATE TABLE requests (request_id TEXT PRIMARY KEY, payload_digest TEXT, subject TEXT, model TEXT, reservation INTEGER, attempts INTEGER, state TEXT, input_bytes INTEGER, max_output INTEGER, identity_digest TEXT)',
)
FIELDS = {'request_id', 'subject', 'model', 'payload', 'max_output'}


def _digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _integer(value, maximum=MAX_UNITS):
    return type(value) is int and 0 <= value <= maximum


def _label(value):
    return type(value) is str and 1 <= len(value) <= 256


def _hash(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


class BudgetController:
    """Controller-owned fixture configuration; worker requests carry no tariffs."""

    def __init__(self, path, *, cap, catalog, scope):
        if not _integer(cap) or not _label(scope) or type(catalog) is not dict or not 1 <= len(catalog) <= 64:
            raise ValueError('invalid fixture configuration')
        for model, rates in catalog.items():
            if not _label(model) or type(rates) not in (tuple, list) or len(rates) != 3 or not all(_integer(rate) for rate in rates):
                raise ValueError('invalid fixture tariff')
        self.path = str(path)
        self._cap = cap
        self._catalog = MappingProxyType({model: tuple(rates) for model, rates in catalog.items()})
        self._scope = scope
        self._config_digest = _digest([1, cap, dict(self.catalog), scope, MAX_UNITS, MAX_REQUESTS, 65536, 1000000])
        self._ready = True
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            return
        except OSError:
            self._ready = False
            return
        os.close(fd)
        try:
            with self._connection() as connection:
                connection.execute('BEGIN IMMEDIATE')
                for statement in SCHEMA:
                    connection.execute(statement)
                connection.execute('INSERT INTO meta VALUES (?)', (self.config_digest,))
                connection.execute('PRAGMA user_version = 1')
        except (sqlite3.Error, OSError):
            self._ready = False

    @property
    def cap(self):
        return self._cap

    @property
    def catalog(self):
        return self._catalog

    @property
    def scope(self):
        return self._scope

    @property
    def config_digest(self):
        return self._config_digest

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.path, timeout=0.25)
        try:
            connection.execute('PRAGMA synchronous = FULL')
            with connection:
                yield connection
        finally:
            connection.close()

    def _validate_state(self, connection):
        actual = connection.execute('SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY sql').fetchall()
        if actual != sorted((statement,) for statement in SCHEMA):
            raise ValueError('incompatible schema')
        if connection.execute('PRAGMA user_version').fetchone() != (1,):
            raise ValueError('incompatible schema version')
        if connection.execute('SELECT config FROM meta').fetchall() != [(self.config_digest,)]:
            raise ValueError('incompatible configuration')
        used = 0
        for number, row in enumerate(connection.execute('SELECT * FROM requests LIMIT ?', (MAX_REQUESTS + 1,))):
            if number >= MAX_REQUESTS:
                raise ValueError('ledger identity bound exceeded')
            request_id, payload, subject, model, reservation, attempts, state, input_bytes, output, identity = row
            if not all(_hash(value) for value in (request_id, payload, subject, identity)):
                raise ValueError('malformed identity')
            if model not in self.catalog or not _integer(reservation) or type(attempts) is not int or attempts != 1 or state not in ('uncertain', 'done'):
                raise ValueError('malformed reservation')
            if not _integer(input_bytes, 65536) or not _integer(output, 1000000):
                raise ValueError('malformed bounds')
            if identity != _digest([self.config_digest, request_id, payload, subject, model, input_bytes, output]):
                raise ValueError('inconsistent identity binding')
            rates = self.catalog[model]
            if reservation != input_bytes * rates[0] + output * rates[1] + rates[2]:
                raise ValueError('inconsistent exposure')
            used += reservation
            if used > self.cap:
                raise ValueError('cap exceeded')
        return used

    def _receipt(self, state='refused', reason=None, **details):
        receipt = dict(state=state, reason=reason, unit='FIXTURE_UNITS', cap=self.cap,
                       config_digest=self.config_digest, scope_digest=_digest(self.scope),
                       request_digest=None, payload_digest=None, subject_digest=None,
                       model_digest=None, reservation=None, attempts=0, ledger_state=None,
                       uncertain=False, remaining=None, forwarded=False,
                       capacity_snapshot='admission')
        receipt.update(details)
        return receipt

    def submit(self, request, adapter):
        """Return redacted admission receipt; never automatically replay/refund."""
        if type(request) is not dict or set(request) != FIELDS:
            return self._receipt(reason='validation')
        request = dict(request)
        if any(type(request[key]) is not str for key in FIELDS - {'max_output'}):
            return self._receipt(reason='validation')
        if any(not _label(request[key]) for key in ('request_id', 'subject', 'model')):
            return self._receipt(reason='validation')
        try:
            input_bytes = len(request['payload'].encode('utf-8'))
        except UnicodeError:
            return self._receipt(reason='validation')
        if input_bytes > 65536 or not _integer(request['max_output'], 1000000):
            return self._receipt(reason='validation')
        details: dict[str, Any] = dict(request_digest=_digest(request['request_id']),
                                        payload_digest=_digest(request['payload']),
                                        subject_digest=_digest(request['subject']),
                                        model_digest=_digest(request['model']))
        request_id = details['request_digest']
        identity = _digest([self.config_digest, request_id, details['payload_digest'], details['subject_digest'],
                            request['model'], input_bytes, request['max_output']])
        try:
            if not self._ready:
                raise ValueError('unavailable ledger')
            with self._connection() as connection:
                connection.execute('BEGIN IMMEDIATE')
                used = self._validate_state(connection)
                details['remaining'] = self.cap - used
                previous = connection.execute('SELECT identity_digest, reservation, state FROM requests WHERE request_id = ?', (request_id,)).fetchone()
                if previous:
                    return self._receipt(reason='duplicate' if previous[0] == identity else 'identity',
                                         reservation=previous[1], attempts=1,
                                         ledger_state=previous[2], uncertain=previous[2] == 'uncertain', **details)
                if request['model'] not in self.catalog:
                    return self._receipt(reason='validation', **details)
                rates = self.catalog[request['model']]
                reservation = input_bytes * rates[0] + request['max_output'] * rates[1] + rates[2]
                if not _integer(reservation):
                    return self._receipt(reason='validation', **details)
                if reservation > self.cap - used or connection.execute('SELECT COUNT(*) FROM requests').fetchone()[0] >= MAX_REQUESTS:
                    return self._receipt(reason='capacity', reservation=reservation, **details)
                connection.execute('INSERT INTO requests VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                                   (request_id, details['payload_digest'], details['subject_digest'], request['model'],
                                    reservation, 1, 'uncertain', input_bytes, request['max_output'], identity))
                details['remaining'] = self.cap - used - reservation
        except (sqlite3.Error, ValueError, OSError) as exc:
            details['remaining'] = None
            code = getattr(exc, 'sqlite_errorcode', 0) & 0xff
            reason = 'lock' if code in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED) else 'state'
            return self._receipt(reason=reason, **details)
        details.update(reservation=reservation, attempts=1)
        try:
            forward = adapter.forward_fixture
            if not callable(forward):
                raise TypeError('fixture adapter callback unavailable')
            # This records the callback attempt, not proof of its external effect.
            details['forwarded'] = True
            forward(dict(request))
            with self._connection() as connection:
                connection.execute('BEGIN IMMEDIATE')
                self._validate_state(connection)
                connection.execute('UPDATE requests SET state = ? WHERE request_id = ?', ('done', request_id))
        except Exception:
            return self._receipt(state='uncertain', ledger_state='uncertain', uncertain=True, **details)
        return self._receipt(state='done', ledger_state='done', **details)
