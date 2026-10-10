#!/usr/bin/env python3
"""Apply checked-in OMH defaults to explicitly selected Hermes homes.

Upstream setup also synchronizes child profiles. Therefore a default-home run
requires all child profiles and one effective memory mode. Children run first
so upstream preserves their existing, separate store bindings. This adapter
never force-replaces plugins or restarts gateways.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys


MODES = {'off', 'review-first', 'auto-safe'}


class SetupError(Exception):
    pass


def read_defaults():
    path = Path(__file__).resolve().parent / 'plugins/defaults.json'
    value = json.loads(path.read_text())
    config = value.get('omh') if isinstance(value, dict) else None
    required = {'full', 'memory_mode', 'tui', 'menubar', 'source'}
    if not isinstance(config, dict) or set(config) != required:
        raise SetupError(f'{path}: omh must contain exactly {sorted(required)}')
    for key in ('full', 'tui', 'menubar'):
        if type(config[key]) is not bool:
            raise SetupError(f'{path}: omh.{key} must be a boolean')
    if config['memory_mode'] not in MODES | {'preserve'}:
        raise SetupError(f'{path}: unsupported omh.memory_mode')
    if not isinstance(config['source'], str) or not re.fullmatch(
            r'git\+https://github\.com/rlaope/oh-my-hermes\.git@[0-9a-f]{40}', config['source']):
        raise SetupError(f'{path}: omh.source must pin the official Git repository to a full commit SHA')
    return config


def scalar(value, location):
    """Read only plain or quoted string scalars; reject YAML features here."""
    if not value or value.startswith('#') or value in ('null', '~'):
        return ''
    if value.startswith('"'):
        parsed, end = json.JSONDecoder().raw_decode(value)
        trailing = value[end:].strip()
        if not isinstance(parsed, str) or (trailing and not trailing.startswith('#')):
            raise SetupError(f'{location}: unsupported quoted scalar')
        return parsed
    if value.startswith("'"):
        match = re.fullmatch(r"'((?:[^']|'')*)'\s*(?:#.*)?", value)
        if not match:
            raise SetupError(f'{location}: unsupported quoted scalar')
        return match[1].replace("''", "'")
    value = re.split(r'\s+#', value, maxsplit=1)[0].strip()
    if value.startswith(('{', '[', '*', '&', '!', '|', '>')) or ': ' in value:
        raise SetupError(f'{location}: unsupported YAML shape; use canonical mapping/scalar config')
    return value


def config_values(path):
    """Bounded reader, not a YAML parser: fail closed on noncanonical targets.

    Avoid a bootstrap dependency on PyYAML. Only memory/provider and the plugin
    store binding are inspected; any noncanonical shape on those paths refuses
    setup rather than guessing ownership.
    """
    if not path.exists():
        return {}
    targets = {('memory', 'provider'), ('plugins', 'entries', 'omh', 'settings', 'omh_home')}
    prefixes = {target[:i] for target in targets for i in range(1, len(target) + 1)}
    stack = []
    values = {}
    seen = set()
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if '\t' in line[:len(line) - len(line.lstrip())]:
            raise SetupError(f'{path}:{number}: tabs are not supported in YAML indentation')
        indent = len(line) - len(line.lstrip(' '))
        while stack and stack[-1][0] >= indent:
            stack.pop()
        match = re.match(r'([A-Za-z_][A-Za-z0-9_-]*):(?:\s+(.*))?$', line.lstrip())
        parent = tuple(key for _, key in stack)
        location = f'{path}:{number}'
        if not match:
            # Noncanonical keys and aliases could conceal one of our targets.
            if not parent or parent in prefixes:
                if line.lstrip().startswith('-') and parent not in prefixes:
                    continue
                raise SetupError(f'{location}: unsupported YAML shape in setup-sensitive config')
            continue
        key, raw = match[1], (match[2] or '').strip()
        current = (*parent, key)
        if current in prefixes:
            if current in seen:
                raise SetupError(f'{location}: duplicate setup-sensitive key')
            seen.add(current)
            if current in targets:
                values[current] = scalar(raw, location)
            elif raw and not raw.startswith('#'):
                raise SetupError(f'{location}: use a canonical nested mapping for {key}')
        if not raw or raw.startswith('#'):
            stack.append((indent, key))
    return values


def profile_plan(root, name, defaults):
    if name != 'default' and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', name):
        raise SetupError(f'Invalid profile name: {name}')
    home = root if name == 'default' else root / 'profiles' / name
    if not home.is_dir() or (name != 'default' and not (home / 'config.yaml').is_file()):
        raise SetupError(f'Missing Hermes profile: {home}')
    if home.is_symlink():
        raise SetupError(f'Symlinked profile is not supported: {home}')
    values = config_values(home / 'config.yaml')
    provider = values.get(('memory', 'provider'), '')
    binding = values.get(('plugins', 'entries', 'omh', 'settings', 'omh_home'), '')
    env_file = home / '.env'
    if not binding and env_file.exists():
        for line in env_file.read_text().splitlines():
            match = re.match(r'^\s*(?:export\s+)?OMH_HOME\s*=\s*(.*)$', line)
            if match:
                binding = scalar(match[1], f'{env_file}:OMH_HOME')
                if not binding:
                    raise SetupError(f'{env_file}: blank OMH_HOME')
    # Standalone OMH resolves an exported OMH_HOME before ~/.omh. Preserve
    # that existing store and read its policy instead of silently rebinding it.
    # Explicit profile configuration (including its own environment) wins.
    exported_binding = False
    if not binding and os.environ.get('OMH_HOME'):
        binding = os.environ['OMH_HOME']
        exported_binding = True
    if binding:
        binding = binding.replace('${HERMES_HOME}', str(home)).replace('$HERMES_HOME', str(home))
        binding = binding.replace('${HOME}', str(Path.home())).replace('$HOME', str(Path.home()))
        if '$' in binding:
            raise SetupError(f'{home}: cannot safely resolve OMH store binding')
        store = Path(binding).expanduser()
        if not store.is_absolute():
            # Upstream standalone environment paths are relative to the
            # launch directory; profile bindings are relative to their home.
            store = (Path.cwd() if exported_binding else home) / store
    else:
        store = Path.home() / '.omh' if provider == 'omh' else home / 'omh'
    mode = defaults['memory_mode']
    if mode == 'preserve':
        mode = 'off'
        if provider == 'omh':
            mode = 'auto-safe'
            profile = store / 'setup-profile.json'
            if profile.exists():
                data = json.loads(profile.read_text())
                if not isinstance(data, dict):
                    raise SetupError(f'{profile}: expected an object')
                policy = data.get('memory_policy', {})
                if not isinstance(policy, dict):
                    raise SetupError(f'{profile}: invalid memory_policy')
                stored = policy.get('mode', data.get('memory_mode', ''))
                source = policy.get('mode_source', '')
                if stored and (source == 'explicit' or (not source and stored != 'review-first')):
                    mode = stored
    if mode not in MODES:
        raise SetupError(f'{home}: unsupported existing OMH memory mode: {mode}')
    return {'name': name, 'home': home, 'store': store, 'mode': mode}


def run(command, *, json_output=False, env=None):
    result = subprocess.run(command, text=True, capture_output=True, env=env)
    if result.returncode:
        raise SetupError(f'{shlex.join(command)} failed ({result.returncode}): {result.stderr.strip() or result.stdout.strip()}')
    if not json_output:
        return result.stdout.strip()
    try:
        payload = json.loads(result.stdout)
    except ValueError as exc:
        raise SetupError(f'{command[0]} returned invalid JSON') from exc
    if not isinstance(payload, dict) or payload.get('ok') is not True:
        raise SetupError(f'{shlex.join(command)} reported failure: {result.stdout.strip()}')
    steps = payload.get('steps', {})
    rows = payload.get('hermes_profiles', [])
    if isinstance(steps, dict):
        rows = [*rows, *steps.get('hermes_profiles', [])]
    failures = [row for row in rows if isinstance(row, dict) and row.get('status') == 'failed']
    if failures:
        raise SetupError(f'OMH child profile setup failed: {json.dumps(failures)}')
    return payload


def prepare_plugin_comments(path):
    """Keep OMH's line-based section reader from stopping at YAML comments.

    Hermes may place enabled/disabled after an unindented comment banner.
    OMH treats that banner as the end of plugins and inserts a duplicate key.
    Indenting only comments leaves YAML values and user settings unchanged.
    """
    if not path.exists():
        return
    original = path.read_text()
    lines = original.splitlines(keepends=True)
    in_plugins = False
    for index, line in enumerate(lines):
        if in_plugins and line.startswith('#'):
            lines[index] = '  ' + line
        elif line.strip() and not line[0].isspace():
            in_plugins = line.strip() == 'plugins:'
    updated = ''.join(lines)
    if updated != original:
        path.write_text(updated)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hermes-home', required=True, type=Path)
    parser.add_argument('--profile', action='append', required=True)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    try:
        defaults = read_defaults()
        package = defaults['source']
        root = args.hermes_home.expanduser().resolve()
        names = list(dict.fromkeys(args.profile))
        plans = [profile_plan(root, name, defaults) for name in names]
        if 'default' in names and (root / 'profiles').is_dir():
            children = {path.name for path in (root / 'profiles').iterdir()
                        if path.is_dir() and not path.name.startswith('.')}
            if children - set(names):
                raise SetupError('Upstream OMH setup syncs child profiles; select every child before configuring default: '
                                 + ', '.join(sorted(children - set(names))))
            if len({plan['mode'] for plan in plans}) > 1:
                raise SetupError('Upstream default-home setup cannot preserve different child memory modes; configure named profiles separately')
        plans.sort(key=lambda plan: plan['name'] == 'default')
        executable = shutil.which('omh')
        if not executable:
            if args.dry_run:
                print(shlex.join(['uv', 'tool', 'install', package]))
                executable = 'omh'
            else:
                uv = shutil.which('uv')
                if not uv:
                    raise SetupError('OMH is missing; install uv or provide omh on PATH')
                run([uv, 'tool', 'install', package])
                executable = shutil.which('omh')
                if not executable:
                    executable = str(Path(run([uv, 'tool', 'dir', '--bin'])) / 'omh')
                    if not os.access(executable, os.X_OK):
                        raise SetupError('uv installed OMH but its executable could not be found')
        for plan in plans:
            prefix = [executable, '--hermes-home', str(plan['home']), '--omh-home', str(plan['store'])]
            setup = [*prefix, 'setup', '--full' if defaults['full'] else '--core', '--no-interactive',
                     '--yes' if defaults['tui'] else '--no-omh-tui',
                     '--with-menubar' if defaults['menubar'] else '--no-menubar',
                     '--memory-mode', plan['mode'], '--json']
            binding = ['hermes', '-p', plan['name'], 'config', 'set',
                       'plugins.entries.omh.settings.omh_home', str(plan['store'])]
            if args.dry_run:
                print(shlex.join(setup))
                print(shlex.join(['env', f'HERMES_HOME={root}', *binding]))
            else:
                prepare_plugin_comments(plan['home'] / 'config.yaml')
                run(setup, json_output=True)
                run(binding, env=dict(os.environ, HERMES_HOME=str(root)))
                print(f'OMH setup: {plan["name"]}')
        # Doctor runs after root synchronization, checking the final state.
        for plan in plans:
            doctor = [executable, '--hermes-home', str(plan['home']), '--omh-home', str(plan['store']), 'doctor', '--json']
            if args.dry_run:
                print(shlex.join(doctor))
            else:
                run(doctor, json_output=True)
                print(f'OMH doctor: {plan["name"]} passed')
        return 0
    except (SetupError, OSError, ValueError, TypeError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
