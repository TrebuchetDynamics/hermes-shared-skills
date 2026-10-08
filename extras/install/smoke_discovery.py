#!/usr/bin/env python3
"""Opt-in installed-Hermes discovery smoke in a temporary home; no model calls."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--agent-dir', required=True, type=Path,
                        help='Installed Hermes source containing tools/skills_tool.py')
    args = parser.parse_args()
    agent = args.agent_dir.resolve(strict=True)
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix='discovery-') as tmp:
        home = Path(tmp)
        (home / 'config.yaml').write_text('model: untouched\n')
        env = dict(os.environ, HERMES_HOME=str(home), HOME=str(home),
                   HF_HUB_OFFLINE='1', PYTHONDONTWRITEBYTECODE='1')
        env.pop('HERMES_PROFILE', None)
        def run(command):
            return subprocess.run(command, env=env, cwd=home, capture_output=True,
                                  text=True, check=True, timeout=60).stdout
        run(['hermes', 'config', 'set', 'skills.external_dirs', json.dumps([str(repo)])])
        listing = run(['hermes', 'skills', 'list', '--enabled-only'])
        for name in ('repo-docs', 'grill-me', 'git-pull-merge'):
            assert name in listing, name
        # Import the installed resolver in a fresh process without launch bootstrap:
        # activate existing dependencies only; bootstrap may provision tools.
        code = '''import sys, json
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from pm.environments import activate_dependencies
activate_dependencies(Path(sys.argv[1]))
from tools.skills_tool import skill_view
repo = Path(sys.argv[2])
for name in ('repo-docs', 'grill-me', 'git-pull-merge'):
    result = json.loads(skill_view(name, preprocess=False))
    assert result['success'], result.get('error')
    assert Path(result['skill_dir']).resolve() == repo / name, (name, result['skill_dir'])
print('PASS: fresh installed resolver loads exact canonical skill sources')
'''
        print(run([sys.executable, '-I', '-c', code, str(agent), str(repo)]).strip())
        assert json.loads(run(['hermes', 'config', 'get', 'model', '--json'])) == 'untouched'
    print('PASS: real CLI listing, resolver content load, unrelated setting and cleanup')


if __name__ == '__main__':
    main()
