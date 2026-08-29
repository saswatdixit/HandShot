"""Reusable modular vector crosshair renderer with weapon-specific reticle geometries for HANDSHOT."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from game.theme import THEME
from game.weapon import WeaponType


@dataclass(frozen=True)
class CrosshairState:
    """Dynamic visual state passed to crosshair renderers."""

    is_firing: bool = False
    is_empty: bool = False
    is_pinched: bool = False
    is_reloading: bool = False
    recoil_offset_px: float = 0.0


def draw_crosshair(
    surface: pygame.Surface,
    position: tuple[float, float],
    weapon_type: WeaponType,
    state: CrosshairState | None = None,
) -> None:
    """Draw a precision minimalist crosshair centered on the filtered aim position.

    Styles:
    - PISTOL: Precision 4-line reticle with center dot.
    - ASSAULT_RIFLE: Expanding tactical reticle communicating recoil and spread.
    - SHOTGUN: Minimal circular dispersion ring communicating pellet spread.
    - SNIPER: Fine hairline precision scope crosshair.
    """
    st = state or CrosshairState()
    x, y = round(position[0]), round(position[1])

    # Color resolution
    if st.is_empty:
        col = THEME.ACCENT_CORAL
    elif st.is_firing or st.is_reloading:
        col = THEME.ACCENT_GOLD
    elif st.is_pinched:
        col = THEME.ACCENT_EMERALD
    else:
        col = THEME.ACCENT_CYAN

    # 1. PISTOL
    if weapon_type is WeaponType.PISTOL:
        rad = 12
        pygame.draw.circle(surface, (255, 255, 255), (x, y), 2)
        pygame.draw.circle(surface, col, (x, y), rad, 1)
        pygame.draw.line(surface, col, (x, y - rad - 6), (x, y - rad - 2), 2)
        pygame.draw.line(surface, col, (x, y + rad + 2), (x, y + rad + 6), 2)
        pygame.draw.line(surface, col, (x - rad - 6, y), (x - rad - 2, y), 2)
        pygame.draw.line(surface, col, (x + rad + 2, y), (x + rad + 6, y), 2)

    # 2. ASSAULT RIFLE (Dynamic tactical recoil bloom)
    elif weapon_type is WeaponType.ASSAULT_RIFLE:
        spread = round(st.recoil_offset_px * 0.85)
        gap = 7 + spread
        length = 8
        pygame.draw.circle(surface, (255, 255, 255), (x, y), 2)
        pygame.draw.line(surface, col, (x, y - gap - length), (x, y - gap), 2)
        pygame.draw.line(surface, col, (x, y + gap), (x, y + gap + length), 2)
        pygame.draw.line(surface, col, (x - gap - length, y), (x - gap, y), 2)
        pygame.draw.line(surface, col, (x + gap, y), (x + gap + length, y), 2)

    # 3. SHOTGUN (Pellet dispersion ring)
    elif weapon_type is WeaponType.SHOTGUN:
        pulse = round(st.recoil_offset_px * 0.5)
        rad = 30 + pulse
        pygame.draw.circle(surface, (255, 255, 255), (x, y), 2)
        pygame.draw.circle(surface, col, (x, y), rad, 1)
        pygame.draw.line(surface, col, (x, y - rad - 4), (x, y - rad + 4), 2)
        pygame.draw.line(surface, col, (x, y + rad - 4), (x, y + rad + 4), 2)
        pygame.draw.line(surface, col, (x - rad - 4, y), (x - rad + 4, y), 2)
        pygame.draw.line(surface, col, (x + rad - 4, y), (x + rad + 4, y), 2)

    # 4. SNIPER (Ultra-fine hairline crosshair)
    elif weapon_type is WeaponType.SNIPER:
        rad = 20
        pygame.draw.circle(surface, (255, 255, 255), (x, y), 2)
        pygame.draw.circle(surface, col, (x, y), rad, 1)
        pygame.draw.line(surface, col, (x, y - rad - 12), (x, y + rad + 12), 1)
        pygame.draw.line(surface, col, (x - rad - 12, y), (x + rad + 12, y), 1)
