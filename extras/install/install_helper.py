"""Per-profile wiring for hermes-shared-skills. Run by install.sh inside Hermes' own Python
(after `import hermes_bootstrap`), so the YAML round-trip keeps comments and formatting.

Args come from INSTALL_ARGS (JSON): repo, profiles, disable_fleet, telegram_menu, soul, allow_all, prune, dry_run.
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
MENU = ['repo_docs', 'autogoal', 'grill_me', 'lgtm', 'git_commit_push', 'git_pull_merge', 'impeccable']
WRAPPERS = {'repo_docs_monitor.py': 'extras/monitors/repo_docs_monitor.py',
            'autogoal_gate.py': 'extras/monitors/autogoal_gate.py',
            'autogoal_monitor.py': 'extras/monitors/autogoal_monitor.py'}
DEFAULT_ONLY = {'scratch_cleanup.py': 'extras/maintenance/scratch_cleanup.py',
                'merge_train_daily.py': 'extras/maintenance/merge_train_daily.py'}

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

    if args.get('prune'):
        disabled = ensure_list(skills, 'disabled')
        for line in (repo / 'extras/install/disabled-skills.txt').read_text().splitlines():
            n = line.strip()
            if n and not n.startswith('#') and n not in disabled:
                disabled.append(n); changes.append(f'disabled += {n}')

    if args.get('allow_all'):
        sec = data.setdefault('security', {})
        ap = data.setdefault('approvals', {})
        wanted = {('security', 'protected_instruction_files'): False, ('approvals', 'mode'): 'off',
                  ('approvals', 'cron_mode'): 'approve', ('approvals', 'single_query_mode'): 'approve',
                  ('approvals', 'unattended_mode'): 'approve', ('approvals', 'mcp_reload_confirm'): False,
                  ('approvals', 'destructive_slash_confirm'): False}
        for (section, key), value in wanted.items():
            node = sec if section == 'security' else ap
            if node.get(key) != value:
                node[key] = value; changes.append(f'{section}.{key}={value}')

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
    wrappers = dict(WRAPPERS, **(DEFAULT_ONLY if name == 'default' else {}))
    for m, rel in wrappers.items():
        wrapper = scripts / m
        body = (f'#!/usr/bin/env python3\n# Wrapper: logic lives in {repo}/{rel}\n'
                f'import runpy, sys\nsys.argv[0] = {m!r}\n'
                f'runpy.run_path({str(repo / rel)!r}, run_name="__main__")\n')
        existing = wrapper.read_text() if wrapper.exists() else None
        if existing == body:
            continue
        # Only refresh exact generated bodies (including the legacy quoting).
        # An extras/ reference or a copied header alone does not confer ownership.
        managed = False
        if existing is not None:
            lines = existing.splitlines()
            marker = '# Wrapper: logic lives in '
            if len(lines) == 5 and lines[1].startswith(marker):
                old_target = lines[1][len(marker):]
                if old_target.endswith('/' + rel):
                    header = f'#!/usr/bin/env python3\n{marker}{old_target}\nimport runpy, sys\n'
                    managed = existing in (
                        header + f'sys.argv[0] = {m!r}\n'
                        + f'runpy.run_path({old_target!r}, run_name="__main__")\n',
                        header + f'sys.argv[0] = "{m}"\n'
                        + f'runpy.run_path("{old_target}", run_name="__main__")\n',
                    )
        if existing is not None and not managed:
            print(f'[{name}] keep existing custom {wrapper} (not ours)')
            continue
        changes.append(f'write {wrapper}')
        if not dry:
            scripts.mkdir(parents=True, exist_ok=True)
            wrapper.write_text(body)

    if args.get('soul'):
        soul = ph / 'SOUL.md'
        text = soul.read_text() if soul.exists() else ''
        add = ''
        for snip in sorted((repo / 'extras/soul').glob('*.md')):
            if snip.name == 'README.md':
                continue
            body = snip.read_text().strip()
            heading = body.splitlines()[0]
            if heading not in text:
                add += '\n\n' + body; changes.append(f'SOUL += {heading[3:]}')
        if add and not dry:
            soul.write_text(text.rstrip('\n') + add + '\n')

    cfg_changes = [c for c in changes if not c.startswith(('write ', 'SOUL'))]
    if cfg_changes and not dry:
        with cfg_path.open('w') as fh:
            yaml.dump(data, fh)
    print(f'[{name}] ' + ('; '.join(changes) if changes else 'already up to date') + (' (dry run)' if dry and changes else ''))
