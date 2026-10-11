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
import shlex
import uuid
from urllib.parse import quote
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

BUDGET = 50
ACTIVE = {'ready', 'running', 'todo', 'review', 'changes_requested'}
# Parked cards (triage after a terminal run, scheduled backoff) block only their own slice:
# a same-title handoff is refused, disjoint work proceeds. See SKILL.md 'Operating priorities'.
PARKED = {'triage', 'scheduled', 'blocked'}
MAX_RETRIES = 3


CONTRACT_FIELDS = ('Objective', 'Scope', 'Verification', 'Source', 'Project payoff',
                   'Current evidence', 'Expected change', 'Acceptance', 'Stop conditions',
                   'Repo-docs pass')


def validate_contract(text, goal_max_turns=BUDGET):
    """Validate structure, not truth, priority, permissions or executable proof."""
    fields = {}
    current = None
    for line in text.splitlines():
        header = re.match(r'^\s*([A-Za-z][A-Za-z -]*):[ \t]*(.*)$', line)
        if header and header.group(1) in (*CONTRACT_FIELDS, 'Goal budget rationale'):
            current = header.group(1)
            if current in fields:
                raise ValueError(f'Duplicate contract field: {current}')
            fields[current] = header.group(2).strip()
        elif current is not None:
            fields[current] += '\n' + line
    for field in CONTRACT_FIELDS:
        if not fields.get(field, '').strip():
            raise ValueError(f'Missing or empty contract field: {field}')
    if goal_max_turns == 100 and not fields.get('Goal budget rationale', '').strip():
        raise ValueError('100 turns requires a nonempty Goal budget rationale: in the contract')
    return {key: value.strip() for key, value in fields.items()}


def require_milestone_admission(workspace, goal_task=None, snapshot_file=None, fallback_file=None):
    """Use the ledger's dependency rules; admission is not completion evidence."""
    workspace = Path(workspace).expanduser().resolve(strict=True)
    ledger = workspace / 'goals.json'
    if not ledger.exists():
        if goal_task or fallback_file:
            raise ValueError('Explicit goal identity requires goals.json')
        return {'goal_task': None, 'milestone': None, 'fallback': None, 'ledger_sha256': None}
    ledger_bytes = ledger.read_bytes()
    data = json.loads(ledger_bytes)
    ledger_digest = hashlib.sha256(ledger_bytes).hexdigest()
    focus = data.get('primary_milestone')
    if not focus and not goal_task and not fallback_file:
        return {'goal_task': None, 'milestone': None, 'fallback': None,
                'ledger_sha256': ledger_digest}
    if not goal_task:
        raise ValueError('Primary milestone requires explicit --goal-task')
    if focus:
        require_fresh_sources(snapshot_file, workspace)
        snapshot = json.loads(Path(snapshot_file).read_text())
        if not any(row['path'] == 'goals.json' and row['sha256'] == ledger_digest for row in snapshot['files']):
            raise ValueError('Focused admission source evidence must include the fresh goal ledger')
    spec = importlib.util.spec_from_file_location('admission_goals',
        Path(__file__).resolve().parents[2] / 'repo-docs/scripts/goals.py')
    assert spec is not None and spec.loader is not None
    goals = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(goals)
    errors = goals.errors(data)
    if errors:
        raise ValueError('Invalid goal ledger: ' + '; '.join(errors))
    eligible = goals.eligible(goals.normalize(data))
    selected = next((t for t, g in eligible if t['id'] == goal_task), None)
    if selected is None:
        raise ValueError('Goal task is not dependency-ready eligible: ' + goal_task)
    fallback = None
    if focus and selected['goal'] != focus:
        if not fallback_file:
            raise ValueError('Unrelated goal task requires complete structured fallback')
        require_fresh_sources(snapshot_file, workspace)
        snapshot = json.loads(Path(snapshot_file).read_text())
        if not any(row['path'] == 'goals.json' and row['sha256'] == ledger_digest for row in snapshot['files']):
            raise ValueError('Fallback source evidence must include the fresh goal ledger')
        fallback = json.loads(Path(fallback_file).read_text())
        bindings = {'version': 1, 'workspace': str(workspace), 'primary_milestone': focus,
                    'goal_task': goal_task, 'ledger_sha256': ledger_digest,
                    'source_snapshot_sha256': hashlib.sha256(Path(snapshot_file).read_bytes()).hexdigest()}
        if not isinstance(fallback, dict) or any(fallback.get(k) != v for k, v in bindings.items()):
            raise ValueError('Fallback does not match fresh ledger/workspace/source evidence')
        decision = fallback.get('reprioritization')
        if decision is not None:
            if ('reasons' in fallback or not isinstance(decision, dict)
                    or any(not isinstance(decision.get(k), str) or not decision[k].strip()
                           for k in ('actor', 'reason', 'evidence_ref'))):
                raise ValueError('Explicit reprioritization requires actor, reason and evidence_ref, not slice reasons')
        else:
            reasons = fallback.get('reasons')
            focused = {t['id'] for t, g in eligible if g['id'] == focus}
            if not isinstance(reasons, list) or any(not isinstance(row, dict) for row in reasons):
                raise ValueError('Fallback needs structured reasons for every eligible focused slice')
            ids = [row.get('task_id') for row in reasons]
            if any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(set(ids)) or set(ids) != focused:
                raise ValueError('Fallback reasons must cover exactly every eligible focused slice')
            for row in reasons:
                if (row.get('kind') not in {'ownership', 'authority', 'environment'}
                        or any(not isinstance(row.get(k), str) or not row[k].strip() for k in ('reason', 'evidence_ref'))):
                    raise ValueError('Fallback reason needs ownership|authority|environment, reason and evidence_ref')
    # Catch focus/dependency edits made while the ledger was being evaluated.
    require_fresh_sources(snapshot_file, workspace)
    if hashlib.sha256(ledger.read_bytes()).hexdigest() != ledger_digest:
        raise ValueError('Goal ledger changed during admission; re-evaluate selection')
    return {'goal_task': goal_task, 'goal': selected['goal'], 'milestone': focus,
            'fallback': fallback, 'ledger_sha256': ledger_digest,
            'fallback_validation': 'caller_attestation_not_truth_verified' if fallback else None}


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
              'checks have run with evidence recorded, owned changes are committed (or an explicit no-commit '
              'instruction/no-change result is recorded), and the card is handed to native review. Review '
              'approval happens after that handoff and is NOT part of this goal: a pending review never makes '
              'this goal unfinished or unachievable.')


def validate_publication_authority(authority, workspace, profile, goal_task, contract):
    """Validate exact caller-supplied owner evidence, not independently prove permission."""
    required = {'version', 'workspace', 'profile', 'goal_task', 'contract_sha256',
                'remote', 'ref', 'owner', 'evidence_ref'}
    expected = {'version': 1, 'workspace': str(Path(workspace).resolve(strict=True)),
                'profile': profile, 'goal_task': goal_task,
                'contract_sha256': hashlib.sha256(contract.encode()).hexdigest()}
    if (not isinstance(authority, dict) or set(authority) != required or not goal_task
            or any(authority.get(key) != value for key, value in expected.items())):
        raise ValueError('publication authority must bind exact workspace/profile/task/contract')
    safe = lambda value: isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', value) is not None
    ref = authority['ref']
    if (not safe(profile) or not safe(goal_task) or not safe(authority['remote'])
            or ref != f'refs/heads/agent/{profile}/{goal_task}'
            or any('..' in token or token.endswith(('.', '.lock')) for token in (profile, goal_task))
            or any(not isinstance(authority[key], str) or not authority[key].strip()
                   for key in ('owner', 'evidence_ref'))):
        raise ValueError('publication permits one exact owned task ref and safe existing remote only')
    return dict(authority, authority_validation='caller_attestation_not_independent_authorization')


def build_task_body(contract, goal_max_turns=BUDGET, *, ledger_mode='worker',
                    integration_owner=None, publication_authority=None):
    if ledger_mode not in ('worker', 'proposal'):
        raise ValueError('ledger mode must be worker or proposal')
    if ledger_mode == 'proposal' and (not isinstance(integration_owner, str) or
            re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', integration_owner) is None):
        raise ValueError('proposal ledger role requires explicit integration owner')
    if ledger_mode == 'worker' and integration_owner is not None:
        raise ValueError('integration owner requires proposal ledger mode')
    if publication_authority is not None:
        required = {'version', 'workspace', 'profile', 'goal_task', 'contract_sha256',
                    'remote', 'ref', 'owner', 'evidence_ref', 'authority_validation'}
        if (set(publication_authority) != required or
                publication_authority.get('authority_validation') != 'caller_attestation_not_independent_authorization'):
            raise ValueError('validated scoped publication authority required')
        raw = {key: value for key, value in publication_authority.items() if key != 'authority_validation'}
        validate_publication_authority(raw, raw['workspace'], raw['profile'], raw['goal_task'], contract)
        if ledger_mode != 'proposal' or integration_owner != raw['owner']:
            raise ValueError('scoped publication requires coherent proposal/integration-owner role')
    goals_command = shlex.join([sys.executable, str(
        Path(__file__).resolve().parents[2] / 'repo-docs/scripts/goals.py')])
    cycle_path = Path(__file__).resolve().parents[2] / 'shared/ENGINEERING-CYCLE.md'
    body = (REVIEW_DOD + '\n\n' + contract + '\n\nExecution: This is the selected autogoal slice, not a picker. '
            'Implement and verify this contract only. Do not discover or enqueue another task. '
            f'Read the bundled engineering cycle at `{cycle_path}` for verified skill routing, '
            'missing-support fallbacks and ledger ownership. Decide routine reversible choices yourself '
            'using accepted constraints, repository conventions and focused evidence; do not ask for '
            'approval of equivalent engineering options or reopen settled decisions. Apply the cycle phase/domain '
            'matrix: planning-and-task-breakdown for actual decomposition gaps, constraint-driven-development '
            'for quality criteria, incremental-implementation for the slice, test-driven-development for behavior '
            'changes, relevant API/UI/migration/CI/observability skills, then code-review-and-quality and '
            'git-workflow-and-versioning at closeout. Read verified installed skill instructions and apply '
            'their methods; record Skill application: trigger, verified skill path, decision/artifact, check/result. '
            'Carry existing decision receipts forward; report unavailable skills and the concrete fallback. '
            'Implement and update scoped documentation, then return exact checks, source evidence and remaining gaps. '
            'Own debugging, fixes, focused tests and review handoff on this card; no intermediate cards. '
            'Fix and rerun in-scope failures until acceptance or 5 consecutive attempts without new evidence, '
            'within the runtime budget and existing scope/ownership limits. '
            'Stop at acceptance; do not burn unused turns. One native review lane is the independent review; '
            'no extra reviewer subagents unless the contract explicitly requires them. '
            'Before solution design or implementation, load `ponytail`; preserve test-driven-development and '
            'never waive safety, acceptance criteria or required checks for a smaller diff. '
            'Read repository instructions and preserve dirty-file ownership. Hermes Agent/Desktop/Conduit '
            'and other upstream/vendor references are unmodified; changes stay inside the boundaries this profile\'s SOUL authorizes. '
            f'Mandatory completion gate: run `python3 {Path(__file__).with_name("finish_task.py").resolve()} '
            '--repo <workspace> --profile <profile> --card <card-id> --message "<task summary>" '
            '--check-json \'["<check executable>", "<arg>"]\' -- <owned-file>...` before review handoff or kanban_complete; '
            'repeat --check-json for each required acceptance command. Its agent_commit.sh helper commits '
            'only explicit owned files to agent/<profile>/<card-id>, preserving HEAD and unrelated staged work. '
            'Require status committed and report its exact branch/SHA; validation_failed, source_changed or '
            'commit_failed leaves implementation incomplete: fix within scope and retry, never claim done. '
            'A no_changes receipt is truthful only for no new owned delta; cite existing source and checks, '
            'never claim a new commit. Explicit no-commit instructions take precedence: do not invoke the gate; '
            'run checks separately and report the restriction and uncommitted files. Do not include foreign '
            'hunks in an owned filename; isolate attribution first. After review fixes rerun the gate. '
            'Commit only with the autogoal agent_commit.sh helper to agent/<profile>/<card-id>; '
            'the integration owner assembles attributed commits for a protected PR with required checks, '
            'no direct main push or protection bypass. Workers perform no other commit, and no push, merge, deploy, '
            'publish, spend, trade, third-party contact, profile configuration change, or schedule change. '
            'Test seams are in scope: when code is hard to test (clock, filesystem, network client, provider), add '
            'the smallest injectable seam yourself, also in a pre-existing dirty file (additive only, listed in the '
            'handoff), instead of asking. If the card text is factually wrong (stale IDs, counts or paths), record the '
            'correction as a card comment, deliver against the corrected scope and state it in the handoff; reviewers '
            'judge against that recorded correction. Never block on card wording. '
            'Run long commands (e2e, Playwright, full suites, builds) under `timeout` (for example `timeout 40m`) '
            'so a hang fails fast and is reported instead of crashing the worker. '
            'Keep scratch under the repo\'s ignored folders or ~/.hermes/cache/scratch/<card-id>/ (never new ~/.cache folders) and delete build outputs you created before finishing. '
            'Keep the profile-local autogoal journal updated with evidence and open questions. '
            'Ledger closure precondition: verify executed acceptance checks and required review acceptance '
            'at the tested source before marking a canonical task done. Pending review leaves that task '
            'in_progress and dependent tasks ineligible; finish this worker at review handoff and let the '
            'authorized owner reconcile closure later. When the '
            'contract names a goals.json task, finish with the repo-docs helper (never hand-edit the JSON): '
            f'`{goals_command} task <repo> <TASK> done`, then '
            f'`{goals_command} evidence <repo> <GOAL> --kind executed --ref "<exact command>" --result pass|fail` '
            'for each check you actually ran (a goal is met only with an executed pass), then '
            f'`{goals_command} render <repo>`. In repos without goals.json, tick the TODO.md task and update its '
            'Goal coverage row with an anchored patch. Use native '
            'kanban lifecycle tools to complete or request review. Ask, don\'t block: never block this '
            'card or pause the goal merely because independent work needs owner input. Ask only for material '
            'missing intent, conflicting requirements or authority not already granted; record the recommendation '
            'in BLOCKERS.md and keep independent authorized work moving. Silence is not authorization or '
            'required review acceptance. Report routine decisions as decisions, not unanswered questions. The goal engine has a '
            f'{goal_max_turns}-turn budget; finish early only when genuinely complete. '
            'Review handoff finishes this worker card, not the product milestone: when same-card review is required, '
            'supply implementation/test evidence, then request native review; pending review is not a missing '
            'implementation criterion. Only the authorized review lane can approve closure. If entry is rejected '
            'solely because review is pending, make one corrected review request citing the card Definition of done, '
            'deliverables and executed checks. If that fails, preserve exact receipts and original card; never '
            'invent approval, force a live claim, replace the card, waive review, loop or rerun unchanged tests. '
            'Report Implemented (behavior at exact revision), Qualified (journey passed on named platform/backend), '
            'and Delivered (qualified change verified merged into main through a protected PR) separately. '
            'Read back merged PR and main ancestry before claiming delivery; fixture is not live-provider '
            'qualification and Chromium is not Android qualification. State Remaining milestone gaps and '
            'the next slice even when this card passes. Workers run focused regressions and relevant analysis; '
            'one integration owner runs the broader gate against a frozen candidate and coordinates heavy jobs. '
            'Reuse evidence only when relevant source, tests, dependencies and environment still match; '
            'receipt-only changes do not justify a full-suite replay unless they are check/build inputs. '
            'Record actual durations, retries, review time and measured usage; unknown cost is unknown. '
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
    if ledger_mode == 'proposal':
        start = body.rindex('When the contract names a goals.json task, finish with the repo-docs helper')
        end = body.index('Use native ', start) + len('Use native ')
        body = (body[:start] + 'Canonical ledger proposals only: do not mutate goals.json, TODO goal coverage or '
                'goal evidence in either the canonical checkout or worker copy. Do not run goals.py task/evidence/render '
                'to claim closure. Submit the exact task/goal IDs, source hashes, attributed changes and acceptance/check '
                'receipts to integration owner ' + integration_owner + ' through existing native task context/comments; '
                'only that owner applies canonical ledger transitions after required review acceptance, '
                'reconciles scoped docs and task bodies, validates/renders the ledger and selects the next '
                'authorized dependency-ready task. Use native ' + body[end:])
    if publication_authority is not None:
        body = body.replace('Workers perform no other commit, and no push, merge, deploy, publish, ',
                            'Workers perform no other commit, and no merge, deploy, non-task publication, ', 1)
        body += (' Scoped task-ref publication authority: after acceptance and owned local commit only, '
                 'the caller supplied owner evidence ' + publication_authority['evidence_ref'] +
                 ' (' + publication_authority['authority_validation'] + '). The ONLY permitted Git publication is `git push ' +
                 shlex.quote(publication_authority['remote']) + ' <receipt-commit-sha>:' + shlex.quote(publication_authority['ref']) +
                 '` from this owned task workspace, substituting the verified local commit receipt SHA '
                 '(HEAD is unchanged by agent_commit.sh); read back the exact remote ref and commit. '
                 'No force/delete, other refs/remotes, main push, merge, deploy, release or profile/schedule change. '
                 'This instruction is not runtime permission enforcement or independent approval; preserve all host and '
                 'repository gates, and refuse if current owner authority/ref ownership cannot be confirmed.')
    return body


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
        original = target.read_bytes()
        previous = json.loads(original)
        identity = lambda row: (row.get('board_id'), row.get('task_id'), row.get('created_at'))
        if identity(previous) != identity(receipt):
            history = journal_dir / 'handoffs'
            history.mkdir(exist_ok=True)
            task_id = previous['task_id']
            if Path(task_id).name != task_id:
                raise ValueError('Invalid prior task ID')
            # Dated immutable content-addressed archives conserve original bytes.
            # Old undated receipts remain undated; never invent a historical date.
            stamp = previous.get('created_at', 'undated')
            stamp = re.sub(r'[^A-Za-z0-9_.-]', '-', str(stamp))
            board_digest = hashlib.sha256(str(previous.get('board_id', 'unknown')).encode()).hexdigest()[:12]
            content_digest = hashlib.sha256(original).hexdigest()
            dated = history / f'{stamp}--{board_digest}--{task_id}--{content_digest}.json'
            if not dated.exists():
                with dated.open('xb') as archive:
                    archive.write(original)
            elif dated.read_bytes() != original:
                raise ValueError('Historical receipt content collision; preserve existing archive')
            # Keep the legacy lookup only on first observation, never overwrite it.
            legacy = history / (task_id + '.json')
            if not legacy.exists():
                with legacy.open('xb') as archive:
                    archive.write(original)
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
    p.add_argument('--ledger-mode', choices=('worker', 'proposal'), default='worker',
                   help='Default worker closure, or proposals for the sole integration owner')
    p.add_argument('--integration-owner', help='Required named owner for proposal ledger mode')
    p.add_argument('--publication-authority', help='Exact owner-evidence JSON binding one remote task ref; default no push')
    p.add_argument('--goal-max-turns', type=int, choices=(50, 100), default=BUDGET,
                   help='New worker budget; never resizes an existing owned card')
    p.add_argument('--goal-task', help='Exact dependency-ready ledger task identity')
    p.add_argument('--fallback-file', help='Structured JSON fallback attestations bound to selection evidence')
    p.add_argument('--source-snapshot', help='Scoped evidence snapshot captured before candidate selection')
    p.add_argument('--base', help='Immutable full base commit; required for new Git write passes')
    p.add_argument('--candidate', help='Explicit committed candidate to assemble; defaults to the pinned base')
    p.add_argument('--prerequisite', action='append', default=[], metavar='REF=FULL_COMMIT')
    p.add_argument('--required-path', action='append', default=[], help='Explicit dependency-closure file that must exist after assembly')
    p.add_argument('--pass-root', default=str(Path.home() / '.hermes/cache/scratch/autogoal-passes'),
                   help='Private isolated Git worktrees, never the shared source checkout')
    p.add_argument('--disjoint-terminal-triage', action='append', default=[], metavar='CARD_ID',
                   help='Governor-only attestation of resource-disjoint work; verify terminal claim under lock, preserve original card')
    p.add_argument('--validate-only', action='store_true',
                   help='Check contract structure without CLI calls, journal writes or dispatch')
    args = p.parse_args()
    if os.environ.get('HERMES_KANBAN_TASK'):
        raise SystemExit('Already a goal worker: execute the assigned card, never launch a nested goal.')
    contract = Path(args.contract_file).read_text().strip()
    try:
        validate_contract(contract, args.goal_max_turns)
        publication = None
        if args.publication_authority:
            publication = validate_publication_authority(json.loads(Path(args.publication_authority).read_text()),
                                                         args.workspace, args.profile, args.goal_task, contract)
        role_body = build_task_body(contract, args.goal_max_turns, ledger_mode=args.ledger_mode,
                                    integration_owner=args.integration_owner, publication_authority=publication)
    except (ValueError, OSError, TypeError, KeyError) as error:
        raise SystemExit(str(error)) from error
    if args.validate_only:
        try:
            admission = require_milestone_admission(args.workspace, args.goal_task, args.source_snapshot, args.fallback_file)
        except (ValueError, OSError, TypeError, KeyError) as error:
            raise SystemExit(str(error)) from error
        print(json.dumps({'outcome': 'contract_validated', 'fields': list(CONTRACT_FIELDS),
                          'goal_max_turns': args.goal_max_turns,
                          'factual_validation': False, 'admission': admission,
                          **({'worker_roles': {'ledger_mode': args.ledger_mode,
                              'integration_owner': args.integration_owner,
                              'publication_ref': publication['ref'] if publication else None,
                              'authority_validation': publication['authority_validation'] if publication else None}}
                             if args.ledger_mode != 'worker' or publication else {})}))
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
        try:
            require_fresh_sources(args.source_snapshot, workspace)
            snapshot_bytes = Path(args.source_snapshot).read_bytes()
        except (ValueError, OSError, TypeError, KeyError) as error:
            raise SystemExit(str(error)) from error
        # Resolve stable board identity before the final admission/freshness checks.
        boards = json.loads(run(prefix, 'kanban', 'boards', 'list', '--json'))
        canonical_board = next(b for b in boards if b['slug'] == 'default')
        board_id = canonical_board.get('id') or canonical_board.get('board_id') or str(Path(canonical_board['db_path']).resolve())
        digest = hashlib.sha256((args.profile + '\n' + str(workspace) + '\n' + args.title + '\n' + contract).encode()).hexdigest()
        body = role_body
        # Final check after live ownership reconciliation, immediately before create.
        try:
            require_fresh_sources(args.source_snapshot, workspace)
            admission = require_milestone_admission(workspace, args.goal_task, args.source_snapshot, args.fallback_file)
            require_fresh_sources(args.source_snapshot, workspace)
            ledger = workspace / 'goals.json'
            current_ledger = hashlib.sha256(ledger.read_bytes()).hexdigest() if ledger.exists() else None
            if current_ledger != admission['ledger_sha256']:
                raise ValueError('Goal ledger changed before create; re-evaluate selection')
        except (ValueError, OSError, TypeError, KeyError) as error:
            raise SystemExit(str(error)) from error
        # Assembly uses only attributed committed inputs, never the dirty checkout union.
        try:
            if not args.base:
                raise ValueError('New write passes require --base full immutable commit')
            pins = {}
            for declaration in args.prerequisite:
                ref, sep, pin = declaration.partition('=')
                if not sep or not ref or ref in pins or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', pin):
                    raise ValueError('Prerequisite requires unique REF=FULL_COMMIT')
                pins[ref] = pin
            spec = importlib.util.spec_from_file_location('autogoal_pass_workspace', Path(__file__).with_name('pass_workspace.py'))
            assert spec is not None and spec.loader is not None
            passes = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(passes)
            if Path(args.source_snapshot).read_bytes() != snapshot_bytes:
                raise ValueError('Source snapshot changed since selection; re-evaluate work')
            expected = json.loads(snapshot_bytes)
            pass_path = Path(args.pass_root).expanduser().resolve() / (digest[:16] + '-' + uuid.uuid4().hex)
            identity = passes.prepare(workspace, pass_path, args.base, args.candidate or args.base,
                                      pins, args.required_path)
            manifest = {'version': 1, 'source_workspace': str(workspace), 'candidate_identity': identity,
                        'files': expected['files'], 'ledger_sha256': admission['ledger_sha256'],
                        'source_snapshot_sha256': hashlib.sha256(snapshot_bytes).hexdigest()}
            manifest_path = journal_dir / ('pass-' + pass_path.name + '.json')
            with manifest_path.open('x') as stream:
                json.dump(manifest, stream, indent=2)
            manifest_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            guard = 'python3 ' + shlex.quote(str(Path(__file__).with_name('pass_workspace.py').resolve())) + \
                    ' --manifest ' + shlex.quote(str(manifest_path)) + ' --manifest-sha256 ' + manifest_sha256 + \
                    ' --workspace ' + shlex.quote(str(pass_path))
            body += ('\n\nMANDATORY WORKER START: Before design, tests or any production edit, run `' + guard +
                     '`. Refusal means stop on the ORIGINAL card, with exact diagnostic; do not refresh evidence, '
                     'correct stale wording into a new scope, edit production or create a replacement. '
                     'All writes stay in this card native workspace; the source checkout is read-only. '
                     'The same helper can gate an initial write command with `-- <command>`. '
                     'This is an executable preflight, not a filesystem sandbox or native runtime hook.')
            # No native calls between this final source/ledger/candidate check and create.
            if Path(args.source_snapshot).read_bytes() != snapshot_bytes:
                raise ValueError('Source snapshot changed during assembly; re-evaluate selection')
            final_admission = require_milestone_admission(workspace, args.goal_task, args.source_snapshot, args.fallback_file)
            if final_admission != admission:
                raise ValueError('Goal admission changed during assembly')
            require_fresh_sources(args.source_snapshot, workspace)
            passes.verify(manifest, pass_path)
        except (ValueError, OSError, TypeError, KeyError) as error:
            raise SystemExit(str(error)) from error
        created = json.loads(run(prefix, *board, 'create', args.title, '--body', body,
                                 '--assignee', args.profile, '--workspace', 'dir:' + str(pass_path),
                                 '--goal', '--goal-max-turns', str(args.goal_max_turns), '--max-retries', str(MAX_RETRIES),
                                 '--completion-contract', 'local-only', '--created-by', 'autogoal',
                                 '--idempotency-key', 'autogoal:' + digest, '--json'))
        task_id = created['id']
        saved = json.loads(run(prefix, *board, 'show', task_id, '--json'))
        task = saved.get('task', saved)
        task.update(goal_fields(prefix, task_id))
        if (task.get('workspace_kind') != 'dir' or Path(task.get('workspace_path', '')).resolve() != pass_path):
            # Native idempotency may reconcile a concurrent/original card. Never migrate it.
            if task.get('assignee') != args.profile:
                print(json.dumps({'outcome': 'workspace_owned', 'task_id': task_id,
                                  'assignee': task.get('assignee'), 'status': task['status']}))
                return
            notification = ensure_notification(prefix, task_id, home, args.profile)
            print(json.dumps({'outcome': 'already_owned', 'task_id': task_id, 'status': task['status'],
                              'notification': notification, 'goal_mode': task['goal_mode'],
                              'goal_max_turns': task['goal_max_turns']}))
            return
        assert task['goal_mode'] and task['goal_max_turns'] == args.goal_max_turns, task
        assert task['assignee'] == args.profile, task
        assert task['workspace_kind'] == 'dir' and Path(task['workspace_path']).resolve() == pass_path, task
        assert task['completion_contract'] == 'local-only', task
        created_at = task.get('created_at')
        if isinstance(created_at, (int, float)):
            created_at = datetime.fromtimestamp(created_at, timezone.utc)
        elif created_at:
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            if created_at.tzinfo is None:
                raise ValueError('Native created_at lacks timezone; preserve original card for reconciliation')
        else:
            created_at = datetime.now(timezone.utc)
        receipt = {'outcome': 'handed_off', 'task_id': task_id, 'profile': args.profile,
                   'workspace': str(pass_path), 'source_workspace': str(workspace),
                   'pass_manifest': manifest, 'pass_manifest_path': str(manifest_path),
                   'pass_manifest_sha256': manifest_sha256,
                   'goal_mode': True, 'goal_max_turns': args.goal_max_turns,
                   'status': task['status'], 'board_id': task.get('board_id') or board_id,
                   'created_at': created_at.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z'),
                   **admission}
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
