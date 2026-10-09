#!/usr/bin/env python3
"""Fetch configured upstream, privately preserve tracked state, then align HEAD.

No git clean: unrelated untracked/ignored files must survive. Run only on a
quiescent checkout (no concurrent writers). install.sh re-execs after this step.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.PIPE)


def sync(repo, dry=False):
    repo = repo.resolve()
    top = Path(os.fsdecode(git(repo, 'rev-parse', '--show-toplevel')).strip()).resolve()
    if top != repo:
        raise ValueError('Installer must live at the Git checkout root')
    branch = os.fsdecode(git(repo, 'symbolic-ref', '--short', 'HEAD')).strip()
    remote = os.fsdecode(git(repo, 'config', f'branch.{branch}.remote')).strip()
    merge = os.fsdecode(git(repo, 'config', f'branch.{branch}.merge')).strip()
    if remote == '.' or not merge.startswith('refs/heads/'):
        raise ValueError('Configure a remote branch upstream before installing')
    if dry:
        print(f'Dry run: would fetch {remote} {merge}, back up tracked state and reset; no Git writes')
        return
    # A failed fetch changes neither HEAD, index nor working files.
    git(repo, 'fetch', '--no-tags', '--', remote, merge)
    target = os.fsdecode(git(repo, 'rev-parse', '--verify', 'FETCH_HEAD^{commit}')).strip()
    for rel in ('install.sh', 'extras/install/install_helper.py'):
        git(repo, 'cat-file', '-e', f'{target}:{rel}')
    # reset --hard can itself delete obstructing untracked files, even without
    # git clean. Include ignored files and ancestor/descendant path collisions.
    incoming = [os.fsdecode(p) for p in git(repo, 'ls-tree', '-r', '--name-only', '-z', target).split(b'\0') if p]
    untracked = [os.fsdecode(p).rstrip('/') for p in git(repo, 'ls-files', '--others', '-z').split(b'\0') if p]
    for local in untracked:
        if any(local == name or local.startswith(name + '/') or name.startswith(local + '/')
               for name in incoming):
            raise ValueError('Untracked or ignored path would be overwritten; move it outside the checkout')
    head = os.fsdecode(git(repo, 'rev-parse', 'HEAD')).strip()
    staged = git(repo, 'diff', '--binary', '--full-index', '--cached', 'HEAD')
    working = git(repo, 'diff', '--binary', '--full-index')
    if head != target or staged or working:
        parent = Path.home() / '.hermes/private-records/shared-skills/install-backups'
        if parent.resolve().is_relative_to(repo):
            raise ValueError('Private backup destination must be outside the repository')
        old_umask = os.umask(0o077)
        try:
            parent.mkdir(parents=True, exist_ok=True)
            backup = Path(tempfile.mkdtemp(prefix='sync-', dir=parent))
            (backup / 'index.patch').write_bytes(staged)
            (backup / 'worktree.patch').write_bytes(working)
            index = Path(os.fsdecode(git(repo, 'rev-parse', '--git-path', 'index')).strip())
            if not index.is_absolute():
                index = repo / index
            shutil.copyfile(index, backup / 'index')
            with tarfile.open(backup / 'tracked.tar', 'w', dereference=False) as archive:
                for raw in git(repo, 'ls-files', '-z').split(b'\0'):
                    if not raw:
                        continue
                    name = os.fsdecode(raw)
                    path = repo / name
                    if path.is_symlink() or path.is_file():
                        archive.add(path, arcname=name, recursive=False)
            ref = 'refs/install-backups/' + backup.name
            git(repo, 'update-ref', ref, head)
            (backup / 'state.json').write_text(json.dumps({
                'repo': str(repo), 'head': head, 'target': target, 'safety_ref': ref,
                'restore': 'On the original HEAD, apply index.patch with git apply --index; '
                           'then worktree.patch with git apply. tracked.tar and index preserve exact files/index.'
            }, indent=2) + '\n')
        finally:
            os.umask(old_umask)
        print(f'Tracked state backup: {backup}; previous HEAD: {ref}')
    git(repo, '-c', 'submodule.recurse=false', 'reset', '--hard', target)
    print(f'Synchronized {branch} to {remote} {merge} ({target})')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repo', type=Path)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        sync(args.repo, args.dry_run)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        # Git stderr can contain private URLs; do not echo it into public logs.
        print(f'Upstream sync stopped before profile setup: {type(exc).__name__}. '
              'Check upstream, permissions and backup storage; use --skip-sync to keep local work.',
              file=__import__('sys').stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
