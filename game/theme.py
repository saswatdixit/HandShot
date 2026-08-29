"""Centralized design system for HANDSHOT — colors, spacing, radii, and visual constants."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemeColors:
    """Restrained, minimal, modern design system palette and layout constants."""

    # ── Backgrounds ──────────────────────────────────────────────────────
    BG_DARK: tuple[int, int, int] = (10, 13, 18)
    BG_SURFACE: tuple[int, int, int] = (18, 23, 32)
    BG_SURFACE_ELEVATED: tuple[int, int, int] = (26, 34, 46)
    BG_SURFACE_HIGHLIGHT: tuple[int, int, int] = (34, 46, 64)

    # ── Borders ──────────────────────────────────────────────────────────
    GRID_LINE: tuple[int, int, int] = (16, 21, 30)
    BORDER_SUBTLE: tuple[int, int, int] = (32, 42, 58)
    BORDER_FOCUS: tuple[int, int, int] = (75, 160, 235)
    BORDER_CARD: tuple[int, int, int] = (42, 56, 78)

    # ── Typography ───────────────────────────────────────────────────────
    TEXT_PRIMARY: tuple[int, int, int] = (242, 245, 250)
    TEXT_SECONDARY: tuple[int, int, int] = (150, 165, 185)
    TEXT_MUTED: tuple[int, int, int] = (90, 105, 125)

    # ── Accents ──────────────────────────────────────────────────────────
    ACCENT_CYAN: tuple[int, int, int] = (90, 215, 255)
    ACCENT_EMERALD: tuple[int, int, int] = (95, 235, 160)
    ACCENT_GOLD: tuple[int, int, int] = (255, 215, 80)
    ACCENT_CORAL: tuple[int, int, int] = (255, 88, 96)
    ACCENT_PURPLE: tuple[int, int, int] = (180, 130, 255)

    # ── Semantic Aliases ─────────────────────────────────────────────────
    SUCCESS: tuple[int, int, int] = (95, 235, 160)
    WARNING: tuple[int, int, int] = (255, 215, 80)
    ERROR: tuple[int, int, int] = (255, 88, 96)

    # ── Targets ──────────────────────────────────────────────────────────
    TARGET_NORMAL_RING: tuple[int, int, int] = (55, 175, 255)
    TARGET_NORMAL_FILL: tuple[int, int, int] = (18, 55, 95)
    TARGET_NORMAL_SHINE: tuple[int, int, int] = (150, 225, 255)
    TARGET_SMALL_RING: tuple[int, int, int] = (85, 235, 255)
    TARGET_SMALL_FILL: tuple[int, int, int] = (12, 75, 120)
    TARGET_SMALL_SHINE: tuple[int, int, int] = (200, 250, 255)
    TARGET_LARGE_RING: tuple[int, int, int] = (45, 130, 215)
    TARGET_LARGE_FILL: tuple[int, int, int] = (15, 42, 80)
    TARGET_LARGE_SHINE: tuple[int, int, int] = (90, 165, 250)
    TARGET_GOLDEN_RING: tuple[int, int, int] = (255, 220, 75)
    TARGET_GOLDEN_FILL: tuple[int, int, int] = (110, 80, 15)
    TARGET_GOLDEN_SHINE: tuple[int, int, int] = (255, 240, 150)

    # ── Reticle Colors ───────────────────────────────────────────────────
    RETICLE_DEFAULT: tuple[int, int, int] = (125, 225, 255)
    RETICLE_HOVER: tuple[int, int, int] = (95, 245, 160)
    RETICLE_FIRE: tuple[int, int, int] = (255, 230, 90)

    # ── Overlays (RGBA) ─────────────────────────────────────────────────
    OVERLAY_DIM: tuple[int, int, int, int] = (10, 13, 18, 180)
    OVERLAY_HEAVY: tuple[int, int, int, int] = (10, 13, 18, 220)

    # ── Card Backgrounds (RGBA) ─────────────────────────────────────────
    CARD_BG: tuple[int, int, int, int] = (18, 23, 32, 240)
    CARD_BG_SELECTED: tuple[int, int, int, int] = (30, 40, 56, 245)
    CARD_BG_WARNING: tuple[int, int, int, int] = (28, 18, 22, 220)

    # ── Spacing Scale ────────────────────────────────────────────────────
    SP_4: int = 4
    SP_8: int = 8
    SP_12: int = 12
    SP_16: int = 16
    SP_24: int = 24
    SP_32: int = 32
    SP_48: int = 48
    SP_64: int = 64

    # ── Border Radii ─────────────────────────────────────────────────────
    RADIUS_SM: int = 6
    RADIUS_MD: int = 10
    RADIUS_LG: int = 14

    # ── Border Widths ────────────────────────────────────────────────────
    BORDER_W_THIN: int = 1
    BORDER_W_FOCUS: int = 2


THEME = ThemeColors()
