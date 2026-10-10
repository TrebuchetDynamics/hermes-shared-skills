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
import candidate_identity
import tempfile
from contextlib import contextmanager


@contextmanager
def isolated_candidate(root, candidate):
    if not candidate_identity.check(candidate, root):
        raise ValueError('Candidate identity, base, tree or prerequisite pins are stale')
    with tempfile.TemporaryDirectory(prefix='candidate-check-') as tmp:
        checkout = Path(tmp) / 'checkout'
        candidate_identity.git(root, 'worktree', 'add', '--detach', str(checkout), candidate['candidate_commit'])
        try:
            tracked = subprocess.check_output(
                ['git', '-C', str(checkout), 'ls-files', '-z'], timeout=30,
                env=candidate_identity.git_environment()).decode().split('\0')
            for name in filter(None, tracked):
                path = checkout / name
                if path.is_symlink() and not path.resolve().is_relative_to(checkout.resolve()):
                    raise ValueError('Candidate symlink escapes the dependency-declared snapshot')
            yield checkout
        finally:
            candidate_identity.git(root, 'worktree', 'remove', '--force', str(checkout))


@contextmanager
def shared_resource_lock(path=None, timeout=30):
    import fcntl
    if not 0 < timeout < float('inf'):
        raise ValueError('resource lock timeout must be finite and positive')
    path = Path(path) if path else Path(os.environ.get('TMPDIR', str(Path.home() / '.hermes/cache/scratch'))) / 'receipt-heavyweight.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with path.open('a') as stream:
        while True:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() - started >= timeout:
                    raise ValueError('Timed out waiting for shared resource lock')
                time.sleep(min(0.05, timeout))
        try:
            yield time.monotonic() - started
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def validate_scope(scope):
    if scope is None:
        return None
    if (not isinstance(scope, dict) or scope.get('mode') not in ('fixture', 'live')
            or any(not isinstance(scope.get(k), str) or not scope[k].strip() for k in ('platform', 'backend'))
            or not isinstance(scope.get('toolchain'), dict) or not scope['toolchain']
            or any(not isinstance(k, str) or not k.strip() or not isinstance(v, str) or not v.strip()
                   for k, v in scope['toolchain'].items())):
        raise ValueError('Scope requires named platform/backend, fixture|live mode and explicit toolchain identities')
    return json.loads(json.dumps(scope))


def execute(root, paths, command, timeout, *, candidate=None, resource_lock=None, lock_timeout=30,
            external_paths=(), qualification_scope=None, generated_outputs=()):
    scope = validate_scope(qualification_scope)
    generated_outputs = list(generated_outputs)
    for name in generated_outputs:
        path = Path(name)
        if (path.is_absolute() or '..' in path.parts or name in paths or not path.parts
                or path.suffix.lower() in ('.py', '.pyc', '.sh', '.js', '.ts', '.so', '.dll', '.exe')):
            raise ValueError('Generated output allowance must name relative non-source output files, never inputs')
    with shared_resource_lock(resource_lock, lock_timeout) as waited:
        external_before = source_freshness.capture(root, list(external_paths)) if external_paths else None
        if external_before and any(row['sha256'] is None for row in external_before['files']):
            raise ValueError('All external dependency inputs must exist')
        receipt = _execute_candidate(root, paths, command, timeout, candidate=candidate, generated_outputs=generated_outputs)
        external_after = source_freshness.capture(root, list(external_paths)) if external_paths else None
        if external_before != external_after:
            receipt['outcome'] = 'source_changed'
        receipt.update(external_before=external_before, external_after=external_after,
                       execution='executed', reused=False, lock_wait_seconds=waited,
                       hard_timeout_seconds=timeout, qualification_scope=scope)
        return receipt


def candidate_command(command, root, checkout):
    # Literal argv paths inside the shared repository use their frozen counterparts.
    # Shell strings/embedded -c programs are explicit caller code, not rewritten.
    root = Path(root).resolve()
    mapped = []
    for arg in command:
        path = Path(arg)
        if path.is_absolute() and path != root and path.is_relative_to(root):
            mapped.append(str(checkout / path.relative_to(root)))
        else:
            mapped.append(arg)
    return mapped


def candidate_environment(root, checkout):
    environment = dict(os.environ)
    for key in ('GIT_INDEX_FILE', 'GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR',
                'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_NAMESPACE'):
        environment.pop(key, None)
    for key in ('PATH', 'PYTHONPATH'):
        if key in environment:
            entries = []
            for entry in environment[key].split(os.pathsep):
                path = Path(entry)
                if path.is_absolute() and path.is_relative_to(Path(root).resolve()):
                    entry = str(checkout / path.relative_to(Path(root).resolve()))
                entries.append(entry)
            environment[key] = os.pathsep.join(entries)
    environment['PWD'] = str(checkout)
    return environment


def _execute_candidate(root, paths, command, timeout, *, candidate=None, generated_outputs=()):
    if candidate is None:
        receipt = _execute(root, paths, command, timeout)
        receipt['qualification'] = 'shared_tree_declared_inputs_only'
        return receipt
    with isolated_candidate(root, candidate) as checkout:
        receipt = _execute(checkout, paths, candidate_command(command, root, checkout), timeout,
                           execution_env=candidate_environment(root, checkout))
        # Embedded programs are not rewritten. Never call a check that visibly
        # reaches the shared checkout exact candidate evidence.
        opaque = any(str(Path(root).resolve()) in arg and not Path(arg).is_absolute()
                     for arg in command)
        # The executable is runtime-hashed; path arguments must stay in the
        # candidate. A pinned interpreter does not pin an external helper script.
        opaque = opaque or any(
            (Path(arg).is_absolute() or '..' in Path(arg).parts)
            and not (checkout / arg).resolve().is_relative_to(checkout.resolve())
            for arg in candidate_command(command, root, checkout)[1:])
        opaque = opaque or Path(command[0]).name in ('sh', 'bash', 'zsh', 'dash')
        if '-c' in command and Path(command[0]).name.startswith('python'):
            import ast
            try:
                program = ast.parse(command[command.index('-c') + 1])
                for node in ast.walk(program):
                    if isinstance(node, ast.Constant) and isinstance(node.value, str) and Path(node.value).is_absolute():
                        opaque = True
                    if isinstance(node, ast.Call):
                        name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, 'attr', '')
                        if name in ('write_text', 'write_bytes', 'touch', 'unlink', 'open', 'exec', 'eval',
                                    'compile', '__import__', 'getattr', 'system', 'popen', 'Popen', 'run'):
                            opaque = True
            except (SyntaxError, IndexError):
                opaque = True
        receipt.update(version=2, qualification_policy='declared-snapshot-v3',
                       qualification='candidate_with_unconfined_command' if opaque else 'exact_candidate',
                       candidate=candidate, command=[redact(arg) for arg in command],
                       command_sha256=command_digest(command),
                       boundary='Dependency-declared candidate snapshot; not a malicious-code sandbox. '
                                'No filesystem access confinement; caller must declare dependency inputs. '
                                'External argv paths, embedded absolute paths, write/dynamic code and opaque shells cannot qualify exactly. '
                                'Untracked-file inspection is post-execution, including ignored files, not read tracing; '
                                'trusted candidate scripts must not create transient undeclared dependency inputs.')
        receipt['generated_outputs'] = list(generated_outputs)
        if generated_outputs:
            receipt['qualification'] = 'candidate_declared_outputs_unconfined'
            receipt['boundary'] += ' Generated outputs are caller-declared outputs, not verified dependency-free; exact qualification refused without read tracing.'
        if (not candidate_identity.check(candidate, root) or
                candidate_identity.git(checkout, 'rev-parse', 'HEAD') != candidate['candidate_commit']):
            receipt['outcome'] = 'candidate_changed'
        elif subprocess.run(['git', '-C', str(checkout), 'diff', '--quiet', 'HEAD', '--'],
                            timeout=30, env=candidate_identity.git_environment()).returncode:
            receipt['outcome'] = 'source_changed'
        else:
            # Include ignored build/cache files: git diff ignores every untracked file.
            generated = subprocess.check_output(
                ['git', '-C', str(checkout), 'ls-files', '--others', '-z'],
                timeout=30, env=candidate_identity.git_environment()).decode().split('\0')
            receipt['generated_files'] = sorted(path for path in generated if path)
            if set(receipt['generated_files']) - set(generated_outputs):
                receipt['outcome'] = 'undeclared_generated_files'
        return receipt


def runtime(command=None, root=None, execution_env=None):
    # Hash values only: backend/environment changes invalidate without recording secrets.
    import shutil
    environment = dict(os.environ if execution_env is None else execution_env)
    actual_environment_hash = hashlib.sha256(json.dumps(environment, sort_keys=True).encode()).hexdigest()
    if execution_env is not None and root is not None:
        # Only ephemeral checkout paths normalize; every other execution value remains bound.
        checkout = str(Path(root).resolve())
        for key in ('PWD', 'PATH', 'PYTHONPATH'):
            if key in environment:
                environment[key] = os.pathsep.join(
                    '<candidate-checkout>' + value[len(checkout):]
                    if value == checkout or value.startswith(checkout + os.sep) else value
                    for value in environment[key].split(os.pathsep))
    executable = None
    if command:
        name = command[0]
        resolved = str(Path(root or '.').resolve() / name) if '/' in name and not Path(name).is_absolute() else shutil.which(name, path=(execution_env or os.environ).get('PATH'))
        if resolved and Path(resolved).is_file():
            executable = hashlib.sha256(Path(resolved).read_bytes()).hexdigest()
    return {'python': sys.version, 'platform': platform.platform(),
            'command_executable_sha256': executable,
            'execution_environment_sha256': actual_environment_hash,
            'executable_sha256': hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
            'packages': sorted([d.metadata['Name'] or '', d.version]
                               for d in importlib.metadata.distributions()),
            'environment_sha256': hashlib.sha256(json.dumps(environment, sort_keys=True).encode()).hexdigest()}


def redact(text):
    import re
    secrets = [value for key, value in os.environ.items() if value and
               re.search(r'TOKEN|SECRET|PASSWORD|CREDENTIAL|API_KEY|PRIVATE_KEY', key, re.I)]
    for value in sorted(secrets, key=len, reverse=True):
        text = text.replace(value, '[REDACTED]')
    return text


def command_digest(command):
    return hashlib.sha256(json.dumps(list(command)).encode()).hexdigest()


def _execute(root, paths, command, timeout, *, execution_env=None):
    if not command or not 0 < timeout < float('inf'):
        raise ValueError('Supply an explicit command and a finite positive hard timeout')
    before = source_freshness.capture(root, paths)
    if any(row['sha256'] is None for row in before['files']):
        raise ValueError('All declared verification inputs must exist')
    environment = runtime(command, root, execution_env)
    started = time.monotonic()
    process = subprocess.Popen(command, cwd=root, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True, env=execution_env)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        code, output = process.returncode, stdout + stderr
        outcome = 'passed' if code == 0 else 'failed'
        if code == 0 and Path(command[0]).name in ('sh', 'bash', 'zsh', 'dash', 'ksh', 'fish'):
            # A shell's final status cannot attest each required command. Use
            # separate argv receipts or a tested runner propagating every failure.
            outcome = 'unverified_shell_status'
    except subprocess.TimeoutExpired:
        import signal
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass  # The process group exited at the deadline.
        stdout, stderr = process.communicate(timeout=5)
        code, output, outcome = None, stdout + stderr, 'timeout'
    after = source_freshness.capture(root, paths)
    environment_after = runtime(command, root, execution_env)
    if before != after:
        outcome = 'source_changed'
    elif environment != environment_after:
        outcome = 'environment_changed'
    return {'version': 1, 'command': [redact(arg) for arg in command],
            'command_sha256': command_digest(command), 'before': before, 'after': after,
            'runtime': environment, 'runtime_after': environment_after,
            'exit_code': code, 'outcome': outcome, 'attempts': 1,
            'elapsed_seconds': time.monotonic() - started,
            'output_sha256': hashlib.sha256(output).hexdigest(),
            'diagnostic': redact(output.decode('utf-8', errors='replace'))[-4096:] if outcome != 'passed' else '',
            'boundary': 'Declared inputs only; not independent review, native acknowledgement or integration'}


def reusable(receipt, root, command, *, candidate=None, paths=None, external_paths=None, qualification_scope=None):
    if not command or Path(command[0]).name in ('sh', 'bash', 'zsh', 'dash', 'ksh', 'fish'):
        return False
    if receipt.get('qualification_scope') != validate_scope(qualification_scope):
        return False
    if paths is not None and list(paths) != [row['path'] for row in receipt['before']['files']]:
        return False
    if external_paths is not None and list(external_paths) != [row['path'] for row in (receipt.get('external_before') or {'files': []})['files']]:
        return False
    # Exact proof is never silently reused as legacy shared-tree evidence.
    exact = receipt.get('version') == 2
    if exact:
        if (receipt.get('qualification') != 'exact_candidate'
                or receipt.get('qualification_policy') != 'declared-snapshot-v3'
                or receipt.get('generated_files') or receipt.get('generated_outputs')):
            return False
        if candidate is None or receipt.get('candidate') != candidate or not candidate_identity.check(candidate, root):
            return False
    elif candidate is not None:
        return False
    if receipt.get('external_before') != receipt.get('external_after'):
        return False
    if receipt.get('external_before') and not source_freshness.check(receipt['external_before'], root)['fresh']:
        return False
    # JSON roundtripping normalizes tuples in distribution metadata.
    if exact:
        with isolated_candidate(root, candidate) as checkout:
            frozen = dict(receipt['before'], workspace=str(checkout.resolve()))
            if not source_freshness.check(frozen, checkout)['fresh']:
                return False
            current = json.loads(json.dumps(runtime(candidate_command(command, root, checkout), checkout,
                                                    candidate_environment(root, checkout))))
        if not candidate_identity.check(candidate, root):
            return False
    else:
        current = json.loads(json.dumps(runtime(command, root)))
    def comparable(value):
        value = json.loads(json.dumps(value))
        if exact and isinstance(value, dict):
            value.pop('execution_environment_sha256', None)
        return value
    return (receipt.get('version') in (1, 2) and receipt.get('outcome') == 'passed'
            and receipt.get('exit_code') == 0 and receipt.get('command') == [redact(arg) for arg in command]
            and receipt.get('command_sha256', command_digest(command)) == command_digest(command)
            and receipt.get('before') == receipt.get('after')
            and comparable(receipt.get('runtime')) == comparable(current)
            and comparable(receipt.get('runtime_after')) == comparable(current)
            and (exact or source_freshness.check(receipt['before'], root)['fresh']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['run', 'reuse'])
    parser.add_argument('--workspace', required=True, type=Path)
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--path', action='append', default=[], help='Explicit source, dependency or environment input')
    parser.add_argument('--timeout', type=float, default=60, help='Finite hard deadline in seconds; explicitly configurable above 300')
    parser.add_argument('--base', help='Immutable full base commit ID (required for exact mode)')
    parser.add_argument('--candidate', help='Candidate commit/ref; never the shared working tree')
    parser.add_argument('--tree', help='Expected candidate tree ID, checked against its commit')
    parser.add_argument('--prerequisite', action='append', default=[], metavar='REF=COMMIT')
    parser.add_argument('--external-path', action='append', default=[], help='Explicit workspace-relative dependency/environment file outside candidate')
    parser.add_argument('--generated-output', action='append', default=[], help='Exact relative output file; narrows evidence because output consumption is not sandboxed')
    parser.add_argument('--resource-lock', type=Path, help='Shared heavyweight resource lock path')
    parser.add_argument('--lock-timeout', type=float, default=30)
    parser.add_argument('--platform', help='Explicit tested platform, not inferred host capability')
    parser.add_argument('--backend', help='Explicit tested backend/provider identity')
    parser.add_argument('--mode', choices=['fixture', 'live'])
    parser.add_argument('--toolchain', action='append', default=[], metavar='NAME=IDENTITY')
    argv = sys.argv[1:]
    if '--' not in argv:
        parser.error('Separate the explicit check command with --')
    split = argv.index('--')
    args = parser.parse_args(argv[:split])
    command = argv[split + 1:]
    try:
        scope = None
        if args.platform or args.backend or args.mode or args.toolchain:
            toolchain = {}
            for item in args.toolchain:
                name, identity = item.split('=', 1)
                if name in toolchain:
                    raise ValueError('Duplicate toolchain name')
                toolchain[name] = identity
            scope = validate_scope({'platform': args.platform, 'backend': args.backend,
                                    'mode': args.mode, 'toolchain': toolchain})
        candidate = None
        if args.base or args.candidate or args.tree or args.prerequisite:
            if not args.base or not args.candidate:
                raise ValueError('Exact candidate mode requires --base and --candidate')
            prerequisites = {}
            for item in args.prerequisite:
                ref, pin = item.split('=', 1)
                if ref in prerequisites:
                    raise ValueError('Duplicate prerequisite ref')
                prerequisites[ref] = pin
            candidate = candidate_identity.capture(args.workspace, args.base, args.candidate, prerequisites, args.tree)
        if args.action == 'reuse':
            started = time.monotonic()
            saved = json.loads(args.receipt.read_text())
            accepted = reusable(saved, args.workspace, command, candidate=candidate,
                                paths=args.path, external_paths=args.external_path, qualification_scope=scope)
            print(json.dumps({'reusable': accepted, 'execution': 'reused' if accepted else 'reuse_rejected',
                              'attempts': 0, 'elapsed_seconds': time.monotonic() - started,
                              'qualification': 'exact_candidate' if candidate else 'shared_tree_declared_inputs_only'}))
            return 0 if accepted else 1
        if args.receipt.exists():
            raise ValueError('Receipt already exists; preserve it and choose a new path')
        receipt = execute(args.workspace, args.path, command, args.timeout, candidate=candidate,
                          resource_lock=args.resource_lock, lock_timeout=args.lock_timeout,
                          external_paths=args.external_path, qualification_scope=scope, generated_outputs=args.generated_output)
        with args.receipt.open('x') as stream:
            stream.write(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps({key: receipt[key] for key in ('outcome', 'attempts', 'elapsed_seconds',
                         'execution', 'qualification', 'lock_wait_seconds', 'hard_timeout_seconds')}))
        return 0 if receipt['outcome'] == 'passed' else 1
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
