"""Offline job wiring regression: real provisioning script, fake external CLI."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2]
FAKE = '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
p = Path(os.environ['FIXTURE_STATE'])
d = json.loads(p.read_text())
a = sys.argv[1:]
if a[:1] == ['-p']: a = a[2:]
if a[:2] == ['profile', 'list']: print('demo')
elif a[:2] == ['config', 'set']: pass
elif a[:2] == ['cron', 'list']:
 for i, j in enumerate(d):
  print(f'{i+1:012x}'); print('  ' + j[j.index('--name')+1])
elif a[:2] == ['cron', 'create']:
 d.append(a); p.write_text(json.dumps(d))
else: raise SystemExit('unexpected fake CLI call: ' + repr(a))
'''


class NewProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='new-profile-')
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        repo = root / 'repo'
        install = repo / 'extras/install'
        install.mkdir(parents=True)
        shutil.copytree(SOURCE / 'extras/cron', repo / 'extras/cron')
        self.script = install / 'new_profile.sh'
        shutil.copy2(SOURCE / 'extras/install/new_profile.sh', self.script)
        stub = repo / 'install.sh'
        stub.write_text('#!/usr/bin/env bash\nexit 0\n')
        stub.chmod(0o755)
        binary = root / 'bin'
        binary.mkdir()
        fake = binary / 'hermes'
        fake.write_text(FAKE)
        fake.chmod(0o755)
        self.workspace = root / 'workspace'
        self.workspace.mkdir()
        self.state = root / 'jobs.json'
        self.state.write_text('[]')
        self.env = dict(os.environ, PATH=str(binary) + os.pathsep + os.environ['PATH'],
                        FIXTURE_STATE=str(self.state), HERMES_HOME=str(root / 'home'))

    def provision(self, cadence, *options):
        result = subprocess.run(['bash', str(self.script), 'demo', str(self.workspace),
                                 '--autogoal', cadence, '--deliver', 'local', *options],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(self.state.read_text())

    def check_cadence(self, cadence, name):
        jobs = self.provision(cadence)
        self.assertEqual(len(jobs), 2)
        docs, auto = jobs
        option = lambda argv, key: argv[argv.index(key) + 1] if key in argv else None
        self.assertEqual(option(auto, '--monitor-script'), 'autogoal_gate.py')
        self.assertEqual(option(auto, '--name'), name)
        self.assertEqual(option(docs, '--monitor-script'), 'repo_docs_monitor.py')
        for job in jobs:
            self.assertEqual(option(job, '--workdir'), str(self.workspace))
            self.assertEqual(option(job, '--deliver'), 'local')
        self.assertIn('--continuity', auto)
        self.assertIn('000000000001', auto[3])
        self.assertNotIn('{repo_docs_job_id}', auto[3])
        self.assertEqual(auto[2].split()[1:], ['*', '*', '*', '*'])
        if cadence == '15m':
            self.assertTrue(auto[2].split()[0].endswith('-59/15'))
        else:
            self.assertTrue(auto[2].split()[0].isdigit())
        before = self.state.read_bytes()
        self.provision(cadence)
        self.assertEqual(self.state.read_bytes(), before, 'existing jobs must not be rewritten')
        self.provision(cadence, '--no-cron')
        self.assertEqual(self.state.read_bytes(), before)

    def test_hourly_busy_gate_and_idempotency(self):
        self.check_cadence('hourly', 'autogoal-hourly')

    def test_15m_busy_gate_and_idempotency(self):
        self.check_cadence('15m', 'autogoal-every-15m')

    def test_no_cron_creates_no_jobs(self):
        self.assertEqual(self.provision('hourly', '--no-cron'), [])


if __name__ == '__main__':
    unittest.main()
