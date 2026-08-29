"""Target bubble types, physics, and behaviour for HANDSHOT (Phase 9)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, auto

from config import settings

Bounds = tuple[float, float, float, float]  # left, top, right, bottom


class BubbleType(Enum):
    """Four distinct target types in Handshot."""

    NORMAL = auto()
    SMALL = auto()
    LARGE = auto()
    GOLDEN = auto()


@dataclass
class Bubble:
    """A target moving inside playable bounds with reflection and bottom boundary handling."""

    position: tuple[float, float]
    velocity: tuple[float, float]
    radius: float
    target_type: BubbleType = BubbleType.NORMAL
    escaped: bool = False
    allow_escape: bool = True

    @property
    def base_score(self) -> int:
        """Base points awarded when hitting this target type before combo multipliers."""
        if self.target_type is BubbleType.SMALL:
            return settings.SCORE_SMALL
        elif self.target_type is BubbleType.LARGE:
            return settings.SCORE_LARGE
        elif self.target_type is BubbleType.GOLDEN:
            return settings.SCORE_GOLDEN
        return settings.SCORE_NORMAL

    @property
    def hit_sound_name(self) -> str:
        """Specific sound effect triggered on hit."""
        if self.target_type is BubbleType.SMALL:
            return "bubble_hit_small"
        elif self.target_type is BubbleType.LARGE:
            return "bubble_hit_large"
        elif self.target_type is BubbleType.GOLDEN:
            return "bubble_hit_golden"
        return "bubble_hit"

    def update(self, delta_seconds: float, bounds: Bounds) -> None:
        """Move with wall reflection, marking escaped if crossing the bottom failure boundary."""
        if delta_seconds <= 0 or self.escaped:
            return

        left, top, right, bottom = bounds
        min_x, max_x = left + self.radius, right - self.radius
        min_y = top + self.radius
        max_y = bottom - self.radius

        x = self.position[0] + self.velocity[0] * delta_seconds
        y = self.position[1] + self.velocity[1] * delta_seconds
        vx, vy = self.velocity

        # Left / Right side walls reflection
        if min_x < max_x:
            x, vx = _reflect_axis(x, vx, min_x, max_x)
        else:
            x = (min_x + max_x) / 2.0

        # Top wall reflection
        if y < min_y:
            y = min_y + (min_y - y)
            vy = abs(vy)

        # Bottom failure boundary
        if self.allow_escape:
            if y >= max_y:
                self.escaped = True
                self.position = (x, y)
                self.velocity = (vx, vy)
                return
        else:
            if y > max_y:
                y = max_y - (y - max_y)
                vy = -abs(vy)

        self.position = (x, y)
        self.velocity = (vx, vy)

    def contains(self, point: tuple[float, float]) -> bool:
        """Point-in-circle collision check with subtle forgiveness padding."""
        return math.dist(self.position, point) <= self.radius + settings.HIT_FORGIVENESS_PADDING


def _reflect_axis(position: float, velocity: float, minimum: float, maximum: float) -> tuple[float, float]:
    """Reflect coordinate within [minimum, maximum] range."""
    if minimum >= maximum:
        return (minimum + maximum) / 2.0, 0.0
    while position < minimum or position > maximum:
        if position < minimum:
            position = minimum + (minimum - position)
            velocity = abs(velocity)
        elif position > maximum:
            position = maximum - (position - maximum)
            velocity = -abs(velocity)
    return position, velocity
