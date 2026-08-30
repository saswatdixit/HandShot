"""Unit tests for Camera Source abstractions and CameraManager."""

from __future__ import annotations

import contextlib
import io
import unittest
from unittest import mock

import numpy as np

from camera.camera_source import CameraSource, CameraSourceType
from camera.camera_manager import CameraManager, select_camera_interactively
from camera.local_camera import CameraError, CameraInfo


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


class SelectCameraInteractivelyTests(unittest.TestCase):
    """Regression cover for the multi-camera selection prompt.

    This path used to raise AttributeError because it printed `c.name`, a field
    CameraInfo has never had (it exposes index/width/height/backend).
    """

    def setUp(self) -> None:
        self._real_list = CameraManager.list_cameras

    def tearDown(self) -> None:
        CameraManager.list_cameras = self._real_list

    @staticmethod
    def _fake_list(cameras: list[CameraInfo]):
        return staticmethod(lambda limit=None: list(cameras))

    def test_single_camera_returns_index_without_prompting(self) -> None:
        CameraManager.list_cameras = self._fake_list([CameraInfo(3, 1280, 720, "DSHOW")])
        self.assertEqual(select_camera_interactively(), 3)

    def test_multiple_cameras_lists_and_selects_without_attribute_error(self) -> None:
        cams = [
            CameraInfo(0, 640, 480, "DSHOW"),
            CameraInfo(2, 1280, 720, "MSMF"),
        ]
        CameraManager.list_cameras = self._fake_list(cams)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), mock.patch("builtins.input", return_value="2"):
            self.assertEqual(select_camera_interactively(), 2)

        printed = buf.getvalue()
        for c in cams:
            self.assertIn(str(c.index), printed)
            self.assertIn(str(c.width), printed)
            self.assertIn(c.backend, printed)

    def test_non_contiguous_indices_are_offered_verbatim(self) -> None:
        """Camera indices need not be 0..n-1; the prompt must list the real ones."""
        CameraManager.list_cameras = self._fake_list([
            CameraInfo(0, 640, 480, "DSHOW"),
            CameraInfo(4, 640, 480, "DSHOW"),
        ])
        prompts: list[str] = []

        def fake_input(prompt: str = "") -> str:
            prompts.append(prompt)
            return "4"

        with contextlib.redirect_stdout(io.StringIO()), mock.patch("builtins.input", fake_input):
            self.assertEqual(select_camera_interactively(), 4)

        self.assertIn("4", prompts[0])

    def test_invalid_then_valid_input_retries(self) -> None:
        CameraManager.list_cameras = self._fake_list([
            CameraInfo(0, 640, 480, "DSHOW"),
            CameraInfo(1, 640, 480, "DSHOW"),
        ])
        with contextlib.redirect_stdout(io.StringIO()), \
                mock.patch("builtins.input", side_effect=["", "9", "abc", "1"]):
            self.assertEqual(select_camera_interactively(), 1)

    def test_no_cameras_raises_camera_error(self) -> None:
        CameraManager.list_cameras = self._fake_list([])
        with self.assertRaises(CameraError):
            select_camera_interactively()


if __name__ == "__main__":
    unittest.main()
