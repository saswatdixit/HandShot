"""Mobile webcam phone stream source for HANDSHOT (Phase 13)."""

from __future__ import annotations

import time
import cv2
import numpy as np

from camera.camera_source import CameraSource, CameraSourceType
from camera.phone_server import PhoneStreamServer
from config import settings


class PhoneCameraSource(CameraSource):
    """Encapsulates wireless mobile phone camera streaming over local network."""

    def __init__(
        self,
        port: int = 8088,
        mirror: bool = False,
        server: PhoneStreamServer | None = None,
    ) -> None:
        if server is not None:
            self.server = server
        elif port != 8088:
            self.server = PhoneStreamServer(port=port)
        else:
            self.server = PhoneStreamServer.get_instance(port=port)

        self._mirror = mirror
        self._last_sequence = 0
        self._width = settings.CAMERA_WIDTH
        self._height = settings.CAMERA_HEIGHT
        self.frames_read = 0
        self.frames_stalled = 0
        self.frames_failed = 0

    @property
    def source_type(self) -> CameraSourceType:
        return CameraSourceType.PHONE

    @property
    def source_name(self) -> str:
        facing = self.server.facing_mode.capitalize()
        return f"Phone Camera ({facing})"

    @property
    def pairing_url(self) -> str:
        return self.server.pairing_url

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def mirror(self) -> bool:
        return self._mirror

    @mirror.setter
    def mirror(self, value: bool) -> None:
        self._mirror = value

    @property
    def measured_fps(self) -> float:
        return self.server.measured_fps

    @property
    def is_connected(self) -> bool:
        return self.server.is_connected

    @property
    def facing_mode(self) -> str:
        return self.server.facing_mode

    @property
    def client_ip(self) -> str | None:
        return self.server.client_ip

    def open(self) -> None:
        self.server.start()

    def read(self) -> np.ndarray | None:
        frame, seq = self.server.get_latest_frame()
        if frame is None or seq == self._last_sequence:
            return None

        self._last_sequence = seq
        self.frames_read += 1
        self._height, self._width = frame.shape[:2]

        if self._mirror:
            frame = cv2.flip(frame, 1)

        return frame

    def release(self) -> None:
        pass

    def toggle_mirror(self) -> bool:
        self._mirror = not self._mirror
        return self._mirror

    def describe(self) -> str:
        status = "STREAMING" if self.is_connected else "WAITING"
        return f"phone {self.server.pairing_url} | {self._width}x{self._height} | {status} | mirror {'on' if self._mirror else 'off'}"
