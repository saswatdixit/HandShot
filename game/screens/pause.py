"""Pause Screen."""

from __future__ import annotations

import pygame
from typing import TYPE_CHECKING

from game.screens.base import Screen
from game.theme import THEME
from game.bubble_game import GameState
from game.ui_renderer import draw_card, draw_keycap

if TYPE_CHECKING:
    from gestures import PinchResult, ReloadResult
    from camera.hand_tracker import TrackingResult

class PauseScreen(Screen):

    def handle_key_event(self, event: pygame.event.Event, now: float) -> bool:
        if event.key in (pygame.K_p, pygame.K_PAUSE, pygame.K_SPACE):
            self.app._game.toggle_pause()
            self.app.audio.play_sfx("menu_select")
            return True
        elif event.key == pygame.K_r:
            self.app._restart_run(now)
            return True
        elif event.key in (pygame.K_m, pygame.K_ESCAPE):
            self.app._game.state = GameState.MODE_SELECT
            self.app.audio.play_sfx("menu_move")
            return True
        return False

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

        w, h = surface.get_size()
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill(THEME.OVERLAY_HEAVY)
        surface.blit(overlay, (0, 0))

        r = self.app.layout.pause_card_rect
        draw_card(surface, r, THEME.BG_SURFACE, THEME.BORDER_FOCUS, border_width=THEME.BORDER_W_FOCUS, border_radius=THEME.RADIUS_LG)

        self.app.typo.draw_text(surface, "Paused", self.app.typo.heading, THEME.TEXT_PRIMARY, (r.centerx, r.top + THEME.SP_32), anchor="center")

        # Action items
        actions = [
            ("P", "Resume"),
            ("R", "Restart"),
            ("M", "Menu"),
        ]
        item_y = r.top + THEME.SP_64 + THEME.SP_16
        for key, label in actions:
            draw_keycap(surface, key, label, self.app.typo.label, self.app.typo.body_small, r.centerx, item_y, active=False)
            item_y += THEME.SP_48
