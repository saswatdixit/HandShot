"""Centralized UI Layout manager, safe zones, and collision-free coordinate calculations for HANDSHOT."""

from __future__ import annotations

import pygame
from config import settings
from game.bubble import Bounds


class UILayout:
    """Calculates responsive bounding rectangles and non-overlapping layout zones."""

    def __init__(self, screen_size: tuple[int, int] = (1280, 720)) -> None:
        self.width = screen_size[0]
        self.height = screen_size[1]
        self._recalculate()

    def update_screen_size(self, screen_size: tuple[int, int]) -> None:
        if (self.width, self.height) != screen_size:
            self.width = max(640, screen_size[0])
            self.height = max(480, screen_size[1])
            self._recalculate()

    def _recalculate(self) -> None:
        w, h = self.width, self.height
        sp = 24  # base margin

        # ── Top HUD Bar ──────────────────────────────────────────────
        self.hud_height = settings.HUD_HEIGHT
        self.top_bar_rect = pygame.Rect(0, 0, w, self.hud_height)

        margin_x = settings.HUD_MARGIN_X
        margin_y = settings.HUD_MARGIN_Y
        zone_h = self.hud_height - margin_y * 2

        left_w = min(320, int(w * 0.30))
        center_w = min(280, int(w * 0.26))
        right_w = min(300, int(w * 0.28))

        self.left_zone = pygame.Rect(margin_x, margin_y, left_w, zone_h)
        self.center_zone = pygame.Rect(w // 2 - center_w // 2, margin_y, center_w, zone_h)
        self.right_zone = pygame.Rect(w - margin_x - right_w, margin_y, right_w, zone_h)

        # ── Bottom Control Strip ─────────────────────────────────────
        self.control_bar_height = settings.CONTROL_BAR_HEIGHT
        bar_w = min(720, w - margin_x * 2)
        self.control_bar_rect = pygame.Rect(w // 2 - bar_w // 2, h - self.control_bar_height - 6, bar_w, self.control_bar_height)

        # ── Playfield Bounds ─────────────────────────────────────────
        self.playfield_bounds: Bounds = (
            float(settings.PLAYFIELD_LEFT),
            float(self.hud_height + 18),
            float(max(settings.PLAYFIELD_LEFT + 10, w - settings.PLAYFIELD_RIGHT_INSET)),
            float(max(self.hud_height + 30, h - self.control_bar_height - 20)),
        )

        # ── Debug Panel ──────────────────────────────────────────────
        dbg_w = 285
        dbg_h = 265
        self.debug_panel_rect = pygame.Rect(w - dbg_w - sp, self.hud_height + 12, dbg_w, dbg_h)

        # ── Modal Cards ──────────────────────────────────────────────
        self.ready_card_rect = self._centered_card(w, h, 480, 260)
        self.pause_card_rect = self._centered_card(w, h, 360, 240)
        self.results_card_rect = self._centered_card(w, h, 460, 440)
        self.camera_card_rect = self._centered_card(w, h, 540, 400)

    @staticmethod
    def _centered_card(w: int, h: int, max_w: int, max_h: int) -> pygame.Rect:
        cw = min(max_w, w - 40)
        return pygame.Rect(w // 2 - cw // 2, h // 2 - max_h // 2, cw, max_h)

    def card_grid_2x2(
        self,
        area_x: int,
        area_y: int,
        area_w: int,
        area_h: int,
        gap_x: int = 20,
        gap_y: int = 16,
    ) -> list[pygame.Rect]:
        """Calculate 4 card rects arranged in a 2×2 grid within an area."""
        card_w = (area_w - gap_x) // 2
        card_h = (area_h - gap_y) // 2
        rects: list[pygame.Rect] = []
        for i in range(4):
            row, col = i // 2, i % 2
            x = area_x + col * (card_w + gap_x)
            y = area_y + row * (card_h + gap_y)
            rects.append(pygame.Rect(x, y, card_w, card_h))
        return rects

    def mode_card_grid(self) -> list[pygame.Rect]:
        """Return 4 mode-select card rects, responsively sized."""
        w, h = self.width, self.height
        max_card_w = min(420, (w - 80) // 2)
        max_card_h = min(140, (h - 280) // 2)
        grid_w = max_card_w * 2 + 20
        grid_h = max_card_h * 2 + 16
        gx = (w - grid_w) // 2
        gy = 160
        return self.card_grid_2x2(gx, gy, grid_w, grid_h, 20, 16)

    def weapon_card_grid(self) -> list[pygame.Rect]:
        """Return 4 weapon-select card rects, responsively sized."""
        w, h = self.width, self.height
        max_card_w = min(420, (w - 80) // 2)
        max_card_h = min(140, (h - 280) // 2)
        grid_w = max_card_w * 2 + 20
        grid_h = max_card_h * 2 + 16
        gx = (w - grid_w) // 2
        gy = 150
        return self.card_grid_2x2(gx, gy, grid_w, grid_h, 20, 16)

    def check_hud_zones_separated(self) -> bool:
        """Verify that Left, Center, and Right HUD zones never horizontally overlap."""
        return self.left_zone.right < self.center_zone.left and self.center_zone.right < self.right_zone.left

    def check_playfield_separated(self) -> bool:
        """Verify that the active playfield bounds are strictly below the HUD and above the control bar."""
        top_clearance = self.playfield_bounds[1] >= self.top_bar_rect.bottom
        bottom_clearance = self.playfield_bounds[3] <= self.control_bar_rect.top
        return top_clearance and bottom_clearance
