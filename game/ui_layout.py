"""Centralized UI Layout manager, safe zones, and collision-free coordinate calculations for HANDSHOT (Phase 12)."""

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

        # Top HUD Bar
        self.hud_height = settings.HUD_HEIGHT
        self.top_bar_rect = pygame.Rect(0, 0, w, self.hud_height)

        # 3 Isolated HUD Zones (Left, Center, Right)
        margin_x = settings.HUD_MARGIN_X
        margin_y = settings.HUD_MARGIN_Y

        left_w = min(280, int(w * 0.28))
        center_w = min(260, int(w * 0.30))
        right_w = min(300, int(w * 0.30))

        self.left_zone = pygame.Rect(margin_x, margin_y, left_w, self.hud_height - margin_y * 2)
        self.center_zone = pygame.Rect(w // 2 - center_w // 2, margin_y, center_w, self.hud_height - margin_y * 2)
        self.right_zone = pygame.Rect(w - margin_x - right_w, margin_y, right_w, self.hud_height - margin_y * 2)

        # Bottom Control Strip
        self.control_bar_height = settings.CONTROL_BAR_HEIGHT
        bar_w = min(720, w - margin_x * 2)
        self.control_bar_rect = pygame.Rect(w // 2 - bar_w // 2, h - self.control_bar_height - 6, bar_w, self.control_bar_height)

        # Playfield Bounds strictly between Top HUD and Bottom Control Strip
        self.playfield_bounds: Bounds = (
            float(settings.PLAYFIELD_LEFT),
            float(self.hud_height + 18),
            float(max(settings.PLAYFIELD_LEFT + 10, w - settings.PLAYFIELD_RIGHT_INSET)),
            float(max(self.hud_height + 30, h - self.control_bar_height - 20)),
        )

        # Debug Panel (Positioned in Top-Right corner below Top HUD)
        dbg_w = 285
        dbg_h = 265
        dbg_x = w - dbg_w - margin_x
        dbg_y = self.hud_height + 12
        self.debug_panel_rect = pygame.Rect(dbg_x, dbg_y, dbg_w, dbg_h)

        # Modal Cards (Ready, Pause, Results, Camera Setup)
        self.ready_card_rect = pygame.Rect(
            w // 2 - min(480, w - 40) // 2,
            h // 2 - 145,
            min(480, w - 40),
            290,
        )

        self.pause_card_rect = pygame.Rect(
            w // 2 - min(440, w - 40) // 2,
            h // 2 - 155,
            min(440, w - 40),
            310,
        )

        self.results_card_rect = pygame.Rect(
            w // 2 - min(480, w - 40) // 2,
            h // 2 - 205,
            min(480, w - 40),
            410,
        )

        self.camera_card_rect = pygame.Rect(
            w // 2 - min(540, w - 40) // 2,
            h // 2 - 200,
            min(540, w - 40),
            400,
        )

    def check_hud_zones_separated(self) -> bool:
        """Verify that Left, Center, and Right HUD zones never horizontally overlap."""
        return self.left_zone.right < self.center_zone.left and self.center_zone.right < self.right_zone.left

    def check_playfield_separated(self) -> bool:
        """Verify that the active playfield bounds are strictly below the HUD and above the control bar."""
        top_clearance = self.playfield_bounds[1] >= self.top_bar_rect.bottom
        bottom_clearance = self.playfield_bounds[3] <= self.control_bar_rect.top
        return top_clearance and bottom_clearance
