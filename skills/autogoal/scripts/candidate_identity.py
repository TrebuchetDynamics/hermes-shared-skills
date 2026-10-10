#!/usr/bin/env python3
"""Capture ancestry-checked immutable Git candidate identities; no staging."""
import re
import os
import subprocess
from pathlib import Path


def git_environment():
    environment = dict(os.environ)
    for key in ('GIT_INDEX_FILE', 'GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR',
                'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_NAMESPACE'):
        environment.pop(key, None)
    return environment


def git(root, *args):
    result = subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', '-C', str(root), *args], capture_output=True,
                            text=True, timeout=30, env=git_environment())
    if result.returncode:
        raise ValueError('Git identity/ancestry check failed: ' + ' '.join(args[:2]))
    return result.stdout.strip()


def capture(root, base, candidate, prerequisites=None, tree=None):
    root = Path(root).resolve(strict=True)
    if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', base):
        raise ValueError('base must be an immutable full commit ID')
    base_commit = git(root, 'rev-parse', '--verify', base + '^{commit}')
    commit = git(root, 'rev-parse', '--verify', candidate + '^{commit}')
    git(root, 'merge-base', '--is-ancestor', base_commit, commit)
    pinned = []
    for ref, expected in sorted((prerequisites or {}).items()):
        actual = git(root, 'rev-parse', '--verify', ref + '^{commit}')
        if actual != expected:
            raise ValueError('prerequisite ref moved or pin is not a full commit ID')
        try:
            git(root, 'merge-base', '--is-ancestor', expected, commit)
        except ValueError as error:
            raise ValueError('required prerequisite is not in candidate ancestry') from error
        pinned.append({'ref': ref, 'commit': actual})
    actual_tree = git(root, 'rev-parse', '--verify', commit + '^{tree}')
    if tree is not None and tree != actual_tree:
        raise ValueError('candidate tree does not match candidate commit')
    return {'version': 1, 'workspace': str(root), 'base_commit': base_commit,
            'candidate_ref': candidate, 'candidate_commit': commit,
            'candidate_tree': actual_tree, 'prerequisites': pinned}


def check(identity, root):
    try:
        return identity == capture(root, identity['base_commit'], identity['candidate_ref'],
                                   {row['ref']: row['commit'] for row in identity['prerequisites']},
                                   identity['candidate_tree'])
    except (ValueError, KeyError, TypeError, OSError):
        return False
