"""Spatial bottom reload zone detector based strictly on hand/wrist position for HANDSHOT."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from config import settings

if TYPE_CHECKING:
    from camera.hand_tracker import Hand


@dataclass(frozen=True)
class ReloadSettings:
    """Tuning parameters for spatial bottom reload zone with dwell and hysteresis."""

    zone_top: float = settings.RELOAD_ZONE_TOP
    zone_exit: float = settings.RELOAD_ZONE_EXIT
    dwell_seconds: float = settings.RELOAD_DWELL_SECONDS
    cooldown_seconds: float = settings.RELOAD_COOLDOWN_SECONDS

    def __post_init__(self) -> None:
        if not (0.0 < self.zone_exit < self.zone_top <= 1.0):
            raise ValueError("zone_exit must be strictly less than zone_top")
        if self.dwell_seconds < 0:
            raise ValueError("dwell_seconds cannot be negative")
        if self.cooldown_seconds < 0:
            raise ValueError("cooldown_seconds cannot be negative")


@dataclass(frozen=True)
class ReloadResult:
    """Snapshot of reload zone state."""

    in_zone: bool
    dwell_time: float
    progress: float
    reload_triggered: bool
    hand_y: float | None


class ReloadDetector:
    """Detects spatial reload by lowering the hand into the bottom reload zone.

    Rules:
    - Uses hand/wrist position ONLY (no finger-pose classification).
    - Entering zone ($y \\ge 0.80$) and dwelling for 300ms triggers reload.
    - Emits reload_triggered exactly ONCE per entry.
    - Re-arm requires hand to move back above exit line ($y \\le 0.70$).
    - Tracking loss cleanly clears dwell timer.
    """

    def __init__(self, settings_: ReloadSettings | None = None) -> None:
        self.settings = settings_ or ReloadSettings()
        self.reset()

    def reset(self) -> None:
        """Reset dwell timer, zone presence, and re-arm state."""
        self._in_zone = False
        self._dwell_time = 0.0
        self._is_rearmed = True
        self._last_reload_time = -math.inf

    @property
    def in_zone(self) -> bool:
        return self._in_zone

    @property
    def dwell_time(self) -> float:
        return self._dwell_time

    def update(
        self,
        hand: Hand | None,
        delta_seconds: float,
        now: float,
    ) -> ReloadResult:
        """Process one tracking frame."""
        if hand is None:
            self._dwell_time = 0.0
            self._in_zone = False
            self._is_rearmed = True
            return ReloadResult(
                in_zone=False,
                dwell_time=0.0,
                progress=0.0,
                reload_triggered=False,
                hand_y=None,
            )

        hand_y = self._get_hand_y(hand)
        dt = max(0.0, delta_seconds)
        reload_triggered = False

        if hand_y >= self.settings.zone_top:
            self._in_zone = True
            self._dwell_time += dt
            if self._dwell_time >= self.settings.dwell_seconds and self._is_rearmed:
                if now - self._last_reload_time >= self.settings.cooldown_seconds:
                    reload_triggered = True
                    self._last_reload_time = now
                    self._is_rearmed = False
        elif hand_y <= self.settings.zone_exit:
            self._in_zone = False
            self._dwell_time = 0.0
            self._is_rearmed = True
        else:
            # In hysteresis buffer [zone_exit, zone_top]
            if not self._in_zone:
                self._dwell_time = 0.0

        progress = min(1.0, self._dwell_time / max(1e-4, self.settings.dwell_seconds)) if self._in_zone else 0.0

        return ReloadResult(
            in_zone=self._in_zone,
            dwell_time=self._dwell_time,
            progress=progress,
            reload_triggered=reload_triggered,
            hand_y=hand_y,
        )

    @staticmethod
    def _get_hand_y(hand: Hand) -> float:
        """Extract vertical position of hand using wrist/palm center."""
        if hasattr(hand, "landmarks_norm") and hand.landmarks_norm is not None and len(hand.landmarks_norm) == 21:
            wrist_y = float(hand.landmarks_norm[settings.WRIST][1])
            mcp_y = float(hand.landmarks_norm[settings.MIDDLE_MCP][1])
            return (wrist_y + mcp_y) / 2.0
        elif hasattr(hand, "landmarks_px") and hand.landmarks_px is not None and len(hand.landmarks_px) == 21:
            frame_h = float(hand.frame_size[1]) if hasattr(hand, "frame_size") and hand.frame_size[1] > 0 else 720.0
            wrist_y = float(hand.landmarks_px[settings.WRIST][1]) / frame_h
            mcp_y = float(hand.landmarks_px[settings.MIDDLE_MCP][1]) / frame_h
            return (wrist_y + mcp_y) / 2.0
        return 0.5
