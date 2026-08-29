"""Unified Camera Manager supporting local USB/built-in webcams and wireless phone cameras (Phase 13)."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import numpy as np

from camera.camera_source import CameraSource, CameraSourceType
from camera.local_camera import (
    BACKEND_NAMES,
    CameraError,
    CameraInfo,
    LocalCameraSource,
)
from camera.phone_camera import PhoneCameraSource
from camera.phone_server import PhoneStreamServer
from config import settings

if TYPE_CHECKING:
    pass


class CameraManager:
    """Master video feed coordinator for local webcams and mobile camera streaming."""

    def __init__(
        self,
        index: int = settings.DEFAULT_CAMERA_INDEX,
        width: int = settings.CAMERA_WIDTH,
        height: int = settings.CAMERA_HEIGHT,
        mirror: bool = settings.MIRROR_CAMERA,
        backend: str | None = None,
        threaded: bool = True,
        source: CameraSource | None = None,
    ) -> None:
        self._local_index = index
        self._req_width = width
        self._req_height = height
        self._req_mirror = mirror
        self._backend = backend
        self.threaded = threaded
        self._phone_server = PhoneStreamServer.get_instance(port=8088)
        self.ensure_phone_server_started()

        if source is not None:
            self._source: CameraSource = source
        else:
            self._source = LocalCameraSource(
                index=index,
                width=width,
                height=height,
                mirror=mirror,
                backend=backend,
                threaded=threaded,
            )

    @property
    def source(self) -> CameraSource:
        return self._source

    @property
    def source_type(self) -> CameraSourceType:
        return self._source.source_type

    @property
    def is_phone(self) -> bool:
        return self._source.source_type is CameraSourceType.PHONE

    @property
    def phone_source(self) -> PhoneCameraSource | None:
        if isinstance(self._source, PhoneCameraSource):
            return self._source
        return None

    @property
    def phone_server(self) -> PhoneStreamServer:
        return self._phone_server

    @property
    def pairing_url(self) -> str:
        """Return live pairing URL, ensuring the HTTP server is actively listening on 0.0.0.0."""
        self.ensure_phone_server_started()
        return self._phone_server.pairing_url

    def ensure_phone_server_started(self) -> None:
        """Guarantee that the phone streaming server is active and listening."""
        if not self._phone_server.is_running:
            self._phone_server.start()

    @property
    def index(self) -> int:
        if isinstance(self._source, LocalCameraSource):
            return self._source.index
        return 0

    @property
    def width(self) -> int:
        return self._source.width

    @property
    def height(self) -> int:
        return self._source.height

    @property
    def mirror(self) -> bool:
        return self._source.mirror

    @mirror.setter
    def mirror(self, value: bool) -> None:
        self._source.mirror = value

    @property
    def measured_fps(self) -> float:
        return self._source.measured_fps

    @property
    def backend_name(self) -> str:
        if isinstance(self._source, LocalCameraSource):
            return self._source.backend_name
        return "PHONE_NET"

    @property
    def open_seconds(self) -> float:
        if isinstance(self._source, LocalCameraSource):
            return self._source.open_seconds
        return 0.1

    @property
    def frames_read(self) -> int:
        return getattr(self._source, "frames_read", 0)

    @property
    def frames_failed(self) -> int:
        return getattr(self._source, "frames_failed", 0)

    @property
    def frames_stalled(self) -> int:
        return getattr(self._source, "frames_stalled", 0)

    def open(self) -> None:
        self._source.open()

    def read(self) -> np.ndarray | None:
        return self._source.read()

    def release(self) -> None:
        self._source.release()
        if self._phone_server.is_running:
            self._phone_server.stop()

    def toggle_mirror(self) -> bool:
        return self._source.toggle_mirror()

    def describe(self) -> str:
        return self._source.describe()

    def __enter__(self) -> "CameraManager":
        self.open()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.release()

    def use_local_camera(self, index: int = 0) -> None:
        """Switch to a local OpenCV webcam."""
        if isinstance(self._source, LocalCameraSource) and self._source.index == index:
            return
        old_mirror = self._source.mirror
        self._source.release()
        self._source = LocalCameraSource(
            index=index,
            width=self._req_width,
            height=self._req_height,
            mirror=old_mirror,
            backend=self._backend,
            threaded=self.threaded,
        )
        self._source.open()

    def use_phone_camera(self, port: int = 8088) -> None:
        """Switch to a mobile phone camera stream over USB/ADB or LAN network."""
        if isinstance(self._source, PhoneCameraSource):
            return
        old_mirror = self._source.mirror
        self._source.release()
        self._source = PhoneCameraSource(port=port, mirror=old_mirror, server=self._phone_server)
        self._source.open()

    @staticmethod
    def list_cameras(limit: int = settings.CAMERA_PROBE_LIMIT) -> list[CameraInfo]:
        return LocalCameraSource.list_cameras(limit)


def select_camera_interactively() -> int:
    """Prompt user to choose a connected local camera index."""
    cameras = CameraManager.list_cameras()
    if not cameras:
        raise CameraError("No camera detected on your system.")
    if len(cameras) == 1:
        return cameras[0].index

    print("\nAvailable cameras:")
    for info in cameras:
        print(f"  {info}")
    while True:
        try:
            choice = input(f"\nSelect camera index [default {cameras[0].index}]: ").strip()
            if not choice:
                return cameras[0].index
            idx = int(choice)
            if any(c.index == idx for c in cameras):
                return idx
            print(f"Invalid index. Choose from: {[c.index for c in cameras]}")
        except ValueError:
            print("Please enter a valid numeric camera index.")
