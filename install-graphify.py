#!/usr/bin/env python3
"""Install Graphify's official Hermes skill into selected existing profiles.

Upstream: https://github.com/Graphify-Labs/graphify
The PyPI distribution is graphifyy; its executable is graphify.
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


MARKERS = ('config.yaml', '.env', 'SOUL.md', 'profile.yaml', 'auth.json', 'state.db')


def existing_skill(target):
    """Only a readable installed skill qualifies for a successful skip."""
    if not os.path.lexists(target):
        return False
    skill = target / 'SKILL.md'
    if not target.is_dir() or not skill.is_file() or not os.access(skill, os.R_OK):
        raise ValueError(f'Existing Graphify destination lacks a readable SKILL.md: {target}; '
                         'preserving it without changes.')
    return True


def destinations(root, profiles):
    root = root.expanduser().absolute()
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f'Hermes root must be an existing, non-symlink directory: {root}')
    result = []
    for name in dict.fromkeys(profiles):
        if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*', name):
            raise ValueError(f'Invalid profile name: {name!r}')
        home = root if name == 'default' else root / 'profiles' / name
        if name != 'default':
            if ((root / 'profiles').is_symlink() or home.is_symlink()
                    or not home.is_dir()
                    or (root / 'profiles/.deleted' / name).exists()
                    or not any((home / marker).is_file() for marker in MARKERS)):
                raise ValueError(f'Profile is not an existing live profile: {name}')
        skills = home / 'skills'
        if skills.is_symlink() or (skills.exists() and not skills.is_dir()):
            raise ValueError(f'Skills root must be a non-symlink directory: {skills}')
        target = skills / 'graphify'
        existing_skill(target)
        result.append(target)
    return result


def ensure_cli():
    executable = shutil.which('graphify')
    if executable:
        return executable
    uv = shutil.which('uv')
    if not uv:
        raise ValueError('Graphify is missing; install uv and rerun (requires uv tool install graphifyy).')
    subprocess.run([uv, 'tool', 'install', 'graphifyy'], check=True)
    executable = shutil.which('graphify')
    if executable:
        return executable
    directory = subprocess.run([uv, 'tool', 'dir', '--bin'], check=True,
                               capture_output=True, text=True).stdout.strip()
    candidate = Path(directory) / 'graphify'
    if directory and candidate.is_file() and os.access(candidate, os.X_OK):
        print(f'Graphify CLI: {candidate}; add {candidate.parent} to PATH for shell use.')
        return str(candidate)
    raise ValueError('uv installed graphifyy but the graphify executable could not be found.')


def install_tree(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.graphify-install-', dir=target.parent) as staging:
        staged = Path(staging) / 'graphify'
        shutil.copytree(source, staged)
        if existing_skill(target):
            print(f'Skipped existing skill: {target}')
            return
        staged.rename(target)
    print(f'Installed Graphify skill: {target}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hermes-home', type=Path, required=True)
    parser.add_argument('--profile', action='append', required=True)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        targets = destinations(args.hermes_home, args.profile)
        if args.dry_run:
            print('Would ensure graphify CLI is available (uv tool install graphifyy if missing).')
            print('Would generate skill in temporary cwd: graphify install --platform hermes --project')
            for target in targets:
                action = 'Skip existing' if existing_skill(target) else 'Install'
                print(f'{action}: {target}')
            return 0
        executable = ensure_cli()
        pending = []
        for target in targets:
            if existing_skill(target):
                print(f'Skipped existing skill: {target}')
            else:
                pending.append(target)
        if not pending:
            return 0
        with tempfile.TemporaryDirectory(prefix='hermes-graphify-') as staging:
            subprocess.run([executable, 'install', '--platform', 'hermes', '--project'],
                           cwd=staging, check=True)
            source = Path(staging) / '.hermes/skills/graphify'
            if not (source / 'SKILL.md').is_file():
                raise ValueError('Graphify did not generate .hermes/skills/graphify/SKILL.md')
            for target in pending:
                install_tree(source, target)
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f'Graphify installation failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
