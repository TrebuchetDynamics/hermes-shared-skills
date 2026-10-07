#!/usr/bin/env python3
"""Offline tests for question_relay.py."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = '**Job ID:** j1\n## Response\n\nDid work.\n\nQuestions (no reply = defaults apply):\n1. Pick A or B? **A (default applied)**\n'


class Relay(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        for name, token in (('botless', ''), ('hasbot', 'TELEGRAM_BOT_TOKEN=123:abc\n')):
            p = self.root / 'profiles' / name
            (p / 'cron' / 'output' / 'j1').mkdir(parents=True)
            (p / 'config.yaml').write_text('model: x\n')
            (p / '.env').write_text(token)
            (p / 'cron' / 'jobs.json').write_text(json.dumps({'jobs': [{'id': 'j1', 'name': 'autogoal'}]}))
            (p / 'cron' / 'output' / 'j1' / '2026-10-07_08-00-00.md').write_text(RUN)
        (self.root / '.env').write_text('TELEGRAM_BOT_TOKEN=1:x\n')

    def relay(self, *extra):
        env = dict(os.environ, HERMES_HOME=str(self.root))
        return subprocess.run([sys.executable, str(HERE / 'question_relay.py'), *extra], env=env,
                              capture_output=True, text=True, check=True).stdout

    def test_relays_botless_profile_once(self):
        out = self.relay()
        self.assertIn('[botless · autogoal]', out)
        self.assertIn('Pick A or B?', out)
        self.assertNotIn('hasbot', out)
        self.assertEqual(self.relay('--cooldown-hours', '0'), '')  # same questions: not repeated

    def test_none_is_not_relayed(self):
        f = self.root / 'profiles' / 'botless' / 'cron' / 'output' / 'j1' / '2026-10-07_08-00-00.md'
        f.write_text('## Response\n\nDone.\nQuestions (no reply = defaults apply): None.\n')
        self.assertEqual(self.relay(), '')


if __name__ == '__main__':
    unittest.main()
