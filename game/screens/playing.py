"""Playing Screen."""

from __future__ import annotations

import pygame
from typing import TYPE_CHECKING

from game.screens.base import Screen
from game.weapon import ALL_WEAPONS

if TYPE_CHECKING:
    from gestures import PinchResult, ReloadResult
    from camera.hand_tracker import TrackingResult

class PlayingScreen(Screen):

    def handle_key_event(self, event: pygame.event.Event, now: float) -> bool:
        if event.key in (pygame.K_p, pygame.K_PAUSE):
            paused = self.app._game.toggle_pause()
            if paused:
                self.app.audio.play_sfx("pause")
            return True
        elif event.key == pygame.K_r:
            self.app._handle_reload(now)
            return True
        elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
            idx = event.key - pygame.K_1
            if 0 <= idx < len(ALL_WEAPONS):
                self.app._game.weapons.select_weapon(ALL_WEAPONS[idx])
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
        # Gameplay rendering is just the base scene right now, no overlays
        self.app.draw_gameplay_base(surface, result, pinch_result, reload_result, aim_pos, now)
