#!/usr/bin/env bash
# Copy this repository's skills into every existing Hermes profile.
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
exec python3 - "$script_dir" "$@" <<'PY'
import argparse
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

repository = Path(sys.argv[1])
parser = argparse.ArgumentParser(
    prog='install-skills.sh',
    description='Copy local skills/ to default and all existing Hermes profiles. '
                'Existing skill paths are skipped; no configuration or gateways are changed.')
parser.add_argument('--dry-run', action='store_true', help='show destinations without writing')
parser.add_argument('--hermes-home', type=Path, metavar='ROOT',
                    help='default Hermes root (otherwise HERMES_HOME or ~/.hermes)')
args = parser.parse_args(sys.argv[2:])
root = args.hermes_home
if root is None:
    root = Path(os.environ.get('HERMES_HOME') or Path.home() / '.hermes').expanduser()
    if root.parent.name == 'profiles':
        root = root.parent.parent
root = root.expanduser().resolve()

def fail(message):
    print(f'Error: {message}', file=sys.stderr)
    sys.exit(1)

if not root.is_dir():
    fail(f'Hermes home does not exist: {root}')
source = repository / 'skills'
if not source.is_dir() or source.is_symlink():
    fail(f'Missing or symlinked skills folder: {source}')
skills = sorted(p for p in source.iterdir() if not p.name.startswith('.') and p.name != '__pycache__' and p.is_dir())
if not skills:
    fail(f'No skill folders found in {source}')
ignore = shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo', '.pytest_cache', '.git', '.DS_Store')
for skill in skills:
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', skill.name) or not (skill / 'SKILL.md').is_file():
        fail(f'Invalid skill folder or missing SKILL.md: {skill}')
    if skill.is_symlink() or any(p.is_symlink() for p in skill.rglob('*')):
        fail(f'Symlinks are not supported inside source skills: {skill}')

# Match the existing plugin installer's live-profile identity rules without
# importing Hermes or reading configuration/credential contents.
profiles = [('default', root)]
profiles_root = root / 'profiles'
markers = ('config.yaml', '.env', 'SOUL.md', 'profile.yaml', 'auth.json', 'state.db')
if profiles_root.is_dir():
    for home in sorted(profiles_root.iterdir()):
        if (home.is_dir() and home.name != 'default'
                and re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', home.name)
                and not (profiles_root / '.deleted' / home.name).exists()
                and any((home / marker).is_file() or (home / marker).is_symlink() for marker in markers)):
            profiles.append((home.name, home))

installed = skipped = planned = failed = 0
for name, home in profiles:
    destination = home / 'skills'
    if home.is_symlink() or destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        print(f'Failed: {name}: unsafe or non-directory destination {destination}', file=sys.stderr)
        failed += 1
        continue
    for skill in skills:
        target = destination / skill.name
        if target.exists() or target.is_symlink():
            print(f'Skip: {skill.name} ({name}) already exists: {target}')
            skipped += 1
            continue
        if args.dry_run:
            print(f'Plan: {skill} -> {target} ({name})')
            planned += 1
            continue
        try:
            destination.mkdir(parents=True, exist_ok=True)
            # Publish only complete copies. Failed copies leave no partial skill.
            with tempfile.TemporaryDirectory(prefix='.install-skills-', dir=destination) as temporary:
                staged = Path(temporary) / skill.name
                shutil.copytree(skill, staged, ignore=ignore)
                if target.exists() or target.is_symlink():
                    raise FileExistsError(f'Destination appeared during install: {target}')
                staged.rename(target)
            print(f'Installed: {skill.name} ({name})')
            installed += 1
        except OSError as error:
            print(f'Failed: {skill.name} ({name}): {error}', file=sys.stderr)
            failed += 1
print(f'Skills: {installed} installed, {planned} planned, {skipped} skipped, {failed} failed')
sys.exit(1 if failed else 0)
PY
