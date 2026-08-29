"""Centralized, responsive typography system for HANDSHOT."""

from __future__ import annotations

import pygame


class Typography:
    """Scalable typography hierarchy with modern system font detection and fallbacks."""

    def __init__(self, screen_size: tuple[int, int] = (1280, 720)) -> None:
        if not pygame.font.get_init():
            pygame.font.init()
        self.screen_size = screen_size
        self._cache: dict[tuple[str, int, bool], pygame.font.Font] = {}
        self._update_fonts()

    def set_screen_size(self, screen_size: tuple[int, int]) -> None:
        if screen_size != self.screen_size:
            self.screen_size = screen_size
            self._cache.clear()
            self._update_fonts()

    def _scale_factor(self) -> float:
        w, h = self.screen_size
        return max(0.65, min(1.30, min(w / 1280.0, h / 720.0)))

    def _get_font(self, font_family: str, size: int, bold: bool = False) -> pygame.font.Font:
        key = (font_family, size, bold)
        if key not in self._cache:
            font = None
            if font_family == "display":
                candidates = [
                    "Outfit",
                    "Inter",
                    "Segoe UI Semibold",
                    "Segoe UI",
                    "Arial",
                    "Trebuchet MS",
                ]
            elif font_family == "mono":
                candidates = ["Consolas", "Courier New", "Lucida Console"]
            else:  # "ui" / body
                candidates = [
                    "Inter",
                    "Segoe UI",
                    "Arial",
                    "Tahoma",
                    "Helvetica",
                ]

            for name in candidates:
                try:
                    font = pygame.font.SysFont(name, size, bold=bold)
                    if font is not None:
                        break
                except Exception:
                    continue

            if font is None:
                font = pygame.font.Font(None, size)
            self._cache[key] = font
        return self._cache[key]

    def _update_fonts(self) -> None:
        sf = self._scale_factor()

        # ── Clean Typography Hierarchy ────────────────────────────────
        self.display = self._get_font("display", max(48, round(72 * sf)), bold=True)
        self.title = self._get_font("display", max(28, round(40 * sf)), bold=True)
        self.heading = self._get_font("display", max(18, round(24 * sf)), bold=True)
        self.body = self._get_font("ui", max(13, round(16 * sf)), bold=False)
        self.body_bold = self._get_font("ui", max(13, round(16 * sf)), bold=True)
        self.body_small = self._get_font("ui", max(11, round(13 * sf)), bold=False)
        self.label = self._get_font("ui", max(10, round(11 * sf)), bold=True)
        self.caption = self._get_font("ui", max(9, round(10 * sf)), bold=False)
        self.score_large = self._get_font("display", max(34, round(48 * sf)), bold=True)
        self.countdown = self._get_font("display", max(56, round(96 * sf)), bold=True)
        self.monospace_debug = self._get_font("mono", max(10, round(12 * sf)), bold=False)

        # ── Backwards Compatibility Aliases ───────────────────────────
        self.h1 = self.title
        self.h2 = self.heading
        self.display_xl = self.display
        self.display_l = self.title
        self.hud_label = self.label
        self.hud_value = self.heading
        self.subtitle = self._get_font("ui", max(13, round(18 * sf)), bold=False)
        self.small = self.body_small
        self.small_bold = self._get_font("ui", max(11, round(13 * sf)), bold=True)
        self.button = self._get_font("ui", max(13, round(17 * sf)), bold=True)
        self.score = self._get_font("display", max(20, round(28 * sf)), bold=True)
        self.debug = self.monospace_debug

    @staticmethod
    def format_score(value: int) -> str:
        """Format a score integer with comma separators."""
        return f"{value:,}"

    @staticmethod
    def draw_text(
        surface: pygame.Surface,
        text: str,
        font: pygame.font.Font,
        color: tuple[int, int, int] | tuple[int, int, int, int],
        pos: tuple[float, float],
        anchor: str = "topleft",
    ) -> pygame.Rect:
        """Render text with calculated bounding box and explicit anchor alignment."""
        if not text:
            return pygame.Rect(int(pos[0]), int(pos[1]), 0, 0)
        surf = font.render(text, True, color[:3])
        rect = surf.get_rect()
        anchor_map = {
            "left": "midleft",
            "right": "midright",
            "top": "midtop",
            "bottom": "midbottom",
        }
        resolved_anchor = anchor_map.get(anchor, anchor)
        setattr(rect, resolved_anchor, (round(pos[0]), round(pos[1])))
        surface.blit(surf, rect)
        return rect

    @staticmethod
    def draw_label(
        surface: pygame.Surface,
        text: str,
        font: pygame.font.Font,
        color: tuple[int, int, int] | tuple[int, int, int, int],
        pos: tuple[float, float],
        anchor: str = "topleft",
        tracking: int = 1,
    ) -> pygame.Rect:
        """Render uppercase label text with configurable letter-spacing (tracking)."""
        if not text:
            return pygame.Rect(int(pos[0]), int(pos[1]), 0, 0)
        upper = text.upper()

        # Calculate total width with tracking
        total_w = 0
        char_surfs: list[pygame.Surface] = []
        for ch in upper:
            ch_surf = font.render(ch, True, color[:3])
            char_surfs.append(ch_surf)
            total_w += ch_surf.get_width() + tracking
        total_w -= tracking  # No trailing gap
        total_h = char_surfs[0].get_height() if char_surfs else 0

        # Resolve anchor to get top-left position
        rect = pygame.Rect(0, 0, total_w, total_h)
        anchor_map = {
            "left": "midleft",
            "right": "midright",
            "top": "midtop",
            "bottom": "midbottom",
        }
        resolved = anchor_map.get(anchor, anchor)
        setattr(rect, resolved, (round(pos[0]), round(pos[1])))

        # Draw characters
        cx = rect.left
        for ch_surf in char_surfs:
            surface.blit(ch_surf, (cx, rect.top))
            cx += ch_surf.get_width() + tracking

        return rect

    @staticmethod
    def measure_text(text: str, font: pygame.font.Font) -> tuple[int, int]:
        """Calculate width and height of text string."""
        if not text:
            return 0, 0
        return font.size(text)
