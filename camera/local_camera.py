"""OpenCV local webcam source for HANDSHOT (Phase 12)."""

from __future__ import annotations

import platform
import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np

from camera.camera_source import CameraSource, CameraSourceType
from config import settings


class CameraError(RuntimeError):
    """Raised when a camera cannot be opened or stops delivering frames."""


if platform.system() == "Windows":
    _CAPTURE_BACKENDS = [
        ("MSMF", cv2.CAP_MSMF),
        ("DSHOW", cv2.CAP_DSHOW),
        ("ANY", cv2.CAP_ANY),
    ]
    _PROBE_BACKENDS = [
        ("DSHOW", cv2.CAP_DSHOW),
        ("MSMF", cv2.CAP_MSMF),
        ("ANY", cv2.CAP_ANY),
    ]
else:
    _CAPTURE_BACKENDS = [("ANY", cv2.CAP_ANY)]
    _PROBE_BACKENDS = [("ANY", cv2.CAP_ANY)]

BACKEND_NAMES = tuple(name for name, _ in _CAPTURE_BACKENDS)


@dataclass(frozen=True)
class CameraInfo:
    index: int
    width: int
    height: int
    backend: str

    def __str__(self) -> str:
        return f"[{self.index}] responds via {self.backend} ({self.width}x{self.height})"


class _FrameGrabber:
    def __init__(self, capture: cv2.VideoCapture) -> None:
        self._capture = capture
        self._condition = threading.Condition()
        self._frame: np.ndarray | None = None
        self._sequence = 0
        self.failures = 0
        self.consecutive_failures = 0
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, name="LocalCameraGrabber", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        with self._condition:
            self._condition.notify_all()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def next_frame(self, after_sequence: int, timeout: float) -> tuple[np.ndarray | None, int]:
        with self._condition:
            if not self._condition.wait_for(
                lambda: not self._running or self._sequence > after_sequence,
                timeout=timeout,
            ):
                return None, after_sequence
            if not self._running or self._frame is None:
                return None, self._sequence
            return self._frame.copy(), self._sequence

    def _loop(self) -> None:
        while self._running:
            ok, frame = self._capture.read()
            with self._condition:
                if ok and frame is not None:
                    self._frame = frame
                    self._sequence += 1
                    self.consecutive_failures = 0
                else:
                    self.failures += 1
                    self.consecutive_failures += 1
                self._condition.notify_all()


class LocalCameraSource(CameraSource):
    """Encapsulates local USB or built-in webcam capture via OpenCV."""

    def __init__(
        self,
        index: int = settings.DEFAULT_CAMERA_INDEX,
        width: int = settings.CAMERA_WIDTH,
        height: int = settings.CAMERA_HEIGHT,
        mirror: bool = settings.MIRROR_CAMERA,
        backend: str | None = None,
        threaded: bool = True,
    ) -> None:
        self.index = index
        self._req_width = width
        self._req_height = height
        self._width = width
        self._height = height
        self._mirror = mirror
        self._backend = backend
        self.threaded = threaded

        self._capture: cv2.VideoCapture | None = None
        self._grabber: _FrameGrabber | None = None
        self._backend_name = backend.upper() if backend else "auto"
        self._open_seconds = 0.0

        self.frames_read = 0
        self.frames_failed = 0
        self.frames_stalled = 0
        self._last_sequence = 0
        self._consecutive_stalls = 0
        self._direct_failures = 0
        self._consecutive_failures = 0

        self._fps: float = 0.0
        self._last_frame_time: float | None = None

    @property
    def source_type(self) -> CameraSourceType:
        return CameraSourceType.LOCAL

    @property
    def source_name(self) -> str:
        return f"Local Webcam ({self.index})"

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
        return self._fps

    @property
    def backend_name(self) -> str:
        return self._backend_name

    @property
    def open_seconds(self) -> float:
        return self._open_seconds

    @property
    def is_connected(self) -> bool:
        return self._capture is not None and self._capture.isOpened()

    def open(self) -> None:
        if self._capture is not None:
            return

        start = time.perf_counter()
        candidates = self._backends_to_try()
        for name, api in candidates:
            cap = cv2.VideoCapture(self.index, api)
            if cap.isOpened():
                self._capture = cap
                self._backend_name = name
                break
            cap.release()

        if self._capture is None or not self._capture.isOpened():
            tried = ", ".join(n for n, _ in candidates)
            raise CameraError(
                f"Could not open camera device {self.index} (tried backends: {tried}). "
                f"Check that the webcam is connected and not in use by another app."
            )

        self._configure_device(self._capture)
        self._warm_up()
        self._open_seconds = time.perf_counter() - start

        if self.threaded:
            self._grabber = _FrameGrabber(self._capture)
            self._grabber.start()

    def _backends_to_try(self) -> list[tuple[str, int]]:
        if self._backend is not None:
            target = self._backend.upper()
            for name, api in _CAPTURE_BACKENDS:
                if name == target:
                    return [(name, api)]
            return [("USER", cv2.CAP_ANY)]
        return list(_CAPTURE_BACKENDS)

    def _configure_device(self, capture: cv2.VideoCapture) -> None:
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self._req_width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self._req_height)
        capture.set(cv2.CAP_PROP_FPS, settings.CAMERA_FPS)
        try:
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

    def _warm_up(self) -> None:
        for _ in range(settings.CAMERA_WARMUP_FRAMES):
            if self._capture is None:
                return
            self._capture.read()
        self._last_frame_time = None

    def read(self) -> np.ndarray | None:
        if self._capture is None:
            raise CameraError("Camera is not open. Call open() first.")

        frame = self._read_threaded() if self._grabber is not None else self._read_direct()
        if frame is None:
            return None

        self.frames_read += 1
        self._height, self._width = frame.shape[:2]
        self._update_fps()

        if self._mirror:
            frame = cv2.flip(frame, 1)
        return frame

    def _read_threaded(self) -> np.ndarray | None:
        assert self._grabber is not None
        if self._grabber.consecutive_failures >= settings.CAMERA_READ_RETRIES:
            raise CameraError(f"Lost connection to camera {self.index} after {self._grabber.consecutive_failures} failed reads.")

        frame, seq = self._grabber.next_frame(self._last_sequence, settings.CAMERA_FRAME_TIMEOUT)
        if frame is None:
            self.frames_stalled += 1
            self._consecutive_stalls += 1
            if self._consecutive_stalls >= settings.CAMERA_READ_RETRIES:
                raise CameraError(f"Camera {self.index} delivered no frames for {self._consecutive_stalls * settings.CAMERA_FRAME_TIMEOUT:.1f}s.")
            return None

        self._consecutive_stalls = 0
        self._last_sequence = seq
        return frame

    def _read_direct(self) -> np.ndarray | None:
        assert self._capture is not None
        ok, frame = self._capture.read()
        if not ok or frame is None:
            self._direct_failures += 1
            self._consecutive_failures += 1
            if self._consecutive_failures >= settings.CAMERA_READ_RETRIES:
                raise CameraError(f"Lost connection to camera {self.index} after {self._consecutive_failures} failed reads.")
            return None
        self._consecutive_failures = 0
        return frame

    def _update_fps(self) -> None:
        now = time.perf_counter()
        if self._last_frame_time is not None:
            instant_fps = 1.0 / max(1e-6, now - self._last_frame_time)
            self._fps = (
                instant_fps
                if self._fps == 0.0
                else settings.FPS_SMOOTHING * self._fps + (1 - settings.FPS_SMOOTHING) * instant_fps
            )
        self._last_frame_time = now

    def release(self) -> None:
        if self._grabber is not None:
            self._grabber.stop()
            self._grabber = None
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def toggle_mirror(self) -> bool:
        self._mirror = not self._mirror
        return self._mirror

    def describe(self) -> str:
        return f"camera {self.index} | {self._width}x{self._height} | {self._backend_name} | mirror {'on' if self._mirror else 'off'}"

    @staticmethod
    def list_cameras(limit: int = settings.CAMERA_PROBE_LIMIT) -> list[CameraInfo]:
        found: list[CameraInfo] = []
        for idx in range(limit):
            for name, api in _PROBE_BACKENDS:
                cap = cv2.VideoCapture(idx, api)
                if cap.isOpened():
                    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    found.append(CameraInfo(index=idx, width=w, height=h, backend=name))
                    cap.release()
                    break
                cap.release()
        return found
