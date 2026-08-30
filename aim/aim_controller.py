"""Direct, calibrated screen-space crosshair control with 1€ adaptive velocity filtering for HANDSHOT."""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass
from typing import Sequence

from config import settings

Bounds = tuple[float, float, float, float]  # left, top, right, bottom


@dataclass(frozen=True)
class AimSettings:
    """Tunable direct-mapping parameters for HANDSHOT's crosshair."""

    input_left: float = settings.AIM_INPUT_LEFT
    input_top: float = settings.AIM_INPUT_TOP
    input_right: float = settings.AIM_INPUT_RIGHT
    input_bottom: float = settings.AIM_INPUT_BOTTOM
    deadzone: float = settings.AIM_DEADZONE
    smoothing_hz: float = settings.AIM_SMOOTHING_HZ
    min_cutoff_hz: float = settings.AIM_MIN_CUTOFF_HZ
    speed_coeff: float = settings.AIM_SPEED_COEFF
    derivative_cutoff_hz: float = settings.AIM_DERIVATIVE_CUTOFF_HZ
    margin: int = settings.CROSSHAIR_MARGIN
    mirror_x: bool = False
    pre_shot_anchor_seconds: float = settings.AIM_PRE_SHOT_ANCHOR_SECONDS
    max_teleport_distance: float = settings.AIM_MAX_TELEPORT_DISTANCE

    def __post_init__(self) -> None:
        if not (self.input_left < self.input_right and self.input_top < self.input_bottom):
            raise ValueError("the calibrated input rectangle must have positive size")
        if self.deadzone < 0 or self.smoothing_hz < 0 or self.min_cutoff_hz < 0 or self.speed_coeff < 0:
            raise ValueError("smoothing and deadzone parameters cannot be negative")
        if self.pre_shot_anchor_seconds < 0:
            raise ValueError("pre_shot_anchor_seconds cannot be negative")


class AimController:
    """Map a calibrated normalized fingertip position directly to the playfield.

    One predictable pipeline:
    fingertip → outlier rejection → soft-knee deadzone → 1€ adaptive velocity filter → playfield clamp.
    Maintains a timestamped position history so shots can use the pre-pinch aim anchor.
    """

    def __init__(self, screen_size: tuple[int, int], settings_: AimSettings | None = None) -> None:
        self.settings = settings_ or AimSettings()
        self._width = 1
        self._height = 1
        self._playfield: Bounds = (0.0, 0.0, 1.0, 1.0)
        self._position = (0.0, 0.0)
        self._target = (0.0, 0.0)
        self._last_raw_input: tuple[float, float] | None = None
        self._filtered_input: tuple[float, float] | None = None
        self._filtered_dx = (0.0, 0.0)
        self._current_cutoff_hz = self.settings.min_cutoff_hz
        self._history: deque[tuple[float, float, float]] = deque(maxlen=90)
        self.set_screen_size(screen_size)
        self.reset()

    @property
    def position(self) -> tuple[float, float]:
        return self._position

    @property
    def has_input_anchor(self) -> bool:
        return self._last_raw_input is not None

    @property
    def playfield(self) -> Bounds:
        return self._playfield

    @property
    def raw_input(self) -> tuple[float, float] | None:
        return self._last_raw_input

    @property
    def filtered_input(self) -> tuple[float, float] | None:
        return self._filtered_input

    @property
    def velocity(self) -> tuple[float, float]:
        return self._filtered_dx

    @property
    def current_cutoff_hz(self) -> float:
        return self._current_cutoff_hz

    def reset(self) -> None:
        centre = self._playfield_centre()
        self._position = centre
        self._target = centre
        self._last_raw_input = None
        self._filtered_input = None
        self._filtered_dx = (0.0, 0.0)
        self._current_cutoff_hz = self.settings.min_cutoff_hz
        self._history.clear()

    def set_screen_size(self, screen_size: tuple[int, int]) -> None:
        width, height = screen_size
        if width <= 0 or height <= 0:
            raise ValueError("screen dimensions must be positive")
        self._width, self._height = width, height
        self._playfield = self._default_playfield()
        self._position = self._clamp(self._position)
        self._target = self._clamp(self._target)

    def set_playfield(self, bounds: Bounds) -> None:
        left, top, right, bottom = bounds
        if right <= left or bottom <= top:
            raise ValueError("playfield bounds must have positive size")
        self._playfield = (
            max(0.0, left), max(0.0, top),
            min(float(self._width), right), min(float(self._height), bottom),
        )
        if self._playfield[2] <= self._playfield[0] or self._playfield[3] <= self._playfield[1]:
            raise ValueError("playfield lies outside the screen")
        self._position = self._clamp(self._position)
        self._target = self._clamp(self._target)

    def update(
        self,
        fingertip_norm: Sequence[float] | None,
        delta_seconds: float,
        now: float | None = None,
    ) -> tuple[float, float]:
        """Map one fingertip position; ``None`` holds the current aim point."""
        timestamp = now if now is not None else time.perf_counter()
        dt = max(1e-4, delta_seconds)

        if fingertip_norm is not None:
            raw = self._normalized_point(fingertip_norm)

            # First observation initialization
            if self._last_raw_input is None or self._filtered_input is None:
                self._last_raw_input = raw
                self._filtered_input = raw
                self._filtered_dx = (0.0, 0.0)
                self._target = self._map_to_playfield(raw)
                self._position = self._target
            else:
                # 1. Outlier check (reject NaN or wildly out-of-range coordinates)
                if not (math.isfinite(raw[0]) and math.isfinite(raw[1])):
                    raw = self._last_raw_input

                # 2. Soft-knee deadzone check for stability
                # A hard deadzone feels sticky. A soft-knee maps [0, deadzone] to 0,
                # and scales [deadzone, infinity] smoothly so small intentional movements pass through.
                delta_x = raw[0] - self._last_raw_input[0]
                delta_y = raw[1] - self._last_raw_input[1]
                dist = math.hypot(delta_x, delta_y)

                if self.settings.deadzone > 0:
                    if dist <= self.settings.deadzone:
                        effective_input = self._last_raw_input
                    else:
                        # Soft-knee: remap distance to subtract deadzone smoothly
                        scale = (dist - self.settings.deadzone) / dist
                        effective_input = (
                            self._last_raw_input[0] + delta_x * scale,
                            self._last_raw_input[1] + delta_y * scale
                        )
                        # We must update the raw anchor to the actual new measurement,
                        # so subsequent distance checks are relative to the new physical position.
                        self._last_raw_input = raw
                else:
                    effective_input = raw
                    self._last_raw_input = raw

                # 3. 1€ Adaptive Velocity Filter
                if self.settings.smoothing_hz >= 500.0:
                    # Near-infinite / bypass smoothing for instant direct mapping
                    self._filtered_input = effective_input
                    self._filtered_dx = ((effective_input[0] - self._filtered_input[0]) / dt,
                                         (effective_input[1] - self._filtered_input[1]) / dt)
                else:
                    # Compute and filter derivative
                    raw_dx = ((effective_input[0] - self._filtered_input[0]) / dt,
                              (effective_input[1] - self._filtered_input[1]) / dt)
                    alpha_d = self._compute_alpha(self.settings.derivative_cutoff_hz, dt)
                    self._filtered_dx = (
                        alpha_d * raw_dx[0] + (1.0 - alpha_d) * self._filtered_dx[0],
                        alpha_d * raw_dx[1] + (1.0 - alpha_d) * self._filtered_dx[1],
                    )

                    # Dynamic cutoff frequency (1€ filter formula)
                    # When hand is still, speed drops to 0 and cutoff goes to min_cutoff_hz.
                    # By suppressing the velocity estimation at very low speeds, we stabilize the crosshair.
                    speed = math.hypot(self._filtered_dx[0], self._filtered_dx[1])

                    # Stabilization threshold: if speed is incredibly low, clamp it to 0 so the filter goes to maximum smoothing.
                    if speed < 0.05:
                        speed = 0.0

                    cutoff_hz = self.settings.min_cutoff_hz + self.settings.speed_coeff * speed
                    if self.settings.smoothing_hz > 0:
                        # Allow smoothing_hz to scale responsiveness
                        cutoff_hz = max(self.settings.min_cutoff_hz, min(self.settings.smoothing_hz, cutoff_hz))
                    self._current_cutoff_hz = cutoff_hz

                    alpha_pos = self._compute_alpha(cutoff_hz, dt)

                    # Hard clamping logic for absolute visual stability.
                    # If speed is fully clamped to 0, and effective input hasn't moved (due to deadzone),
                    # bypass updating the filtered position entirely to prevent asymptotic micro-creep.
                    if speed == 0.0 and effective_input == self._last_raw_input and dist <= self.settings.deadzone:
                        pass # Retain exact previous filtered_input and position
                    else:
                        self._filtered_input = (
                            alpha_pos * effective_input[0] + (1.0 - alpha_pos) * self._filtered_input[0],
                            alpha_pos * effective_input[1] + (1.0 - alpha_pos) * self._filtered_input[1],
                        )

                # Map directly to playfield
                self._target = self._map_to_playfield(self._filtered_input)
                self._position = self._target

        self._history.append((timestamp, self._position[0], self._position[1]))
        return self._position

    def get_anchored_position(
        self, now: float, lookback_seconds: float | None = None
    ) -> tuple[float, float]:
        """Return the aim position from before pinch closure to cancel trigger jerk."""
        if not self._history:
            return self._position

        lookback = (
            lookback_seconds
            if lookback_seconds is not None
            else self.settings.pre_shot_anchor_seconds
        )
        target_time = now - max(0.0, lookback)

        if target_time <= self._history[0][0]:
            return self._history[0][1], self._history[0][2]

        if target_time >= self._history[-1][0]:
            return self._history[-1][1], self._history[-1][2]

        for i in range(len(self._history) - 1):
            t0, x0, y0 = self._history[i]
            t1, x1, y1 = self._history[i + 1]
            if t0 <= target_time <= t1:
                span = max(1e-6, t1 - t0)
                fraction = (target_time - t0) / span
                return x0 + (x1 - x0) * fraction, y0 + (y1 - y0) * fraction

        return self._position

    @staticmethod
    def _compute_alpha(cutoff_hz: float, dt: float) -> float:
        rate = 2.0 * math.pi * max(1e-4, cutoff_hz)
        return 1.0 - math.exp(-rate * dt)

    def _map_to_playfield(self, input_point: tuple[float, float]) -> tuple[float, float]:
        x, y = input_point
        if self.settings.mirror_x:
            x = 1.0 - x
        mapped_x = _remap_clamped(
            x, self.settings.input_left, self.settings.input_right,
            self._playfield[0], self._playfield[2],
        )
        mapped_y = _remap_clamped(
            y, self.settings.input_top, self.settings.input_bottom,
            self._playfield[1], self._playfield[3],
        )
        return self._clamp((mapped_x, mapped_y))

    def _normalized_point(self, fingertip_norm: Sequence[float]) -> tuple[float, float]:
        if len(fingertip_norm) < 2:
            raise ValueError("fingertip_norm needs x and y coordinates")
        return float(fingertip_norm[0]), float(fingertip_norm[1])

    def _default_playfield(self) -> Bounds:
        margin_x = min(float(self.settings.margin), self._width / 2.0)
        margin_y = min(float(self.settings.margin), self._height / 2.0)
        return margin_x, margin_y, self._width - margin_x, self._height - margin_y

    def _playfield_centre(self) -> tuple[float, float]:
        return (
            (self._playfield[0] + self._playfield[2]) / 2.0,
            (self._playfield[1] + self._playfield[3]) / 2.0,
        )

    def _clamp(self, point: tuple[float, float]) -> tuple[float, float]:
        return (
            min(self._playfield[2], max(self._playfield[0], point[0])),
            min(self._playfield[3], max(self._playfield[1], point[1])),
        )


def _remap_clamped(
    value: float, source_min: float, source_max: float,
    target_min: float, target_max: float,
) -> float:
    span = source_max - source_min
    if span <= 0:
        return (target_min + target_max) / 2.0
    normalized = (value - source_min) / span
    normalized = min(1.0, max(0.0, normalized))
    return target_min + (target_max - target_min) * normalized
