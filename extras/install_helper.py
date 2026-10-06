"""Per-profile wiring for hermes-shared-skills. Run by install.sh inside Hermes' own Python
(after `import hermes_bootstrap`), so the YAML round-trip keeps comments and formatting.

Args come from INSTALL_ARGS (JSON): repo, profiles, disable_fleet, telegram_menu, dry_run.
"""
import json
import os
from pathlib import Path

from ruamel.yaml import YAML

args = json.loads(os.environ['INSTALL_ARGS'])
repo = Path(args['repo']).resolve()
home = Path(os.environ.get('HERMES_HOME') or Path.home() / '.hermes')
dry = args.get('dry_run', False)
FLEET = ['fleet-governor', 'fleet-blockers', 'fleet-status']
MENU = ['repo_docs', 'autogoal', 'grill_me', 'lgtm', 'git_commit_push', 'impeccable']
MONITORS = ['repo_docs_monitor.py', 'autogoal_monitor.py']

yaml = YAML()  # round-trip
yaml.preserve_quotes = True


def profile_home(name):
    return home if name == 'default' else home / 'profiles' / name


def ensure_list(node, key):
    if node.get(key) is None:
        node[key] = []
    return node[key]


for name in args['profiles']:
    ph = profile_home(name)
    cfg_path = ph / 'config.yaml'
    if not cfg_path.exists():
        print(f'[{name}] skip: {cfg_path} not found')
        continue
    data = yaml.load(cfg_path.read_text()) or {}
    changes = []

    skills = data.setdefault('skills', {})
    ext = ensure_list(skills, 'external_dirs')
    if str(repo) not in [str(Path(os.path.expanduser(str(e))).resolve()) for e in ext]:
        ext.append(str(repo)); changes.append(f'external_dirs += {repo}')

    if args.get('disable_fleet') and name != 'default':
        disabled = ensure_list(skills, 'disabled')
        for s in FLEET:
            if s not in disabled:
                disabled.append(s); changes.append(f'disabled += {s}')

    if args.get('telegram_menu'):
        tg = (data.get('platforms') or {}).get('telegram')
        if tg is not None:
            menu = tg.setdefault('extra', {}).setdefault('command_menu', {})
            prio = ensure_list(menu, 'priority')
            for s in MENU:
                if s not in prio:
                    prio.append(s); changes.append(f'telegram menu += {s}')
        else:
            print(f'[{name}] telegram not configured; menu pins skipped')

    scripts = ph / 'scripts'
    for m in MONITORS:
        wrapper = scripts / m
        body = (f'#!/usr/bin/env python3\n# Wrapper: logic lives in {repo}/extras/monitors/{m}\n'
                f'import runpy, sys\nsys.argv[0] = "{m}"\n'
                f'runpy.run_path("{repo}/extras/monitors/{m}", run_name="__main__")\n')
        if not wrapper.exists() or 'extras/monitors' not in wrapper.read_text():
            if wrapper.exists():
                print(f'[{name}] keep existing custom {wrapper} (not ours)')
                continue
            changes.append(f'write {wrapper}')
            if not dry:
                scripts.mkdir(parents=True, exist_ok=True)
                wrapper.write_text(body)

    if changes and not dry:
        with cfg_path.open('w') as fh:
            yaml.dump(data, fh)
    print(f'[{name}] ' + ('; '.join(changes) if changes else 'already up to date') + (' (dry run)' if dry and changes else ''))
