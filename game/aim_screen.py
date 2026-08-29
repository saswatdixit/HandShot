"""Phase 10.5 Pygame Aim Screen with complete UI/UX, typography, layout overhaul, and vector icons."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

from aim.aim_controller import AimController, AimSettings
from audio.audio_manager import AudioManager
from config import settings
from game.bubble import Bounds, Bubble, BubbleType
from game.bubble_game import BubbleGame, GameState
from game.game_mode import ALL_MODES, GameMode, ModeConfig
from game.particles import ParticleSystem
from game.typography import Typography
from game.ui_renderer import (
    draw_card,
    draw_keycap,
    draw_vector_heart,
    draw_vector_leaf,
    draw_vector_speaker,
    draw_vector_star,
    draw_vector_stopwatch,
    draw_vector_target,
)
from gestures.pinch_detector import PinchDetector, PinchPhase, PinchResult

if TYPE_CHECKING:
    from camera.camera_manager import CameraManager
    from camera.hand_tracker import HandTracker, TrackingResult


@dataclass
class ShotEffect:
    position: tuple[float, float]
    created_at: float
    expires_at: float
    hit: bool

    def visible(self, now: float) -> bool:
        return now < self.expires_at


@dataclass
class FloatingScore:
    text: str
    x: float
    y: float
    created_at: float
    expires_at: float
    color: tuple[int, int, int] = (110, 235, 255)

    def visible(self, now: float) -> bool:
        return now < self.expires_at


class AimScreen:
    """Orchestrates arcade flow, responsive vector UI, and hand-aim interaction."""

    def __init__(
        self,
        camera: CameraManager | None,
        tracker: HandTracker | None,
        debug_hud: bool = False,
    ) -> None:
        self.camera = camera
        self.tracker = tracker
        self._aim = AimController(
            (settings.GAME_WIDTH, settings.GAME_HEIGHT),
            AimSettings(
                input_left=settings.AIM_INPUT_LEFT,
                input_top=settings.AIM_INPUT_TOP,
                input_right=settings.AIM_INPUT_RIGHT,
                input_bottom=settings.AIM_INPUT_BOTTOM,
                deadzone=settings.AIM_DEADZONE,
                smoothing_hz=settings.AIM_SMOOTHING_HZ,
                margin=settings.CROSSHAIR_MARGIN,
                pre_shot_anchor_seconds=settings.AIM_PRE_SHOT_ANCHOR_SECONDS,
            ),
        )
        self._pinch = PinchDetector()
        self._game = BubbleGame(start_state=GameState.MODE_SELECT)
        self.audio = AudioManager()
        self._particles = ParticleSystem()
        self._shot: ShotEffect | None = None
        self._floating_scores: list[FloatingScore] = []
        self._fire_pulse_until = 0.0
        self._life_lost_flash_until = 0.0
        self._debug_hud = debug_hud
        self._last_pinch: PinchResult | None = None
        self._last_shot_display_until = 0.0
        self._selected_mode_idx = 0
        self._last_countdown_number = 3
        self._audio_notify_until = 0.0
        self._audio_notify_text = ""
        self._game_over_entered_at = 0.0
        self.typo = Typography((settings.GAME_WIDTH, settings.GAME_HEIGHT))

    def run(self, duration: float = 0.0) -> int:
        pygame.init()
        screen = pygame.display.set_mode(
            (settings.GAME_WIDTH, settings.GAME_HEIGHT), pygame.RESIZABLE
        )
        pygame.display.set_caption(settings.GAME_WINDOW_NAME)
        clock = pygame.time.Clock()
        self.typo.set_screen_size(screen.get_size())

        started = time.perf_counter()
        last_result: TrackingResult | None = None
        running = True
        exit_code = 0
        self._aim.set_playfield(self._playfield(screen.get_size()))

        try:
            while running:
                delta_seconds = clock.tick(settings.GAME_FPS) / 1000.0
                now = time.perf_counter()

                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                    elif event.type == pygame.VIDEORESIZE:
                        screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                        self.typo.set_screen_size(event.size)
                        self._aim.set_screen_size(event.size)
                        self._aim.set_playfield(self._playfield(event.size))
                    elif event.type == pygame.KEYDOWN:
                        running = self._handle_key_event(event, screen, now)

                # Camera & Hand Tracking read
                frame = self.camera.read() if self.camera else None
                pinch_result: PinchResult | None = None
                if frame is not None and self.tracker is not None:
                    last_result = self.tracker.process(frame, mirrored=self.camera.mirror)
                    if last_result.hand is not None:
                        pinch_result = self._pinch.update(last_result.hand, now)
                    else:
                        pinch_result = self._pinch.update(None, now)

                if pinch_result is not None:
                    self._last_pinch = pinch_result

                has_hand = (last_result is not None and last_result.has_hand)
                fingertip = (
                    last_result.hand.index_tip_norm
                    if last_result is not None and last_result.hand is not None
                    else None
                )
                position = self._aim.update(fingertip, delta_seconds, now=now)

                # Update simulation & audio
                self._update_simulation(delta_seconds, screen, has_hand, now)

                # Process shooting in PLAYING state
                shot_event = self._pinch_to_shot_event(pinch_result, now)
                if shot_event is not None and self._game.state is GameState.PLAYING:
                    self._process_shot(shot_event, now)

                # Update particles
                self._particles.update(delta_seconds, now)

                # Expire floating scores
                self._floating_scores = [fs for fs in self._floating_scores if fs.visible(now)]

                # Render frame
                self._draw(screen, position, last_result, pinch_result, now)
                pygame.display.flip()

                if duration and time.perf_counter() - started >= duration:
                    running = False
        except Exception as exc:
            print(f"\nGame error: {exc}")
            exit_code = 1
        finally:
            self.audio.close()
            pygame.quit()
        return exit_code

    # -- Input Handling ----------------------------------------------------

    def _handle_key_event(self, event: pygame.event.Event, screen: pygame.Surface, now: float) -> bool:
        st = self._game.state

        if event.key in (pygame.K_ESCAPE, pygame.K_q):
            if st is GameState.MODE_SELECT:
                return False
            elif st in (GameState.PLAYING, GameState.PAUSED, GameState.GAME_OVER):
                self._game.state = GameState.MODE_SELECT
                self._particles.clear()
                self.audio.stop_music()
                self.audio.play_sfx("menu_move")
                return True
            else:
                self._game.state = GameState.MODE_SELECT
                return True

        if event.key == pygame.K_m:
            if st in (GameState.GAME_OVER, GameState.PAUSED):
                self._game.state = GameState.MODE_SELECT
                self._particles.clear()
                self.audio.stop_music()
                self.audio.play_sfx("menu_move")
            else:
                is_muted = self.audio.toggle_mute()
                self._audio_notify_text = "AUDIO MUTED" if is_muted else "AUDIO UNMUTED"
                self._audio_notify_until = now + 1.5

        elif event.key == pygame.K_c:
            if self.camera:
                self.camera.toggle_mirror()
                self._aim.reset()
                self._pinch.reset()
                if self.tracker:
                    self.tracker.reset()

        elif event.key == pygame.K_d:
            self._debug_hud = not self._debug_hud

        # Mode Select Navigation
        if st is GameState.MODE_SELECT:
            if event.key in (pygame.K_UP, pygame.K_w):
                self._selected_mode_idx = (self._selected_mode_idx - 2) % len(ALL_MODES)
                self.audio.play_sfx("menu_move")
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self._selected_mode_idx = (self._selected_mode_idx + 2) % len(ALL_MODES)
                self.audio.play_sfx("menu_move")
            elif event.key in (pygame.K_LEFT, pygame.K_a):
                self._selected_mode_idx = (self._selected_mode_idx - 1) % len(ALL_MODES)
                self.audio.play_sfx("menu_move")
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self._selected_mode_idx = (self._selected_mode_idx + 1) % len(ALL_MODES)
                self.audio.play_sfx("menu_move")
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                chosen_mode = ALL_MODES[self._selected_mode_idx]
                self._game.set_mode(chosen_mode, self._playfield(screen.get_size()))
                self._particles.clear()
                self.audio.play_sfx("menu_select")

        elif st is GameState.PLAYING:
            if event.key in (pygame.K_p, pygame.K_PAUSE):
                paused = self._game.toggle_pause()
                if paused:
                    self.audio.play_sfx("pause")
            elif event.key == pygame.K_r:
                self._restart_run(screen, now)

        elif st is GameState.PAUSED:
            if event.key in (pygame.K_p, pygame.K_PAUSE, pygame.K_SPACE):
                self._game.toggle_pause()
                self.audio.play_sfx("menu_select")
            elif event.key == pygame.K_r:
                self._restart_run(screen, now)

        elif st is GameState.GAME_OVER:
            if event.key == pygame.K_r:
                self._restart_run(screen, now)

        return True

    def _restart_run(self, screen: pygame.Surface, now: float) -> None:
        self._aim.reset()
        self._pinch.reset()
        self._floating_scores.clear()
        self._particles.clear()
        self._game.reset(self._playfield(screen.get_size()), start_state=GameState.READY, now=now)
        if self.tracker is not None:
            self.tracker.reset()
        self.audio.stop_music()
        self.audio.play_sfx("menu_select")

    # -- Simulation & Audio Triggers ---------------------------------------

    def _update_simulation(self, delta_seconds: float, screen: pygame.Surface, has_hand: bool, now: float) -> None:
        prev_state = self._game.state
        prev_countdown = self._game.countdown_number

        escaped = self._game.update(
            delta_seconds,
            self._playfield(screen.get_size()),
            hand_tracked=has_hand,
            now=now,
        )

        if self._game.state is GameState.COUNTDOWN:
            if self._game.countdown_number != prev_countdown:
                if self._game.countdown_number > 0:
                    self.audio.play_sfx("countdown_tick")
                elif self._game.countdown_number == 0:
                    self.audio.play_sfx("countdown_go")
                self._last_countdown_number = self._game.countdown_number

        elif prev_state is GameState.COUNTDOWN and self._game.state is GameState.PLAYING:
            self._pinch.reset()
            self.audio.play_music(self._game.mode.theme_music_track)

        elif prev_state is GameState.PLAYING and self._game.state is GameState.GAME_OVER:
            self.audio.stop_music()
            self._game_over_entered_at = now
            if self._game.is_new_high_score:
                self.audio.play_sfx("high_score")
            else:
                self.audio.play_sfx("game_over")

        if escaped and has_hand and self._game.state is GameState.PLAYING:
            if self._game.mode.allow_life_loss:
                self._life_lost_flash_until = now + 0.30
                self.audio.play_sfx("life_lost")
            else:
                self.audio.play_sfx("bubble_escape")

    def _process_shot(self, event: ShotEffect, now: float) -> None:
        hit_bubble, points = self._game.shoot(event.position)
        event.hit = (hit_bubble is not None)
        self._shot = event
        self._fire_pulse_until = now + settings.CROSSHAIR_FIRE_PULSE_SECONDS

        if hit_bubble is not None:
            self._particles.emit_target_burst(
                hit_bubble.position[0], hit_bubble.position[1], hit_bubble.target_type, now
            )

            mult = self._game.combo.multiplier
            tag = f"+{points}" if mult == 1 else f"+{points} [x{mult}]"
            if hit_bubble.target_type is BubbleType.GOLDEN:
                pop_col = (255, 225, 80)
            elif hit_bubble.target_type is BubbleType.SMALL:
                pop_col = (80, 235, 255)
            elif hit_bubble.target_type is BubbleType.LARGE:
                pop_col = (140, 205, 255)
            else:
                pop_col = (105, 245, 160)

            self._floating_scores.append(
                FloatingScore(tag, hit_bubble.position[0], hit_bubble.position[1], now, now + 0.85, color=pop_col)
            )
            self.audio.play_sfx(hit_bubble.hit_sound_name)

            combo_val = self._game.combo.current_combo
            if combo_val >= settings.COMBO_TIER_3_HITS and (combo_val % 5 == 0 or combo_val == 10):
                self.audio.play_sfx("combo_streak")
            elif combo_val in (settings.COMBO_TIER_1_HITS, settings.COMBO_TIER_2_HITS):
                self.audio.play_sfx("combo")
        else:
            self.audio.play_sfx("bubble_miss")

    def _pinch_to_shot_event(self, pinch_result: PinchResult | None, now: float) -> ShotEffect | None:
        if pinch_result is not None and pinch_result.shot:
            self._last_shot_display_until = now + 0.40
            anchor_pos = self._aim.get_anchored_position(now)
            return ShotEffect(position=anchor_pos, created_at=now, expires_at=now + settings.SHOT_EFFECT_SECONDS, hit=False)
        return None

    # -- Rendering ---------------------------------------------------------

    def _draw(
        self,
        screen: pygame.Surface,
        position: tuple[float, float],
        result: TrackingResult | None,
        pinch_result: PinchResult | None,
        now: float,
    ) -> None:
        width, height = screen.get_size()
        bounds = self._playfield((width, height))
        screen.fill((9, 14, 23))

        # Restrained minimal grid
        grid_color = (16, 25, 40)
        for x in range(0, width, 72):
            pygame.draw.line(screen, grid_color, (x, 0), (x, height))
        for y in range(0, height, 72):
            pygame.draw.line(screen, grid_color, (0, y), (width, y))

        # Bottom hazard boundary line (if mode allows life loss)
        if self._game.mode.allow_life_loss and self._game.state in (GameState.PLAYING, GameState.PAUSED):
            hazard_y = round(bounds[3])
            for hx in range(round(bounds[0]), round(bounds[2]), 16):
                pygame.draw.line(screen, (60, 85, 120), (hx, hazard_y), (hx + 8, hazard_y), 1)

        # Draw bubbles during active gameplay and pause
        if self._game.state in (GameState.PLAYING, GameState.PAUSED):
            for bubble in self._game.targets.bubbles:
                self._draw_bubble(screen, bubble, now)

        # Draw particles and shockwaves
        self._particles.draw(screen, now)

        # Draw shot rings
        if self._shot is not None and self._shot.visible(now):
            shot_x, shot_y = round(self._shot.position[0]), round(self._shot.position[1])
            if self._shot.hit:
                progress = (self._shot.expires_at - now) / max(settings.SHOT_EFFECT_SECONDS, 1e-6)
                radius = round(16 + 22 * (1.0 - progress))
                pygame.draw.circle(screen, (110, 245, 160), (shot_x, shot_y), radius, 2)
            else:
                pygame.draw.line(screen, (255, 140, 90), (shot_x - 6, shot_y - 6), (shot_x + 6, shot_y + 6), 2)
                pygame.draw.line(screen, (255, 140, 90), (shot_x - 6, shot_y + 6), (shot_x + 6, shot_y - 6), 2)

        # Draw floating score popups
        for fs in self._floating_scores:
            age = now - fs.created_at
            lifespan = fs.expires_at - fs.created_at
            fade = max(0.0, min(1.0, 1.0 - (age / max(lifespan, 1e-6))))
            float_y = fs.y - (age * 45.0)
            score_surf = self.typo.heading.render(fs.text, True, fs.color)
            score_surf.set_alpha(round(fade * 255))
            screen.blit(score_surf, score_surf.get_rect(center=(round(fs.x), round(float_y))))

        # Draw responsive crosshair
        hovered = any(bubble.contains(position) for bubble in self._game.targets.bubbles)
        active_shot = self._shot if self._shot is not None and self._shot.visible(now) else None
        self._draw_crosshair(screen, position, hovered, active_shot, self._fire_pulse_until, now)

        # Life loss red edge flash
        if now < self._life_lost_flash_until:
            flash_alpha = round(((self._life_lost_flash_until - now) / 0.30) * 80)
            flash_surf = pygame.Surface((width, height), pygame.SRCALPHA)
            pygame.draw.rect(flash_surf, (255, 50, 50, flash_alpha), (0, 0, width, height), 6)
            screen.blit(flash_surf, (0, 0))

        # Render Top HUD (isolated non-colliding zones)
        has_hand = (result is not None and result.has_hand)
        if self._game.state is not GameState.MODE_SELECT:
            self._draw_hud(screen, result, width, height, now)

        # Render State Screens
        if self._game.state is GameState.MODE_SELECT:
            self._draw_mode_select(screen, width, height, now)
        elif self._game.state is GameState.READY:
            self._draw_ready(screen, width, height, has_hand)
        elif self._game.state is GameState.COUNTDOWN:
            self._draw_countdown(screen, width, height, now)
        elif self._game.state is GameState.PAUSED:
            self._draw_paused(screen, width, height)
        elif self._game.state is GameState.GAME_OVER:
            self._draw_game_over(screen, width, height, now)

        # Audio toast notification
        if now < self._audio_notify_until:
            toast_rect = pygame.Rect(width - 170, height - 36, 150, 26)
            draw_card(screen, toast_rect, (20, 32, 50, 220), (60, 95, 140), border_radius=6)
            self.typo.draw_text(screen, self._audio_notify_text, self.typo.small_bold, (255, 220, 80), toast_rect.center, anchor="center")

        # Debug HUD (isolated below top bar)
        if self._debug_hud:
            self._draw_debug_hud(screen, result, pinch_result, now)

    # -- UI Screens & HUD Layout -------------------------------------------

    def _draw_hud(
        self,
        screen: pygame.Surface,
        result: TrackingResult | None,
        width: int,
        height: int,
        now: float,
    ) -> None:
        """Top Header Bar with strictly isolated Left, Center, and Right zones."""
        mode = self._game.mode
        hud_h = 84

        # Header background panel
        draw_card(screen, (0, 0, width, hud_h), (11, 17, 28, 240), (28, 42, 64), border_width=1, border_radius=0)

        # === 1. LEFT ZONE (Branding, Mode, Tracking) ===
        lx = 24
        self.typo.draw_text(screen, "HANDSHOT", self.typo.title, (130, 225, 255), (lx, 14), anchor="topleft")
        self.typo.draw_text(screen, f"{mode.name} ARCADE", self.typo.subtitle, (140, 165, 195), (lx, 42), anchor="topleft")

        # Tracking status pill
        track_y = 64
        if self.tracker is None:
            st_col, st_txt = (150, 150, 150), "TRACKING OFF"
        elif result is not None and result.has_hand:
            st_col, st_txt = (105, 245, 160), "TRACKED"
        elif result is not None and result.coasting:
            st_col, st_txt = (255, 180, 70), "COASTING"
        else:
            st_col, st_txt = (240, 180, 80), "SEARCHING"

        pygame.draw.circle(screen, st_col, (lx + 4, track_y + 4), 4)
        self.typo.draw_text(screen, st_txt, self.typo.small_bold, st_col, (lx + 14, track_y), anchor="topleft")

        # === 2. CENTER ZONE (Score & Combo Badge) ===
        cx = width // 2
        self.typo.draw_text(screen, "SCORE", self.typo.hud_label, (140, 165, 195), (cx, 12), anchor="midtop")
        self.typo.draw_text(screen, f"{self._game.score.score:,}", self.typo.score, (115, 235, 255), (cx, 28), anchor="midtop")

        # Combo badge (compact pill underneath score)
        if mode.allow_combo and self._game.combo.current_combo > 1:
            combo = self._game.combo.current_combo
            mult = self._game.combo.multiplier
            is_streak = (combo >= settings.COMBO_TIER_3_HITS)
            combo_text = f"×{mult} STREAK" if is_streak else f"×{mult} COMBO"
            badge_bg = (55, 28, 12) if is_streak else (24, 38, 58)
            badge_border = (255, 130, 50) if is_streak else (80, 140, 210)
            badge_col = (255, 180, 70) if is_streak else (255, 225, 90)

            badge_w, badge_h = self.typo.measure_text(combo_text, self.typo.small_bold)
            badge_rect = pygame.Rect(cx - (badge_w + 16) // 2, 58, badge_w + 16, badge_h + 4)
            draw_card(screen, badge_rect, badge_bg, badge_border, border_radius=5)
            self.typo.draw_text(screen, combo_text, self.typo.small_bold, badge_col, badge_rect.center, anchor="center")

        # === 3. RIGHT ZONE (Best, Lives / Timer, Accuracy, Mute) ===
        rx = width - 24
        self.typo.draw_text(screen, "BEST", self.typo.hud_label, (140, 165, 195), (rx - 65, 12), anchor="topright")
        self.typo.draw_text(screen, f"{self._game.high_score:,}", self.typo.hud_value, (255, 215, 80), (rx, 10), anchor="topright")

        # Mode status row (Hearts / Timer / Mode Tag)
        status_y = 40
        if mode.allow_life_loss:
            for i in range(mode.initial_lives):
                is_active = (i < self._game.stats.lives)
                draw_vector_heart(screen, rx - 48 + i * 22, status_y + 4, size=16, active=is_active)
        elif mode.time_limit_seconds is not None:
            rem = self._game.time_remaining or 0.0
            time_col = (255, 95, 95) if rem < 10.0 else (255, 215, 80)
            draw_vector_stopwatch(screen, rx - 65, status_y + 4, radius=8, color=time_col)
            self.typo.draw_text(screen, f"{rem:.1f}s", self.typo.hud_value, time_col, (rx, status_y - 2), anchor="topright")
        else:
            if mode.mode == GameMode.CHILL:
                draw_vector_leaf(screen, rx - 70, status_y + 4, radius=8)
            else:
                draw_vector_target(screen, rx - 70, status_y + 4, radius=8)
            self.typo.draw_text(screen, mode.badge, self.typo.body_bold, (110, 235, 150), (rx, status_y - 2), anchor="topright")

        # Accuracy & Audio Mute icon row
        acc_y = 64
        self.typo.draw_text(screen, f"ACCURACY {self._game.stats.accuracy:.1f}%", self.typo.small, (160, 185, 210), (rx - 30, acc_y), anchor="topright")
        draw_vector_speaker(screen, rx - 8, acc_y + 6, radius=7, muted=self.audio.muted)

        # Bottom control hints
        self.typo.draw_text(
            screen,
            "[P] Pause    [R] Restart    [M] Mute    [C] Mirror    [D] Debug HUD",
            self.typo.small,
            (140, 160, 185),
            (width // 2, height - 20),
            anchor="midbottom",
        )

    def _draw_mode_select(
        self,
        screen: pygame.Surface,
        width: int,
        height: int,
        now: float,
    ) -> None:
        """Balanced 2x2 Grid Mode Selection Screen with rich vector cards."""
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((8, 12, 22, 230))
        screen.blit(overlay, (0, 0))

        # Header Title
        self.typo.draw_text(screen, "HANDSHOT", self.typo.display_l, (130, 225, 255), (width // 2, 45), anchor="center")
        self.typo.draw_text(screen, "GESTURE ARCADE  •  CHOOSE YOUR MODE", self.typo.heading, (255, 220, 80), (width // 2, 85), anchor="center")

        # 2x2 Grid Layout
        card_w = min(480, (width - 70) // 2)
        card_h = 105
        gap_x = 24
        gap_y = 20

        grid_w = card_w * 2 + gap_x
        grid_h = card_h * 2 + gap_y
        start_x = (width - grid_w) // 2
        start_y = 135

        for i, mode in enumerate(ALL_MODES):
            row = i // 2
            col = i % 2
            card_x = start_x + col * (card_w + gap_x)
            card_y = start_y + row * (card_h + gap_y)

            is_selected = (i == self._selected_mode_idx)

            card_bg = (24, 38, 62, 245) if is_selected else (13, 20, 32, 190)
            border_col = (115, 235, 255) if is_selected else (40, 60, 88)
            b_width = 2 if is_selected else 1

            draw_card(screen, (card_x, card_y, card_w, card_h), card_bg, border_col, border_width=b_width, border_radius=12)

            # Mode Vector Icon
            icon_x = card_x + 30
            icon_y = card_y + 32
            if mode.mode == GameMode.CLASSIC:
                draw_vector_heart(screen, icon_x, icon_y, size=18, active=True)
            elif mode.mode == GameMode.CHILL:
                draw_vector_leaf(screen, icon_x, icon_y, radius=10)
            elif mode.mode == GameMode.TIMED:
                draw_vector_stopwatch(screen, icon_x, icon_y, radius=10)
            else:
                draw_vector_target(screen, icon_x, icon_y, radius=10)

            # Mode Name
            name_col = (255, 240, 90) if is_selected else (220, 235, 250)
            self.typo.draw_text(screen, mode.name, self.typo.heading, name_col, (card_x + 52, card_y + 20), anchor="topleft")

            # Selection Pill Tag
            if is_selected:
                draw_keycap(screen, "SELECTED", self.typo.small_bold, card_x + card_w - 55, card_y + 30, text_color=(105, 245, 160), bg_color=(20, 48, 42), border_color=(45, 160, 110))

            # Mode Tagline & Description
            desc_col = (195, 215, 235) if is_selected else (140, 155, 175)
            self.typo.draw_text(screen, mode.tagline, self.typo.body, desc_col, (card_x + 22, card_y + 54), anchor="topleft")

            # High Score Bar
            best = self._game.high_score if mode.mode == self._game.mode.mode else 0
            best_txt = f"BEST SCORE: {best:,}"
            self.typo.draw_text(screen, best_txt, self.typo.small_bold, (130, 220, 255) if is_selected else (100, 130, 160), (card_x + 22, card_y + 80), anchor="topleft")

        # Footer controls
        self.typo.draw_text(
            screen,
            "[ W / A / S / D / Arrows ] Select Mode    [ ENTER / SPACE ] Start Game    [ M ] Mute    [ Q ] Quit",
            self.typo.small,
            (160, 185, 210),
            (width // 2, height - 34),
            anchor="center",
        )

    def _draw_ready(
        self,
        screen: pygame.Surface,
        width: int,
        height: int,
        has_hand: bool,
    ) -> None:
        """Polished Hand Acquisition Card with animated progress."""
        card_w, card_h = min(480, width - 40), 290
        card_x = (width - card_w) // 2
        card_y = (height - card_h) // 2

        draw_card(screen, (card_x, card_y, card_w, card_h), (11, 18, 30, 240), (50, 75, 115), border_width=2, border_radius=14)

        # Header Title & Subtitle
        self.typo.draw_text(screen, f"HANDSHOT • {self._game.mode.name}", self.typo.title, (130, 225, 255), (width // 2, card_y + 36), anchor="center")
        self.typo.draw_text(screen, "READY TO PLAY", self.typo.heading, (255, 220, 80), (width // 2, card_y + 76), anchor="center")

        # Central Status Indicator Box
        box_w = 340
        box_h = 100
        box_x = (width - box_w) // 2
        box_y = card_y + 110

        draw_card(screen, (box_x, box_y, box_w, box_h), (16, 26, 42, 200), (40, 60, 90), border_radius=8)

        if has_hand:
            progress = min(1.0, self._game.ready_hand_timer / max(settings.READY_HAND_STABLE_SECONDS, 1e-6))
            self.typo.draw_text(screen, "HAND DETECTED", self.typo.heading, (105, 245, 160), (width // 2, box_y + 24), anchor="center")
            self.typo.draw_text(screen, "Calibrating...", self.typo.small, (170, 200, 230), (width // 2, box_y + 50), anchor="center")

            # Progress Bar
            bar_w = 240
            bar_h = 8
            bar_x = (width - bar_w) // 2
            bar_y = box_y + 72
            pygame.draw.rect(screen, (28, 44, 66), (bar_x, bar_y, bar_w, bar_h), border_radius=4)
            fill_w = round(bar_w * progress)
            if fill_w > 0:
                pygame.draw.rect(screen, (105, 245, 160), (bar_x, bar_y, fill_w, bar_h), border_radius=4)
            self.typo.draw_text(screen, f"{round(progress * 100)}%", self.typo.small_bold, (105, 245, 160), (bar_x + bar_w + 10, bar_y - 2), anchor="topleft")
        else:
            self.typo.draw_text(screen, "SHOW YOUR HAND", self.typo.heading, (240, 185, 80), (width // 2, box_y + 32), anchor="center")
            self.typo.draw_text(screen, "Waiting for camera tracking...", self.typo.body, (170, 190, 215), (width // 2, box_y + 64), anchor="center")

        # Bottom Hint
        self.typo.draw_text(screen, "Hold your index finger naturally in view to begin", self.typo.small, (150, 175, 205), (width // 2, card_y + 245), anchor="center")

    def _draw_countdown(
        self,
        screen: pygame.Surface,
        width: int,
        height: int,
        now: float,
    ) -> None:
        """Punchy, animated single-numeral countdown with zero overlapping HUD clutter."""
        text = self._game.countdown_text
        if not text:
            return

        is_go = (text == "GO!")
        clean_text = "GO" if is_go else text
        color = (105, 245, 160) if is_go else (245, 250, 255)

        if not is_go:
            self.typo.draw_text(screen, f"READY • {self._game.mode.name}", self.typo.title, (255, 220, 80), (width // 2, (height // 2) - 80), anchor="center")

        self.typo.draw_text(screen, clean_text, self.typo.countdown, color, (width // 2, height // 2), anchor="center")

        sub_text = "POP THE DESCENDING TARGETS!" if is_go else "AIM WITH INDEX FINGER • PINCH TO SHOOT"
        self.typo.draw_text(screen, sub_text, self.typo.body, (170, 195, 225), (width // 2, (height // 2) + 80), anchor="center")

    def _draw_paused(
        self,
        screen: pygame.Surface,
        width: int,
        height: int,
    ) -> None:
        """Clean modal Pause Screen."""
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((8, 14, 24, 220))
        screen.blit(overlay, (0, 0))

        card_w, card_h = min(440, width - 40), 310
        card_x = (width - card_w) // 2
        card_y = (height - card_h) // 2

        draw_card(screen, (card_x, card_y, card_w, card_h), (14, 22, 36, 250), (55, 80, 120), border_width=2, border_radius=14)

        self.typo.draw_text(screen, "PAUSED", self.typo.title, (255, 220, 80), (width // 2, card_y + 36), anchor="center")
        self.typo.draw_text(screen, f"{self._game.mode.name} MODE  |  SCORE: {self._game.score.score:,}", self.typo.subtitle, (150, 180, 215), (width // 2, card_y + 72), anchor="center")

        options = [
            ("P / SPACE", "Resume Game", (105, 245, 160)),
            ("R", "Restart Run", (130, 225, 255)),
            ("M", "Change Mode", (255, 220, 80)),
            ("Q / ESC", "Quit Game", (255, 120, 120)),
        ]

        oy = card_y + 115
        for key_text, label, col in options:
            draw_keycap(screen, key_text, self.typo.small_bold, card_x + 75, oy + 10, text_color=col)
            self.typo.draw_text(screen, label, self.typo.body, (230, 240, 250), (card_x + 155, oy), anchor="topleft")
            oy += 36

    def _draw_game_over(
        self,
        screen: pygame.Surface,
        width: int,
        height: int,
        now: float,
    ) -> None:
        """Rewarding Results Card with animated score count-up and vector breakdown table."""
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((8, 14, 24, 235))
        screen.blit(overlay, (0, 0))

        card_w, card_h = min(480, width - 40), 410
        card_x = (width - card_w) // 2
        card_y = (height - card_h) // 2

        draw_card(screen, (card_x, card_y, card_w, card_h), (14, 22, 36, 250), (55, 80, 125), border_width=2, border_radius=14)

        mode = self._game.mode
        if mode.time_limit_seconds is not None:
            header_text, header_col = "TIME'S UP!", (255, 215, 80)
        elif mode.allow_life_loss:
            header_text, header_col = "GAME OVER", (255, 85, 95)
        else:
            header_text, header_col = "RUN COMPLETE", (105, 245, 160)

        self.typo.draw_text(screen, header_text, self.typo.title, header_col, (width // 2, card_y + 32), anchor="center")

        # Animated Score Count-up
        elapsed = max(0.0, now - self._game_over_entered_at)
        count_progress = min(1.0, elapsed / 0.8)
        display_score = round(self._game.score.score * count_progress)

        self.typo.draw_text(screen, f"{display_score:,}", self.typo.display_l, (115, 235, 255), (width // 2, card_y + 70), anchor="center")
        self.typo.draw_text(screen, "FINAL SCORE", self.typo.hud_label, (140, 165, 195), (width // 2, card_y + 98), anchor="center")

        # New High Score Star Banner
        sy = card_y + 115
        if self._game.is_new_high_score:
            draw_vector_star(screen, (width // 2) - 110, sy + 6, radius=8)
            draw_vector_star(screen, (width // 2) + 110, sy + 6, radius=8)
            self.typo.draw_text(screen, "NEW HIGH SCORE", self.typo.small_bold, (255, 220, 80), (width // 2, sy), anchor="center")
            sy += 24

        # Statistics Table
        stats = self._game.stats
        stat_rows = [
            ("Mode", f"{mode.name}"),
            ("Best Score", f"{self._game.high_score:,}"),
            ("Accuracy", f"{stats.accuracy:.1f}%"),
            ("Targets Hit", f"{stats.targets_hit}"),
            ("Golden Hits", f"{stats.golden_targets_hit}"),
            ("Shots Fired", f"{stats.shots_fired}"),
            ("Highest Combo", f"×{stats.highest_combo}"),
        ]

        table_w = card_w - 70
        table_x = card_x + 35
        for i, (label, val) in enumerate(stat_rows):
            row_y = sy + i * 22
            if i % 2 == 0:
                pygame.draw.rect(screen, (20, 30, 48), (table_x, row_y - 2, table_w, 20), border_radius=4)
            self.typo.draw_text(screen, label, self.typo.small, (160, 185, 210), (table_x + 10, row_y), anchor="topleft")
            self.typo.draw_text(screen, val, self.typo.small_bold, (240, 245, 255), (table_x + table_w - 10, row_y), anchor="topright")

        # Action Buttons
        by = card_y + card_h - 38
        self.typo.draw_text(screen, "[ R ] PLAY AGAIN    [ M ] CHANGE MODE    [ Q ] QUIT", self.typo.button, (110, 235, 255), (width // 2, by), anchor="center")

    # -- Target & Crosshair Drawing ----------------------------------------

    def _draw_bubble(self, screen: pygame.Surface, bubble: Bubble, now: float) -> None:
        """Render distinct visual styles for NORMAL, SMALL, LARGE, and GOLDEN targets."""
        x, y = round(bubble.position[0]), round(bubble.position[1])
        radius = round(bubble.radius)
        tt = bubble.target_type

        if tt is BubbleType.GOLDEN:
            glow_rad = radius + 4 + round(math.sin(now * 6.0) * 1.5)
            pygame.draw.circle(screen, (120, 80, 10), (x, y), glow_rad)
            pygame.draw.circle(screen, (190, 135, 20), (x, y), radius)
            pygame.draw.circle(screen, (255, 215, 60), (x, y), radius, 3)
            d_rad = max(4, radius // 3)
            pts = [(x, y - d_rad), (x + d_rad, y), (x, y + d_rad), (x - d_rad, y)]
            pygame.draw.polygon(screen, (255, 245, 150), pts)

        elif tt is BubbleType.SMALL:
            pygame.draw.circle(screen, (12, 85, 140), (x, y), radius + 3)
            pygame.draw.circle(screen, (80, 235, 255), (x, y), radius, 2)
            pygame.draw.circle(screen, (200, 250, 255), (x - radius // 3, y - radius // 3), max(2, radius // 4))

        elif tt is BubbleType.LARGE:
            pygame.draw.circle(screen, (14, 48, 96), (x, y), radius + 5)
            pygame.draw.circle(screen, (45, 125, 210), (x, y), radius, 3)
            pygame.draw.circle(screen, (28, 78, 142), (x, y), max(4, radius - 10), 1)
            pygame.draw.circle(screen, (100, 185, 255), (x - radius // 3, y - radius // 3), max(3, radius // 6))

        else:  # NORMAL
            pygame.draw.circle(screen, (18, 72, 136), (x, y), radius + 4)
            pygame.draw.circle(screen, (55, 170, 255), (x, y), radius, 3)
            pygame.draw.circle(screen, (120, 215, 255), (x - radius // 3, y - radius // 3), max(3, radius // 6))

    @staticmethod
    def _draw_crosshair(
        screen: pygame.Surface,
        position: tuple[float, float],
        hovered: bool,
        shot: ShotEffect | None,
        fire_pulse_until: float,
        now: float,
    ) -> None:
        """Render high-contrast, minimal arcade crosshair reticle."""
        width, height = screen.get_size()
        x, y = int(round(position[0])), int(round(position[1]))
        x = max(settings.CROSSHAIR_MARGIN, min(width - settings.CROSSHAIR_MARGIN, x))
        y = max(settings.CROSSHAIR_MARGIN, min(height - settings.CROSSHAIR_MARGIN, y))

        pulsing = (now < fire_pulse_until)
        if pulsing:
            scale = settings.CROSSHAIR_MAX_SCALE
            ring_color = (255, 230, 90)
            dot_color = (255, 255, 255)
            gap = 5
            arm_len = 11
        elif hovered:
            scale = 1.05
            ring_color = (95, 245, 160)
            dot_color = (130, 255, 185)
            gap = 4
            arm_len = 9
        else:
            scale = 1.0
            ring_color = (120, 220, 255)
            dot_color = (245, 250, 255)
            gap = 4
            arm_len = 8

        radius = round(settings.CROSSHAIR_RADIUS * scale)
        pygame.draw.circle(screen, dot_color, (x, y), 2)
        pygame.draw.circle(screen, ring_color, (x, y), radius, 2)
        pygame.draw.line(screen, ring_color, (x, y - radius - arm_len), (x, y - radius - gap), 2)
        pygame.draw.line(screen, ring_color, (x, y + radius + gap), (x, y + radius + arm_len), 2)
        pygame.draw.line(screen, ring_color, (x - radius - arm_len, y), (x - radius - gap, y), 2)
        pygame.draw.line(screen, ring_color, (x + radius + gap, y), (x + radius + arm_len, y), 2)

    def _draw_debug_hud(
        self,
        screen: pygame.Surface,
        result: TrackingResult | None,
        pinch_result: PinchResult | None,
        now: float,
    ) -> None:
        """Render isolated, compact monospaced Debug Panel strictly below top HUD."""
        width, _ = screen.get_size()
        panel_w = 260
        panel_h = 200
        panel_x = width - panel_w - 20
        panel_y = 96  # Strictly below the top HUD bar

        draw_card(screen, (panel_x, panel_y, panel_w, panel_h), (8, 14, 24, 230), (45, 70, 105), border_radius=8)

        cam_fps = self.camera.measured_fps if self.camera is not None else 0.0
        cam_backend = self.camera.backend_name if self.camera is not None else "n/a"
        cam_text = f"CAM: OK ({cam_fps:.0f} FPS, {cam_backend})"

        st = self._game.state
        if st is GameState.MODE_SELECT:
            st_text = f"STATE: SELECT ({ALL_MODES[self._selected_mode_idx].name})"
            st_color = (255, 220, 80)
        elif st is GameState.READY:
            st_text = f"STATE: READY ({self._game.ready_hand_timer:.2f}s/{settings.READY_HAND_STABLE_SECONDS:.2f}s)"
            st_color = (255, 220, 80)
        elif st is GameState.COUNTDOWN:
            st_text = f"STATE: COUNTDOWN ({self._game.countdown_text or '...'})"
            st_color = (110, 235, 255)
        elif st is GameState.PLAYING:
            st_text = f"STATE: PLAY ({self._game.mode.name} t={self._game.gameplay_time:.1f}s)"
            st_color = (105, 245, 160)
        elif st is GameState.PAUSED:
            st_text = "STATE: PAUSED"
            st_color = (255, 210, 80)
        else:
            st_text = "STATE: GAME OVER"
            st_color = (255, 95, 95)

        if self.tracker is None:
            hand_text, hand_color = "HAND: disabled", (150, 150, 150)
        elif result is None:
            hand_text, hand_color = "HAND: starting...", (180, 180, 180)
        elif result.fresh and result.hand is not None:
            tip = result.hand.index_tip_norm
            hand_text = f"HAND: tracked ({tip[0]:.2f}, {tip[1]:.2f})"
            hand_color = (100, 240, 160)
        elif result.coasting and result.hand is not None:
            hand_text = f"HAND: coasting ({result.stale_frames}f held)"
            hand_color = (255, 180, 70)
        else:
            hand_text, hand_color = "HAND: lost", (255, 100, 90)

        aim_x, aim_y = round(self._aim.position[0]), round(self._aim.position[1])
        aim_text = f"AIM: x={aim_x}, y={aim_y}"

        pinch = pinch_result or self._last_pinch
        dist_val = pinch.normalized_distance if pinch is not None else None
        if dist_val is not None:
            dist_status = "PINCH" if dist_val <= settings.PINCH_CLOSE_THRESHOLD else ("OPEN" if dist_val >= settings.PINCH_RELEASE_THRESHOLD else "MID")
            dist_text = f"PINCH DIST: {dist_val:.2f} ({dist_status})"
        else:
            dist_text = "PINCH: —"

        if now < self._last_shot_display_until:
            shot_text, shot_color = f"SHOT: FIRED! (#{self._game.stats.shots_fired})", (255, 240, 90)
        elif self._game.state is not GameState.PLAYING:
            shot_text, shot_color = f"SHOT: blocked ({self._game.state.name})", (160, 175, 195)
        elif pinch is not None and pinch.phase is PinchPhase.READY:
            shot_text, shot_color = "SHOT: ready for pinch", (170, 190, 210)
        else:
            shot_text, shot_color = "SHOT: pinched / hold", (190, 170, 200)

        stats_text = f"LIVES: {self._game.stats.lives}  HITS: {self._game.stats.targets_hit}  SHOTS: {self._game.stats.shots_fired}"

        y = panel_y + 8
        for line, col in [
            (cam_text, (130, 220, 255)),
            (st_text, st_color),
            (hand_text, hand_color),
            (aim_text, (220, 235, 255)),
            (dist_text, (255, 210, 80)),
            (shot_text, shot_color),
            (stats_text, (130, 220, 255)),
        ]:
            self.typo.draw_text(screen, line, self.typo.debug, col, (panel_x + 10, y), anchor="topleft")
            y += 20

        # Gauge bar at bottom of panel
        gauge_x = panel_x + 10
        gauge_y = panel_y + panel_h - 16
        gauge_w = panel_w - 20
        gauge_h = 6
        pygame.draw.rect(screen, (28, 42, 60), (gauge_x, gauge_y, gauge_w, gauge_h))

        max_disp = 1.20
        close_x = gauge_x + round(min(1.0, settings.PINCH_CLOSE_THRESHOLD / max_disp) * gauge_w)
        open_x = gauge_x + round(min(1.0, settings.PINCH_RELEASE_THRESHOLD / max_disp) * gauge_w)
        pygame.draw.line(screen, (100, 245, 160), (close_x, gauge_y - 2), (close_x, gauge_y + gauge_h + 2), 2)
        pygame.draw.line(screen, (255, 210, 80), (open_x, gauge_y - 2), (open_x, gauge_y + gauge_h + 2), 2)

        if dist_val is not None:
            cur_x = gauge_x + round(min(1.0, max(0.0, dist_val / max_disp)) * gauge_w)
            pygame.draw.circle(screen, (255, 255, 255), (cur_x, gauge_y + gauge_h // 2), 4)

    def _playfield(self, screen_size: tuple[int, int]) -> Bounds:
        width, height = screen_size
        return (
            float(settings.PLAYFIELD_LEFT),
            float(settings.PLAYFIELD_TOP),
            float(max(settings.PLAYFIELD_LEFT + 1, width - settings.PLAYFIELD_RIGHT_INSET)),
            float(max(settings.PLAYFIELD_TOP + 1, height - settings.PLAYFIELD_BOTTOM_INSET)),
        )
