"""Unit tests for Phase 13 ADB USB reverse port forwarding manager."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from camera.adb_manager import ADBManager


class ADBManagerTests(unittest.TestCase):
    def test_adb_binary_detection(self) -> None:
        adb = ADBManager(port=8088)
        self.assertIsInstance(adb.is_available, bool)

    def test_adb_status_dictionary(self) -> None:
        adb = ADBManager(port=8088)
        status = adb.get_status()
        self.assertIn("adb_available", status)
        self.assertIn("devices_found", status)
        self.assertIn("reverse_active", status)
        self.assertIn("forwarded_port", status)
        self.assertEqual(status["forwarded_port"], 8088)

    @patch("subprocess.run")
    def test_mock_device_detection_and_reverse_setup(self, mock_run: MagicMock) -> None:
        # Mock 'adb devices' output with authorized device
        mock_devices_proc = MagicMock()
        mock_devices_proc.returncode = 0
        mock_devices_proc.stdout = "List of devices attached\n1234567890ABCDEF\tdevice\n\n"

        # Mock 'adb reverse tcp:8088 tcp:8088' output
        mock_reverse_proc = MagicMock()
        mock_reverse_proc.returncode = 0
        mock_reverse_proc.stdout = "8088\n"

        # Side effects for get_connected_devices() + setup_reverse() (which calls get_connected_devices() then reverse)
        mock_run.side_effect = [mock_devices_proc, mock_devices_proc, mock_reverse_proc]

        adb = ADBManager(port=8088)
        adb.adb_bin = "mock_adb.exe"

        devices = adb.get_connected_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["serial"], "1234567890ABCDEF")
        self.assertEqual(devices[0]["status"], "device")

        success = adb.setup_reverse()
        self.assertTrue(success)
        self.assertTrue(adb.reverse_active)
        self.assertEqual(adb.device_serial, "1234567890ABCDEF")

    @patch("subprocess.run")
    def test_mock_unauthorized_device_handling(self, mock_run: MagicMock) -> None:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "List of devices attached\nUNAUTH123\tunauthorized\n\n"
        mock_run.return_value = mock_proc

        adb = ADBManager(port=8088)
        adb.adb_bin = "mock_adb.exe"

        success = adb.setup_reverse()
        self.assertFalse(success)
        self.assertFalse(adb.reverse_active)
        self.assertFalse(adb.device_authorized)


if __name__ == "__main__":
    unittest.main()
