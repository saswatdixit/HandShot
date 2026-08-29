"""Natural, robust, and responsive thumb-and-index pinch detection for HANDSHOT."""

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
    debounce_frames: int = settings.PINCH_DEBOUNCE_FRAMES
    release_stable_frames: int = settings.PINCH_RELEASE_STABLE_FRAMES

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

    Features:
    - Distance- and rotation-invariant composite hand scaling (palm length, knuckle width, bone span)
    - Hysteresis: separate close and release thresholds to prevent state oscillation
    - Debouncing: fast temporal confirmation rejecting isolated 1-frame spikes
    - Clean tracking loss handling: resets state without generating phantom shots
    """

    def __init__(self, settings_: PinchSettings | None = None) -> None:
        self.settings = settings_ or PinchSettings()
        self._smoothed_dist: float | None = None
        self._close_confirm_count = 0
        self._release_confirm_count = 0
        self.reset()

    def reset(self) -> None:
        self._phase = PinchPhase.READY
        self._last_shot_time = -math.inf
        self._smoothed_dist = None
        self._close_confirm_count = 0
        self._release_confirm_count = 0

    @property
    def phase(self) -> PinchPhase:
        return self._phase

    def update(self, hand: Hand | None, now: float) -> PinchResult:
        """Process one tracked hand sample at monotonic time ``now``."""
        if hand is None:
            # Cleanly reset on tracking loss without stuck state or phantom shots
            self._phase = PinchPhase.READY
            self._smoothed_dist = None
            self._close_confirm_count = 0
            self._release_confirm_count = 0
            return PinchResult(self._phase, False, False, None, None)

        raw_distance = self._normalized_distance(hand)

        # Light filter in the ambiguous hover zone, immediate passthrough at thresholds
        if self._smoothed_dist is None:
            self._smoothed_dist = raw_distance
        else:
            if raw_distance <= self.settings.close_threshold or raw_distance >= self.settings.release_threshold:
                self._smoothed_dist = raw_distance
            else:
                self._smoothed_dist = 0.75 * raw_distance + 0.25 * self._smoothed_dist

        distance = self._smoothed_dist
        shot = False

        if self._phase is PinchPhase.READY:
            if distance <= self.settings.close_threshold:
                self._close_confirm_count += 1
                if self._close_confirm_count >= self.settings.debounce_frames:
                    if now - self._last_shot_time >= self.settings.cooldown_seconds:
                        self._last_shot_time = now
                        shot = True
                        self._phase = PinchPhase.PINCHED
                        self._close_confirm_count = 0
                        self._release_confirm_count = 0
            else:
                self._close_confirm_count = 0

        elif self._phase in (PinchPhase.PINCHED, PinchPhase.AWAITING_RELEASE):
            if distance >= self.settings.release_threshold:
                self._release_confirm_count += 1
                if self._release_confirm_count >= self.settings.release_stable_frames:
                    self._phase = PinchPhase.READY
                    self._release_confirm_count = 0
                    self._close_confirm_count = 0
            else:
                self._release_confirm_count = 0

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
            index_pip = (float(pts[settings.INDEX_PIP][0]), float(pts[settings.INDEX_PIP][1]))
        else:
            landmarks = hand.landmarks_norm
            thumb = (float(landmarks[settings.THUMB_TIP][0]), float(landmarks[settings.THUMB_TIP][1]))
            index = (float(landmarks[settings.INDEX_TIP][0]), float(landmarks[settings.INDEX_TIP][1]))
            wrist = (float(landmarks[settings.WRIST][0]), float(landmarks[settings.WRIST][1]))
            middle_mcp = (float(landmarks[settings.MIDDLE_MCP][0]), float(landmarks[settings.MIDDLE_MCP][1]))
            index_mcp = (float(landmarks[settings.INDEX_MCP][0]), float(landmarks[settings.INDEX_MCP][1]))
            pinky_mcp = (float(landmarks[settings.PINKY_MCP][0]), float(landmarks[settings.PINKY_MCP][1]))
            index_pip = (float(landmarks[settings.INDEX_PIP][0]), float(landmarks[settings.INDEX_PIP][1]))

        tip_distance = math.dist(thumb, index)
        palm_length = math.dist(wrist, middle_mcp)
        palm_width = math.dist(index_mcp, pinky_mcp)

        # Proximal bone length if available
        index_proximal = math.dist(index_mcp, index_pip) if index_pip != (0.0, 0.0) else 0.0

        # Composite scale metric invariant to hand tilt and distance
        hand_scale = max(
            palm_length,
            palm_width * 1.15,
            index_proximal * 2.8,
            1e-6,
        )
        return tip_distance / hand_scale
