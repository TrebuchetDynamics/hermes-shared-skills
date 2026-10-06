"""Read canonical blocker files; never infer user actions or attest exhaustion."""
import argparse
import hashlib
import json
import re
from pathlib import Path

CATEGORIES = {'USER_INPUT', 'SUDO', 'USER_DECISION'}
IMPACTS = {'PROJECT_BLOCKING', 'SCOPE_BLOCKING', 'ADMIN_BLOCKING'}
REQUIRED = {'Status', 'Category', 'Owner', 'Task/Card', 'Blocked scope',
            'Why blocked', 'Evidence', 'User action required', 'Resume condition',
            'Created', 'Last checked'}


def parse_entries(text):
    entries, problems, section, current = [], [], None, None
    sections = []
    def finish():
        if current is not None:
            entries.append(current)
    for line in text.splitlines():
        bare = re.sub(r'^#{1,6}\s+', '', line.strip())
        if bare in {'Active', 'Resolved'}:
            finish()
            current = None
            section = bare
            sections.append(bare)
            continue
        match = re.fullmatch(r'(BLK-\d{8}-\d{3})\s+[—–-]\s+(.+)', bare)
        if match:
            finish()
            current = {'id': match[1], 'title': match[2], 'section': section, 'fields': {}}
        elif bare.startswith('BLK-'):
            problems.append('malformed blocker identifier/heading')
        elif current is not None:
            field = re.fullmatch(r'-\s+([^:]+):\s*(.*)', line.strip())
            if field:
                if field[1] in current['fields']:
                    problems.append('duplicate field in ' + current['id'])
                current['fields'][field[1]] = field[2]
        elif section == 'Active' and bare and bare != 'None.':
            problems.append('unrecognized Active content; not a valid hard-blocker entry')
    finish()
    if sections != ['Active', 'Resolved']:
        problems.append('canonical Active/Resolved sections missing, duplicated or out of order')
    ids = [entry['id'] for entry in entries]
    if len(ids) != len(set(ids)):
        problems.append('duplicate blocker ID within canonical file')
    for entry in entries:
        fields = entry['fields']
        needed = REQUIRED if entry['section'] == 'Active' else {'Status', 'Category', 'Resolved', 'Resolution', 'Evidence'}
        missing = sorted(key for key in needed if not fields.get(key))
        if missing:
            problems.append(entry['id'] + ': missing ' + ', '.join(missing))
        if fields.get('Category') not in CATEGORIES:
            problems.append(entry['id'] + ': invalid hard-blocker category')
        if 'Impact' in fields and fields['Impact'] not in IMPACTS:
            problems.append(entry['id'] + ': invalid impact classification')
        expected = {'Active': 'ACTIVE', 'Resolved': 'RESOLVED'}.get(entry['section'])
        if fields.get('Status') != expected or expected is None:
            problems.append(entry['id'] + ': status/section mismatch')
        if entry['section'] == 'Active' and fields.get('Owner') != 'user':
            problems.append(entry['id'] + ': owner must be user')
    return entries, problems


def collect(repositories):
    result = {'schema': 'fleet-blockers/v1', 'recorded_active': [], 'issues': [],
              'coverage': {'expected': len(repositories), 'read': 0},
              'semantic_verification_performed': False, 'sources': []}
    for repo in repositories:
        path = Path(repo['root']) / 'BLOCKERS.md'
        try:
            data = path.read_bytes()
        except OSError:
            result['issues'].append({'repository': repo['repository'], 'path': str(path),
                                     'issue': 'canonical file unavailable; not proof of no blockers'})
            continue
        result['coverage']['read'] += 1
        digest = hashlib.sha256(data).hexdigest()
        result['sources'].append({'repository': repo['repository'], 'path': str(path),
                                  'sha256': digest})
        try:
            entries, problems = parse_entries(data.decode('utf-8'))
        except UnicodeError:
            entries, problems = [], ['canonical file is not UTF-8']
        for problem in problems:
            result['issues'].append({'repository': repo['repository'], 'path': str(path), 'issue': problem})
        # Entry-local defects must not hide unrelated valid active entries.
        # Structural ambiguity (including duplicate IDs) still fails closed.
        if any(not problem.startswith('BLK-') for problem in problems):
            continue
        invalid_ids = {problem.split(':', 1)[0] for problem in problems}
        for entry in entries:
            if entry['section'] != 'Active' or entry['id'] in invalid_ids:
                continue
            fields = entry['fields']
            result['recorded_active'].append({
                'repository': repo['repository'], 'id': entry['id'], 'title': entry['title'],
                'category': fields['Category'], 'impact': fields.get('Impact'),
                'task_card': fields['Task/Card'],
                'user_action_required': fields['User action required'],
                'consequence_of_waiting': fields['Blocked scope'],
                'why_blocked': fields['Why blocked'], 'evidence': fields['Evidence'],
                'resume_condition': fields['Resume condition'], 'last_checked': fields['Last checked'],
                'source': str(path), 'source_sha256': digest,
                'verification': 'REQUIRES_REEVALUATION'})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', type=Path, required=True)
    args = parser.parse_args()
    result = collect(json.loads(args.registry.read_text())['repositories'])
    print(json.dumps(result, indent=2))
    return 2 if result['issues'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
