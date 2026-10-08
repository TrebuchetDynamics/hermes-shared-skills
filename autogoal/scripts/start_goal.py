#!/usr/bin/env python3
"""Hand one selected autogoal contract to Hermes' native goal-mode worker."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import sqlite3
from urllib.parse import quote
from pathlib import Path
import subprocess

BUDGET = 50
ACTIVE = {'ready', 'running', 'todo', 'review', 'changes_requested'}
# Parked cards (triage after a terminal run, scheduled backoff) block only their own slice:
# a same-title handoff is refused, disjoint work proceeds. See SKILL.md 'Operating priorities'.
PARKED = {'triage', 'scheduled', 'blocked'}
MAX_RETRIES = 3


CONTRACT_FIELDS = ('Objective', 'Scope', 'Verification', 'Source', 'Project payoff',
                   'Current evidence', 'Expected change', 'Acceptance', 'Stop conditions',
                   'Repo-docs pass')


def validate_contract(text):
    """Validate structure, not truth, priority, permissions or executable proof."""
    fields = {}
    current = None
    for line in text.splitlines():
        header = re.match(r'^\s*([A-Za-z][A-Za-z -]*):[ \t]*(.*)$', line)
        if header and header.group(1) in CONTRACT_FIELDS:
            current = header.group(1)
            if current in fields:
                raise ValueError(f'Duplicate contract field: {current}')
            fields[current] = header.group(2).strip()
        elif current is not None:
            fields[current] += '\n' + line
    for field in CONTRACT_FIELDS:
        if not fields.get(field, '').strip():
            raise ValueError(f'Missing or empty contract field: {field}')
    return {key: value.strip() for key, value in fields.items()}


def require_fresh_sources(snapshot_file, workspace):
    if snapshot_file is None:
        raise ValueError('Source snapshot required for a new handoff; capture evidence before selection')
    spec=importlib.util.spec_from_file_location('autogoal_freshness',Path(__file__).with_name('source_freshness.py'))
    freshness=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(freshness)
    result=freshness.check(json.loads(Path(snapshot_file).read_text()),workspace)
    if not result['fresh']:
        raise ValueError('Source changed since selection; re-evaluate unresolved work before dispatch: '+', '.join(result['changed']))
    return result


REVIEW_DOD = ('Definition of done for this card (goal judge): the contract below is implemented, its '
              'checks have run with evidence recorded, and the card is handed to native review. Review '
              'approval happens after that handoff and is NOT part of this goal: a pending review never makes '
              'this goal unfinished or unachievable.')


def build_task_body(contract):
    return (REVIEW_DOD + '\n\n' + contract + '\n\nExecution: This is the selected autogoal slice, not a picker. '
            'Implement and verify this contract only. Do not discover or enqueue another task. '
            'Read repository instructions and preserve dirty-file ownership. Hermes Agent/Desktop/Conduit '
            'and other upstream/vendor references are unmodified; changes stay inside the boundaries this profile\'s SOUL authorizes. '
            'Commit only with the autogoal agent_commit.sh helper to agent/<profile>/<card-id> (the daily merge train '
            'lands done cards); no other commit, and no push, merge, deploy, '
            'publish, spend, trade, third-party contact, profile configuration change, or schedule change. '
            'Test seams are in scope: when code is hard to test (clock, filesystem, network client, provider), add '
            'the smallest injectable seam yourself, also in a pre-existing dirty file (additive only, listed in the '
            'handoff), instead of asking. If the card text is factually wrong (stale IDs, counts or paths), record the '
            'correction as a card comment, deliver against the corrected scope and state it in the handoff; reviewers '
            'judge against that recorded correction. Never block on card wording. '
            'Run long commands (e2e, Playwright, full suites, builds) under `timeout` (for example `timeout 40m`) '
            'so a hang fails fast and is reported instead of crashing the worker. '
            'Keep scratch under the repo\'s ignored folders or ~/.hermes/cache/scratch/<card-id>/ (never new ~/.cache folders) and delete build outputs you created before finishing. '
            'Keep the profile-local autogoal journal updated with evidence and open questions. When the '
            'contract names a goals.json task, finish with the repo-docs helper (never hand-edit the JSON): '
            '`python ~/.hermes/shared-skills/repo-docs/scripts/goals.py task <repo> <TASK> done`, then '
            '`goals.py evidence <repo> <GOAL> --kind executed --ref "<exact command>" --result pass|fail` '
            'for each check you actually ran (a goal is met only with an executed pass), then '
            '`goals.py render <repo>`. In repos without goals.json, tick the TODO.md task and update its '
            'Goal coverage row with an anchored patch. Use native '
            'kanban lifecycle tools to complete or request review. Ask, don\'t block: never block this '
            'card or pause the goal because owner input is needed. Apply the recommended default for '
            'reversible choices (design/visual direction, approach, review-artifact approval), hold only '
            'irreversible red-line steps, record each owner question in BLOCKERS.md with a default, and '
            'list them under "Questions (no reply = defaults apply)" in the handoff. The goal engine has a '
            '50-turn budget; finish early only when genuinely complete. '
            'Review handoff is not final completion: when same-card review is required, '
            'supply implementation/test evidence, then request '
            'native review; pending native review is not a missing implementation criterion. '
            'Only the authorized review lane can approve closure. If the lifecycle judge rejects '
            'entry solely because that review is pending, preserve the original card, record the '
            'exact rejection and remaining review gate, and return source-bound receipts to the fleet '
            'governor for supported same-card administrative review-entry assessment. Ask the operator '
            'only if no supported governor authority resolves this gate; never invent approval or '
            'bypass a rejected transition without supported authority, force a live claim or waive mandatory review. '
            'Do not retry indefinitely, replace the card or rerun unchanged tests to cure a lifecycle rejection. '
            'Before calling kanban_complete, include Acceptance evidence: map every acceptance criterion '
            'to the actual changed artifact, exact command/result or inspected contract, and source revision '
            'or scoped fingerprint. State the expected change actually delivered, not only tests passed. '
            'Carry forward predecessor receipts only when relevant source is unchanged. Mark missing '
            'coverage NOT_CHECKED; a passing unrelated suite, judge verdict or queue receipt is not proof. '
            'Trace changed imports to their runtime delivery boundary: for a source-run CLI or '
            'manually copied runtime artifact, inspect transitive local modules and relevant '
            'packaging manifests; checkout tests do not prove packaged execution. Use the '
            'smallest isolated dependency-closure check when warranted. Keep image build/run/deployment NOT_CHECKED '
            'unless separately authorized and actually executed. If explicit scope excludes packaging edits, '
            'record the dependency gap and scope gate rather than changing excluded manifests. '
            'Perform the cheapest focused check first; use canonical verification when required by the '
            'repository or host. If a host verification gate repeats, inspect evidence freshness and '
            'command recognition, then run only the missing authorized check; never alter or bypass '
            'the ledger, disable the gate, or rerun unrelated suites to manufacture progress.')


def run(prefix, *args):
    return subprocess.check_output(prefix + list(args), text=True, timeout=30).strip()


def profile_home(prefix):
    text = run(prefix, 'profile', 'show', prefix[-1])
    for line in text.splitlines():
        if line.startswith('Path:'):
            return Path(line.partition(':')[2].strip()).resolve(strict=True)
    raise RuntimeError('Profile CLI did not return its canonical home')


def goal_fields(prefix, task_id):
    # Current CLI JSON omits these two fields. Read only the exact card row
    # in the CLI-resolved default board, never a guessed profile database.
    boards = json.loads(run(prefix, 'kanban', 'boards', 'list', '--json'))
    db_path = next(b['db_path'] for b in boards if b['slug'] == 'default')
    uri = 'file:' + quote(str(Path(db_path).resolve())) + '?mode=ro'
    with sqlite3.connect(uri, uri=True) as db:
        row = db.execute('SELECT goal_mode, goal_max_turns FROM tasks WHERE id=?', (task_id,)).fetchone()
    if row is None:
        raise RuntimeError('Created card missing from canonical board')
    return {'goal_mode': bool(row[0]), 'goal_max_turns': row[1]}


def validate_disjoint_triage(task, runs, claim, profile, title, workspace):
    """Governor-attested disjointness is not inferred from card status/title."""
    if (task.get('status') != 'triage' or task.get('assignee') != profile
            or task.get('title') == title or task.get('workspace_kind') != 'dir'
            or Path(task.get('workspace_path', '')).resolve() != Path(workspace).resolve()):
        raise ValueError('Disjoint exception requires a distinct same-profile/workspace triage card')
    if claim.get('current_run_id') is not None or claim.get('worker_pid') is not None:
        raise ValueError('Disjoint triage card has an active claim')
    if not runs or runs[-1].get('status') not in {'blocked', 'crashed'} or not runs[-1].get('ended_at'):
        raise ValueError('Disjoint triage card needs an observed terminal blocked/crashed run')
    return task['id']


def existing_task(tasks, profile, title, workspace=None, disjoint_triage=()):
    for task in tasks:
        if task.get('id') in disjoint_triage and task.get('status') == 'triage' and task.get('title') != title:
            continue
        if task.get('status') not in ACTIVE:
            continue
        same_workspace = (workspace is not None and task.get('workspace_kind') == 'dir'
                          and task.get('workspace_path')
                          and Path(task['workspace_path']).resolve() == Path(workspace).resolve())
        if task.get('assignee') == profile or same_workspace:
            return task
    for task in tasks:
        if (task.get('assignee') == profile and task.get('status') in PARKED
                and task.get('title') == title):
            return task  # Wording changes must not bypass an unresolved blocker.
    return None


def ensure_notification(prefix, task_id, home, profile):
    """Subscribe this profile's configured home chat, never wake another agent."""
    channel = None
    env_file = home / '.env'
    if env_file.is_file():
        for line in env_file.read_text().splitlines():
            key, sep, value = line.partition('=')
            if sep and key.strip() == 'TELEGRAM_HOME_CHANNEL':
                channel = value.strip().strip('\"').strip("'")
    if not channel:
        return None  # No configured Telegram home: preserve local-only profiles.
    if not channel.lstrip('-').isdigit():
        raise ValueError('Invalid configured Telegram home channel')
    board = ['kanban', '--board', 'default']
    run(prefix, *board, 'notify-subscribe', task_id, '--platform', 'telegram',
        '--chat-id', channel, '--notifier-profile', profile, '--delivery-mode', 'notify')
    subscriptions = json.loads(run(prefix, *board, 'notify-list', task_id, '--json'))
    for sub in subscriptions:
        if (sub['task_id'] == task_id and sub['platform'] == 'telegram'
                and str(sub['chat_id']) == channel and sub['notifier_profile'] == profile
                and sub['delivery_mode'] == 'notify'):
            return {k: sub[k] for k in ('platform', 'chat_id', 'notifier_profile', 'delivery_mode')}
    raise RuntimeError('Goal card exists but notification subscription was not verified; reconcile this card, do not create another')


def save_receipt(journal_dir, receipt):
    journal_dir.mkdir(parents=True, exist_ok=True)
    target = journal_dir / 'goal-handoff.json'
    if target.exists():
        previous = json.loads(target.read_text())
        if previous.get('task_id') != receipt['task_id']:
            history = journal_dir / 'handoffs'
            history.mkdir(exist_ok=True)
            task_id = previous['task_id']
            if Path(task_id).name != task_id:
                raise ValueError('Invalid prior task ID')
            (history / (task_id + '.json')).write_text(json.dumps(previous, indent=2) + '\n')
    temporary = target.with_suffix('.json.pending')
    temporary.write_text(json.dumps(receipt, indent=2) + '\n')
    temporary.replace(target)


def record_handoff(prefix, journal_dir, home, profile, receipt):
    # Persist the exact created card before any fallible transport operation.
    save_receipt(journal_dir, receipt)
    try:
        receipt['notification'] = ensure_notification(prefix, receipt['task_id'], home, profile)
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as error:
        receipt['outcome'] = 'notification_blocked'
        receipt['notification_error'] = str(error)
    save_receipt(journal_dir, receipt)
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile', required=True)
    p.add_argument('--workspace', required=True)
    p.add_argument('--title', required=True)
    p.add_argument('--contract-file', required=True)
    p.add_argument('--source-snapshot', help='Scoped evidence snapshot captured before candidate selection')
    p.add_argument('--disjoint-terminal-triage', action='append', default=[], metavar='CARD_ID',
                   help='Governor-only attestation of resource-disjoint work; verify terminal claim under lock, preserve original card')
    p.add_argument('--validate-only', action='store_true',
                   help='Check contract structure without CLI calls, journal writes or dispatch')
    args = p.parse_args()
    if os.environ.get('HERMES_KANBAN_TASK'):
        raise SystemExit('Already a goal worker: execute the assigned card, never launch a nested goal.')
    contract = Path(args.contract_file).read_text().strip()
    try:
        validate_contract(contract)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    if args.validate_only:
        print(json.dumps({'outcome': 'contract_validated', 'fields': list(CONTRACT_FIELDS),
                          'factual_validation': False}))
        return
    prefix = ['hermes', '-p', args.profile]
    workspace = Path(args.workspace).expanduser().resolve(strict=True)
    configured = Path(run(prefix, 'config', 'get', 'terminal.cwd')).expanduser().resolve(strict=True)
    if workspace != configured:
        raise SystemExit(f'Workspace differs from profile cwd: {workspace} != {configured}')
    # Resolve the target, not the launch profile or a guessed ~/.hermes path.
    home = profile_home(prefix)
    journal_dir = home / 'autogoal'
    journal_dir.mkdir(parents=True, exist_ok=True)
    with (journal_dir / 'goal-handoff.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        board = ['kanban', '--board', 'default']
        tasks = json.loads(run(prefix, *board, 'list', '--json'))
        disjoint_triage = set()
        for task_id in args.disjoint_terminal_triage:
            detail = json.loads(run(prefix, *board, 'show', task_id, '--json'))
            boards = json.loads(run(prefix, 'kanban', 'boards', 'list', '--json'))
            db_path = next(b['db_path'] for b in boards if b['slug'] == 'default')
            with sqlite3.connect('file:' + quote(str(Path(db_path).resolve())) + '?mode=ro', uri=True) as db:
                row = db.execute('SELECT status,current_run_id,worker_pid FROM tasks WHERE id=?', (task_id,)).fetchone()
            if row is None or row[0] != 'triage':
                raise SystemExit('Disjoint triage state changed before handoff')
            claim = {'current_run_id': row[1], 'worker_pid': row[2]}
            disjoint_triage.add(validate_disjoint_triage(detail['task'], detail.get('runs', []), claim,
                                                       args.profile, args.title, workspace))
        task = existing_task(tasks, args.profile, args.title, workspace, disjoint_triage)
        if task is not None and task.get('assignee') != args.profile:
            print(json.dumps({'outcome': 'workspace_owned', 'task_id': task['id'],
                              'assignee': task.get('assignee'), 'status': task['status']}))
            return  # Do not attach this profile's notifier to another owner's card.
        if task is not None:
            notification = ensure_notification(prefix, task['id'], home, args.profile)
            print(json.dumps({'outcome': 'already_owned', 'task_id': task['id'], 'status': task['status'], 'notification': notification, **goal_fields(prefix, task['id'])}))
            return
        # Final check after live ownership reconciliation, immediately before create.
        try:
            require_fresh_sources(args.source_snapshot, workspace)
        except (ValueError, OSError, TypeError, KeyError) as error:
            raise SystemExit(str(error)) from error
        digest = hashlib.sha256((args.profile + '\n' + str(workspace) + '\n' + args.title + '\n' + contract).encode()).hexdigest()
        body = build_task_body(contract)
        created = json.loads(run(prefix, *board, 'create', args.title, '--body', body,
                                 '--assignee', args.profile, '--workspace', 'dir:' + str(workspace),
                                 '--goal', '--goal-max-turns', str(BUDGET), '--max-retries', str(MAX_RETRIES),
                                 '--completion-contract', 'local-only', '--created-by', 'autogoal',
                                 '--idempotency-key', 'autogoal:' + digest, '--json'))
        task_id = created['id']
        saved = json.loads(run(prefix, *board, 'show', task_id, '--json'))
        task = saved.get('task', saved)
        task.update(goal_fields(prefix, task_id))
        assert task['goal_mode'] and task['goal_max_turns'] == BUDGET, task
        assert task['assignee'] == args.profile, task
        assert task['workspace_kind'] == 'dir' and Path(task['workspace_path']).resolve() == workspace, task
        assert task['completion_contract'] == 'local-only', task
        receipt = {'outcome': 'handed_off', 'task_id': task_id, 'profile': args.profile,
                   'workspace': str(workspace), 'goal_mode': True, 'goal_max_turns': BUDGET,
                   'status': task['status']}
        receipt = record_handoff(prefix, journal_dir, home, args.profile, receipt)
        # Notification setup and dispatch may have advanced the card. Preserve
        # the durable receipt even if this final read fails.
        try:
            latest = json.loads(run(prefix, *board, 'show', task_id, '--json'))
            receipt['status'] = latest.get('task', latest)['status']
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            receipt['observation_error'] = str(error)
        save_receipt(journal_dir, receipt)
        print(json.dumps(receipt))


if __name__ == '__main__':
    main()
