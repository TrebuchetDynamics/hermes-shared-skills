#!/usr/bin/env python3
"""Run first-party offline checks. Never runs Hermes/model-backed regressions.

Usage: python scripts/check.py
Requires Python 3.12+, ruamel.yaml, and bash. Runs each test as a separate
process because existing standalone suites modify sys.path independently.
"""
import subprocess
import sys
from pathlib import Path

from validate_skills import discover_skills, validate_catalog

ROOT = Path(__file__).resolve().parents[1]
# These two explicitly invoke a real model: keep them manual, not CI.
MODEL_TESTS = {'repo-docs/scripts/test_goal_gap_regression.py',
               'hard-blockers/scripts/test_repo_docs.py'}
# Installed-environment controls are explicit opt-in, not offline CI.
NATIVE_TESTS = {'autogoal/scripts/test_native_lifecycle_controls.py',
                'autogoal/scripts/test_native_containment_linux.py',
                'autogoal/scripts/test_controller_bridge_linux.py'}


def first_party_files(root):
    root = Path(root).resolve()
    for path in sorted(root.rglob('*')):
        parts = path.relative_to(root).parts
        if parts[0] == 'vendor' or any(part.startswith('.') or part == '__pycache__' for part in parts):
            continue
        if path.is_file() and not path.is_symlink() and root in path.resolve().parents:
            yield path


def discover_tests(root):
    root = Path(root).resolve()
    return [p for p in first_party_files(root)
            if p.name.startswith('test_') and p.suffix == '.py'
            and p.relative_to(root).as_posix() not in MODEL_TESTS | NATIVE_TESTS]


def main():
    errors = validate_catalog(ROOT)
    for path in first_party_files(ROOT):
        try:
            if path.suffix == '.py':
                compile(path.read_text(encoding='utf-8'), str(path), 'exec')
            elif path.suffix == '.sh':
                result = subprocess.run(['bash', '-n', str(path)], capture_output=True, text=True, timeout=30)
                if result.returncode:
                    errors.append(f'{path.relative_to(ROOT)}: {result.stderr.strip()}')
        except (OSError, UnicodeError, SyntaxError, subprocess.TimeoutExpired) as exc:
            errors.append(f'{path.relative_to(ROOT)}: {exc}')
    if errors:
        print('\n'.join(errors), flush=True)
        return 1
    print(f'PASS: {len(discover_skills(ROOT))} skill contracts and Python/shell syntax', flush=True)
    tests = discover_tests(ROOT)
    if not tests:
        print('FAIL: no offline test suites discovered', flush=True)
        return 1
    failed = []
    for path in tests:
        label = path.relative_to(ROOT).as_posix()
        print(f'\nCHECK {label}', flush=True)
        try:
            result = subprocess.run([sys.executable, str(path)], cwd=ROOT, timeout=180)
            if result.returncode:
                failed.append(f'{label} (exit {result.returncode})')
        except (OSError, subprocess.TimeoutExpired) as exc:
            failed.append(f'{label} ({exc})')
    print(f'\nOffline suites: {len(tests) - len(failed)} passed, {len(failed)} failed; '
          f'{len(MODEL_TESTS)} model-backed and {len(NATIVE_TESTS)} opt-in native suites excluded.', flush=True)
    for error in failed:
        print(f'FAIL: {error}', flush=True)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
