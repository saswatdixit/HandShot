"""The intentionally small, single-target Phase 4 shooting surface."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class TrainingTarget:
    """A stationary target that briefly flashes when a shot hits it."""

    center_fraction: tuple[float, float] = (0.72, 0.52)
    radius: float = 44.0
    hit_until: float = 0.0

    def center(self, screen_size: tuple[int, int]) -> tuple[float, float]:
        return (
            screen_size[0] * self.center_fraction[0],
            screen_size[1] * self.center_fraction[1],
        )

    def contains(self, position: tuple[float, float], screen_size: tuple[int, int]) -> bool:
        centre = self.center(screen_size)
        return math.dist(position, centre) <= self.radius

    def register_hit(self, now: float, effect_seconds: float) -> None:
        self.hit_until = now + effect_seconds

    def is_hit(self, now: float) -> bool:
        return now < self.hit_until


@dataclass(frozen=True)
class ShotEffect:
    """A short visual confirmation emitted from the crosshair position."""

    position: tuple[float, float]
    hit: bool
    expires_at: float

    def visible(self, now: float) -> bool:
        return now < self.expires_at
