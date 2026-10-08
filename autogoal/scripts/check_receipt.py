#!/usr/bin/env python3
"""Run one authorized check and bind its receipt to declared inputs. No retries."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import source_freshness


def runtime():
    # No credential values are saved. Non-Python tools must be pinned in a declared
    # environment input; this fingerprint cannot infer a check's dependency closure.
    environment = {key: os.environ.get(key) for key in
                   ('PATH', 'PYTHONPATH', 'VIRTUAL_ENV', 'LANG', 'LC_ALL')}
    return {'python': sys.version, 'platform': platform.platform(),
            'executable_sha256': hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
            'packages': sorted([d.metadata['Name'] or '', d.version]
                               for d in importlib.metadata.distributions()),
            'environment_sha256': hashlib.sha256(json.dumps(environment, sort_keys=True).encode()).hexdigest()}


def execute(root, paths, command, timeout):
    if not command or not 0 < timeout <= 300:
        raise ValueError('Supply an explicit command and a timeout greater than zero, at most 300 seconds')
    before = source_freshness.capture(root, paths)
    if any(row['sha256'] is None for row in before['files']):
        raise ValueError('All declared verification inputs must exist')
    environment = runtime()
    started = time.monotonic()
    process = subprocess.Popen(command, cwd=root, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        code, output = process.returncode, stdout + stderr
        outcome = 'passed' if code == 0 else 'failed'
    except subprocess.TimeoutExpired:
        import signal
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass  # The process group exited at the deadline.
        stdout, stderr = process.communicate(timeout=5)
        code, output, outcome = None, stdout + stderr, 'timeout'
    after = source_freshness.capture(root, paths)
    environment_after = runtime()
    if before != after:
        outcome = 'source_changed'
    elif environment != environment_after:
        outcome = 'environment_changed'
    return {'version': 1, 'command': list(command), 'before': before, 'after': after,
            'runtime': environment, 'runtime_after': environment_after,
            'exit_code': code, 'outcome': outcome, 'attempts': 1,
            'elapsed_seconds': time.monotonic() - started,
            'output_sha256': hashlib.sha256(output).hexdigest(),
            'diagnostic': output[-4096:].decode('utf-8', errors='replace') if outcome != 'passed' else '',
            'boundary': 'Declared inputs only; not independent review, native acknowledgement or integration'}


def reusable(receipt, root, command):
    # JSON roundtripping normalizes tuples in distribution metadata.
    current = json.loads(json.dumps(runtime()))
    return (receipt.get('version') == 1 and receipt.get('outcome') == 'passed'
            and receipt.get('exit_code') == 0 and receipt.get('command') == list(command)
            and receipt.get('before') == receipt.get('after')
            and json.loads(json.dumps(receipt.get('runtime'))) == current
            and json.loads(json.dumps(receipt.get('runtime_after'))) == current
            and source_freshness.check(receipt['before'], root)['fresh'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['run', 'reuse'])
    parser.add_argument('--workspace', required=True, type=Path)
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--path', action='append', default=[], help='Explicit source, dependency or environment input')
    parser.add_argument('--timeout', type=float, default=60)
    argv = sys.argv[1:]
    if '--' not in argv:
        parser.error('Separate the explicit check command with --')
    split = argv.index('--')
    args = parser.parse_args(argv[:split])
    command = argv[split + 1:]
    try:
        if args.action == 'reuse':
            accepted = reusable(json.loads(args.receipt.read_text()), args.workspace, command)
            print(json.dumps({'reusable': accepted}))
            return 0 if accepted else 1
        if args.receipt.exists():
            raise ValueError('Receipt already exists; preserve it and choose a new path')
        receipt = execute(args.workspace, args.path, command, args.timeout)
        args.receipt.write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps({'outcome': receipt['outcome'], 'attempts': receipt['attempts']}))
        return 0 if receipt['outcome'] == 'passed' else 1
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
