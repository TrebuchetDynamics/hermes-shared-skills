#!/usr/bin/env python3
"""Opt-in real Hermes CLI smoke test. No inference or dependency installs."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    with tempfile.TemporaryDirectory(prefix='stt-smoke-') as tmp:
        home = Path(tmp)
        cfg = home / 'config.yaml'
        cfg.write_text('model: untouched\nsecurity:\n  redact_secrets: true\n')
        script = Path(__file__).with_name('configure_stt.py')
        env = dict(os.environ, HERMES_HOME=str(home))
        env.pop('HERMES_PROFILE', None)
        def run(args):
            return subprocess.run(args, env=env, check=True, capture_output=True,
                                  text=True, timeout=120).stdout
        base = [sys.executable, str(script), '--home', str(home)]
        before = cfg.read_bytes()
        run(base + ['--provider', 'local'])
        assert cfg.read_bytes() == before, 'preview changed config'
        for _ in range(2):
            run(base + ['--provider', 'local', '--model', 'tiny', '--apply'])
        for key, expected in [('stt.enabled', True), ('stt.provider', 'local'),
                              ('stt.local.model', 'tiny'), ('model', 'untouched'),
                              ('security.redact_secrets', True)]:
            actual = json.loads(run(['hermes', 'config', 'get', key, '--json']))
            assert actual == expected, (key, actual, expected)
        run(base + ['--provider', 'off', '--apply'])
        assert json.loads(run(['hermes', 'config', 'get', 'stt.enabled', '--json'])) is False
        print('PASS: real CLI preview, repeated apply, readback, unrelated settings, disable')
    print('PASS: isolated temporary home removed; no live profiles used')


if __name__ == '__main__':
    main()
