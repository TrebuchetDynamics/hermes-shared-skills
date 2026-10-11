#!/usr/bin/env python3
"""Run owned offline unittest suites; never import tests while building inventory."""
import argparse
from collections import defaultdict
import os
from pathlib import Path
import signal
import subprocess
import sys

TEST_DIRS = ('tests', 'skills/autogoal/scripts', 'skills/repo-docs/scripts',
             'skills/git-commit-push/scripts')
EXCLUSIONS = {
    'skills/repo-docs/scripts/test_goal_gap_regression.py':
        ('model', 'runs Hermes chat and writes profile receipts at import'),
    'skills/autogoal/scripts/test_native_lifecycle_controls.py':
        ('native', 'requires an installed Hermes interpreter and native CLI'),
    'skills/autogoal/scripts/test_native_handoff.py':
        ('native', 'optional installed Hermes native handoff suite'),
    'skills/autogoal/scripts/test_native_containment_linux.py':
        ('native', 'optional installed Linux containment backend'),
    'skills/autogoal/scripts/test_controller_bridge_linux.py':
        ('native', 'optional installed Linux controller/backend composition'),
    'tests/integration_plugin.py':
        ('integration', 'requires the optional Hermes loader environment'),
    'tests/integration_bundle.py':
        ('integration', 'requires an existing isolated Hermes installation'),
    'tests/integration_hindsight.py':
        ('integration', 'requires installed Hermes and Hindsight; captures SDK calls without server traffic'),
}
LIVE_FLAGS = ('CONTAINMENT_LINUX_TESTS', 'RUN_CONTROLLER_BRIDGE_LINUX',
              'HERMES_NATIVE_HANDOFF_TEST')


def discover_tests(root):
    """Only direct test_*.py children of the maintained test directories."""
    root = Path(root).resolve()
    tests = []
    for directory in TEST_DIRS:
        folder = root / directory
        if folder.is_symlink() or not folder.is_dir():
            continue
        for path in sorted(folder.glob('test_*.py')):
            if (path.is_file() and not path.is_symlink()
                    and path.relative_to(root).as_posix() not in EXCLUSIONS):
                tests.append(path)
    return tests


def run_directory(directory, tests, env, timeout):
    """Use the module runner so multiprocessing spawn has a real entry point."""
    command = [sys.executable, '-m', 'unittest', *[path.stem for path in tests]]
    with subprocess.Popen(command, cwd=directory, env=env, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          start_new_session=os.name == 'posix') as process:
        try:
            output, _ = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name == 'posix':
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
            output, _ = process.communicate()
            print(output, end='', flush=True)
            print(f'TIMEOUT: {directory} after {timeout:g}s', flush=True)
            return False
    print(output, end='', flush=True)
    return process.returncode == 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list', action='store_true', help='list inventory without importing or running tests')
    parser.add_argument('--timeout', type=float, default=180, help='seconds allowed per test directory (default: 180)')
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    root = Path(__file__).resolve().parents[1]
    tests = discover_tests(root)
    groups = defaultdict(list)
    for path in tests:
        groups[path.parent].append(path)
        if args.list:
            print(f'RUN {path.relative_to(root)}')
    excluded = 0
    for name, (category, reason) in EXCLUSIONS.items():
        if (root / name).is_file():
            print(f'EXCLUDE {name} [{category}]: {reason}', flush=True)
            excluded += 1
    print(f'Offline inventory: {len(tests)} modules in {len(groups)} directories; '
          f'{excluded} excluded. No model/native qualification.', flush=True)
    if args.list:
        return 0
    if not tests:
        print('FAIL: no offline tests found', flush=True)
        return 1
    env = dict(os.environ)
    for flag in LIVE_FLAGS:
        env.pop(flag, None)
    passed = failed = 0
    for directory, modules in groups.items():
        print(f'CHECK {directory.relative_to(root)} ({len(modules)} modules)', flush=True)
        if run_directory(directory, modules, env, args.timeout):
            passed += 1
        else:
            failed += 1
    print(f'Offline result: {passed} test directories passed; {failed} failed; '
          f'{excluded} modules excluded.', flush=True)
    return int(bool(failed))


if __name__ == '__main__':
    sys.exit(main())
