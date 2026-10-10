"""Conservative delivery claims from explicit, candidate-bound evidence.

This validates receipts, not their issuers: fixture scope stays fixture scope.
Git integration is independently read from the supplied local repository.
"""
import re
import subprocess
import check_receipt
import candidate_identity


def qualification_check(check, candidate, repo):
    """Validate helper evidence against explicitly supplied verification inputs."""
    if repo is None or not isinstance(check, dict):
        return None
    receipt = check.get('receipt')
    scope = check.get('qualification_scope')
    if (not isinstance(check.get('name'), str) or not check['name'].strip()
            or not isinstance(receipt, dict) or receipt.get('version') != 2
            or receipt.get('qualification') != 'exact_candidate'
            or receipt.get('candidate') != candidate or receipt.get('outcome') != 'passed'
            or scope is None or receipt.get('qualification_scope') != scope
            or not isinstance(check.get('command'), list) or not check['command']
            or not all(isinstance(arg, str) for arg in check['command'])
            or any(not isinstance(check.get(k), list)
                   or not all(isinstance(p, str) and p for p in check[k])
                   for k in ('paths', 'external_paths'))):
        return None
    try:
        if not check_receipt.reusable(receipt, repo, check['command'], candidate=candidate,
                                      paths=check['paths'], external_paths=check['external_paths'],
                                      qualification_scope=scope):
            return None
        return dict(scope, name=check['name'])
    except (ValueError, KeyError, TypeError, OSError, subprocess.TimeoutExpired):
        return None


def integration_state(candidate, integration, repo):
    """Check local ancestry and explicit protected-PR provenance, never mutate Git."""
    if repo is None or not isinstance(integration, dict) or not valid_candidate(candidate):
        return 'unknown'
    if integration.get('candidate') != candidate or integration.get('target') != 'refs/heads/main':
        return 'unknown'
    candidate = candidate_fields(candidate)
    def git(*args):
        return subprocess.run(['git', '-C', str(repo), *args], text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
    def revision(value):
        if not isinstance(value, str) or re.fullmatch(r'[0-9a-f]{40}', value) is None:
            return False
        result = git('rev-parse', '--verify', value + '^{commit}')
        return result.returncode == 0 and result.stdout.strip() == value
    def ancestor(a, b):
        return git('merge-base', '--is-ancestor', a, b).returncode == 0
    try:
        if not all(revision(candidate[k]) for k in ('commit', 'base')):
            return 'unknown'
        tree = git('rev-parse', candidate['commit'] + '^{tree}')
        if tree.returncode or tree.stdout.strip() != candidate['tree']:
            return 'unknown'
        if not ancestor(candidate['base'], candidate['commit']):
            return 'unknown'
        if any(not revision(v) or not ancestor(v, candidate['commit'])
               for v in candidate['prerequisites'].values()):
            return 'unknown'
        before, after = integration.get('before'), integration.get('after')
        if not revision(before) or not revision(after):
            return 'unknown'
        main = git('rev-parse', '--verify', 'refs/heads/main^{commit}')
        if main.returncode or not ancestor(after, main.stdout.strip()):
            return 'unknown'
        if not ancestor(candidate['commit'], after) or not ancestor(before, after):
            return 'unknown'
        if integration.get('action') == 'synchronize' and before == after:
            return 'already synchronized'
        provenance = integration.get('provenance', {})
        if (integration.get('action') != 'merge' or before == after
                or ancestor(candidate['commit'], before) or not isinstance(provenance, dict)
                or provenance.get('source') != 'protected_pr'
                or not isinstance(provenance.get('id'), str) or not provenance['id'].strip()
                or provenance.get('observed') is not True or provenance.get('protected') is not True
                or provenance.get('required_checks') != 'passed'
                or provenance.get('head') != candidate['commit']
                or provenance.get('merge_commit') != after):
            return 'unknown'
        return 'merged'
    except (OSError, subprocess.TimeoutExpired):
        return 'unknown'


def candidate_fields(value):
    """Read both explicit identities and candidate_identity.capture's v1 format."""
    if not isinstance(value, dict):
        return {}
    if 'version' not in value:
        return value
    rows = value.get('prerequisites')
    if (value.get('version') != 1 or not isinstance(value.get('workspace'), str)
            or not value['workspace'] or not isinstance(value.get('candidate_ref'), str)
            or not value['candidate_ref'] or not isinstance(rows, list)
            or any(not isinstance(r, dict) or not isinstance(r.get('ref'), str)
                   or not r['ref'] for r in rows)):
        return {}
    pins = {r['ref']: r.get('commit') for r in rows}
    if len(pins) != len(rows):
        return {}
    return {'commit': value.get('candidate_commit'), 'tree': value.get('candidate_tree'),
            'base': value.get('base_commit'), 'prerequisites': pins}


def valid_candidate(value):
    value = candidate_fields(value)
    def sha(s):
        return isinstance(s, str) and re.fullmatch(r'[0-9a-f]{40}', s) is not None
    return (all(sha(value.get(k)) for k in ('commit', 'tree', 'base'))
            and isinstance(value.get('prerequisites'), dict)
            and all(isinstance(k, str) and k and sha(v)
                    for k, v in value['prerequisites'].items()))


def evaluate(evidence, repo=None):
    evidence = evidence if isinstance(evidence, dict) else {}
    candidate = evidence.get('candidate')
    implementation = evidence.get('implementation', {})
    artifacts = implementation.get('artifacts') if isinstance(implementation, dict) else None
    implemented = (repo is not None and valid_candidate(candidate)
                   and candidate_identity.check(candidate, repo) and isinstance(artifacts, list)
                   and bool(artifacts) and all(isinstance(x, str) and x for x in artifacts))
    qualification = evidence.get('qualification', {})
    qualification = qualification if isinstance(qualification, dict) else {}
    checks = qualification.get('checks')
    validated = ([qualification_check(c, candidate, repo) for c in checks]
                 if isinstance(checks, list) and checks else [])
    required = qualification.get('required_checks')
    names = [c['name'] for c in validated if c is not None]
    complete = (isinstance(required, list) and bool(required)
                and all(isinstance(name, str) and name.strip() for name in required)
                and len(set(required)) == len(required)
                and len(set(names)) == len(names) and set(required).issubset(names))
    qualified = (implemented and qualification.get('candidate') == candidate
                 and complete and bool(validated) and all(c is not None and
                     (evidence.get('required_mode') is None or c['mode'] == evidence['required_mode'])
                     for c in validated))
    scope = sorted({f"{c['name']}: {c['platform']}/{c['backend']} ({c['mode']})"
                    for c in validated if c is not None}) if qualified else []
    progress = ('Qualified: ' + ', '.join(scope) + '; delivery unknown' if qualified else
                'Implemented; qualification unknown; delivery unknown' if implemented else
                'Implementation unknown; qualification unknown; delivery unknown')
    integration = integration_state(candidate, evidence.get('integration'), repo)
    delivered = qualified and integration == 'merged'
    if delivered:
        progress = 'Delivered: merged main; qualified ' + ', '.join(scope)
    elif integration == 'already synchronized':
        progress = progress.replace('delivery unknown', 'already synchronized; delivery unknown')
    return {'state': 'delivered' if delivered else 'qualified' if qualified else 'implemented' if implemented else 'unknown',
            'candidate': candidate if valid_candidate(candidate) else None,
            'implemented': implemented, 'qualified': qualified, 'delivered': delivered,
            'milestone_complete': False, 'qualification_scope': scope,
            'integration': integration, 'progress': progress}
