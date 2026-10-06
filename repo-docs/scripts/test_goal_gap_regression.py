"""Run the real bare /repo-docs twice on a fresh fixture: docs must be built, every
unmet goal must get a TODO.md task keyed to it, and the second pass must be byte-exact.

Rebuild the fixture first (see references/bootstrap-idempotency-regression.md); this
script refuses to run on a fixture that already contains generated docs.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

fixture = Path(sys.argv[1] if len(sys.argv) > 1 else
               os.path.join((os.environ.get('HERMES_HOME') or os.path.expanduser('~/.hermes')), 'cache/scratch/repo-docs-goalgap-regression'))
receipt = Path((os.environ.get('HERMES_HOME') or os.path.expanduser('~/.hermes'))) / 'install-receipts/repo-docs' / str(int(time.time()))
receipt.mkdir(parents=True)

protected = ['pubspec.yaml', 'lib/main.dart', 'test/counter_test.dart']
baseline = ['README.md', 'PRD.md', 'spec.md', 'test-plan.md', 'runbook.md', 'CHANGELOG.md']


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file() and '.git' not in p.parts}


initial = hashes(fixture)
if set(initial) != set(protected) | {'README.md'}:
    sys.exit(f'fixture is not fresh: {sorted(initial)}')

env = os.environ.copy()
env['HERMES_EPHEMERAL_SYSTEM_PROMPT'] = (
    f'This is an isolated repo-docs behavioral regression. Only documentation writes inside {fixture} '
    'are authorized. Do not change source, tests, manifest or agent-instruction files. Do not install '
    'tools, run Flutter, access network, modify profiles/configuration/schedules or tasks, dispatch '
    'goals, commit, push or touch production. Follow the actual bare repo-docs Bootstrap/Maintain '
    'policy, preserving byte-exact no-op on a second pass. The README states the accepted intent; no '
    'user action is required. The fixture has no platform runners; do not imply product tests ran.')
command = ['hermes', 'chat', '--in', str(fixture), '--oneshot', '-Q',
           '--max-turns', '40', '--run-budget', '420', '-q', '/repo-docs']
results = []
for number in (1, 2):
    proc = subprocess.run(command, env=env, capture_output=True, text=True, timeout=480)
    (receipt / f'pass-{number}.stdout.txt').write_text(proc.stdout)
    (receipt / f'pass-{number}.stderr.txt').write_text(proc.stderr)
    snap = hashes(fixture)
    (receipt / f'pass-{number}.hashes.json').write_text(json.dumps(snap, indent=2))
    results.append({'pass': number, 'exit_code': proc.returncode, 'hashes': snap})
    print('PASS', number, 'EXIT', proc.returncode, 'FILES', sorted(snap), flush=True)
    if proc.returncode:
        break

last = results[-1]['hashes']
todo = (fixture / 'TODO.md').read_text() if (fixture / 'TODO.md').exists() else ''
goal4_task = re.search(r'-\s*\[ \][^\n]*\n(?:[ \t]+[^\n]*\n|\n)*?[^\n]*GOAL-4', todo) or \
    re.search(r'-\s*\[ \][^\n]*GOAL-4', todo)
goals = json.loads((fixture / 'goals.json').read_text()).get('goals', []) if (fixture / 'goals.json').exists() else []
checks = {
    'two_commands_exit_zero': len(results) == 2 and all(r['exit_code'] == 0 for r in results),
    'protected_inputs_unchanged': all(initial[p] == last.get(p) for p in protected),
    'baseline_docs_built': all(p in last for p in baseline),
    'stale_readme_test_path_fixed': 'test/obsolete_counter_test.dart' not in (fixture / 'README.md').read_text(),
    'todo_has_goal_coverage': 'goal coverage' in todo.lower(),
    'goal4_has_open_task': bool(goal4_task),
    'goal4_task_in_now_or_next': bool(re.search(r'^## (Now|Next)\b(?:(?!^## ).)*GOAL-4', todo, re.M | re.S)),
    'goals_json_valid': subprocess.run([sys.executable, str(Path(__file__).with_name('goals.py')), 'validate', str(fixture)],
                                       capture_output=True, text=True).stdout.strip() == 'ok',
    'goal1_3_unverified_not_met': all(g['status'] == 'unverified' for g in goals if g['id'] in ('GOAL-1', 'GOAL-2', 'GOAL-3')) and len(goals) >= 4,
    'goal4_unmet_in_json': any(g['id'] == 'GOAL-4' and g['status'] == 'unmet' for g in goals),
    'todo_coverage_rendered': '<!-- goals:coverage:begin -->' in todo,
    'no_adr_or_openapi_invented': not any(p.startswith('adr/') or 'openapi' in p.lower() for p in last),
    'second_pass_byte_exact': len(results) == 2 and results[0]['hashes'] == results[1]['hashes'],
}
print(json.dumps(checks, indent=2))
(receipt / 'verification.json').write_text(json.dumps(
    {'command': command, 'checks': checks, 'initial_hashes': initial, 'results': results,
     'product_tests_run': False}, indent=2))
print('receipt', receipt)
sys.exit(0 if all(checks.values()) else 1)
