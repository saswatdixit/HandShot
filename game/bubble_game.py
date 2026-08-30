"""Phase 8 game flow session coordinating states (MODE_SELECT, READY, COUNTDOWN, PLAYING, PAUSED, GAME_OVER), modes, targets, and stats."""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum, auto

from config import settings
from game.bubble import Bounds, Bubble, BubbleType
from game.game_mode import GameMode, ModeConfig, get_default_mode
from game.scoring import (
    ComboTracker,
    GameStats,
    ScoreTracker,
    load_high_score,
    save_high_score,
)
from game.target_manager import TargetManager
from game.weapon import WeaponSpec, WeaponSystem


class GameState(Enum):
    """Core game states across the arcade lifecycle."""

    MODE_SELECT = auto()    # Select between Classic, Chill, Timed, Practice
    WEAPON_SELECT = auto()  # Select weapon (Pistol, AR, Shotgun, Sniper)
    READY = auto()          # Waiting for hand tracking to stabilize
    COUNTDOWN = auto()      # 3 -> 2 -> 1 -> GO!
    PLAYING = auto()        # Active gameplay
    PAUSED = auto()         # Frozen by player (P / ESC key)
    GAME_OVER = auto()      # Results screen / session ended


@dataclass(frozen=True)
class ImpactOutcome:
    """Result of resolving a single impact point (one pellet) against the field."""

    bubble: Bubble | None
    points: int = 0
    multiplier: int = 1

    @property
    def hit(self) -> bool:
        return self.bubble is not None


class BubbleGame:
    """Core game session coordinating state flow, mode, score, combo, health, and targets."""

    def __init__(
        self,
        rng: random.Random | None = None,
        mode: ModeConfig | None = None,
        start_state: GameState = GameState.MODE_SELECT,
        default_weapon: WeaponSpec | None = None,
    ) -> None:
        self.mode = mode or get_default_mode()
        self.state = start_state
        self.weapons = WeaponSystem(default_weapon)
        self.score = ScoreTracker()
        self.combo = ComboTracker()
        self.stats = GameStats(lives=self.mode.initial_lives)
        self.high_score = load_high_score(mode_name=self.mode.name)
        self.is_new_high_score = False
        self.targets = TargetManager(rng=rng)
        self.targets.apply_mode(self.mode)

        # State machine timers
        self.ready_hand_timer: float = 0.0
        self.countdown_elapsed: float = 0.0
        self.countdown_text: str = ""
        self.countdown_number: int = 3
        self.gameplay_time: float = 0.0

    @property
    def time_remaining(self) -> float | None:
        """Remaining round time for timed modes in seconds, or None if untimed."""
        if self.mode.time_limit_seconds is not None:
            return max(0.0, self.mode.time_limit_seconds - self.gameplay_time)
        return None

    def set_mode(
        self,
        mode: ModeConfig,
        bounds: Bounds | None = None,
        start_state: GameState = GameState.READY,
    ) -> None:
        """Switch active game mode and refresh mode settings and targets."""
        self.mode = mode
        self.weapons.infinite_magazine = self.mode.infinite_ammo
        self.weapons.reload_enabled = not self.mode.infinite_ammo
        self.high_score = load_high_score(mode_name=self.mode.name)
        self.targets.apply_mode(self.mode)
        if bounds is not None:
            self.reset(bounds, start_state=start_state)

    def reset(
        self,
        bounds: Bounds,
        start_state: GameState = GameState.READY,
        now: float = 0.0,
    ) -> None:
        """Completely restart run with fresh lives, stats, score, and targets."""
        self.state = start_state
        self.weapons.infinite_magazine = self.mode.infinite_ammo
        self.weapons.reload_enabled = not self.mode.infinite_ammo
        self.weapons.reset_ammo()
        self.score.reset()
        self.combo.reset()
        self.stats.reset(self.mode.initial_lives)
        self.high_score = load_high_score(mode_name=self.mode.name)
        self.is_new_high_score = False
        self.ready_hand_timer = 0.0
        self.countdown_elapsed = 0.0
        self.countdown_text = ""
        self.countdown_number = 3
        self.gameplay_time = 0.0
        self.targets.apply_mode(self.mode)
        self.targets.reset(bounds)

    def toggle_pause(self) -> bool:
        """Toggle between PLAYING and PAUSED. Returns True if now paused."""
        if self.state is GameState.PLAYING:
            self.state = GameState.PAUSED
            return True
        elif self.state is GameState.PAUSED:
            self.state = GameState.PLAYING
            return False
        return False

    def update(
        self,
        delta_seconds: float,
        bounds: Bounds,
        hand_tracked: bool = True,
        now: float = 0.0,
    ) -> list[Bubble]:
        """Update the active state machine and gameplay targets."""
        if self.state in (GameState.MODE_SELECT, GameState.WEAPON_SELECT):
            return []

        if self.state is GameState.READY:
            self._update_ready(delta_seconds, hand_tracked)
            return []

        if self.state is GameState.COUNTDOWN:
            self._update_countdown(delta_seconds, bounds)
            return []

        if self.state is GameState.PAUSED or self.state is GameState.GAME_OVER:
            return []

        # --- PLAYING STATE ---
        self.gameplay_time += delta_seconds

        # Timed mode expiry check
        if self.mode.time_limit_seconds is not None:
            if self.gameplay_time >= self.mode.time_limit_seconds:
                self._trigger_game_over()
                return []

        # Progressive difficulty scaling based on score (if enabled by mode)
        if self.mode.difficulty_scaling:
            self.targets.set_difficulty_score(self.score.score)

        # Update targets and check for escapes
        escaped_bubbles = self.targets.update(delta_seconds, bounds)
        if escaped_bubbles:
            if hand_tracked and self.mode.allow_life_loss:
                for _ in escaped_bubbles:
                    self.stats.lose_life(1)
                    if self.mode.allow_combo:
                        self.combo.register_escape()
                if self.stats.lives <= 0:
                    self._trigger_game_over()

        return escaped_bubbles

    def _update_ready(self, delta_seconds: float, hand_tracked: bool) -> None:
        """Accumulate stable hand presence before beginning countdown."""
        if hand_tracked:
            self.ready_hand_timer += delta_seconds
            if self.ready_hand_timer >= settings.READY_HAND_STABLE_SECONDS:
                self.state = GameState.COUNTDOWN
                self.countdown_elapsed = 0.0
                self.countdown_number = 3
                self.countdown_text = "3"
        else:
            self.ready_hand_timer = max(0.0, self.ready_hand_timer - delta_seconds * 1.5)

    def _update_countdown(self, delta_seconds: float, bounds: Bounds) -> None:
        """Step countdown through 3 -> 2 -> 1 -> GO! -> PLAYING."""
        self.countdown_elapsed += delta_seconds
        step_duration = settings.COUNTDOWN_STEP_SECONDS
        go_duration = settings.COUNTDOWN_GO_SECONDS
        total_duration = step_duration * 3 + go_duration

        if self.countdown_elapsed < step_duration:
            self.countdown_number = 3
            self.countdown_text = "3"
        elif self.countdown_elapsed < step_duration * 2:
            self.countdown_number = 2
            self.countdown_text = "2"
        elif self.countdown_elapsed < step_duration * 3:
            self.countdown_number = 1
            self.countdown_text = "1"
        elif self.countdown_elapsed < total_duration:
            self.countdown_number = 0
            self.countdown_text = "GO!"
        else:
            self.state = GameState.PLAYING
            self.countdown_text = ""
            self.countdown_number = 0
            self.ready_hand_timer = 0.0
            # Ensure fresh target spawn as the round begins
            self.targets.reset(bounds)

    def register_impact(self, position: tuple[float, float]) -> ImpactOutcome:
        """Resolve ONE impact point (a single pellet) against the target field.

        This is the authoritative scoring implementation: hit detection, combo,
        points, stats, and high-score persistence all live here, so the live
        gameplay path and ``shoot()`` cannot drift apart.

        It deliberately does NOT call ``stats.record_shot()`` and does NOT reset
        the combo on a miss. Those are per-trigger-pull concerns, and one trigger
        pull of a multi-pellet weapon produces several impacts. The caller owns
        them (see ``shoot()`` for the single-pellet case).
        """
        if self.state is not GameState.PLAYING:
            return ImpactOutcome(None)

        hit = self.targets.shoot(position)
        if hit is None:
            return ImpactOutcome(None)

        is_golden = (hit.target_type is BubbleType.GOLDEN)
        self.stats.record_hit(is_golden=is_golden)
        multiplier = self.combo.register_hit() if self.mode.allow_combo else 1
        self.stats.highest_combo = max(self.stats.highest_combo, self.combo.highest_combo)
        points = hit.base_score * multiplier
        self.score.add(points)

        if self.score.score > self.high_score:
            self.is_new_high_score = True
            self.high_score = self.score.score
            # Deliberately in-memory only: this runs once per pellet inside the
            # 60fps loop. `_trigger_game_over()` performs the single disk write.

        return ImpactOutcome(hit, points, multiplier)

    def shoot(self, position: tuple[float, float]) -> tuple[Bubble | None, int]:
        """Fire one single-impact shot. Only registers in PLAYING state.

        Convenience wrapper for single-pellet fire: counts the trigger pull, then
        resolves exactly one impact via ``register_impact()``. Multi-pellet
        weapons cannot use this (one pull -> N impacts); those callers do the
        ``record_shot()`` / per-pellet ``register_impact()`` / miss-reset
        sequence themselves.
        """
        if self.state is not GameState.PLAYING:
            return None, 0

        self.stats.record_shot()
        outcome = self.register_impact(position)

        if outcome.bubble is None and self.mode.allow_combo:
            self.combo.register_miss()

        return outcome.bubble, outcome.points

    def _trigger_game_over(self) -> None:
        """End the run and persist high score."""
        self.state = GameState.GAME_OVER
        if self.score.score > self.high_score:
            self.is_new_high_score = True
            self.high_score = self.score.score
            save_high_score(self.score.score, mode_name=self.mode.name)
        else:
            save_high_score(self.score.score, mode_name=self.mode.name)
