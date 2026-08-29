"""Controlled spawning, movement, progressive difficulty, and shot collision for bubbles (Phase 9)."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from config import settings
from game.bubble import Bounds, Bubble, BubbleType


@dataclass(frozen=True)
class BubbleSettings:
    initial_count: int = settings.BUBBLE_INITIAL_COUNT
    max_active: int = settings.BUBBLE_MAX_ACTIVE_START
    spawn_interval_seconds: float = settings.BUBBLE_SPAWN_INTERVAL_START
    radius_min: float = float(settings.BUBBLE_RADIUS_MIN)
    radius_max: float = float(settings.BUBBLE_RADIUS_MAX)
    speed_min: float = settings.BUBBLE_SPEED_MIN_START
    speed_max: float = settings.BUBBLE_SPEED_MAX_START
    spawn_attempts: int = settings.BUBBLE_SPAWN_ATTEMPTS
    spawn_separation: float = float(settings.BUBBLE_SPAWN_SEPARATION)


class TargetManager:
    """Manage bubble lifecycle, progressive difficulty, target variety, and collision."""

    def __init__(self, base_settings: BubbleSettings | None = None, rng: random.Random | None = None) -> None:
        self.settings = base_settings or BubbleSettings()
        self._rng = rng or random.Random()
        self.bubbles: list[Bubble] = []
        self._spawn_elapsed = 0.0
        self._mode_config = None

        # Dynamic difficulty variables
        self.current_speed_min = self.settings.speed_min
        self.current_speed_max = self.settings.speed_max
        self.current_spawn_interval = self.settings.spawn_interval_seconds
        self.current_max_active = self.settings.max_active
        self.difficulty_progress = 0.0

    def apply_mode(self, mode) -> None:
        """Configure baseline parameters, probabilities, and limits from active ModeConfig."""
        self._mode_config = mode
        self.settings = BubbleSettings(
            initial_count=mode.bubble_initial_count,
            max_active=mode.max_active_start,
            spawn_interval_seconds=mode.spawn_interval_start,
            speed_min=mode.speed_min_start,
            speed_max=mode.speed_max_start,
        )
        self.current_speed_min = mode.speed_min_start
        self.current_speed_max = mode.speed_max_start
        self.current_spawn_interval = mode.spawn_interval_start
        self.current_max_active = mode.max_active_start

    def reset(self, bounds: Bounds) -> None:
        self.bubbles.clear()
        self._spawn_elapsed = 0.0
        self.set_difficulty_score(0)
        for _ in range(self.settings.initial_count):
            if self.spawn_one(bounds) is None:
                break

    def set_difficulty_score(self, current_score: int) -> None:
        """Gradually scale speed, spawn rate, and max targets based on run score."""
        mode = self._mode_config
        if mode is not None and not mode.difficulty_scaling:
            self.current_speed_min = mode.speed_min_start
            self.current_speed_max = mode.speed_max_start
            self.current_spawn_interval = mode.spawn_interval_start
            self.current_max_active = mode.max_active_start
            self.difficulty_progress = 0.0
            return

        min_speed_start = mode.speed_min_start if mode else settings.BUBBLE_SPEED_MIN_START
        min_speed_end = mode.speed_min_end if mode else settings.BUBBLE_SPEED_MIN_END
        max_speed_start = mode.speed_max_start if mode else settings.BUBBLE_SPEED_MAX_START
        max_speed_end = mode.speed_max_end if mode else settings.BUBBLE_SPEED_MAX_END
        spawn_start = mode.spawn_interval_start if mode else settings.BUBBLE_SPAWN_INTERVAL_START
        spawn_end = mode.spawn_interval_end if mode else settings.BUBBLE_SPAWN_INTERVAL_END
        active_start = mode.max_active_start if mode else settings.BUBBLE_MAX_ACTIVE_START
        active_end = mode.max_active_end if mode else settings.BUBBLE_MAX_ACTIVE_END

        max_score = max(1.0, float(settings.DIFFICULTY_MAX_SCORE))
        p = min(1.0, max(0.0, float(current_score) / max_score))
        self.difficulty_progress = p

        self.current_speed_min = min_speed_start + p * (min_speed_end - min_speed_start)
        self.current_speed_max = max_speed_start + p * (max_speed_end - max_speed_start)
        self.current_spawn_interval = spawn_start - p * (spawn_start - spawn_end)
        self.current_max_active = round(active_start + p * (active_end - active_start))

    def update(self, delta_seconds: float, bounds: Bounds) -> list[Bubble]:
        """Update bubble positions, manage spawning, and return escaped bubbles."""
        for bubble in self.bubbles:
            bubble.update(delta_seconds, bounds)

        # Collect and remove escaped bubbles (guarantees exactly one life loss per bubble)
        escaped_bubbles = [b for b in self.bubbles if b.escaped]
        if escaped_bubbles:
            self.bubbles = [b for b in self.bubbles if not b.escaped]

        self._spawn_elapsed += max(0.0, delta_seconds)
        while (
            len(self.bubbles) < self.current_max_active
            and self._spawn_elapsed >= self.current_spawn_interval
        ):
            self._spawn_elapsed -= self.current_spawn_interval
            if self.spawn_one(bounds) is None:
                self._spawn_elapsed = min(self._spawn_elapsed, self.current_spawn_interval)
                break

        if len(self.bubbles) >= self.current_max_active:
            self._spawn_elapsed = 0.0

        return escaped_bubbles

    def shoot(self, position: tuple[float, float]) -> Bubble | None:
        """Remove and return the closest bubble under a point-shot, if any."""
        candidates = [bubble for bubble in self.bubbles if bubble.contains(position)]
        if not candidates:
            return None
        hit = min(candidates, key=lambda bubble: math.dist(bubble.position, position))
        self.bubbles.remove(hit)
        return hit

    def _choose_target_type(self) -> BubbleType:
        """Pick a target type based on the active mode's probability distribution."""
        probs = (
            self._mode_config.spawn_probabilities
            if self._mode_config is not None
            else settings.SPAWN_PROBS_CLASSIC
        )
        p_normal, p_small, p_large, p_golden = probs
        roll = self._rng.random()

        if roll < p_normal:
            return BubbleType.NORMAL
        elif roll < p_normal + p_small:
            return BubbleType.SMALL
        elif roll < p_normal + p_small + p_large:
            return BubbleType.LARGE
        return BubbleType.GOLDEN

    def _get_target_radius(self, target_type: BubbleType) -> float:
        if target_type is BubbleType.SMALL:
            return self._rng.uniform(settings.RADIUS_SMALL_MIN, settings.RADIUS_SMALL_MAX)
        elif target_type is BubbleType.LARGE:
            return self._rng.uniform(settings.RADIUS_LARGE_MIN, settings.RADIUS_LARGE_MAX)
        elif target_type is BubbleType.GOLDEN:
            return self._rng.uniform(settings.RADIUS_GOLDEN_MIN, settings.RADIUS_GOLDEN_MAX)
        return self._rng.uniform(settings.RADIUS_NORMAL_MIN, settings.RADIUS_NORMAL_MAX)

    def _get_target_speed_multiplier(self, target_type: BubbleType) -> float:
        if target_type is BubbleType.SMALL:
            return settings.SPEED_MULT_SMALL
        elif target_type is BubbleType.LARGE:
            return settings.SPEED_MULT_LARGE
        elif target_type is BubbleType.GOLDEN:
            return settings.SPEED_MULT_GOLDEN
        return settings.SPEED_MULT_NORMAL

    def spawn_one(self, bounds: Bounds) -> Bubble | None:
        """Create a non-overlapping target with type-specific attributes in the upper playfield."""
        for _ in range(self.settings.spawn_attempts):
            target_type = self._choose_target_type()
            radius = self._get_target_radius(target_type)
            centre = self._random_centre(bounds, radius)
            if centre is None or not self._has_clearance(centre, radius):
                continue
            speed_mult = self._get_target_speed_multiplier(target_type)
            velocity = self._random_velocity(speed_mult)
            bubble = Bubble(centre, velocity, radius, target_type=target_type)
            self.bubbles.append(bubble)
            return bubble
        return None

    def _random_centre(self, bounds: Bounds, radius: float) -> tuple[float, float] | None:
        left, top, right, bottom = bounds
        min_x, max_x = left + radius, right - radius
        min_y = top + radius
        max_y = top + max(radius + 10, (bottom - top) * 0.45)
        if min_x > max_x or min_y > max_y:
            return None
        return self._rng.uniform(min_x, max_x), self._rng.uniform(min_y, max_y)

    def _has_clearance(self, centre: tuple[float, float], radius: float) -> bool:
        return all(
            math.dist(centre, bubble.position)
            >= radius + bubble.radius + self.settings.spawn_separation
            for bubble in self.bubbles
        )

    def _random_velocity(self, speed_mult: float = 1.0) -> tuple[float, float]:
        # Bias downward across the screen
        angle = self._rng.uniform(0.25, math.pi - 0.25)
        base_speed = self._rng.uniform(self.current_speed_min, self.current_speed_max)
        speed = base_speed * speed_mult
        return math.cos(angle) * speed, math.sin(angle) * speed
