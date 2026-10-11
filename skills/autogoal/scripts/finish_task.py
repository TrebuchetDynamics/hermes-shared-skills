"""Run acceptance commands and publish owned files to a local task ref only.

The caller attests file ownership and supplies the required checks. This helper
cannot infer acceptance or override a repository/user no-commit instruction.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def fingerprint(repo, files):
    result = {}
    for name in files:
        path = repo / name
        if path.is_symlink():
            result[name] = ('symlink', os.readlink(path))
        elif path.is_file():
            result[name] = (path.stat().st_mode, hashlib.sha256(path.read_bytes()).hexdigest())
        else:
            result[name] = None
    return result


def finish(repo, profile, card, message, files, checks, timeout):
    receipts = []
    before = fingerprint(repo, files)
    for command in checks:
        try:
            completed = subprocess.run(command, cwd=repo, timeout=timeout, stdout=sys.stderr)
            receipts.append({'argv': command, 'exit_code': completed.returncode})
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {'status': 'validation_failed', 'checks': receipts, 'error': str(exc)}, 1
        if completed.returncode:
            return {'status': 'validation_failed', 'checks': receipts}, 1
    if fingerprint(repo, files) != before:
        return {'status': 'source_changed', 'checks': receipts,
                'error': 'Acceptance changed owned files; inspect and rerun validation.'}, 1
    try:
        result = subprocess.run(['bash', str(Path(__file__).with_name('agent_commit.sh')),
            str(repo), profile, card, message, *files], capture_output=True, text=True,
            env={**os.environ, 'AGENT_COMMIT_JSON': '0'}, timeout=timeout)
        if result.returncode:
            return {'status': 'commit_failed', 'checks': receipts, 'error': result.stderr.strip()}, 1
        branch, sha, *rest = result.stdout.strip().split()
        if rest:
            return {'status': 'no_changes', 'checks': receipts, 'source_commit': sha}, 0
        readback = subprocess.check_output(['git', '-C', str(repo), 'rev-parse',
                                           'refs/heads/' + branch], text=True).strip()
        if readback != sha:
            raise ValueError('Task ref changed before commit readback')
        return {'status': 'committed', 'checks': receipts, 'branch': branch, 'commit': sha,
                'files': files}, 0
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return {'status': 'commit_failed', 'checks': receipts, 'error': str(exc)}, 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repo', 'profile', 'card', 'message'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--check-json', action='append', required=True,
                        help='Required acceptance argv as a JSON array; repeat for each check')
    parser.add_argument('--timeout', type=int, default=2400)
    parser.add_argument('files', nargs='+', help='Explicit owned root-relative files, never directories')
    args = parser.parse_args()
    checks = [json.loads(value) for value in args.check_json]
    if args.timeout <= 0 or any(not isinstance(check, list) or not check or
            any(not isinstance(arg, str) or not arg for arg in check) for check in checks):
        parser.error('checks must be nonempty JSON argv arrays; timeout must be positive')
    receipt, code = finish(Path(args.repo).resolve(), args.profile, args.card,
                          args.message, args.files, checks, args.timeout)
    print(json.dumps(receipt))
    return code


if __name__ == '__main__':
    sys.exit(main())
