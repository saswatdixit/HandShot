"""Mode Selection Screen."""

from __future__ import annotations

import pygame
from typing import TYPE_CHECKING

from game.screens.base import Screen
from game.theme import THEME
from game.game_mode import ALL_MODES
from game.bubble_game import GameState
from game.ui_renderer import draw_card, draw_vector_target, draw_vector_star, draw_vector_leaf, draw_vector_stopwatch

if TYPE_CHECKING:
    from gestures import PinchResult, ReloadResult
    from camera.hand_tracker import TrackingResult

class ModeSelectScreen(Screen):

    def handle_key_event(self, event: pygame.event.Event, now: float) -> bool:
        if event.key in (pygame.K_UP, pygame.K_w):
            self.app._selected_mode_idx = (self.app._selected_mode_idx - 2) % len(ALL_MODES)
            self.app.audio.play_sfx("menu_move")
            return True
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.app._selected_mode_idx = (self.app._selected_mode_idx + 2) % len(ALL_MODES)
            self.app.audio.play_sfx("menu_move")
            return True
        elif event.key in (pygame.K_LEFT, pygame.K_a):
            self.app._selected_mode_idx = (self.app._selected_mode_idx - 1) % len(ALL_MODES)
            self.app.audio.play_sfx("menu_move")
            return True
        elif event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_TAB):
            self.app._selected_mode_idx = (self.app._selected_mode_idx + 1) % len(ALL_MODES)
            self.app.audio.play_sfx("menu_move")
            return True
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            chosen_mode = ALL_MODES[self.app._selected_mode_idx]
            self.app._game.set_mode(chosen_mode, self.app.layout.playfield_bounds, start_state=GameState.WEAPON_SELECT)
            self.app._particles.clear()
            self.app.audio.play_sfx("menu_select")
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
        width, height = surface.get_size()
        surface.fill(THEME.BG_DARK)
        self.app._draw_ambient_grid(surface, width, height)

        # ── Title Area ───────────────────────────────────────────────
        self.app.typo.draw_text(surface, "HANDSHOT", self.app.typo.title, THEME.TEXT_PRIMARY, (width // 2, 48), anchor="center")
        self.app.typo.draw_label(surface, "Aim  ·  React  ·  Shoot", self.app.typo.label, THEME.TEXT_MUTED, (width // 2, 92), anchor="center", tracking=3)

        # ── Subtitle ────────────────────────────────────────────────
        self.app.typo.draw_text(surface, "Select Mode", self.app.typo.body, THEME.TEXT_SECONDARY, (width // 2, 126), anchor="center")

        # ── 2×2 Mode Cards ──────────────────────────────────────────
        cards = self.app.layout.mode_card_grid()

        _mode_meta = {
            ALL_MODES[0].mode: ("3 LIVES", ""), # Classic
            ALL_MODES[1].mode: ("∞ AMMO", ""),  # Arcade
            ALL_MODES[2].mode: ("ENDLESS", ""), # Chill
            ALL_MODES[3].mode: ("60 SEC", ""),  # Timed
        }

        _mode_icon = {
            ALL_MODES[0].mode: (draw_vector_target, THEME.ACCENT_CYAN),
            ALL_MODES[1].mode: (draw_vector_star, THEME.ACCENT_PURPLE),
            ALL_MODES[2].mode: (draw_vector_leaf, THEME.ACCENT_EMERALD),
            ALL_MODES[3].mode: (draw_vector_stopwatch, THEME.ACCENT_GOLD),
        }

        for i, m in enumerate(ALL_MODES):
            rect = cards[i]
            is_sel = (i == self.app._selected_mode_idx)

            bg = THEME.CARD_BG_SELECTED if is_sel else THEME.CARD_BG
            border = THEME.BORDER_FOCUS if is_sel else THEME.BORDER_SUBTLE
            bw = THEME.BORDER_W_FOCUS if is_sel else THEME.BORDER_W_THIN

            draw_card(surface, rect, bg, border, border_width=bw, border_radius=THEME.RADIUS_LG)

            # Icon
            icon_fn, icon_col = _mode_icon.get(m.mode, (draw_vector_star, THEME.ACCENT_PURPLE))
            icon_fn(surface, rect.left + THEME.SP_24, rect.top + THEME.SP_24, radius=12, color=icon_col if is_sel else THEME.TEXT_MUTED)

            # Mode name
            name_col = THEME.TEXT_PRIMARY if is_sel else THEME.TEXT_SECONDARY
            self.app.typo.draw_text(surface, m.name, self.app.typo.heading, name_col, (rect.left + THEME.SP_48 + THEME.SP_4, rect.top + THEME.SP_16), anchor="topleft")

            # Tagline
            tag_col = THEME.TEXT_SECONDARY if is_sel else THEME.TEXT_MUTED
            self.app.typo.draw_text(surface, m.tagline, self.app.typo.body_small, tag_col, (rect.left + THEME.SP_48 + THEME.SP_4, rect.top + THEME.SP_48 - THEME.SP_4), anchor="topleft")

            # Bottom row: mode meta + high score
            meta_y = rect.bottom - THEME.SP_24
            meta_label, _ = _mode_meta.get(m.mode, ("", ""))
            meta_col = icon_col if is_sel else THEME.TEXT_MUTED
            self.app.typo.draw_label(surface, meta_label, self.app.typo.label, meta_col, (rect.left + THEME.SP_16, meta_y), anchor="left", tracking=2)

            # High score
            hi = self.app._game.high_score if self.app._game.mode.mode == m.mode else 0
            if hi > 0:
                self.app.typo.draw_text(surface, f"BEST {hi:,}", self.app.typo.caption, THEME.WARNING, (rect.right - THEME.SP_16, meta_y), anchor="right")

            # Selection indicator
            if is_sel:
                sel_x = rect.right - THEME.SP_16
                sel_y = rect.top + THEME.SP_16
                pygame.draw.circle(surface, THEME.BORDER_FOCUS, (sel_x, sel_y), 4)

        # ── Footer Instructions ──────────────────────────────────────
        footer_y = height - THEME.SP_32
        self.app.typo.draw_text(
            surface,
            "↑↓←→  Navigate     ENTER  Play     ESC  Quit",
            self.app.typo.caption,
            THEME.TEXT_MUTED,
            (width // 2, footer_y),
            anchor="center",
        )
