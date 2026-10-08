"""CLI failures are bounded and never blindly retried."""
import subprocess
import unittest
from unittest.mock import patch
import start_goal


class BoundsTests(unittest.TestCase):
    def test_cli_calls_have_deadline_and_propagate_failures_once(self):
        for failure in [subprocess.TimeoutExpired(['hermes'], 30),
                        subprocess.CalledProcessError(2, ['hermes'])]:
            with self.subTest(failure=type(failure).__name__), \
                    patch.object(start_goal.subprocess, 'check_output', side_effect=failure) as call:
                with self.assertRaises(type(failure)):
                    start_goal.run(['hermes'], 'kanban', 'list')
                call.assert_called_once_with(['hermes', 'kanban', 'list'], text=True, timeout=30)


if __name__ == '__main__':
    unittest.main()
