"""Ensure actual worker handoffs follow workflow/delivery policy."""
import unittest
import start_goal


class WorkflowHandoffTests(unittest.TestCase):
    def test_body_separates_card_and_product_delivery(self):
        body = start_goal.build_task_body('Objective: Resume the exact session')
        self.assertIn('Implemented', body)
        self.assertIn('Qualified', body)
        self.assertIn('Delivered', body)
        self.assertIn('Remaining milestone gaps', body)
        self.assertIn('protected PR', body)
        self.assertIn('required checks', body)
        self.assertIn('no direct main push', body)
        self.assertNotIn('daily merge train lands done cards', body)
        self.assertIn('fixture is not live-provider', body)
        self.assertIn('Chromium is not Android', body)
        self.assertIn('integration owner', body)
        self.assertIn('dependencies and environment', body)
        self.assertIn('one corrected review request', body)
        self.assertNotIn('administrative review-entry assessment', body)


if __name__ == '__main__':
    unittest.main()
