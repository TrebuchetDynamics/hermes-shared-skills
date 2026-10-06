#!/usr/bin/env python3
"""Install the third-party skills listed in manifest.json into <repo>/vendor/<source>/<skill>/.

  sync_vendor.py [--only NAME[,NAME]] [--pin] [--dry-run]

- Fetches each source at its pinned `ref` with a sparse, blob-less clone (only the listed paths).
- Copies each skill folder, appends the source's overlay (if any) and the Hermes note to SKILL.md,
  and writes vendor/<source>/UPSTREAM.md (repo, commit, license) plus the upstream LICENSE.
- Refuses a skill whose name collides with a first-party skill in this repo.
- --pin fetches each source at upstream HEAD and records that commit in manifest.json.
A skill path may be written `path=name` to rename the installed folder (e.g. a root SKILL.md).
vendor/ is gitignored: third-party content keeps its own license and is never committed here.
"""
import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / 'manifest.json'
NOTE = (HERE / 'hermes-note.md').read_text()
VENDOR = REPO / 'vendor'


def git(*args, cwd=None):
    return subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def first_party_names():
    return {p.parent.name for p in REPO.glob('*/SKILL.md')}


def bundled_names():
    """Skills Hermes itself bundles into profiles (a vendored duplicate would be shadowed)."""
    import os
    home = Path(os.environ.get('HERMES_HOME') or Path.home() / '.hermes')
    manifest = home / 'skills' / '.bundled_manifest'
    return {l.split(':', 1)[0] for l in manifest.read_text().splitlines() if l} if manifest.exists() else set()


def fetch(source, tmp):
    dest = Path(tmp) / source['name']
    git('clone', '-q', '--filter=blob:none', '--no-checkout', f"https://github.com/{source['repo']}", str(dest))
    paths = [s.split('=')[0] for s in source['skills']]
    if any(p in ('.', '') for p in paths):
        git('sparse-checkout', 'disable', cwd=dest)
    else:
        git('sparse-checkout', 'set', '--no-cone', *[f'/{p}/' for p in paths] + ['/LICENSE*'], cwd=dest)
    ref = source.get('ref') or 'HEAD'
    git('checkout', '-q', ref if ref != 'HEAD' else 'HEAD', cwd=dest)
    return dest, git('rev-parse', 'HEAD', cwd=dest)


def install(source, src_root, commit, dry):
    taken = first_party_names()
    bundled = bundled_names()
    out_dir = VENDOR / source['name']
    installed = []
    for spec in source['skills']:
        path, _, rename = spec.partition('=')
        src = src_root if path in ('.', '') else src_root / path
        name = rename or src.name
        if not (src / 'SKILL.md').exists():
            raise SystemExit(f"{source['name']}: {path} has no SKILL.md at {commit[:10]}")
        if name in taken:
            raise SystemExit(f"{source['name']}: skill '{name}' collides with a first-party skill; rename it with path=newname")
        if name in bundled:
            raise SystemExit(f"{source['name']}: skill '{name}' is already bundled with Hermes; drop it from the manifest")
        installed.append(name)
        if dry:
            continue
        target = out_dir / name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(src, target, ignore=shutil.ignore_patterns('.git', 'node_modules', '.github'))
        skill_md = target / 'SKILL.md'
        text = skill_md.read_text().rstrip('\n') + '\n'
        if rename:  # the slash command comes from the frontmatter name, so rename it too
            import re
            text = re.sub(r'^name:\s*.*$', f'name: {rename}', text, count=1, flags=re.M)
        if source.get('overlay'):
            text += '\n' + (REPO / source['overlay']).read_text().strip('\n') + '\n'
        skill_md.write_text(text + NOTE)
    if not dry:
        out_dir.mkdir(parents=True, exist_ok=True)
        for lic in src_root.glob('LICENSE*'):
            shutil.copy2(lic, out_dir / lic.name)
        (out_dir / 'UPSTREAM.md').write_text(
            f"# {source['name']}\n\n- Source: https://github.com/{source['repo']}/tree/{commit}\n"
            f"- License: {source['license']} (see LICENSE in this folder)\n- Skills: {', '.join(installed)}\n"
            f"- Installed by extras/vendor/sync_vendor.py; local edits are overwritten on the next sync.\n")
    return installed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='')
    ap.add_argument('--pin', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    manifest = json.loads(MANIFEST.read_text())
    only = {x for x in a.only.split(',') if x}
    total = []
    with tempfile.TemporaryDirectory() as tmp:
        for source in manifest['sources']:
            if only and source['name'] not in only:
                continue
            # --pin updates existing pins to upstream HEAD, not to the old pin again.
            fetch_source = {**source, 'ref': 'HEAD'} if a.pin else source
            root, commit = fetch(fetch_source, tmp)
            names = install(source, root, commit, a.dry_run)
            total += names
            print(f"{source['name']:28} {commit[:10]}  {', '.join(names)}")
            if a.pin:
                source['ref'] = commit
    if a.pin and not a.dry_run:
        MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(f"{'would install' if a.dry_run else 'installed'} {len(total)} vendored skills into {VENDOR}")


if __name__ == '__main__':
    main()
