"""Exercise actual bare repo-docs twice on the isolated blocker fixture."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

fixture = Path((os.environ.get('HERMES_HOME') or os.path.expanduser('~/.hermes'))) / 'cache/scratch/blockers-repo-docs-regression'
receipt = Path((os.environ.get('HERMES_HOME') or os.path.expanduser('~/.hermes'))) / 'install-receipts/hard-blockers' / str(int(time.time()))
receipt.mkdir(parents=True)


def hashes(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob('*')) if path.is_file() and '.git' not in path.parts}


initial = hashes(fixture)
env = os.environ.copy()
env['HERMES_EPHEMERAL_SYSTEM_PROMPT'] = (
    'This is an isolated repo-docs behavioral regression. Only documentation writes '
    f'inside {fixture} are authorized. '
    'Do not change source, tests, manifest or agent-instruction files. Do not install '
    'tools, run Flutter, access network, modify profiles/configuration/schedules or '
    'tasks, dispatch goals, commit, push or touch production. Follow the actual bare '
    'repo-docs Bootstrap/Maintain policy, preserving byte-exact no-op on a second pass. '
    'Inspect fixture source/README accepted intent; no user action is required. '
    'The fixture has no platform runners; do not imply product tests were executed.')
command = ['hermes', 'chat', '--in', str(fixture), '--oneshot', '-Q',
           '--max-turns', '25', '--run-budget', '210', '-q', '/repo-docs']
results = []
for number in (1, 2):
    proc = subprocess.run(command, env=env, capture_output=True, text=True, timeout=250)
    (receipt / f'pass-{number}.stdout.txt').write_text(proc.stdout)
    (receipt / f'pass-{number}.stderr.txt').write_text(proc.stderr)
    snap = hashes(fixture)
    (receipt / f'pass-{number}.hashes.json').write_text(json.dumps(snap, indent=2))
    results.append({'pass': number, 'exit_code': proc.returncode, 'hashes': snap})
    print('PASS', number, 'EXIT', proc.returncode, 'FILES', sorted(snap), flush=True)
    if proc.returncode:
        break

protected = ['pubspec.yaml', 'lib/main.dart', 'test/counter_test.dart']
last = results[-1]['hashes']
checks = {
    'two_commands_exit_zero': len(results) == 2 and all(r['exit_code'] == 0 for r in results),
    'protected_inputs_unchanged': all(initial[p] == last.get(p) for p in protected),
    'blockers_created': 'BLOCKERS.md' in last,
    'blockers_empty': (fixture / 'BLOCKERS.md').exists() and 'BLK-' not in (fixture / 'BLOCKERS.md').read_text(),
    'second_pass_byte_exact': len(results) == 2 and results[0]['hashes'] == results[1]['hashes'],
    'stale_readme_test_path_fixed': 'test/obsolete_counter_test.dart' not in (fixture / 'README.md').read_text(),
    'no_adr_or_openapi_invented': not any(p.startswith('adr/') or 'openapi' in p.lower() for p in last),
}
shutil.copytree(fixture, receipt / 'fixture')
(receipt / 'verification.json').write_text(json.dumps({'command': command, 'checks': checks,
    'initial_hashes': initial, 'results': results, 'product_tests_run': False}, indent=2))
print('RECEIPT', str(receipt), flush=True)
print(json.dumps(checks, indent=2), flush=True)
raise SystemExit(0 if all(checks.values()) else 1)
