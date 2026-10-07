#!/usr/bin/env python3
"""goals.json: the machine-readable goal list that repo-docs writes and autogoal reads.

TODO.md stays the human view; its `Goal coverage` table is rendered from this file.
Agents change goals.json only through these commands, never by hand-editing JSON.

  goals.py validate <repo>                       structural + evidence-rule check (exit 1 on errors)
  goals.py fmt <repo>                            canonical byte-stable rewrite (applies the "met" rule)
  goals.py next <repo> [--json]                  next eligible open task (dependencies satisfied)
  goals.py render <repo>                         rewrite TODO.md's goal-coverage block from goals.json
  goals.py task <repo> <TASK> <open|in_progress|done>
  goals.py section <repo> <TASK> <Now|Next|Needs decision>
  goals.py add-task <repo> <TASK> --goal <GOAL> --title <text> [--section Now|Next|Needs decision] [--depends-on T1,T2]
  goals.py evidence <repo> <GOAL> --kind executed|inspection --ref <cmd/path> --result pass|fail [--ran-at ISO]

Rule (the met rule): a goal is `met` only with at least one evidence entry of kind `executed`
and result `pass`. Anything else claimed as met is downgraded to `unverified` by fmt.
"""
import argparse
import json
import re
import sys
from pathlib import Path

GOAL_STATUS = ('unmet', 'partial', 'unverified', 'met')
TASK_STATUS = ('open', 'in_progress', 'done')
SECTIONS = ('Now', 'Next', 'Needs decision', 'Done')
KINDS = ('executed', 'inspection')
RESULTS = ('pass', 'fail')
# Order: section (Now before Next), then goal priority (the product's stated order), then status as a
# tie-break: unverified/partial (prove or finish what exists) before unmet (new work).
STATUS_RANK = {'unverified': 0, 'partial': 1, 'unmet': 2, 'met': 3}
SECTION_RANK = {'Now': 0, 'Next': 1}
BEGIN, END = '<!-- goals:coverage:begin -->', '<!-- goals:coverage:end -->'


def path_of(repo):
    return Path(repo) / 'goals.json'


def load(repo):
    p = path_of(repo)
    if not p.exists():
        sys.exit(f'{p} not found')
    return json.loads(p.read_text())


def proven(goal):
    return any(e.get('kind') == 'executed' and e.get('result') == 'pass' for e in goal.get('evidence', []))


def normalize(data):
    """Apply the met rule, fill defaults and sort into a stable order."""
    goals, tasks = data.get('goals', []), data.get('tasks', [])
    for g in goals:
        g.setdefault('depends_on', []); g.setdefault('evidence', []); g.setdefault('tasks', [])
        g.setdefault('priority', 100)
        if g.get('status') == 'met' and not proven(g):
            g['status'] = 'unverified'
        g['evidence'] = sorted(g['evidence'], key=lambda e: (e.get('kind', ''), e.get('ref', '')))
        g['depends_on'] = sorted(set(g['depends_on'])); g['tasks'] = sorted(set(g['tasks']))
    for t in tasks:
        t.setdefault('depends_on', []); t.setdefault('section', 'Next'); t.setdefault('status', 'open')
        t['depends_on'] = sorted(set(t['depends_on']))
        if t['status'] == 'done':
            t['section'] = 'Done'
    # Goals keep authoring order (priority, then id); tasks follow section then id.
    goals.sort(key=lambda g: (g['priority'], g['id']))
    tasks.sort(key=lambda t: (SECTIONS.index(t['section']) if t['section'] in SECTIONS else 9, t['id']))
    return {'version': 1, 'goals': goals, 'tasks': tasks}


def errors(data):
    errs = []
    goals, tasks = data.get('goals'), data.get('tasks')
    if data.get('version') != 1:
        errs.append('version must be 1')
    if not isinstance(goals, list) or not isinstance(tasks, list):
        return errs + ['goals and tasks must be lists']
    gids = [g.get('id') for g in goals]; tids = [t.get('id') for t in tasks]
    for dup in {i for i in gids if gids.count(i) > 1} | {i for i in tids if tids.count(i) > 1}:
        errs.append(f'duplicate id {dup}')
    for g in goals:
        gid = g.get('id', '?')
        for k in ('id', 'title', 'source', 'status'):
            if not g.get(k):
                errs.append(f'{gid}: missing {k}')
        if g.get('status') not in GOAL_STATUS:
            errs.append(f'{gid}: status must be one of {GOAL_STATUS}')
        if g.get('status') == 'met' and not proven(g):
            errs.append(f'{gid}: met without executed+pass evidence (run fmt to downgrade to unverified)')
        for e in g.get('evidence', []):
            if e.get('kind') not in KINDS or e.get('result') not in RESULTS or not e.get('ref'):
                errs.append(f'{gid}: evidence needs kind {KINDS}, result {RESULTS} and ref')
        for d in g.get('depends_on', []):
            if d not in gids:
                errs.append(f'{gid}: depends_on unknown goal {d}')
        for t in g.get('tasks', []):
            if t not in tids:
                errs.append(f'{gid}: unknown task {t}')
        open_tasks = [t for t in tasks if t.get('goal') == gid and t.get('status') != 'done']
        if g.get('status') != 'met' and not open_tasks:
            errs.append(f'{gid}: {g.get("status")} goal has no open task')
    for t in tasks:
        tid = t.get('id', '?')
        for k in ('id', 'goal', 'title', 'status'):
            if not t.get(k):
                errs.append(f'{tid}: missing {k}')
        if t.get('goal') not in gids:
            errs.append(f'{tid}: unknown goal {t.get("goal")}')
        if t.get('status') not in TASK_STATUS:
            errs.append(f'{tid}: status must be one of {TASK_STATUS}')
        if t.get('section', 'Next') not in SECTIONS:
            errs.append(f'{tid}: section must be one of {SECTIONS}')
        for d in t.get('depends_on', []):
            if d not in tids:
                errs.append(f'{tid}: depends_on unknown task {d}')
    return errs


def dump(repo, data):
    path_of(repo).write_text(json.dumps(normalize(data), indent=2, sort_keys=True, ensure_ascii=False) + '\n')


def eligible(data):
    goals = {g['id']: g for g in data['goals']}
    tasks = {t['id']: t for t in data['tasks']}
    out = []
    for t in data['tasks']:
        g = goals.get(t['goal'])
        if t['status'] == 'done' or t.get('section') not in SECTION_RANK or not g or g['status'] == 'met':
            continue
        if any(tasks.get(d, {}).get('status') != 'done' for d in t['depends_on']):
            continue
        if any(goals.get(d, {}).get('status') != 'met' for d in g['depends_on']):
            continue
        out.append((SECTION_RANK[t['section']], g['priority'], STATUS_RANK[g['status']], t['id'], t, g))
    return [(t, g) for *_, t, g in sorted(out, key=lambda r: r[:4])]


def render(repo, data):
    tasks = {t['id']: t for t in data['tasks']}
    rows = ['| Goal | Status | Evidence | Task |', '| --- | --- | --- | --- |']
    for g in data['goals']:
        ev = '; '.join(f"{e['kind']} `{e['ref']}` → {e['result']}" for e in g['evidence']) or '—'
        open_t = [t for t in g['tasks'] if tasks.get(t, {}).get('status') != 'done']
        rows.append(f"| {g['id']}: {g['title']} | {g['status']} | {ev} | {', '.join(open_t) or '—'} |")
    block = '\n'.join([BEGIN, '', 'Generated from `goals.json` by `goals.py render`. `met` requires an executed, passing check.', '', *rows, '', END])
    todo = Path(repo) / 'TODO.md'
    text = todo.read_text() if todo.exists() else '# TODO\n\n## Goal coverage\n\n'
    if BEGIN in text and END in text:
        text = text[:text.index(BEGIN)] + block + text[text.index(END) + len(END):]
    elif '## Goal coverage' in text:
        head, tail = text.split('## Goal coverage', 1)
        nxt = re.search(r'\n## ', tail)
        rest = tail[nxt.start():] if nxt else '\n'
        text = head + '## Goal coverage\n\n' + block + '\n' + rest
    else:
        text = text.rstrip('\n') + '\n\n## Goal coverage\n\n' + block + '\n'
    todo.write_text(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('validate', 'fmt', 'render'):
        sub.add_parser(name).add_argument('repo')
    n = sub.add_parser('next'); n.add_argument('repo'); n.add_argument('--json', action='store_true')
    t = sub.add_parser('task'); t.add_argument('repo'); t.add_argument('task'); t.add_argument('status', choices=TASK_STATUS)
    s2 = sub.add_parser('section'); s2.add_argument('repo'); s2.add_argument('task')
    s2.add_argument('section', choices=[s for s in SECTIONS if s != 'Done'])
    n2 = sub.add_parser('add-task'); n2.add_argument('repo'); n2.add_argument('task')
    n2.add_argument('--goal', required=True); n2.add_argument('--title', required=True)
    n2.add_argument('--section', default='Next', choices=[s for s in SECTIONS if s != 'Done'])
    n2.add_argument('--depends-on', default='')
    e = sub.add_parser('evidence'); e.add_argument('repo'); e.add_argument('goal')
    e.add_argument('--kind', choices=KINDS, required=True); e.add_argument('--ref', required=True)
    e.add_argument('--result', choices=RESULTS, required=True); e.add_argument('--ran-at', default='')
    a = ap.parse_args()
    data = load(a.repo)

    if a.cmd == 'validate':
        errs = errors(data)
        print('\n'.join(errs) if errs else 'ok')
        sys.exit(1 if errs else 0)
    if a.cmd == 'fmt':
        dump(a.repo, data); print('ok'); return
    if a.cmd == 'render':
        render(a.repo, normalize(data)); print('ok'); return
    if a.cmd == 'next':
        picks = eligible(normalize(data))
        if a.json:
            print(json.dumps([{'task': t, 'goal': g['id'], 'goal_status': g['status']} for t, g in picks], indent=2))
        elif picks:
            t, g = picks[0]
            print(f"{t['id']} ({t['section']}) → {g['id']} [{g['status']}]: {t['title']}")
        else:
            print('none')
        return
    if a.cmd == 'task':
        task = next((x for x in data['tasks'] if x['id'] == a.task), None) or sys.exit(f'unknown task {a.task}')
        task['status'] = a.status
        dump(a.repo, data)
        goal = next((g for g in data['goals'] if g['id'] == task['goal']), None)
        still_open = [t for t in data['tasks'] if t.get('goal') == task['goal'] and t.get('status') != 'done']
        if a.status == 'done' and goal and goal.get('status') != 'met' and not still_open:
            print(f"WARNING: {goal['id']} is still {goal['status']} with no open task. Record the check you ran: "
                  f"goals.py evidence {a.repo} {goal['id']} --kind executed --ref \"<command>\" --result pass")
        print('ok'); return
    if a.cmd == 'section':
        task = next((x for x in data['tasks'] if x['id'] == a.task), None) or sys.exit(f'unknown task {a.task}')
        if task.get('status') == 'done':
            sys.exit(f'task {a.task} is done')
        task['section'] = a.section
        dump(a.repo, data); print(f'ok {a.task} -> {a.section}'); return
    if a.cmd == 'add-task':
        if any(x['id'] == a.task for x in data['tasks']):
            sys.exit(f'task {a.task} already exists')
        goal = next((x for x in data['goals'] if x['id'] == a.goal), None) or sys.exit(f'unknown goal {a.goal}')
        deps = [d for d in a.depends_on.split(',') if d]
        known = {x['id'] for x in data['tasks']}
        missing = [d for d in deps if d not in known]
        if missing:
            sys.exit(f'unknown depends_on task(s): {missing}')
        data['tasks'].append({'id': a.task, 'goal': a.goal, 'title': a.title, 'status': 'open',
                              'section': a.section, 'depends_on': deps})
        goal['tasks'] = sorted(set(goal.get('tasks', []) + [a.task]))
        dump(a.repo, data); print(f'ok {a.task} -> {a.goal} ({a.section})'); return
    if a.cmd == 'evidence':
        goal = next((x for x in data['goals'] if x['id'] == a.goal), None) or sys.exit(f'unknown goal {a.goal}')
        entry = {'kind': a.kind, 'ref': a.ref, 'result': a.result}
        if a.ran_at:
            entry['ran_at'] = a.ran_at
        goal['evidence'] = [x for x in goal.get('evidence', []) if (x.get('kind'), x.get('ref')) != (a.kind, a.ref)] + [entry]
        if a.kind == 'executed' and a.result == 'pass' and goal.get('status') in ('unverified', 'partial') \
                and all(t.get('status') == 'done' for t in data['tasks'] if t.get('goal') == a.goal):
            goal['status'] = 'met'
        if a.kind == 'executed' and a.result == 'fail' and goal.get('status') == 'met':
            goal['status'] = 'partial'
        dump(a.repo, data); print(f"ok {goal['id']} → {goal['status']}"); return


if __name__ == '__main__':
    main()
