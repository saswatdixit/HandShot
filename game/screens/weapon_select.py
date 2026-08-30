"""Weapon Selection Screen."""

from __future__ import annotations

import pygame
from typing import TYPE_CHECKING

from game.screens.base import Screen
from game.theme import THEME
from game.weapon import ALL_WEAPONS
from game.bubble_game import GameState
from game.ui_renderer import draw_card, draw_keycap

if TYPE_CHECKING:
    from gestures import PinchResult, ReloadResult
    from camera.hand_tracker import TrackingResult

class WeaponSelectScreen(Screen):

    def handle_key_event(self, event: pygame.event.Event, now: float) -> bool:
        if event.key == pygame.K_1:
            self.app._selected_weapon_idx = 0
            self.app.audio.play_sfx("menu_move")
            return True
        elif event.key == pygame.K_2:
            self.app._selected_weapon_idx = 1
            self.app.audio.play_sfx("menu_move")
            return True
        elif event.key == pygame.K_3:
            self.app._selected_weapon_idx = 2
            self.app.audio.play_sfx("menu_move")
            return True
        elif event.key == pygame.K_4:
            self.app._selected_weapon_idx = 3
            self.app.audio.play_sfx("menu_move")
            return True
        elif event.key in (pygame.K_UP, pygame.K_w):
            self.app._selected_weapon_idx = (self.app._selected_weapon_idx - 2) % len(ALL_WEAPONS)
            self.app.audio.play_sfx("menu_move")
            return True
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.app._selected_weapon_idx = (self.app._selected_weapon_idx + 2) % len(ALL_WEAPONS)
            self.app.audio.play_sfx("menu_move")
            return True
        elif event.key in (pygame.K_LEFT, pygame.K_a):
            self.app._selected_weapon_idx = (self.app._selected_weapon_idx - 1) % len(ALL_WEAPONS)
            self.app.audio.play_sfx("menu_move")
            return True
        elif event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_TAB):
            self.app._selected_weapon_idx = (self.app._selected_weapon_idx + 1) % len(ALL_WEAPONS)
            self.app.audio.play_sfx("menu_move")
            return True
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            chosen_weapon = ALL_WEAPONS[self.app._selected_weapon_idx]
            self.app._game.weapons.select_weapon(chosen_weapon)
            self.app._game.reset(self.app.layout.playfield_bounds, start_state=GameState.READY, now=now)
            self.app._particles.clear()
            self.app.audio.play_sfx("menu_select")
            return True
        elif event.key == pygame.K_ESCAPE:
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
        width, height = surface.get_size()
        surface.fill(THEME.BG_DARK)
        self.app._draw_ambient_grid(surface, width, height)

        # ── Title ────────────────────────────────────────────────────
        mode_str = self.app._game.mode.badge
        self.app.typo.draw_text(surface, "Select Weapon", self.app.typo.heading, THEME.TEXT_PRIMARY, (width // 2, 48), anchor="center")
        self.app.typo.draw_label(surface, mode_str, self.app.typo.label, THEME.TEXT_MUTED, (width // 2, 80), anchor="center", tracking=3)

        # ── 2×2 Weapon Cards ────────────────────────────────────────
        cards = self.app.layout.weapon_card_grid()

        for i, w_spec in enumerate(ALL_WEAPONS):
            rect = cards[i]
            is_sel = (i == self.app._selected_weapon_idx)

            bg = THEME.CARD_BG_SELECTED if is_sel else THEME.CARD_BG
            border = THEME.BORDER_FOCUS if is_sel else THEME.BORDER_SUBTLE
            bw = THEME.BORDER_W_FOCUS if is_sel else THEME.BORDER_W_THIN

            draw_card(surface, rect, bg, border, border_width=bw, border_radius=THEME.RADIUS_LG)

            # Number badge
            num_str = str(i + 1)
            draw_keycap(surface, num_str, "", self.app.typo.label, self.app.typo.caption, rect.left + THEME.SP_24, rect.top + THEME.SP_24, active=is_sel)

            # Weapon name
            text_x = rect.left + THEME.SP_48 + THEME.SP_8
            name_col = THEME.TEXT_PRIMARY if is_sel else THEME.TEXT_SECONDARY
            self.app.typo.draw_text(surface, w_spec.name, self.app.typo.heading, name_col, (text_x, rect.top + THEME.SP_16), anchor="topleft")

            # Tagline + difficulty
            detail = f"{w_spec.tagline}  ·  {w_spec.difficulty_rating}"
            detail_col = THEME.TEXT_SECONDARY if is_sel else THEME.TEXT_MUTED
            self.app.typo.draw_text(surface, detail, self.app.typo.body_small, detail_col, (text_x, rect.top + THEME.SP_48 - THEME.SP_4), anchor="topleft")

            # Ammo + reload time
            ammo_desc = "∞" if self.app._game.mode.infinite_ammo else f"{w_spec.magazine_size} / ∞"
            reload_str = f"{w_spec.reload_time_seconds:.1f}s"
            stat_str = f"{ammo_desc}   ·   {reload_str} reload"
            self.app.typo.draw_text(surface, stat_str, self.app.typo.caption, THEME.TEXT_MUTED, (text_x, rect.top + THEME.SP_64 + THEME.SP_4), anchor="topleft")

            # Selection indicator
            if is_sel:
                sel_x = rect.right - THEME.SP_16
                sel_y = rect.top + THEME.SP_16
                pygame.draw.circle(surface, THEME.BORDER_FOCUS, (sel_x, sel_y), 4)

        # ── Footer ──────────────────────────────────────────────────
        self.app.typo.draw_text(
            surface,
            "1-4  Select     ENTER  Start     ESC  Back",
            self.app.typo.caption,
            THEME.TEXT_MUTED,
            (width // 2, height - THEME.SP_32),
            anchor="center",
        )
