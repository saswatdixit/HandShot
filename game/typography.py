"""Centralized, responsive typography system for HANDSHOT (Phase 12)."""

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

        # Explicit Typography Levels (Phase 12)
        self.display = self._get_font("display", max(52, round(84 * sf)), bold=True)
        self.h1 = self._get_font("display", max(26, round(36 * sf)), bold=True)
        self.h2 = self._get_font("display", max(18, round(24 * sf)), bold=True)
        self.body = self._get_font("ui", max(13, round(16 * sf)), bold=False)
        self.body_bold = self._get_font("ui", max(13, round(16 * sf)), bold=True)
        self.body_small = self._get_font("ui", max(11, round(13 * sf)), bold=False)
        self.label = self._get_font("ui", max(11, round(12 * sf)), bold=True)
        self.caption = self._get_font("ui", max(10, round(11 * sf)), bold=False)
        self.score = self._get_font("display", max(20, round(28 * sf)), bold=True)
        self.score_large = self._get_font("display", max(32, round(44 * sf)), bold=True)
        self.monospace_debug = self._get_font("mono", max(11, round(13 * sf)), bold=False)

        # Backwards Compatibility Aliases
        self.display_xl = self.display
        self.display_l = self.h1
        self.title = self.h1
        self.heading = self.h2
        self.subtitle = self._get_font("ui", max(13, round(18 * sf)), bold=False)
        self.hud_label = self.label
        self.hud_value = self._get_font("display", max(18, round(25 * sf)), bold=True)
        self.small = self.body_small
        self.small_bold = self._get_font("ui", max(11, round(13 * sf)), bold=True)
        self.button = self._get_font("ui", max(13, round(17 * sf)), bold=True)
        self.countdown = self._get_font("display", max(56, round(96 * sf)), bold=True)
        self.debug = self.monospace_debug

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
    def measure_text(text: str, font: pygame.font.Font) -> tuple[int, int]:
        """Calculate width and height of text string."""
        if not text:
            return 0, 0
        return font.size(text)
