from __future__ import annotations

import unittest

from avreamd import cli


class CliHelpersTests(unittest.TestCase):
    def test_pick_serial_prefers_wifi_for_wifi_mode(self) -> None:
        data = {
            "devices": [
                {
                    "state": "device",
                    "serials": {
                        "usb": "USB123",
                        "wifi": "192.168.1.10:5555",
                    },
                }
            ],
            "recommended": "USB123",
        }
        self.assertEqual(cli._pick_serial_for_mode(data, "wifi"), "192.168.1.10:5555")

    def test_pick_serial_falls_back_to_recommended(self) -> None:
        data = {"devices": [{"state": "offline", "serials": {"usb": "USB123"}}], "recommended": "USB999"}
        self.assertEqual(cli._pick_serial_for_mode(data, "usb"), "USB999")


class CliParserTests(unittest.TestCase):
    def test_parse_camera_start(self) -> None:
        parser = cli.build_parser()
        args = parser.parse_args(["camera", "start", "--lens", "back", "--rotation", "90", "--preview-window"])
        self.assertEqual(args.command, "camera")
        self.assertEqual(args.camera_cmd, "start")
        self.assertEqual(args.lens, "back")
        self.assertEqual(args.rotation, "90")
        self.assertTrue(args.preview_window)

    def test_parse_start_defaults(self) -> None:
        parser = cli.build_parser()
        args = parser.parse_args(["start"])
        self.assertEqual(args.command, "start")
        self.assertEqual(args.mode, "wifi")
        self.assertEqual(args.lens, "front")
        self.assertFalse(args.preview_window)

    def test_parse_update_install(self) -> None:
        parser = cli.build_parser()
        args = parser.parse_args(["update", "install", "--allow-stop-streams"])
        self.assertEqual(args.command, "update")
        self.assertEqual(args.update_cmd, "install")
        self.assertTrue(args.allow_stop_streams)


if __name__ == "__main__":
    unittest.main()
