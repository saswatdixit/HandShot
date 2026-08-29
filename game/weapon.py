"""Modular weapon architecture, configurations, and state system for HANDSHOT."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from enum import Enum


class WeaponType(Enum):
    """Available weapon classes in HANDSHOT."""

    PISTOL = "pistol"
    ASSAULT_RIFLE = "assault_rifle"
    SHOTGUN = "shotgun"
    SNIPER = "sniper"


@dataclass(frozen=True)
class WeaponSpec:
    """Configurable specifications for a weapon."""

    weapon_type: WeaponType
    name: str
    tagline: str
    difficulty_rating: str
    description: str
    magazine_size: int
    reserve_ammo: int  # -1 represents infinite reserves (∞)
    fire_cooldown_seconds: float
    reload_time_seconds: float
    spread_radius_px: float
    pellet_count: int
    damage: int
    recoil_px: float
    fire_sound: str
    reload_sound: str
    reload_done_sound: str
    empty_sound: str


# --------------------------------------------------------------------------
# Rebalanced Weapon Definitions
# --------------------------------------------------------------------------

PISTOL_SPEC = WeaponSpec(
    weapon_type=WeaponType.PISTOL,
    name="PISTOL",
    tagline="Precise",
    difficulty_rating="Easy",
    description="Reliable semi-auto sidearm with fast handling and zero spread.",
    magazine_size=20,
    reserve_ammo=-1,
    fire_cooldown_seconds=0.18,
    reload_time_seconds=1.10,
    spread_radius_px=0.0,
    pellet_count=1,
    damage=10,
    recoil_px=3.5,
    fire_sound="fire_pistol",
    reload_sound="reload_start",
    reload_done_sound="reload_done",
    empty_sound="empty_click",
)

ASSAULT_RIFLE_SPEC = WeaponSpec(
    weapon_type=WeaponType.ASSAULT_RIFLE,
    name="ASSAULT",
    difficulty_rating="Medium",
    tagline="Fast Fire",
    description="High rate-of-fire rifle for fast target sweeping and volume fire.",
    magazine_size=60,
    reserve_ammo=-1,
    fire_cooldown_seconds=0.09,
    reload_time_seconds=1.50,
    spread_radius_px=14.0,
    pellet_count=1,
    damage=8,
    recoil_px=5.5,
    fire_sound="fire_rifle",
    reload_sound="reload_start",
    reload_done_sound="reload_done",
    empty_sound="empty_click",
)

SHOTGUN_SPEC = WeaponSpec(
    weapon_type=WeaponType.SHOTGUN,
    name="SHOTGUN",
    tagline="Spread",
    difficulty_rating="Close Range",
    description="Pump shotgun firing 6 dispersed pellets to clear clustered targets.",
    magazine_size=10,
    reserve_ammo=-1,
    fire_cooldown_seconds=0.55,
    reload_time_seconds=1.80,
    spread_radius_px=36.0,
    pellet_count=6,
    damage=15,
    recoil_px=10.0,
    fire_sound="fire_shotgun",
    reload_sound="reload_start",
    reload_done_sound="reload_done",
    empty_sound="empty_click",
)

SNIPER_SPEC = WeaponSpec(
    weapon_type=WeaponType.SNIPER,
    name="SNIPER",
    tagline="Precision",
    difficulty_rating="Hard",
    description="High-velocity heavy rifle delivering pin-point accuracy.",
    magazine_size=8,
    reserve_ammo=-1,
    fire_cooldown_seconds=0.80,
    reload_time_seconds=2.00,
    spread_radius_px=0.0,
    pellet_count=1,
    damage=30,
    recoil_px=14.0,
    fire_sound="fire_sniper",
    reload_sound="reload_start",
    reload_done_sound="reload_done",
    empty_sound="empty_click",
)

ALL_WEAPONS: list[WeaponSpec] = [
    PISTOL_SPEC,
    ASSAULT_RIFLE_SPEC,
    SHOTGUN_SPEC,
    SNIPER_SPEC,
]


class WeaponSystem:
    """Manages active weapon, ammunition states, firing rates, and reload cycles."""

    def __init__(
        self,
        default_spec: WeaponSpec | None = None,
        infinite_magazine: bool = False,
        reload_enabled: bool = True,
    ) -> None:
        self._spec = default_spec or PISTOL_SPEC
        self.infinite_magazine = infinite_magazine
        self.reload_enabled = reload_enabled
        self._mag_ammo = self._spec.magazine_size
        self._reserve_ammo = self._spec.reserve_ammo
        self._is_reloading = False
        self._reload_start_time = 0.0
        self._reload_progress = 0.0
        self._last_fire_time = -math.inf
        self._rng = random.Random()

    @property
    def spec(self) -> WeaponSpec:
        return self._spec

    @property
    def mag_ammo(self) -> int:
        return self._spec.magazine_size if self.infinite_magazine else self._mag_ammo

    @property
    def reserve_ammo(self) -> int:
        return self._reserve_ammo

    @property
    def is_reloading(self) -> bool:
        return False if self.infinite_magazine else self._is_reloading

    @property
    def reload_progress(self) -> float:
        return self._reload_progress

    @property
    def is_empty(self) -> bool:
        return False if self.infinite_magazine else (self._mag_ammo <= 0)

    @property
    def is_out_of_ammo(self) -> bool:
        if self.infinite_magazine or self._reserve_ammo == -1:
            return False
        return self._mag_ammo <= 0 and self._reserve_ammo <= 0

    @property
    def ammo_display_str(self) -> str:
        """Formatted ammunition readout for HUD display."""
        if self.infinite_magazine:
            return "∞"
        if self._reserve_ammo == -1:
            return f"{self._mag_ammo} / ∞"
        return f"{self._mag_ammo} / {self._reserve_ammo}"

    def select_weapon(self, spec: WeaponSpec) -> None:
        """Switch active weapon spec and reset magazine."""
        self._spec = spec
        self.reset_ammo()

    def reset_ammo(self) -> None:
        """Refill magazine to weapon spec defaults."""
        self._mag_ammo = self._spec.magazine_size
        self._reserve_ammo = self._spec.reserve_ammo
        self._is_reloading = False
        self._reload_progress = 0.0
        self._last_fire_time = -math.inf

    def can_fire(self, now: float) -> bool:
        """Check if weapon can fire at timestamp ``now``."""
        if not self.infinite_magazine:
            if self._is_reloading:
                return False
            if self._mag_ammo <= 0:
                return False
        if (now - self._last_fire_time) < self._spec.fire_cooldown_seconds:
            return False
        return True

    def fire(
        self,
        now: float,
        aim_pos: tuple[float, float],
        rng: random.Random | None = None,
    ) -> list[tuple[float, float]]:
        """Consume 1 round from magazine (if finite) and calculate pellet impact points."""
        if not self.can_fire(now):
            return []

        if not self.infinite_magazine:
            self._mag_ammo -= 1

        self._last_fire_time = now
        rand = rng or self._rng

        impacts: list[tuple[float, float]] = []
        cx, cy = aim_pos

        if self._spec.pellet_count <= 1:
            if self._spec.spread_radius_px > 0:
                angle = rand.uniform(0.0, 2.0 * math.pi)
                radius = rand.uniform(0.0, self._spec.spread_radius_px)
                impacts.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
            else:
                impacts.append((cx, cy))
        else:
            # Shotgun multi-pellet spread
            impacts.append((cx, cy))  # Central pellet
            for _ in range(self._spec.pellet_count - 1):
                angle = rand.uniform(0.0, 2.0 * math.pi)
                radius = rand.uniform(4.0, self._spec.spread_radius_px)
                impacts.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))

        return impacts

    def can_reload(self) -> bool:
        """Check if reload can be initiated."""
        if self.infinite_magazine or not self.reload_enabled:
            return False
        if self._is_reloading:
            return False
        if self._mag_ammo >= self._spec.magazine_size:
            return False
        if self._reserve_ammo == 0:
            return False
        return True

    def start_reload(self, now: float) -> bool:
        """Initiate weapon reload sequence."""
        if not self.can_reload():
            return False
        self._is_reloading = True
        self._reload_start_time = now
        self._reload_progress = 0.0
        return True

    def cancel_reload(self) -> None:
        """Cancel an ongoing reload."""
        self._is_reloading = False
        self._reload_progress = 0.0

    def update(self, delta_seconds: float, now: float) -> bool:
        """Update reload timer. Returns True on the exact frame reload completes."""
        if self.infinite_magazine or not self._is_reloading:
            self._reload_progress = 0.0
            return False

        elapsed = max(0.0, now - self._reload_start_time)
        self._reload_progress = min(1.0, elapsed / max(1e-4, self._spec.reload_time_seconds))

        if elapsed >= self._spec.reload_time_seconds:
            # Complete reload: refill magazine
            if self._reserve_ammo == -1:
                self._mag_ammo = self._spec.magazine_size
            else:
                needed = self._spec.magazine_size - self._mag_ammo
                transferred = min(needed, self._reserve_ammo)
                self._mag_ammo += transferred
                self._reserve_ammo -= transferred
            self._is_reloading = False
            self._reload_progress = 0.0
            return True

        return False
