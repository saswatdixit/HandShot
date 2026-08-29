"""Game mode definitions and configurations for HANDSHOT."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from config import settings


class GameMode(Enum):
    """Supported game modes for HANDSHOT."""

    CLASSIC = auto()
    ARCADE = auto()
    CHILL = auto()
    TIMED = auto()
    PRACTICE = auto()
    SURVIVAL = auto()
    RUSH = auto()


@dataclass(frozen=True)
class ModeConfig:
    """Configurable rules, physics, and gameplay constraints per game mode."""

    mode: GameMode = GameMode.CLASSIC
    name: str = "CLASSIC"
    tagline: str = "3 Lives • Progressive difficulty arcade challenge"
    badge: str = "CLASSIC"
    initial_lives: int = settings.INITIAL_LIVES
    time_limit_seconds: float | None = None
    bubble_initial_count: int = settings.BUBBLE_INITIAL_COUNT
    max_active_start: int = settings.BUBBLE_MAX_ACTIVE_START
    max_active_end: int = settings.BUBBLE_MAX_ACTIVE_END
    speed_min_start: float = settings.BUBBLE_SPEED_MIN_START
    speed_min_end: float = settings.BUBBLE_SPEED_MIN_END
    speed_max_start: float = settings.BUBBLE_SPEED_MAX_START
    speed_max_end: float = settings.BUBBLE_SPEED_MAX_END
    spawn_interval_start: float = settings.BUBBLE_SPAWN_INTERVAL_START
    spawn_interval_end: float = settings.BUBBLE_SPAWN_INTERVAL_END
    spawn_probabilities: tuple[float, float, float, float] = settings.SPAWN_PROBS_CLASSIC
    allow_life_loss: bool = True
    allow_combo: bool = True
    difficulty_scaling: bool = True
    infinite_ammo: bool = False
    theme_music_track: str = "classic"


def get_classic_mode() -> ModeConfig:
    """Standard 3-life arcade mode with reload mechanics and progressive difficulty."""
    return ModeConfig(
        mode=GameMode.CLASSIC,
        name="CLASSIC",
        tagline="3 Lives • Limited magazine with infinite reserves",
        badge="CLASSIC",
        initial_lives=settings.INITIAL_LIVES,
        time_limit_seconds=None,
        bubble_initial_count=settings.BUBBLE_INITIAL_COUNT,
        max_active_start=settings.BUBBLE_MAX_ACTIVE_START,
        max_active_end=settings.BUBBLE_MAX_ACTIVE_END,
        speed_min_start=settings.BUBBLE_SPEED_MIN_START,
        speed_min_end=settings.BUBBLE_SPEED_MIN_END,
        speed_max_start=settings.BUBBLE_SPEED_MAX_START,
        speed_max_end=settings.BUBBLE_SPEED_MAX_END,
        spawn_interval_start=settings.BUBBLE_SPAWN_INTERVAL_START,
        spawn_interval_end=settings.BUBBLE_SPAWN_INTERVAL_END,
        spawn_probabilities=settings.SPAWN_PROBS_CLASSIC,
        allow_life_loss=True,
        allow_combo=True,
        difficulty_scaling=True,
        infinite_ammo=False,
        theme_music_track="classic",
    )


def get_arcade_mode() -> ModeConfig:
    """Infinite ammo casual mode: zero reloads, pure tracking and shooting."""
    return ModeConfig(
        mode=GameMode.ARCADE,
        name="ARCADE",
        tagline="Infinite Ammo • No reload, pure fast-paced popping",
        badge="ARCADE",
        initial_lives=0,
        time_limit_seconds=None,
        bubble_initial_count=settings.BUBBLE_INITIAL_COUNT,
        max_active_start=settings.BUBBLE_MAX_ACTIVE_START,
        max_active_end=settings.BUBBLE_MAX_ACTIVE_END,
        speed_min_start=settings.BUBBLE_SPEED_MIN_START,
        speed_min_end=settings.BUBBLE_SPEED_MIN_END,
        speed_max_start=settings.BUBBLE_SPEED_MAX_START,
        speed_max_end=settings.BUBBLE_SPEED_MAX_END,
        spawn_interval_start=settings.BUBBLE_SPAWN_INTERVAL_START,
        spawn_interval_end=settings.BUBBLE_SPAWN_INTERVAL_END,
        spawn_probabilities=settings.SPAWN_PROBS_CLASSIC,
        allow_life_loss=False,
        allow_combo=True,
        difficulty_scaling=True,
        infinite_ammo=True,
        theme_music_track="classic",
    )


def get_chill_mode() -> ModeConfig:
    """Relaxed endless popping mode with gentle speed, no lives, and no pressure."""
    return ModeConfig(
        mode=GameMode.CHILL,
        name="RELAXED",
        tagline="Endless • Relaxed speed, no lives, pure practice",
        badge="RELAXED",
        initial_lives=0,
        time_limit_seconds=None,
        bubble_initial_count=settings.CHILL_BUBBLE_INITIAL_COUNT,
        max_active_start=settings.CHILL_BUBBLE_MAX_ACTIVE,
        max_active_end=settings.CHILL_BUBBLE_MAX_ACTIVE,
        speed_min_start=settings.CHILL_BUBBLE_SPEED_MIN,
        speed_min_end=settings.CHILL_BUBBLE_SPEED_MIN,
        speed_max_start=settings.CHILL_BUBBLE_SPEED_MAX,
        speed_max_end=settings.CHILL_BUBBLE_SPEED_MAX,
        spawn_interval_start=settings.CHILL_BUBBLE_SPAWN_INTERVAL,
        spawn_interval_end=settings.CHILL_BUBBLE_SPAWN_INTERVAL,
        spawn_probabilities=settings.SPAWN_PROBS_CHILL,
        allow_life_loss=False,
        allow_combo=True,
        difficulty_scaling=False,
        infinite_ammo=False,
        theme_music_track="chill",
    )


def get_timed_mode() -> ModeConfig:
    """Fast-paced 60-second score attack mode."""
    return ModeConfig(
        mode=GameMode.TIMED,
        name="TIMED",
        tagline="60 Seconds • Fast-paced score attack rush",
        badge="TIMED",
        initial_lives=0,
        time_limit_seconds=settings.TIMED_MODE_DURATION,
        bubble_initial_count=3,
        max_active_start=4,
        max_active_end=6,
        speed_min_start=80.0,
        speed_min_end=130.0,
        speed_max_start=140.0,
        speed_max_end=200.0,
        spawn_interval_start=1.20,
        spawn_interval_end=0.75,
        spawn_probabilities=settings.SPAWN_PROBS_TIMED,
        allow_life_loss=False,
        allow_combo=True,
        difficulty_scaling=True,
        infinite_ammo=False,
        theme_music_track="timed",
    )


def get_practice_mode() -> ModeConfig:
    """Target range mode with slow bubbles for fine-tuning aim and pinch."""
    return ModeConfig(
        mode=GameMode.PRACTICE,
        name="PRACTICE",
        tagline="Target Range • Fine-tune pinch timing and aim",
        badge="PRACTICE",
        initial_lives=0,
        time_limit_seconds=None,
        bubble_initial_count=settings.PRACTICE_BUBBLE_INITIAL_COUNT,
        max_active_start=settings.PRACTICE_BUBBLE_MAX_ACTIVE,
        max_active_end=settings.PRACTICE_BUBBLE_MAX_ACTIVE,
        speed_min_start=settings.PRACTICE_BUBBLE_SPEED_MIN,
        speed_min_end=settings.PRACTICE_BUBBLE_SPEED_MIN,
        speed_max_start=settings.PRACTICE_BUBBLE_SPEED_MAX,
        speed_max_end=settings.PRACTICE_BUBBLE_SPEED_MAX,
        spawn_interval_start=settings.PRACTICE_BUBBLE_SPAWN_INTERVAL,
        spawn_interval_end=settings.PRACTICE_BUBBLE_SPAWN_INTERVAL,
        spawn_probabilities=settings.SPAWN_PROBS_PRACTICE,
        allow_life_loss=False,
        allow_combo=True,
        difficulty_scaling=False,
        infinite_ammo=False,
        theme_music_track="practice",
    )


ALL_MODES: list[ModeConfig] = [
    get_classic_mode(),
    get_arcade_mode(),
    get_chill_mode(),
    get_timed_mode(),
]


def get_default_mode() -> ModeConfig:
    """Return the default starting mode (CLASSIC)."""
    return get_classic_mode()
