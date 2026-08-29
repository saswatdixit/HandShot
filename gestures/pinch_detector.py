"""Natural, robust, and responsive thumb-and-index pinch detection for HANDSHOT (Phase 10)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

from config import settings

if TYPE_CHECKING:
    from camera.hand_tracker import Hand


class PinchPhase(Enum):
    """Explicit pinch lifecycle for debug HUD and game logic."""

    READY = auto()
    PINCHED = auto()
    AWAITING_RELEASE = auto()  # Kept for backward compatibility


@dataclass(frozen=True)
class PinchSettings:
    close_threshold: float = settings.PINCH_CLOSE_THRESHOLD
    release_threshold: float = settings.PINCH_RELEASE_THRESHOLD
    cooldown_seconds: float = settings.PINCH_COOLDOWN_SECONDS

    def __post_init__(self) -> None:
        if self.close_threshold <= 0 or self.release_threshold <= self.close_threshold:
            raise ValueError("release_threshold must be greater than close_threshold")
        if self.cooldown_seconds < 0:
            raise ValueError("cooldown_seconds cannot be negative")


@dataclass(frozen=True)
class PinchResult:
    """Detector state after one fresh hand-tracking sample."""

    phase: PinchPhase
    is_pinched: bool
    shot: bool
    normalized_distance: float | None
    raw_distance: float | None = None


class PinchDetector:
    """Generate exactly one shot per pinch: READY → PINCHED (fires shot) → release → READY.

    Designed for effortless, natural finger contact without forced squeezing,
    featuring scale/rotation-invariant normalization, lightweight noise filtering,
    and instantaneous single-frame re-arming.
    """

    def __init__(self, settings_: PinchSettings | None = None) -> None:
        self.settings = settings_ or PinchSettings()
        self._smoothed_dist: float | None = None
        self.reset()

    def reset(self) -> None:
        self._phase = PinchPhase.READY
        self._last_shot_time = -math.inf
        self._smoothed_dist = None

    @property
    def phase(self) -> PinchPhase:
        return self._phase

    def update(self, hand: Hand | None, now: float) -> PinchResult:
        """Process one tracked hand sample at monotonic time ``now``."""
        if hand is None:
            # Cleanly reset on tracking loss without stuck state or phantom shots
            self._phase = PinchPhase.READY
            self._smoothed_dist = None
            return PinchResult(self._phase, False, False, None, None)

        raw_distance = self._normalized_distance(hand)

        # Immediate threshold response with hysteresis and jitter suppression in hover zone
        if self._smoothed_dist is None:
            self._smoothed_dist = raw_distance
        else:
            if raw_distance <= self.settings.close_threshold or raw_distance >= self.settings.release_threshold:
                self._smoothed_dist = raw_distance
            else:
                self._smoothed_dist = 0.70 * raw_distance + 0.30 * self._smoothed_dist

        distance = self._smoothed_dist
        shot = False

        if self._phase is PinchPhase.READY:
            if distance <= self.settings.close_threshold:
                if now - self._last_shot_time >= self.settings.cooldown_seconds:
                    self._last_shot_time = now
                    shot = True
                    self._phase = PinchPhase.PINCHED
        elif self._phase in (PinchPhase.PINCHED, PinchPhase.AWAITING_RELEASE):
            if distance >= self.settings.release_threshold:
                self._phase = PinchPhase.READY

        is_pinched = (self._phase is PinchPhase.PINCHED)
        return PinchResult(self._phase, is_pinched, shot, distance, raw_distance)

    @staticmethod
    def _normalized_distance(hand: Hand) -> float:
        """Calculate scale-, distance-, and rotation-invariant pinch distance."""
        if hasattr(hand, "landmarks_px") and hand.landmarks_px is not None and len(hand.landmarks_px) == 21:
            pts = hand.landmarks_px
            thumb = (float(pts[settings.THUMB_TIP][0]), float(pts[settings.THUMB_TIP][1]))
            index = (float(pts[settings.INDEX_TIP][0]), float(pts[settings.INDEX_TIP][1]))
            wrist = (float(pts[settings.WRIST][0]), float(pts[settings.WRIST][1]))
            middle_mcp = (float(pts[settings.MIDDLE_MCP][0]), float(pts[settings.MIDDLE_MCP][1]))
            index_mcp = (float(pts[settings.INDEX_MCP][0]), float(pts[settings.INDEX_MCP][1]))
            pinky_mcp = (float(pts[settings.PINKY_MCP][0]), float(pts[settings.PINKY_MCP][1]))
        else:
            landmarks = hand.landmarks_norm
            thumb = (float(landmarks[settings.THUMB_TIP][0]), float(landmarks[settings.THUMB_TIP][1]))
            index = (float(landmarks[settings.INDEX_TIP][0]), float(landmarks[settings.INDEX_TIP][1]))
            wrist = (float(landmarks[settings.WRIST][0]), float(landmarks[settings.WRIST][1]))
            middle_mcp = (float(landmarks[settings.MIDDLE_MCP][0]), float(landmarks[settings.MIDDLE_MCP][1]))
            index_mcp = (float(landmarks[settings.INDEX_MCP][0]), float(landmarks[settings.INDEX_MCP][1]))
            pinky_mcp = (float(landmarks[settings.PINKY_MCP][0]), float(landmarks[settings.PINKY_MCP][1]))

        tip_distance = math.dist(thumb, index)
        palm_length = math.dist(wrist, middle_mcp)
        palm_width = math.dist(index_mcp, pinky_mcp)
        hand_scale = max(palm_length, palm_width * 1.25, 1e-6)
        return tip_distance / hand_scale
