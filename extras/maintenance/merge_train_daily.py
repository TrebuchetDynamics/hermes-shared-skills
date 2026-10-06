#!/usr/bin/env python3
"""Cron entry for the daily merge train: start it detached and exit silently (see
fleet-governor/references/merge-train.md). The report lands in ~/.hermes/fleet-governor/merge-train/."""
import subprocess
import sys
from pathlib import Path

train = Path(__file__).resolve().parents[2] / 'fleet-governor' / 'scripts' / 'merge_train.py'
subprocess.run([sys.executable, str(train), 'launch', *sys.argv[1:]], check=True)
