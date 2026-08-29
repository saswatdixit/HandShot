"""OpenCV webcam access for HANDSHOT (Phase 1).

Responsibilities (main.md section 3):
  * find available camera devices
  * open / close a device reliably
  * hand out BGR frames to the rest of the app
  * optional mirroring so hand movement feels natural (section 33)
  * clear errors instead of crashes when the camera is missing (section 45)

Nothing in here knows about hand tracking or the game.
"""

from __future__ import annotations

import platform
import sys
import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np

from config import settings


class CameraError(RuntimeError):
    """Raised when a camera cannot be opened or stops delivering frames."""


# Backend preference, measured on the dev machine (Windows 11, 1280x720):
#   MSMF  -> 29.7 fps, but ~6s to open
#   DSHOW -> 9.9 fps (stuck on YUY2; ignores MJPG requests), ~1.8s to open
# Frame rate matters far more than a one-off open delay (main.md sections 44
# and 53), so capture prefers MSMF. Device *probing* only needs to know a
# device answers, so it uses the fast-opening order to keep --list-cameras
# snappy. Cameras differ: --backend forces a specific one.
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


def _quiet_opencv() -> None:
    """Silence OpenCV's device-probe warnings; harmless if unavailable."""
    try:
        cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_SILENT)
    except Exception:  # pragma: no cover - depends on OpenCV build
        pass


@dataclass(frozen=True)
class CameraInfo:
    """A camera device that responded to a probe.

    The resolution is whatever the probe backend opened by default, not the
    device maximum, so it is only meant to help identify the device.
    """

    index: int
    width: int
    height: int
    backend: str

    def __str__(self) -> str:
        return (
            f"[{self.index}] responds via {self.backend} "
            f"(probe default {self.width}x{self.height})"
        )


class _FrameGrabber:
    """Pulls frames off the device on a background thread.

    `cap.read()` blocks until the driver has the next frame. Calling it inline
    means capture waiting and hand tracking never overlap. This grabber keeps
    only the newest frame, so consumers always get current data and never queue
    up stale frames (main.md section 44).
    """

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
            target=self._loop, name="handshot-capture", daemon=True
        )
        self._thread.start()

    def _loop(self) -> None:
        while self._running:
            ok, frame = self._capture.read()
            with self._condition:
                if not ok or frame is None:
                    self.failures += 1
                    self.consecutive_failures += 1
                else:
                    # cv2 allocates a new array per read, so handing this one
                    # to the consumer is safe - the grabber never touches it
                    # again.
                    self._frame = frame
                    self._sequence += 1
                    self.consecutive_failures = 0
                self._condition.notify_all()
            if not ok:
                time.sleep(0.005)  # don't spin on a failing device

    def next_frame(
        self, since: int, timeout: float
    ) -> tuple[np.ndarray | None, int]:
        """Return the newest frame newer than `since`, plus its sequence id."""
        with self._condition:
            if self._sequence == since:
                self._condition.wait(timeout)
            if self._sequence == since:
                return None, since  # stalled
            return self._frame, self._sequence

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.5)
            self._thread = None


class CameraManager:
    """Owns a single cv2.VideoCapture and serves frames from it."""

    def __init__(
        self,
        index: int = settings.DEFAULT_CAMERA_INDEX,
        width: int = settings.CAMERA_WIDTH,
        height: int = settings.CAMERA_HEIGHT,
        fps: int = settings.CAMERA_FPS,
        mirror: bool = settings.MIRROR_CAMERA,
        backend: str | None = None,
        threaded: bool = settings.CAMERA_THREADED,
    ) -> None:
        self.index = index
        self.requested_width = width
        self.requested_height = height
        self.requested_fps = fps
        self.mirror = mirror
        self.requested_backend = backend.upper() if backend else None
        self.threaded = threaded

        self._capture: cv2.VideoCapture | None = None
        self._grabber: _FrameGrabber | None = None
        self._last_sequence = 0
        self._backend_name = "none"
        self._width = 0
        self._height = 0
        self.open_seconds = 0.0

        self.frames_read = 0
        self.frames_stalled = 0
        self._direct_failures = 0
        self._consecutive_failures = 0
        self._consecutive_stalls = 0
        self._last_frame_time: float | None = None
        self._fps_estimate = 0.0

    @property
    def frames_failed(self) -> int:
        """Frames the driver refused to deliver."""
        if self._grabber is not None:
            return self._grabber.failures
        return self._direct_failures

    # -- lifecycle ---------------------------------------------------------

    def _backend_candidates(self) -> list[tuple[str, int]]:
        if self.requested_backend is None:
            return _CAPTURE_BACKENDS
        candidates = [b for b in _CAPTURE_BACKENDS if b[0] == self.requested_backend]
        if not candidates:
            raise CameraError(
                f"Unknown camera backend '{self.requested_backend}'. "
                f"Available: {', '.join(BACKEND_NAMES)}"
            )
        return candidates

    def open(self) -> None:
        """Open the device, or raise CameraError with a useful message."""
        if self.is_open:
            return

        _quiet_opencv()
        attempts: list[str] = []
        started = time.perf_counter()

        for name, backend in self._backend_candidates():
            capture = cv2.VideoCapture(self.index, backend)
            if not capture.isOpened():
                capture.release()
                attempts.append(f"{name}: could not open device")
                continue

            self._configure(capture)

            # An opened device that never yields a frame is still unusable
            # (common when another application already holds the camera).
            ok, frame = capture.read()
            if not ok or frame is None:
                capture.release()
                attempts.append(f"{name}: opened but delivered no frames")
                continue

            self._capture = capture
            self._backend_name = name
            self._height, self._width = frame.shape[:2]
            self._warm_up()
            if self.threaded:
                self._grabber = _FrameGrabber(capture)
                self._grabber.start()
            self.open_seconds = time.perf_counter() - started
            return

        detail = "; ".join(attempts) if attempts else "no backends available"
        raise CameraError(
            f"No camera detected at index {self.index}.\n"
            f"Please connect a webcam, close any app already using it, and try again.\n"
            f"(tried -> {detail})"
        )

    def _configure(self, capture: cv2.VideoCapture) -> None:
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.requested_width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.requested_height)
        capture.set(cv2.CAP_PROP_FPS, self.requested_fps)
        # Keep the driver queue short so we always process the newest frame;
        # a deep buffer shows up directly as aiming latency (section 44).
        try:
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:  # pragma: no cover - backend dependent
            pass

    def _warm_up(self) -> None:
        """Discard the first frames while exposure settles."""
        for _ in range(settings.CAMERA_WARMUP_FRAMES):
            if self._capture is None:
                return
            self._capture.read()
        self._last_frame_time = None

    def release(self) -> None:
        # Stop the grabber first so it cannot read from a released device.
        if self._grabber is not None:
            self._grabber.stop()
            self._grabber = None
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        # `_backend_name` is deliberately kept so diagnostics printed after
        # shutdown still report which backend was used.

    def __enter__(self) -> "CameraManager":
        self.open()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.release()

    # -- frames ------------------------------------------------------------

    def read(self) -> np.ndarray | None:
        """Return the next BGR frame.

        Returns None when no new frame is available yet, so the caller can
        simply try again. Raises CameraError once the device fails or stalls
        repeatedly.
        """
        if self._capture is None:
            raise CameraError("Camera is not open. Call open() first.")

        frame = (
            self._read_threaded() if self._grabber is not None else self._read_direct()
        )
        if frame is None:
            return None

        self.frames_read += 1
        self._height, self._width = frame.shape[:2]
        self._update_fps()

        if self.mirror:
            frame = cv2.flip(frame, 1)
        return frame

    def _read_threaded(self) -> np.ndarray | None:
        assert self._grabber is not None
        if self._grabber.consecutive_failures >= settings.CAMERA_READ_RETRIES:
            raise CameraError(
                f"Lost connection to camera {self.index} after "
                f"{self._grabber.consecutive_failures} failed reads."
            )

        frame, sequence = self._grabber.next_frame(
            self._last_sequence, settings.CAMERA_FRAME_TIMEOUT
        )
        if frame is None:
            self.frames_stalled += 1
            self._consecutive_stalls += 1
            if self._consecutive_stalls >= settings.CAMERA_READ_RETRIES:
                raise CameraError(
                    f"Camera {self.index} delivered no frames for "
                    f"{self._consecutive_stalls * settings.CAMERA_FRAME_TIMEOUT:.1f}s."
                )
            return None

        self._consecutive_stalls = 0
        self._last_sequence = sequence
        return frame

    def _read_direct(self) -> np.ndarray | None:
        assert self._capture is not None
        ok, frame = self._capture.read()
        if not ok or frame is None:
            self._direct_failures += 1
            self._consecutive_failures += 1
            if self._consecutive_failures >= settings.CAMERA_READ_RETRIES:
                raise CameraError(
                    f"Lost connection to camera {self.index} after "
                    f"{self._consecutive_failures} failed reads."
                )
            return None
        self._consecutive_failures = 0
        return frame

    def _update_fps(self) -> None:
        now = time.perf_counter()
        if self._last_frame_time is not None:
            delta = now - self._last_frame_time
            if delta > 0:
                instant = 1.0 / delta
                alpha = settings.FPS_SMOOTHING
                self._fps_estimate = (
                    instant if self._fps_estimate == 0.0
                    else alpha * self._fps_estimate + (1.0 - alpha) * instant
                )
        self._last_frame_time = now

    # -- state -------------------------------------------------------------

    @property
    def is_open(self) -> bool:
        return self._capture is not None and self._capture.isOpened()

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def backend_name(self) -> str:
        return self._backend_name

    @property
    def measured_fps(self) -> float:
        return self._fps_estimate

    def toggle_mirror(self) -> bool:
        self.mirror = not self.mirror
        return self.mirror

    def describe(self) -> str:
        return (
            f"camera {self.index} | {self.width}x{self.height} | "
            f"{self.backend_name} | mirror {'on' if self.mirror else 'off'}"
        )

    # -- discovery ---------------------------------------------------------

    @staticmethod
    def list_cameras(limit: int = settings.CAMERA_PROBE_LIMIT) -> list[CameraInfo]:
        """Probe device indices 0..limit-1 and report the ones that work."""
        _quiet_opencv()
        found: list[CameraInfo] = []

        for index in range(limit):
            for name, backend in _PROBE_BACKENDS:
                capture = cv2.VideoCapture(index, backend)
                if not capture.isOpened():
                    capture.release()
                    continue
                ok, frame = capture.read()
                capture.release()
                if ok and frame is not None:
                    height, width = frame.shape[:2]
                    found.append(CameraInfo(index, width, height, name))
                    break  # this index works; skip remaining backends
        return found


def select_camera_interactively(
    limit: int = settings.CAMERA_PROBE_LIMIT,
    stream=sys.stdout,
) -> int:
    """Ask the user which detected camera to use. Returns a device index."""
    cameras = CameraManager.list_cameras(limit)
    if not cameras:
        raise CameraError(
            "No camera detected.\n\nPlease connect a webcam and try again."
        )
    if len(cameras) == 1:
        print(f"Using the only camera found: {cameras[0]}", file=stream)
        return cameras[0].index

    print("Available cameras:", file=stream)
    for position, info in enumerate(cameras):
        print(f"  {position}) {info}", file=stream)

    while True:
        choice = input(f"Select camera [0-{len(cameras) - 1}] (Enter = 0): ").strip()
        if not choice:
            return cameras[0].index
        if choice.isdigit() and int(choice) < len(cameras):
            return cameras[int(choice)].index
        print("Invalid choice, try again.", file=stream)
