"""Unit tests for Phase 12 Camera Source abstractions and CameraManager."""

from __future__ import annotations

import unittest
import numpy as np

from camera.camera_source import CameraSource, CameraSourceType
from camera.camera_manager import CameraManager
from camera.phone_camera import PhoneCameraSource


class MockCameraSource(CameraSource):
    def __init__(self, name: str = "MockCam", mirror: bool = False) -> None:
        self._name = name
        self._mirror = mirror
        self._open = False
        self._fps = 30.0
        self._frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    @property
    def source_type(self) -> CameraSourceType:
        return CameraSourceType.LOCAL

    @property
    def source_name(self) -> str:
        return self._name

    @property
    def width(self) -> int:
        return 1280

    @property
    def height(self) -> int:
        return 720

    @property
    def mirror(self) -> bool:
        return self._mirror

    @mirror.setter
    def mirror(self, value: bool) -> None:
        self._mirror = value

    @property
    def measured_fps(self) -> float:
        return self._fps

    @property
    def is_connected(self) -> bool:
        return self._open

    def open(self) -> None:
        self._open = True

    def read(self) -> np.ndarray | None:
        if not self._open:
            return None
        return self._frame.copy()

    def release(self) -> None:
        self._open = False

    def toggle_mirror(self) -> bool:
        self._mirror = not self._mirror
        return self._mirror

    def describe(self) -> str:
        return f"mock | 1280x720 | mirror {'on' if self._mirror else 'off'}"


class CameraSourceTests(unittest.TestCase):
    def test_camera_manager_lifecycle_with_mock_source(self) -> None:
        mock = MockCameraSource()
        manager = CameraManager(source=mock)
        self.assertFalse(mock.is_connected)

        manager.open()
        self.assertTrue(mock.is_connected)
        self.assertEqual(manager.width, 1280)
        self.assertEqual(manager.height, 720)

        frame = manager.read()
        self.assertIsNotNone(frame)
        self.assertEqual(frame.shape, (720, 1280, 3))

        # Mirror toggle
        self.assertFalse(manager.mirror)
        manager.toggle_mirror()
        self.assertTrue(manager.mirror)

        manager.release()
        self.assertFalse(mock.is_connected)

    def test_phone_camera_source_instantiation(self) -> None:
        phone_src = PhoneCameraSource(port=9443)
        self.assertEqual(phone_src.source_type, CameraSourceType.PHONE)
        self.assertIn("https://", phone_src.pairing_url)
        self.assertIn(":9443", phone_src.pairing_url)
        self.assertFalse(phone_src.is_connected)

    def test_camera_manager_phone_server_integration(self) -> None:
        mock = MockCameraSource()
        manager = CameraManager(source=mock)
        try:
            # pairing_url should guarantee server is listening over HTTPS
            url = manager.pairing_url
            self.assertIn("https://", url)
            self.assertTrue(manager.phone_server.is_running)
        finally:
            manager.release()
            self.assertFalse(manager.phone_server.is_running)


if __name__ == "__main__":
    unittest.main()
