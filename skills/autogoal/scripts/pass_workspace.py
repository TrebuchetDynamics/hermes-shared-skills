#!/usr/bin/env python3
"""Prepare immutable-base native directory workspaces without copying dirty files."""
import argparse
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

spec = importlib.util.spec_from_file_location('pass_candidate_identity', Path(__file__).with_name('candidate_identity.py'))
assert spec is not None and spec.loader is not None
candidate_identity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate_identity)


def prepare(source, target, base, candidate, prerequisites=None, required_paths=()):
    source = Path(source).resolve(strict=True)
    target = Path(target).resolve()
    identity = candidate_identity.capture(source, base, candidate)
    pins = prerequisites or {}
    for ref, pin in pins.items():
        if candidate_identity.git(source, 'rev-parse', '--verify', ref + '^{commit}') != pin:
            raise ValueError('prerequisite ref moved or missing immutable pin')
    if target == source or target.is_relative_to(source):
        raise ValueError('Pass workspace must be outside the shared checkout')
    target.parent.mkdir(parents=True, exist_ok=True)
    candidate_identity.git(source, 'worktree', 'add', '--detach', str(target), identity['candidate_commit'])
    try:
        for ref, pin in sorted(pins.items()):
            candidate_identity.git(target, '-c', 'user.name=Autogoal assembly', '-c',
                                   'user.email=autogoal@local', 'merge', '--no-edit', pin)
        for name in required_paths:
            path = Path(name)
            if path.is_absolute() or '..' in path.parts or '.git' in path.parts:
                raise ValueError('Unsafe required path')
            resolved = (target / path).resolve()
            if not resolved.is_relative_to(target) or not resolved.is_file():
                raise ValueError('Missing required path: ' + name)
        commit = candidate_identity.git(target, 'rev-parse', 'HEAD')
        return candidate_identity.capture(target, base, commit, pins)
    except (ValueError, OSError):
        candidate_identity.git(source, 'worktree', 'remove', '--force', str(target))
        raise


def verify(manifest, workspace):
    workspace = Path(workspace).resolve(strict=True)
    identity = manifest['candidate_identity']
    if (str(workspace) != identity['workspace']
            or candidate_identity.git(workspace, 'rev-parse', 'HEAD') != identity['candidate_commit']
            or not candidate_identity.check(identity, workspace)):
        raise ValueError('Pass candidate identity changed')
    if candidate_identity.git(workspace, 'status', '--porcelain', '--untracked-files=all'):
        raise ValueError('Pass workspace changed before worker start')
    source = Path(manifest['source_workspace']).resolve(strict=True)
    for root in (source, workspace):
        for row in manifest['files']:
            path = Path(row['path'])
            if path.is_absolute() or '..' in path.parts or '.git' in path.parts:
                raise ValueError('Unsafe source path')
            file = (root / path).resolve()
            if not file.is_relative_to(root):
                raise ValueError('Source path escapes workspace')
            actual = hashlib.sha256(file.read_bytes()).hexdigest() if file.exists() else None
            if actual != row['sha256']:
                raise ValueError('Source changed before worker start: ' + row['path'])
        ledger = root / 'goals.json'
        actual = hashlib.sha256(ledger.read_bytes()).hexdigest() if ledger.exists() else None
        if actual != manifest['ledger_sha256']:
            raise ValueError('Goal ledger changed before worker start')
    return True


def run_checked(manifest, workspace, command):
    verify(manifest, workspace)
    return subprocess.run(command, cwd=workspace, env=candidate_identity.git_environment(),
                          timeout=180, check=True).returncode


def native_main_only_gate():
    # ponytail: refuse rather than invent a prompt-only native lock adapter.
    raise ValueError('native dispatcher has no common-repository admission hook held for the full worker lifecycle; '
                     'shared helpers cannot fence cross-profile/native writers before workspace setup and goal startup')


def prepare_main_only(source, target, base, snapshot_file, goal_task, required_paths, writable_paths):
    """Offline preparation only: committed attributed inputs, never a dirty union.

    Writable paths describe the task contract, not a filesystem sandbox. Native
    dispatch stays gated until the dispatcher owns serialization before setup.
    """
    source = Path(source).resolve(strict=True)
    target = Path(target).resolve()
    if (candidate_identity.git(source, 'branch', '--show-current') != 'main'
            or candidate_identity.git(source, 'rev-parse', '--show-toplevel') != str(source)
            or not (source / '.git').is_dir()):
        raise ValueError('main-only requires the canonical main checkout, not a worktree')
    identity = candidate_identity.capture(source, base, base)
    if candidate_identity.git(source, 'rev-parse', 'HEAD') != identity['candidate_commit']:
        raise ValueError('main-only base must equal current canonical HEAD')
    snapshot_bytes = Path(snapshot_file).read_bytes()
    expected = json.loads(snapshot_bytes)
    spec = importlib.util.spec_from_file_location('main_only_admission', Path(__file__).with_name('start_goal.py'))
    assert spec is not None and spec.loader is not None
    admission_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(admission_module)
    admission = admission_module.require_milestone_admission(source, goal_task, snapshot_file)
    admission_module.require_fresh_sources(snapshot_file, source)
    if not goal_task or admission['goal_task'] != goal_task:
        raise ValueError('exact eligible goal task required')
    files = {row['path']: row['sha256'] for row in expected['files']}
    if files.get('goals.json') != admission['ledger_sha256']:
        raise ValueError('source evidence must include exact goal ledger')
    if not required_paths or not set(required_paths).issubset(files):
        raise ValueError('explicit dependency closure must be covered by source evidence')
    if not writable_paths or len(writable_paths) != len(set(writable_paths)):
        raise ValueError('nonempty unique task writable allowlist required')
    # Use the same credential/symlink boundary for both inputs and allowed output names.
    spec = importlib.util.spec_from_file_location('main_only_freshness', Path(__file__).with_name('source_freshness.py'))
    assert spec is not None and spec.loader is not None
    freshness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(freshness)
    freshness.capture(source, list(writable_paths))
    inputs = {}
    for name, digest in files.items():
        path = source / name
        if digest is None:
            raise ValueError('immutable snapshot inputs must exist')
        data = path.read_bytes()
        committed = subprocess.run(['git', '-C', str(source), 'show', base + ':' + name],
                                   capture_output=True, timeout=30, check=True,
                                   env=candidate_identity.git_environment()).stdout
        if data != committed or hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('unattributed dirty source input: ' + name)
        inputs[name] = data
    if target == source or target.is_relative_to(source) or target.exists():
        raise ValueError('snapshot must be a new external filesystem directory')
    target.mkdir(parents=True, mode=0o700)
    try:
        for name, data in inputs.items():
            file = target / name
            file.parent.mkdir(parents=True, exist_ok=True)
            with file.open('xb') as stream:
                stream.write(data)
            file.chmod(0o400)
        for directory in sorted((p for p in target.rglob('*') if p.is_dir()), reverse=True):
            directory.chmod(0o500)
        target.chmod(0o500)
        admission_module.require_fresh_sources(snapshot_file, source)
        if (Path(snapshot_file).read_bytes() != snapshot_bytes or
                candidate_identity.git(source, 'rev-parse', 'HEAD') != base):
            raise ValueError('source identity changed during preparation')
        return {'version': 1, 'mode': 'main-only', 'source_workspace': str(source),
                'snapshot': str(target), 'candidate_identity': identity,
                'files': expected['files'], 'admission': admission,
                'source_snapshot_sha256': hashlib.sha256(snapshot_bytes).hexdigest(),
                'writable_paths': list(writable_paths), 'required_paths': list(required_paths),
                'boundary': 'offline_preparation_not_native_admission'}
    except Exception:
        import shutil
        for path in target.rglob('*'):
            path.chmod(0o700 if path.is_dir() else 0o600)
        target.chmod(0o700)
        shutil.rmtree(target)
        raise


def verify_main_only(manifest):
    source = Path(manifest['source_workspace']).resolve(strict=True)
    snapshot = Path(manifest['snapshot']).resolve(strict=True)
    if (manifest.get('version') != 1 or manifest.get('mode') != 'main-only'
            or snapshot == source or snapshot.is_relative_to(source)
            or not (source / '.git').is_dir()
            or candidate_identity.git(source, 'branch', '--show-current') != 'main'
            or candidate_identity.git(source, 'rev-parse', 'HEAD') != manifest['candidate_identity']['candidate_commit']
            or not candidate_identity.check(manifest['candidate_identity'], source)):
        raise ValueError('main-only source identity changed')
    spec = importlib.util.spec_from_file_location('main_verify_freshness', Path(__file__).with_name('source_freshness.py'))
    assert spec is not None and spec.loader is not None
    freshness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(freshness)
    for root in (source, snapshot):
        scoped = {'version': 1, 'workspace': str(root), 'files': manifest['files']}
        if not freshness.check(scoped, root)['fresh']:
            raise ValueError('main-only source/snapshot bytes changed')
    return source


def run_main_only(manifest, command, *, ownership_guard=None, timeout=180):
    """Held common-repository lock for a synchronous worker and cleanup.

    The trusted runtime must supply its native all-board ownership guard before
    invoking this, and coordinate every writer. No installed native hook exists;
    CLI admission therefore refuses. Tests supply an isolated-fixture guard.
    The lock is cooperative, not a sandbox against malicious same-UID workers.
    """
    if ownership_guard is None:
        native_main_only_gate()
    import fcntl
    import os
    import signal
    import time
    if not callable(ownership_guard) or not command or not 0 < timeout <= 180:
        raise ValueError('trusted ownership guard, command and bounded runtime required')
    source = Path(manifest['source_workspace']).resolve(strict=True)
    common = Path(candidate_identity.git(source, 'rev-parse', '--path-format=absolute', '--git-common-dir'))
    fd = os.open(common / 'autogoal-main-only.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('another writer already owns the common repository') from exc
        ownership_guard()
        verify_main_only(manifest)
        interrupted = []
        handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
        try:
            for sig in handlers:
                signal.signal(sig, lambda sig, frame: interrupted.append(sig))
            # Inherit the lock: abrupt supervisor death cannot release it while
            # this cooperating worker still runs. Cleanup precedes normal unlock.
            proc = subprocess.Popen(command, cwd=source, env=candidate_identity.git_environment(),
                                    pass_fds=(fd,), start_new_session=True)
            deadline = time.monotonic() + timeout
            try:
                while True:
                    status = os.waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOWAIT | os.WNOHANG)
                    if status is not None:
                        break
                    if interrupted:
                        raise ValueError('main-only supervisor interrupted; worker group canceled')
                    if time.monotonic() >= deadline:
                        raise subprocess.TimeoutExpired(command, timeout)
                    time.sleep(.01)
            finally:
                # Preserve PID ownership (WNOWAIT) through all group signaling.
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=5)
            if proc.returncode:
                raise subprocess.CalledProcessError(proc.returncode, command)
            return proc.returncode
        finally:
            for sig, handler in handlers.items():
                signal.signal(sig, handler)
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('isolated', 'main-only'), default='isolated')
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--manifest-sha256', required=True, help='Exact hash embedded in original card')
    parser.add_argument('--workspace', required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.mode == 'main-only':
        try:
            native_main_only_gate()
        except ValueError as exc:
            parser.exit(2, str(exc) + '\n')
    manifest_bytes = Path(args.manifest).read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != args.manifest_sha256:
        parser.exit(2, 'Pass manifest changed; preserve original card and re-evaluate\n')
    manifest = json.loads(manifest_bytes)
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if command:
        run_checked(manifest, args.workspace, command)
    else:
        verify(manifest, args.workspace)
        print(json.dumps({'outcome': 'worker_start_admitted', 'workspace': args.workspace}))


if __name__ == '__main__':
    main()
