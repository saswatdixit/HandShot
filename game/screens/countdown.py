"""Countdown Screen."""

from __future__ import annotations

import pygame
from typing import TYPE_CHECKING

from game.screens.base import Screen
from game.theme import THEME

if TYPE_CHECKING:
    from gestures import PinchResult, ReloadResult
    from camera.hand_tracker import TrackingResult

class CountdownScreen(Screen):

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

        width, height = surface.get_size()
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill(THEME.OVERLAY_DIM)
        surface.blit(overlay, (0, 0))

        num_str = self.app._game.countdown_text or "3"
        col = THEME.SUCCESS if num_str == "GO!" else THEME.ACCENT_CYAN
        self.app.typo.draw_text(surface, num_str, self.app.typo.countdown, col, (width // 2, height // 2 - THEME.SP_24), anchor="center")

        hint = "Pinch to shoot" if self.app._game.mode.infinite_ammo else "Pinch to shoot  ·  Move hand down to reload"
        self.app.typo.draw_text(surface, hint, self.app.typo.body, THEME.TEXT_SECONDARY, (width // 2, height // 2 + THEME.SP_64 + THEME.SP_16), anchor="center")
