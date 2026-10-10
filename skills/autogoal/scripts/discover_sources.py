"""Read-only bounded discovery of likely project planning sources."""
import argparse
import json
import os
from pathlib import Path

PRUNE = {'.git', 'node_modules', '.dart_tool', 'build', 'dist', '.venv', 'venv', '.hermes', '.omh', '.agents', '.cache', 'vendor', 'Pods'}
PRIMARY = {'BACKLOG', 'TODO', 'TASKS', 'ROADMAP', 'PLAN', 'GOALS', 'CONTEXT', 'STATUS', 'README', 'AGENTS'}
HINTS = ('backlog', 'todo', 'roadmap', 'goal', 'plan', 'current-status', 'active-claim', 'ownership', 'parity', 'gap', 'acceptance')
DOC_DIRS = {'plans', 'planning', 'roadmaps', 'goals', 'coordination', 'architecture', 'adr', 'design', 'specs', 'runbooks', 'audits', 'quality', 'testing', 'troubleshooting', 'api', 'guides'}

def discover(root, limit=50, exclude=()):
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError('Workspace must be an existing directory')
    excluded = set()
    for item in exclude:
        path = Path(item)
        if path.is_absolute() or '..' in path.parts or not path.parts:
            raise ValueError('Exclusions must be nonempty root-relative paths without ..')
        excluded.add(path.as_posix())
    candidates = []
    visited = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        relative = Path(directory).relative_to(root)
        dirs[:] = sorted(d for d in dirs if d not in PRUNE and not d.startswith('.') and (relative / d).as_posix() not in excluded and not (Path(directory)/d).is_symlink()) if len(relative.parts) < 5 else []
        for name in sorted(files):
            visited += 1
            if visited > 20000:
                return {'workspace': str(root), 'scan_truncated': True, 'candidates': sorted(candidates, key=lambda x: (x['rank'], x['path']))[:limit]}
            path = Path(directory)/name
            if path.is_symlink() or path.suffix.lower() not in {'.md', '.markdown', '.yaml', '.yml'}:
                continue
            stem = path.stem.upper()
            lower = name.lower()
            primary = stem in PRIMARY
            hinted = any(hint in lower for hint in HINTS)
            plan_dir = any(part.lower() in DOC_DIRS for part in relative.parts)
            if not (primary or hinted or plan_dir):
                continue
            rank = (0 if primary and not relative.parts else
                    1 if any(h in lower for h in ('active-claim', 'ownership', 'current-status', 'goal')) else
                    2 if primary and stem not in {'README', 'AGENTS'} else
                    3 if (hinted or plan_dir) and stem != 'README' else
                    5 if stem == 'AGENTS' else 6)
            candidates.append({'path': str(path.relative_to(root)), 'rank': rank, 'lead_only': True})
    return {'workspace': str(root), 'scan_truncated': False, 'candidates': sorted(candidates, key=lambda x: (x['rank'], x['path']))[:limit]}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace')
    parser.add_argument('--limit', type=int, default=50)
    parser.add_argument('--exclude', action='append', default=[], help='Root-relative upstream/vendor directory to skip; repeatable')
    args = parser.parse_args()
    if args.limit < 1:
        parser.error('--limit must be positive')
    print(json.dumps(discover(args.workspace, args.limit, args.exclude), indent=2))
