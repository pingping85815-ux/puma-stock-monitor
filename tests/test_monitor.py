import json
import os
import tempfile
import unittest
from unittest.mock import patch

import monitor


class MonitorTests(unittest.TestCase):
    def test_json_ld_product_detection(self):
        block = json.dumps(
            {
                "@context": "https://schema.org",
                "@type": "Product",
                "name": "Test cap",
                "sku": "4070034024903",
                "offers": {"availability": "http://schema.org/OutOfStock"},
            }
        )
        product = monitor.product_from_json_ld([block])
        self.assertEqual(product["sku"], "4070034024903")

    def test_notification_transitions(self):
        self.assertTrue(monitor.should_notify(None, True))
        self.assertTrue(monitor.should_notify(False, True))
        self.assertFalse(monitor.should_notify(True, True))
        self.assertFalse(monitor.should_notify(None, False))
        self.assertFalse(monitor.should_notify(False, False))

    def test_cloud_state_parser(self):
        with patch.dict(os.environ, {"PREVIOUS_STOCK_STATE": "InStock"}):
            self.assertIs(monitor.parse_cloud_previous_state(), True)
        with patch.dict(os.environ, {"PREVIOUS_STOCK_STATE": "OutOfStock"}):
            self.assertIs(monitor.parse_cloud_previous_state(), False)
        with patch.dict(os.environ, {"PREVIOUS_STOCK_STATE": ""}):
            self.assertIsNone(monitor.parse_cloud_previous_state())

    def test_github_output(self):
        with tempfile.NamedTemporaryFile(mode="r+", encoding="utf-8") as output:
            with patch.dict(os.environ, {"GITHUB_OUTPUT": output.name}):
                monitor.write_github_output("stock_state", "OutOfStock")
            output.seek(0)
            self.assertEqual(output.read(), "stock_state=OutOfStock\n")

    def test_public_email_settings_and_gmail_defaults(self):
        env = {
            "SMTP_USER": "sender@example.com",
            "SMTP_PASSWORD": "not-a-real-password",
            "RECIPIENT_EMAIL": "recipient@example.com",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = monitor.smtp_settings()
        self.assertEqual(settings["host"], "smtp.gmail.com")
        self.assertEqual(settings["port"], 465)
        self.assertEqual(settings["to"], "recipient@example.com")


if __name__ == "__main__":
    unittest.main()
