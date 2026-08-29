"""MediaPipe hand tracking for HANDSHOT (Phase 2).

Wraps the MediaPipe Tasks HandLandmarker so the rest of the app never touches
MediaPipe types directly. It hands back a plain `Hand` object with landmark
coordinates in both normalized and pixel space, plus the index fingertip that
Phase 3 will turn into the crosshair.

Note on API choice: mediapipe 1.x removed the old `mp.solutions.hands` module,
so the Tasks API is used. It needs a `hand_landmarker.task` model bundle, which
`ensure_model()` downloads once into assets/models/.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from config import settings


class HandTrackerError(RuntimeError):
    """Raised when the hand tracking model cannot be loaded."""


# --------------------------------------------------------------------------
# Model file
# --------------------------------------------------------------------------


def ensure_model(
    path: Path = settings.HAND_MODEL_PATH,
    url: str = settings.HAND_MODEL_URL,
    quiet: bool = False,
) -> Path:
    """Return the model path, downloading the bundle on first run."""
    if path.exists() and path.stat().st_size > 0:
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".part")
    if not quiet:
        print(f"Downloading hand tracking model to {path} ...")

    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            partial.write_bytes(response.read())
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        partial.unlink(missing_ok=True)
        raise HandTrackerError(
            f"Could not download the hand tracking model.\n"
            f"Reason: {exc}\n"
            f"Download it manually from:\n  {url}\n"
            f"and save it as:\n  {path}"
        ) from exc

    partial.replace(path)
    if not quiet:
        print(f"Model ready ({path.stat().st_size / 1_000_000:.1f} MB).")
    return path


# --------------------------------------------------------------------------
# Result types
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Hand:
    """One detected hand in a single frame."""

    # (21, 3) normalized coordinates: x, y in [0, 1] image space, z relative
    # depth. Values can fall slightly outside [0, 1] when the hand is partly
    # out of frame, so clamp only where it matters (e.g. drawing).
    landmarks_norm: np.ndarray
    # (21, 2) integer pixel coordinates in the frame the hand came from.
    landmarks_px: np.ndarray
    # The user's actual hand ("Left"/"Right"), already corrected for mirroring.
    handedness: str
    score: float
    frame_size: tuple[int, int]  # (width, height)

    def point_norm(self, index: int) -> np.ndarray:
        return self.landmarks_norm[index]

    def point_px(self, index: int) -> tuple[int, int]:
        x, y = self.landmarks_px[index]
        return int(x), int(y)

    @property
    def index_tip_norm(self) -> np.ndarray:
        """Normalized index fingertip - the aiming reference point."""
        return self.landmarks_norm[settings.INDEX_TIP]

    @property
    def index_tip_px(self) -> tuple[int, int]:
        return self.point_px(settings.INDEX_TIP)

    @property
    def thumb_tip_px(self) -> tuple[int, int]:
        return self.point_px(settings.THUMB_TIP)

    @property
    def wrist_px(self) -> tuple[int, int]:
        return self.point_px(settings.WRIST)

    @property
    def bbox_px(self) -> tuple[int, int, int, int]:
        """(x_min, y_min, x_max, y_max) around all landmarks."""
        xs, ys = self.landmarks_px[:, 0], self.landmarks_px[:, 1]
        return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


@dataclass(frozen=True)
class TrackingResult:
    """What the tracker knows after processing one frame."""

    hand: Hand | None
    fresh: bool  # True when this frame produced a new detection
    stale_frames: int  # frames since the last fresh detection
    process_ms: float

    @property
    def has_hand(self) -> bool:
        return self.hand is not None

    @property
    def coasting(self) -> bool:
        """Reusing the last known hand during a short tracking dropout."""
        return self.hand is not None and not self.fresh


# --------------------------------------------------------------------------
# Tracker
# --------------------------------------------------------------------------


class HandTracker:
    """Detects and tracks one primary hand across a video stream."""

    def __init__(
        self,
        model_path: Path | None = None,
        max_hands: int = settings.MAX_HANDS,
        detection_confidence: float = settings.MIN_HAND_DETECTION_CONFIDENCE,
        presence_confidence: float = settings.MIN_HAND_PRESENCE_CONFIDENCE,
        tracking_confidence: float = settings.MIN_TRACKING_CONFIDENCE,
        grace_frames: int = settings.TRACKING_GRACE_FRAMES,
        input_width: int | None = settings.TRACKING_INPUT_WIDTH,
        auto_download: bool = True,
    ) -> None:
        path = Path(model_path) if model_path else settings.HAND_MODEL_PATH
        if auto_download:
            path = ensure_model(path)
        elif not path.exists():
            raise HandTrackerError(f"Hand tracking model not found: {path}")

        options = vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(path)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=max_hands,
            min_hand_detection_confidence=detection_confidence,
            min_hand_presence_confidence=presence_confidence,
            min_tracking_confidence=tracking_confidence,
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)
        self._closed = False

        self.grace_frames = grace_frames
        self.input_width = input_width
        self.model_path = path

        self._last_hand: Hand | None = None
        self._stale_frames = 0
        self._last_timestamp_ms = -1

        # Simple counters, useful for the diagnostics report.
        self.frames_processed = 0
        self.frames_with_hand = 0

    # -- processing --------------------------------------------------------

    def process(
        self,
        frame_bgr: np.ndarray,
        timestamp_ms: int | None = None,
        mirrored: bool = False,
    ) -> TrackingResult:
        """Run hand tracking on one BGR frame.

        `mirrored` tells the tracker the frame was horizontally flipped, so the
        handedness label can be corrected to the user's real hand.
        """
        if self._closed:
            raise HandTrackerError("HandTracker is closed.")

        started = time.perf_counter()
        height, width = frame_bgr.shape[:2]

        # Track on a smaller copy when the frame is large. Landmarks are
        # normalized, so pixel coordinates are still derived from the original
        # frame size and line up with what the player sees.
        source = frame_bgr
        if self.input_width and width > self.input_width:
            scaled_height = max(1, round(height * self.input_width / width))
            source = cv2.resize(
                frame_bgr, (self.input_width, scaled_height),
                interpolation=cv2.INTER_LINEAR,
            )

        rgb = np.ascontiguousarray(source[:, :, ::-1])
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        # VIDEO mode requires strictly increasing timestamps.
        stamp = timestamp_ms if timestamp_ms is not None else int(time.perf_counter() * 1000)
        if stamp <= self._last_timestamp_ms:
            stamp = self._last_timestamp_ms + 1
        self._last_timestamp_ms = stamp

        result = self._landmarker.detect_for_video(mp_image, stamp)
        self.frames_processed += 1

        hand = self._build_primary_hand(result, width, height, mirrored)
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        if hand is not None:
            self.frames_with_hand += 1
            self._last_hand = hand
            self._stale_frames = 0
            return TrackingResult(hand, True, 0, elapsed_ms)

        # No detection this frame: hold the last known hand briefly so the aim
        # point does not jump around (main.md section 45).
        self._stale_frames += 1
        if self._last_hand is not None and self._stale_frames <= self.grace_frames:
            return TrackingResult(self._last_hand, False, self._stale_frames, elapsed_ms)

        self._last_hand = None
        return TrackingResult(None, False, self._stale_frames, elapsed_ms)

    def _build_primary_hand(
        self,
        result: vision.HandLandmarkerResult,
        width: int,
        height: int,
        mirrored: bool,
    ) -> Hand | None:
        """Convert MediaPipe output into a single `Hand`, or None."""
        if not result.hand_landmarks:
            return None

        candidates: list[Hand] = []
        for position, landmarks in enumerate(result.hand_landmarks):
            if len(landmarks) != settings.LANDMARK_COUNT:
                continue

            norm = np.array(
                [(lm.x, lm.y, lm.z) for lm in landmarks], dtype=np.float32
            )
            pixels = np.rint(norm[:, :2] * np.array([width, height])).astype(np.int32)

            label, score = "unknown", 0.0
            if position < len(result.handedness) and result.handedness[position]:
                category = result.handedness[position][0]
                label, score = category.category_name, float(category.score)
                # MediaPipe labels assume an unmirrored image, so a flipped
                # frame reports the opposite hand.
                if mirrored:
                    label = {"Left": "Right", "Right": "Left"}.get(label, label)

            candidates.append(
                Hand(
                    landmarks_norm=norm,
                    landmarks_px=pixels,
                    handedness=label,
                    score=score,
                    frame_size=(width, height),
                )
            )

        if not candidates:
            return None
        # With several hands in view, prefer the closest one - largest landmark
        # bounding box (main.md section 45).
        return max(candidates, key=_bbox_area)

    # -- state -------------------------------------------------------------

    @property
    def detection_rate(self) -> float:
        if self.frames_processed == 0:
            return 0.0
        return self.frames_with_hand / self.frames_processed

    def reset(self) -> None:
        """Forget the last known hand (e.g. after switching camera)."""
        self._last_hand = None
        self._stale_frames = 0

    def close(self) -> None:
        if not self._closed:
            self._landmarker.close()
            self._closed = True

    def __enter__(self) -> "HandTracker":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def _bbox_area(hand: Hand) -> int:
    x_min, y_min, x_max, y_max = hand.bbox_px
    return max(0, x_max - x_min) * max(0, y_max - y_min)
