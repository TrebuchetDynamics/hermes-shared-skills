#!/usr/bin/env python3
"""Read a prior autogoal handoff's live card/run; never mutate or dispatch."""
import argparse
import json
from pathlib import Path
from start_goal import run, profile_home


def reconcile(prefix, home, profile, task_id=None):
    if task_id is None:
        receipt = home / 'autogoal' / 'goal-handoff.json'
        if not receipt.exists():
            return {'profile': profile, 'outcome': 'no_handoff', 'continuity': 'missing'}
        task_id = json.loads(receipt.read_text())['task_id']
    snapshot = json.loads(run(prefix, 'kanban', '--board', 'default', 'show', task_id, '--json'))
    task = snapshot.get('task', snapshot)
    if task.get('assignee') != profile:
        raise RuntimeError('Prior handoff belongs to a different profile; do not reconcile as owned')
    runs = snapshot.get('runs', [])
    latest = max(runs, key=lambda r: r.get('id', 0)) if runs else {}
    events = snapshot.get('events', [])
    return {'profile': profile, 'task_id': task_id, 'status': task['status'],
            'title': task.get('title'), 'run_id': latest.get('id'),
            'worker_outcome': latest.get('outcome'),
            'summary': latest.get('summary') or snapshot.get('latest_summary'),
            'error': latest.get('error') or task.get('last_failure_error'),
            'metadata': latest.get('metadata') or {},
            'latest_event': events[-1] if events else None,
            'observation': 'live_read_only', 'worker_observed': bool(runs)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--task-id')
    args = parser.parse_args()
    prefix = ['hermes', '-p', args.profile]
    print(json.dumps(reconcile(prefix, profile_home(prefix), args.profile, args.task_id), indent=2))


if __name__ == '__main__':
    main()
