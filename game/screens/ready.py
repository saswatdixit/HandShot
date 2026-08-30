"""Ready Screen."""

from __future__ import annotations

import pygame
from typing import TYPE_CHECKING

from game.screens.base import Screen
from game.theme import THEME
from game.ui_renderer import draw_card, draw_progress_bar
from config import settings

if TYPE_CHECKING:
    from gestures import PinchResult, ReloadResult
    from camera.hand_tracker import TrackingResult

class ReadyScreen(Screen):

    def draw(
        self,
        surface: pygame.Surface,
        result: TrackingResult | None,
        pinch_result: PinchResult | None,
        reload_result: ReloadResult | None,
        aim_pos: tuple[float, float],
        now: float,
    ) -> None:
        self.app.draw_gameplay_base(surface, result, pinch_result, reload_result, aim_pos, now)

        has_hand = result is not None and result.has_hand
        r = self.app.layout.ready_card_rect
        draw_card(surface, r, THEME.BG_SURFACE, THEME.BORDER_SUBTLE, border_width=THEME.BORDER_W_FOCUS, border_radius=THEME.RADIUS_LG)

        if has_hand:
            title_text = "Hand Detected"
            title_col = THEME.SUCCESS
            sub_text = "Hold hand steady to begin..."
            prog = min(1.0, self.app._game.ready_hand_timer / settings.READY_HAND_STABLE_SECONDS)
        else:
            title_text = "Raise Your Hand"
            title_col = THEME.ACCENT_CYAN
            sub_text = "Position your hand in front of the camera"
            prog = 0.0

        self.app.typo.draw_text(surface, title_text, self.app.typo.heading, title_col, (r.centerx, r.top + THEME.SP_32), anchor="center")
        self.app.typo.draw_text(surface, sub_text, self.app.typo.body, THEME.TEXT_SECONDARY, (r.centerx, r.top + THEME.SP_64), anchor="center")

        # Progress bar
        bar_w = r.width - THEME.SP_64
        bar_x = r.left + THEME.SP_32
        bar_y = r.top + THEME.SP_64 + THEME.SP_32
        draw_progress_bar(surface, bar_x, bar_y, bar_w, 8, prog, THEME.BG_SURFACE_ELEVATED, THEME.SUCCESS, border_radius=4)
