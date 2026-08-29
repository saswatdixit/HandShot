"""Phase 6 scoring, combo tracking, run statistics, and high score persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from config import settings


class ScoreTracker:
    """Track only the current run's successful bubble points."""

    def __init__(self) -> None:
        self.score = 0

    def reset(self) -> None:
        self.score = 0

    def add(self, points: int) -> int:
        self.score += points
        return self.score


class ComboTracker:
    """Track consecutive hits and dynamic score multiplier.

    Multipliers:
      0–2 hits -> 1x (base score)
      3–4 hits -> 2x
      5+ hits  -> 3x
    Streak resets to 0 on misses or escaped bubbles.
    """

    def __init__(self) -> None:
        self.current_combo = 0
        self.highest_combo = 0
        self.multiplier = 1

    def reset(self) -> None:
        self.current_combo = 0
        self.highest_combo = 0
        self.multiplier = 1

    def register_hit(self) -> int:
        """Increment streak, update highest combo and multiplier, return active multiplier."""
        self.current_combo += 1
        if self.current_combo > self.highest_combo:
            self.highest_combo = self.current_combo

        if self.current_combo >= settings.COMBO_TIER_3_HITS:
            self.multiplier = settings.COMBO_TIER_3_MULTIPLIER
        elif self.current_combo >= settings.COMBO_TIER_2_HITS:
            self.multiplier = settings.COMBO_TIER_2_MULTIPLIER
        elif self.current_combo >= settings.COMBO_TIER_1_HITS:
            self.multiplier = settings.COMBO_TIER_1_MULTIPLIER
        else:
            self.multiplier = 1

        return self.multiplier

    def register_miss(self) -> None:
        """Reset active combo streak on missed shot."""
        self.current_combo = 0
        self.multiplier = 1

    def register_escape(self) -> None:
        """Reset active combo streak on escaped bubble."""
        self.current_combo = 0
        self.multiplier = 1


@dataclass
class GameStats:
    """Track run performance, health/lives, accuracy, and special targets."""

    lives: int = settings.INITIAL_LIVES
    shots_fired: int = 0
    targets_hit: int = 0
    golden_targets_hit: int = 0
    highest_combo: int = 0

    @property
    def accuracy(self) -> float:
        if self.shots_fired == 0:
            return 0.0
        return (self.targets_hit / self.shots_fired) * 100.0

    def record_shot(self) -> None:
        self.shots_fired += 1

    def record_hit(self, is_golden: bool = False) -> None:
        self.targets_hit += 1
        if is_golden:
            self.golden_targets_hit += 1

    def lose_life(self, amount: int = 1) -> int:
        self.lives = max(0, self.lives - amount)
        return self.lives

    def reset(self, initial_lives: int = settings.INITIAL_LIVES) -> None:
        self.lives = initial_lives
        self.shots_fired = 0
        self.targets_hit = 0
        self.golden_targets_hit = 0
        self.highest_combo = 0


def load_high_score(path: Path = settings.STATS_SAVE_PATH, mode_name: str = "CLASSIC") -> int:
    """Safely load persisted high score for a specific mode from local JSON file."""
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                modes_data = data.get("modes")
                if isinstance(modes_data, dict) and mode_name in modes_data:
                    return int(modes_data.get(mode_name, 0))
                # Backwards compatibility fallback for classic mode
                if mode_name == "CLASSIC":
                    return int(data.get("high_score", 0))
    except Exception:
        pass
    return 0


def save_high_score(score: int, path: Path = settings.STATS_SAVE_PATH, mode_name: str = "CLASSIC") -> bool:
    """Persist score if it exceeds previous high score for this mode. Returns True if new best."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data: dict = {}
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
            except Exception:
                data = {}

        current_best = load_high_score(path, mode_name)
        if score > current_best:
            if "modes" not in data or not isinstance(data["modes"], dict):
                data["modes"] = {}
            data["modes"][mode_name] = score
            if mode_name == "CLASSIC":
                data["high_score"] = score
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return True
    except Exception:
        pass
    return False
