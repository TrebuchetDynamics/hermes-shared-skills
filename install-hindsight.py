#!/usr/bin/env python3
"""Configure isolated Hindsight banks and embedded stores for existing profiles.

Connection settings come from each profile's existing config, or --config for
new profiles. Credentials stay in each profile's .env or secret provider.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit


CONNECTION_KEYS = {'mode', 'api_url', 'llm_provider', 'llm_model', 'llm_base_url'}
MODES = {'cloud', 'local_embedded', 'local_external'}
NAME = re.compile(r'[a-z0-9][a-z0-9_-]{0,63}\Z')
MARKERS = ('config.yaml', '.env', 'SOUL.md', 'profile.yaml', 'auth.json', 'state.db')


def read_object(path):
    if path.is_symlink():
        raise ValueError(f'Refusing symlinked configuration: {path}')
    data = json.loads(path.read_text()) if path.exists() else {}
    if not isinstance(data, dict):
        raise ValueError(f'Expected a JSON object: {path}')
    return data


def profile_home(root, name):
    if not NAME.fullmatch(name):
        raise ValueError(f'Invalid profile name: {name!r}')
    home = root if name == 'default' else root / 'profiles' / name
    if (home.is_symlink() or (name != 'default' and (root / 'profiles').is_symlink())
            or not home.is_dir() or not any((home / m).is_file() for m in MARKERS)
            or (name != 'default' and (root / 'profiles/.deleted' / name).exists())):
        raise ValueError(f'Not an existing live profile: {name}')
    if (home / 'hindsight').is_symlink():
        raise ValueError(f'Refusing shared Hindsight directory: {home / "hindsight"}')
    return home


def validate_connection(config, name):
    mode = config.get('mode')
    if mode not in MODES:
        raise ValueError(f'{name}: choose a Hindsight backend with --config connection.json '
                         '(mode: cloud, local_embedded, or local_external)')
    if mode == 'local_embedded':
        if not config.get('llm_provider') or not config.get('llm_model'):
            raise ValueError(f'{name}: local_embedded requires llm_provider and llm_model in --config')
    if mode == 'local_external' and not config.get('api_url'):
        raise ValueError(f'{name}: local_external requires api_url in --config')
    for key in ('api_url', 'llm_base_url'):
        if config.get(key):
            parsed = urlsplit(config[key])
            if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError(f'{name}: {key} must be an HTTP(S) URL without embedded credentials')


def reject_legacy_routing(home, name):
    """Do not shadow an existing bank resolved outside profile-local JSON."""
    legacy = (Path.home() / '.hindsight/config.json').exists()
    env_path = home / '.env'
    if env_path.exists():
        legacy = legacy or bool(re.search(
            r'(?m)^\s*(?:export\s+)?HINDSIGHT_(?:BANK_ID|MODE|API_URL)\s*=', env_path.read_text()))
    legacy = legacy or any(os.environ.get(key) for key in ('HINDSIGHT_BANK_ID', 'HINDSIGHT_MODE', 'HINDSIGHT_API_URL'))
    config_path = home / 'config.yaml'
    if config_path.exists():
        # Native Hermes writes a canonical nested mapping. Unknown inline memory
        # mappings need explicit localization rather than guessing their provider.
        section = re.search(r'(?ms)^memory:([^\n]*)(.*?)(?=^\S|\Z)', config_path.read_text())
        if section:
            inline = section[1].strip()
            legacy = legacy or bool(inline and not inline.startswith('#')) or bool(re.search(
                r'''(?m)^\s+provider:\s*['"]?hindsight(?:['"]?\s*(?:#.*)?)?$''', section[2]))
    if legacy:
        raise ValueError(f'{name}: existing legacy/environment Hindsight routing requires explicit '
                         'migration to this profile\'s hindsight/config.json before setup')


def build_plans(root, names, connection):
    defaults = read_object(Path(__file__).resolve().parent / 'plugins/defaults.json')['hindsight']
    plans = []
    for name in dict.fromkeys(names):
        home = profile_home(root, name)
        path = home / 'hindsight/config.json'
        existing = read_object(path)
        if not existing:
            reject_legacy_routing(home, name)
        # Existing profiles keep their connection settings; a supplied template
        # configures new profiles, never redirects an existing memory backend.
        config = {**defaults, **(connection if not existing else {}), **existing}
        validate_connection(config, name)
        if config.get('bank_id_template'):
            raise ValueError(f'{name}: bank_id_template must be empty for profile-only memory isolation')
        if config.get('recall_additional_banks') or config.get('recallAdditionalBanks'):
            raise ValueError(f'{name}: cross-bank recall conflicts with profile-only memory isolation')
        identity = f'hermes-{name}-{hashlib.sha256(str(home).encode()).hexdigest()[:12]}'
        legacy_bank = (config.get('banks') or {}).get('hermes', {}).get('bankId')
        config['bank_id'] = config.get('bank_id') or legacy_bank or ('hermes' if existing else identity)
        config['bank_id_template'] = ''
        config['profile'] = config.get('profile') or ('hermes' if existing else identity)
        for key in ('bank_id', 'profile'):
            if not isinstance(config[key], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', config[key]):
                raise ValueError(f'{name}: invalid Hindsight {key}')
        plans.append({'name': name, 'home': home, 'path': path, 'config': config})

    # Include unselected profiles: a subset setup must not reuse a sibling's bank.
    configurations = {p['name']: p['config'] for p in plans}
    others = ['default', *(p.name for p in (root / 'profiles').glob('*') if NAME.fullmatch(p.name))]
    for name in others:
        if name in configurations:
            continue
        candidate = root if name == 'default' else root / 'profiles' / name
        if (not candidate.is_dir() or not any((candidate / m).is_file() for m in MARKERS)
                or (name != 'default' and (root / 'profiles/.deleted' / name).exists())):
            continue
        home = profile_home(root, name)
        existing = read_object(home / 'hindsight/config.json')
        if existing:
            configurations[name] = existing
        else:
            reject_legacy_routing(home, name)
    banks, daemons = {}, {}
    for name, config in configurations.items():
        if config.get('bank_id_template') or config.get('recall_additional_banks') or config.get('recallAdditionalBanks'):
            raise ValueError(f'{name}: dynamic banks or cross-bank recall conflicts with profile-only memory isolation')
        bank = config.get('bank_id') or (config.get('banks') or {}).get('hermes', {}).get('bankId') or 'hermes'
        # Conservative: names stay unique even on different servers, protecting
        # against a future endpoint change that would merge memory partitions.
        if bank in banks:
            raise ValueError(f'{name} and {banks[bank]} share Hindsight bank {bank!r}; '
                             'preserve/migrate existing data before assigning separate banks')
        banks[bank] = name
        if config.get('mode') in ('local', 'local_embedded'):
            daemon = config.get('profile') or 'hermes'
            if daemon in daemons:
                raise ValueError(f'{name} and {daemons[daemon]} share embedded profile {daemon!r}')
            daemons[daemon] = name
    return plans


def write_config(path, config):
    if path.exists() and read_object(path) == config:
        path.chmod(0o600)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.config-', suffix='.json', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(config, stream, indent=2)
            stream.write('\n')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hermes-home', required=True, type=Path)
    parser.add_argument('--profile', action='append', required=True)
    parser.add_argument('--config', type=Path, help='Connection-only JSON template for new profiles; no credentials')
    parser.add_argument('--prepare', action='store_true', help='Write isolated config before plugin installation; do not select provider')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    try:
        root = args.hermes_home.expanduser().absolute()
        if root.is_symlink() or not root.is_dir():
            raise ValueError('Hermes root must be an existing non-symlink directory')
        root = root.resolve()
        connection = read_object(args.config.expanduser()) if args.config else {}
        if set(connection) - CONNECTION_KEYS:
            raise ValueError('--config accepts connection settings only; put credentials in each profile .env')
        plans = build_plans(root, args.profile, connection)
        # Validate every target before changing any profile.
        if not args.prepare and not args.dry_run:
            for plan in plans:
                if not (plan['home'] / 'plugins/hindsight/plugin.yaml').is_file():
                    raise ValueError(f'{plan["name"]}: install the Hindsight plugin before activation')
        for plan in plans:
            cfg = plan['config']
            print(f'{"Plan" if args.dry_run else "Hindsight"}: {plan["name"]} '
                  f'mode={cfg["mode"]} bank={cfg["bank_id"]} embedded-profile={cfg["profile"]}', flush=True)
            if args.dry_run:
                continue
            write_config(plan['path'], cfg)
            if not args.prepare:
                for key, value in (('memory.provider', 'hindsight'), ('memory.memory_enabled', 'false'),
                                   ('memory.user_profile_enabled', 'false')):
                    result = subprocess.run(['hermes', '-p', plan['name'], 'config', 'set', key, value],
                        env=dict(os.environ, HERMES_HOME=str(root)), text=True, capture_output=True)
                    if result.returncode:
                        raise ValueError(f'{plan["name"]}: failed to set {key}; configuration saved for retry')
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f'Hindsight setup failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
