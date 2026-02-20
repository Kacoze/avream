from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "ui" / "src"))

from avream_ui.window_state import SelectedPhone  # noqa: E402


class WindowStateTests(unittest.TestCase):
    def test_selected_phone_from_payload(self) -> None:
        payload = {
            "id": "dev1",
            "serial": "ABC123",
            "state": "device",
            "transport": "usb",
            "transports": ["usb", "wifi"],
            "serials": {"usb": "ABC123", "wifi": "192.168.1.2:5555"},
            "wifi_candidate_endpoint": "192.168.1.2:5555",
            "wifi_candidate_ip": "192.168.1.2",
        }
        item = SelectedPhone.from_payload(payload)
        self.assertEqual(item.serial, "ABC123")
        self.assertEqual(item.serials["usb"], "ABC123")
        self.assertEqual(item.as_dict()["id"], "dev1")


if __name__ == "__main__":
    unittest.main()
