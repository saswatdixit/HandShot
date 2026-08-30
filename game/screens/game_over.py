"""Game Over Screen."""

from __future__ import annotations

import pygame
from typing import TYPE_CHECKING

from game.screens.base import Screen
from game.theme import THEME
from game.bubble_game import GameState
from game.ui_renderer import draw_card, draw_separator

if TYPE_CHECKING:
    from gestures import PinchResult, ReloadResult
    from camera.hand_tracker import TrackingResult

class GameOverScreen(Screen):

    def handle_key_event(self, event: pygame.event.Event, now: float) -> bool:
        if event.key in (pygame.K_r, pygame.K_RETURN, pygame.K_SPACE):
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

        r = self.app.layout.results_card_rect
        draw_card(surface, r, THEME.BG_SURFACE, THEME.BORDER_FOCUS, border_width=THEME.BORDER_W_FOCUS, border_radius=THEME.RADIUS_LG)

        # Title
        is_high = self.app._game.is_new_high_score
        title = "New High Score!" if is_high else "Run Complete"
        title_col = THEME.WARNING if is_high else THEME.ACCENT_CYAN
        self.app.typo.draw_text(surface, title, self.app.typo.heading, title_col, (r.centerx, r.top + THEME.SP_24), anchor="center")

        # Big score
        score_txt = self.app.typo.format_score(self.app._game.score.score)
        self.app.typo.draw_text(surface, score_txt, self.app.typo.display, THEME.TEXT_PRIMARY, (r.centerx, r.top + THEME.SP_64 + THEME.SP_8), anchor="center")

        # "FINAL SCORE" label
        self.app.typo.draw_label(surface, "FINAL SCORE", self.app.typo.caption, THEME.TEXT_MUTED, (r.centerx, r.top + THEME.SP_64 + THEME.SP_48 + THEME.SP_4), anchor="center", tracking=3)

        # Mode · Weapon
        mode_weapon = f"{self.app._game.mode.name}  ·  {self.app._game.weapons.spec.name}"
        self.app.typo.draw_text(surface, mode_weapon, self.app.typo.body_small, THEME.TEXT_SECONDARY, (r.centerx, r.top + 148), anchor="center")

        # Separator
        sep_y = r.top + 170
        draw_separator(surface, r.left + THEME.SP_32, sep_y, r.right - THEME.SP_32)

        # Stats rows
        stats = [
            ("ACCURACY", f"{self.app._game.stats.accuracy:.0f}%"),
            ("HITS", str(self.app._game.stats.targets_hit)),
            ("SHOTS", str(self.app._game.stats.shots_fired)),
            ("TIME", f"{self.app._game.gameplay_time:.1f}s"),
        ]
        row_y = sep_y + THEME.SP_16
        stat_left = r.left + THEME.SP_48
        stat_right = r.right - THEME.SP_48
        for label, value in stats:
            self.app.typo.draw_label(surface, label, self.app.typo.label, THEME.TEXT_MUTED, (stat_left, row_y), anchor="left", tracking=2)
            self.app.typo.draw_text(surface, value, self.app.typo.body_bold, THEME.TEXT_PRIMARY, (stat_right, row_y), anchor="right")
            row_y += THEME.SP_32

        # Action footer
        self.app.typo.draw_text(
            surface,
            "ENTER  Play Again     ESC  Menu",
            self.app.typo.caption,
            THEME.TEXT_MUTED,
            (r.centerx, r.bottom - THEME.SP_24),
            anchor="center",
        )
