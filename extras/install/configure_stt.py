#!/usr/bin/env python3
"""Preview STT settings for an existing Hermes home; apply only when requested."""
import argparse
import json
import os
import subprocess
from pathlib import Path


def configure(home, provider, model, apply=False, runner=None):
    if provider not in ('local', 'off') or model not in ('tiny', 'base', 'small', 'medium', 'large-v3'):
        raise ValueError('Unsupported STT provider or local model')
    home = Path(home).expanduser().resolve()
    if not (home / 'config.yaml').is_file():
        raise ValueError(f'Existing config.yaml required in {home}')
    settings: dict[str, bool | str] = {}
    if provider == 'local':
        settings.update({'stt.provider': 'local', 'stt.local.model': model})
    # Never enable a previously disabled cloud provider before selecting local.
    settings['stt.enabled'] = provider != 'off'
    print(f'Target HERMES_HOME={home}')
    for key, value in settings.items():
        print(f'{key} = {value}')
    if not apply:
        print('Preview only; use --apply to change this target.')
        return 0
    env = dict(os.environ, HERMES_HOME=str(home))
    env.pop('HERMES_PROFILE', None)
    run = runner or subprocess.run
    for key, value in settings.items():
        encoded = value if isinstance(value, str) else json.dumps(value)
        run(['hermes', 'config', 'set', key, encoded],
            env=env, check=True, capture_output=True, text=True, timeout=30)
        result = run(['hermes', 'config', 'get', key, '--json'],
                     env=env, check=True, capture_output=True, text=True, timeout=30)
        if json.loads(result.stdout) != value:
            raise ValueError(f'Readback mismatch for {key}')
    print('STT settings verified. Recognition and dependencies have not been tested.')
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', required=True, type=Path)
    parser.add_argument('--provider', required=True, choices=['local', 'off'])
    parser.add_argument('--model', default='base', choices=['tiny', 'base', 'small', 'medium', 'large-v3'])
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    try:
        return configure(args.home, args.provider, args.model, args.apply)
    except ValueError as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
