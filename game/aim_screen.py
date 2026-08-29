"""Phase 12 Pygame Aim Screen with minimalist design, camera selection, QR pairing, and mobile streaming."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

from aim.aim_controller import AimController, AimSettings
from audio.audio_manager import AudioManager
from camera.camera_manager import CameraManager
from camera.qr_generator import QRCode
from config import settings
from game.bubble import Bounds, Bubble, BubbleType
from game.bubble_game import BubbleGame, GameState
from game.game_mode import ALL_MODES, GameMode, ModeConfig
from game.particles import ParticleSystem
from game.theme import THEME
from game.typography import Typography
from game.ui_layout import UILayout
from game.ui_renderer import (
    draw_card,
    draw_control_bar,
    draw_keycap,
    draw_vector_heart,
    draw_vector_leaf,
    draw_vector_phone,
    draw_vector_speaker,
    draw_vector_star,
    draw_vector_stopwatch,
    draw_vector_target,
    draw_vector_webcam,
)
from gestures.pinch_detector import PinchDetector, PinchPhase, PinchResult

if TYPE_CHECKING:
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
    color: tuple[int, int, int] = THEME.ACCENT_CYAN

    def visible(self, now: float) -> bool:
        return now < self.expires_at


class AimScreen:
    """Orchestrates arcade game flow, camera sources, and minimalist modern UI."""

    def __init__(
        self,
        camera: CameraManager | None,
        tracker: HandTracker | None,
        debug_hud: bool = False,
    ) -> None:
        if not pygame.get_init():
            pygame.init()
        if not pygame.font.get_init():
            pygame.font.init()

        self.camera = camera
        self.tracker = tracker
        self.layout = UILayout((settings.GAME_WIDTH, settings.GAME_HEIGHT))
        self.typo = Typography((settings.GAME_WIDTH, settings.GAME_HEIGHT))

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
        self._selected_camera_idx = 0  # 0: Local Webcam, 1: Phone Camera
        self._last_countdown_number = 3
        self._audio_notify_until = 0.0
        self._audio_notify_text = ""
        self._game_over_entered_at = 0.0
        self._qr_surface: pygame.Surface | None = None
        self._cached_qr_url: str | None = None

    def run(self, duration: float = 0.0) -> int:
        screen = pygame.display.set_mode(
            (settings.GAME_WIDTH, settings.GAME_HEIGHT), pygame.RESIZABLE
        )
        pygame.display.set_caption(settings.GAME_WINDOW_NAME)
        clock = pygame.time.Clock()

        self._resize(screen.get_size())

        started = time.perf_counter()
        last_result: TrackingResult | None = None
        running = True
        exit_code = 0

        try:
            while running:
                delta_seconds = clock.tick(settings.GAME_FPS) / 1000.0
                now = time.perf_counter()

                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                    elif event.type == pygame.VIDEORESIZE:
                        screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                        self._resize(event.size)
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

    def _resize(self, size: tuple[int, int]) -> None:
        self.layout.update_screen_size(size)
        self.typo.set_screen_size(size)
        self._aim.set_screen_size(size)
        self._aim.set_playfield(self.layout.playfield_bounds)

    # -- Input Handling ----------------------------------------------------

    def _handle_key_event(self, event: pygame.event.Event, screen: pygame.Surface, now: float) -> bool:
        st = self._game.state

        if event.key in (pygame.K_ESCAPE, pygame.K_q):
            if st is GameState.MODE_SELECT:
                return False
            elif st in (GameState.CAMERA_SELECT, GameState.PLAYING, GameState.PAUSED, GameState.GAME_OVER):
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
                self._game.set_mode(chosen_mode, self.layout.playfield_bounds)
                self._particles.clear()
                self.audio.play_sfx("menu_select")

        # Camera Select Navigation
        elif st is GameState.CAMERA_SELECT:
            if event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_TAB, pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d):
                self._selected_camera_idx = 1 - self._selected_camera_idx
                self._on_camera_selection_changed()
                self.audio.play_sfx("menu_move")
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._game.state = GameState.READY
                self.audio.play_sfx("menu_select")

        elif st is GameState.PLAYING:
            if event.key in (pygame.K_p, pygame.K_PAUSE):
                paused = self._game.toggle_pause()
                if paused:
                    self.audio.play_sfx("pause")
            elif event.key == pygame.K_r:
                self._restart_run(now)

        elif st is GameState.PAUSED:
            if event.key in (pygame.K_p, pygame.K_PAUSE, pygame.K_SPACE):
                self._game.toggle_pause()
                self.audio.play_sfx("menu_select")
            elif event.key == pygame.K_r:
                self._restart_run(now)

        elif st is GameState.GAME_OVER:
            if event.key == pygame.K_r:
                self._restart_run(now)

        return True

    def _on_camera_selection_changed(self) -> None:
        if self.camera is None:
            return
        if self._selected_camera_idx == 0:
            self.camera.use_local_camera()
        else:
            self.camera.use_phone_camera()

    def _restart_run(self, now: float) -> None:
        self._aim.reset()
        self._pinch.reset()
        self._floating_scores.clear()
        self._particles.clear()
        self._game.reset(self.layout.playfield_bounds, start_state=GameState.READY, now=now)
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
            self.layout.playfield_bounds,
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
            tag = f"+{points}" if mult == 1 else f"+{points}  x{mult}"
            if hit_bubble.target_type is BubbleType.GOLDEN:
                pop_col = THEME.ACCENT_GOLD
            elif hit_bubble.target_type is BubbleType.SMALL:
                pop_col = THEME.ACCENT_CYAN
            elif hit_bubble.target_type is BubbleType.LARGE:
                pop_col = (130, 195, 255)
            else:
                pop_col = THEME.ACCENT_EMERALD

            self._floating_scores.append(
                FloatingScore(tag, hit_bubble.position[0], hit_bubble.position[1], now, now + 0.80, color=pop_col)
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
        w, h = screen.get_size()
        bounds = self.layout.playfield_bounds
        screen.fill(THEME.BG_DARK)

        # Subtle geometric grid
        for x in range(0, w, 64):
            pygame.draw.line(screen, THEME.GRID_LINE, (x, 0), (x, h))
        for y in range(0, h, 64):
            pygame.draw.line(screen, THEME.GRID_LINE, (0, y), (w, y))

        # Bottom hazard baseline (if mode allows life loss)
        if self._game.mode.allow_life_loss and self._game.state in (GameState.PLAYING, GameState.PAUSED):
            hazard_y = round(bounds[3])
            for hx in range(round(bounds[0]), round(bounds[2]), 16):
                pygame.draw.line(screen, (50, 70, 95), (hx, hazard_y), (hx + 8, hazard_y), 1)

        # Draw bubbles during active gameplay and pause
        if self._game.state in (GameState.PLAYING, GameState.PAUSED):
            for bubble in self._game.targets.bubbles:
                self._draw_bubble(screen, bubble, now)

        # Draw particles
        self._particles.draw(screen, now)

        # Draw shot feedback
        if self._shot is not None and self._shot.visible(now):
            shot_x, shot_y = round(self._shot.position[0]), round(self._shot.position[1])
            if self._shot.hit:
                progress = (self._shot.expires_at - now) / max(settings.SHOT_EFFECT_SECONDS, 1e-6)
                radius = round(16 + 20 * (1.0 - progress))
                pygame.draw.circle(screen, THEME.ACCENT_EMERALD, (shot_x, shot_y), radius, 2)
            else:
                pygame.draw.line(screen, THEME.ACCENT_CORAL, (shot_x - 5, shot_y - 5), (shot_x + 5, shot_y + 5), 2)
                pygame.draw.line(screen, THEME.ACCENT_CORAL, (shot_x - 5, shot_y + 5), (shot_x + 5, shot_y - 5), 2)

        # Draw floating scores
        for fs in self._floating_scores:
            age = now - fs.created_at
            lifespan = fs.expires_at - fs.created_at
            fade = max(0.0, min(1.0, 1.0 - (age / max(lifespan, 1e-6))))
            float_y = fs.y - (age * 40.0)
            score_surf = self.typo.h2.render(fs.text, True, fs.color)
            score_surf.set_alpha(round(fade * 255))
            screen.blit(score_surf, score_surf.get_rect(center=(round(fs.x), round(float_y))))

        # Draw responsive crosshair
        hovered = any(bubble.contains(position) for bubble in self._game.targets.bubbles)
        active_shot = self._shot if self._shot is not None and self._shot.visible(now) else None
        self._draw_crosshair(screen, position, hovered, active_shot, self._fire_pulse_until, now)

        # Life loss red edge flash
        if now < self._life_lost_flash_until:
            flash_alpha = round(((self._life_lost_flash_until - now) / 0.30) * 75)
            flash_surf = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(flash_surf, (*THEME.ACCENT_CORAL, flash_alpha), (0, 0, w, h), 6)
            screen.blit(flash_surf, (0, 0))

        # Render Top HUD (isolated non-colliding zones)
        has_hand = (result is not None and result.has_hand)
        if self._game.state not in (GameState.MODE_SELECT, GameState.CAMERA_SELECT):
            self._draw_hud(screen, result, now)

        # Render State Screens
        if self._game.state is GameState.MODE_SELECT:
            self._draw_mode_select(screen, w, h)
        elif self._game.state is GameState.CAMERA_SELECT:
            self._draw_camera_select(screen, w, h)
        elif self._game.state is GameState.READY:
            self._draw_ready(screen, has_hand)
        elif self._game.state is GameState.COUNTDOWN:
            self._draw_countdown(screen, w, h)
        elif self._game.state is GameState.PAUSED:
            self._draw_paused(screen)
        elif self._game.state is GameState.GAME_OVER:
            self._draw_game_over(screen, now)

        # Audio toast notification
        if now < self._audio_notify_until:
            toast_rect = pygame.Rect(w - 170, h - 74, 150, 26)
            draw_card(screen, toast_rect, (20, 28, 42, 220), THEME.BORDER_SUBTLE, border_radius=6)
            self.typo.draw_text(screen, self._audio_notify_text, self.typo.body_bold, THEME.ACCENT_GOLD, toast_rect.center, anchor="center")

        # Bottom Control Strip
        if self._game.state not in (GameState.MODE_SELECT, GameState.CAMERA_SELECT, GameState.PAUSED):
            draw_control_bar(screen, self.layout.control_bar_rect, self.typo, muted=self.audio.muted, debug_on=self._debug_hud)

        # Debug HUD (toggled with D, strictly below top bar)
        if self._debug_hud:
            self._draw_debug_hud(screen, result, pinch_result, now)

    # -- UI Screens & HUD Layout -------------------------------------------

    def _draw_hud(
        self,
        screen: pygame.Surface,
        result: TrackingResult | None,
        now: float,
    ) -> None:
        """Minimalist Top Header Bar with quiet aesthetic and clear hierarchy."""
        mode = self._game.mode

        # Header background panel
        draw_card(screen, self.layout.top_bar_rect, (12, 16, 24, 230), THEME.BORDER_SUBTLE, border_width=1, border_radius=0)

        # === 1. LEFT ZONE (Branding, Mode, Subtle Tracking Status) ===
        lz = self.layout.left_zone
        self.typo.draw_text(screen, "HANDSHOT", self.typo.h1, THEME.ACCENT_CYAN, (lz.left, lz.top + 4), anchor="topleft")
        self.typo.draw_text(screen, f"{mode.name.capitalize()} Mode", self.typo.body, THEME.TEXT_SECONDARY, (lz.left, lz.top + 32), anchor="topleft")

        # Tracking status indicator
        track_y = lz.top + 54
        if self.tracker is None:
            st_col, st_txt = THEME.TEXT_MUTED, "TRACKING OFF"
        elif result is not None and result.has_hand:
            st_col, st_txt = THEME.ACCENT_EMERALD, "TRACKED"
        elif result is not None and result.coasting:
            st_col, st_txt = THEME.ACCENT_GOLD, "COASTING"
        else:
            st_col, st_txt = THEME.ACCENT_CORAL, "SEARCHING"

        pygame.draw.circle(screen, st_col, (lz.left + 4, track_y + 6), 4)
        self.typo.draw_text(screen, st_txt, self.typo.caption, st_col, (lz.left + 14, track_y), anchor="topleft")

        # === 2. CENTER ZONE (Prominent Score & Combo) ===
        cz = self.layout.center_zone
        cx = cz.centerx

        self.typo.draw_text(screen, f"{self._game.score.score:,}", self.typo.score_large, THEME.TEXT_PRIMARY, (cx, cz.top + 4), anchor="midtop")
        self.typo.draw_text(screen, "SCORE", self.typo.label, THEME.TEXT_MUTED, (cx, cz.top + 46), anchor="midtop")

        # Combo badge
        if mode.allow_combo and self._game.combo.current_combo > 1:
            combo = self._game.combo.current_combo
            mult = self._game.combo.multiplier
            is_streak = (combo >= settings.COMBO_TIER_3_HITS)
            combo_text = f"x{mult} STREAK" if is_streak else f"x{mult} COMBO"
            badge_col = THEME.ACCENT_GOLD if is_streak else THEME.ACCENT_CYAN

            badge_w, badge_h = self.typo.measure_text(combo_text, self.typo.caption)
            badge_rect = pygame.Rect(cx - (badge_w + 14) // 2, cz.top + 60, badge_w + 14, badge_h + 3)
            draw_card(screen, badge_rect, (24, 34, 48), THEME.BORDER_SUBTLE, border_radius=4)
            self.typo.draw_text(screen, combo_text, self.typo.caption, badge_col, badge_rect.center, anchor="center")

        # === 3. RIGHT ZONE (Best, Accuracy, Lives / Timer, Mute) ===
        rz = self.layout.right_zone
        rx = rz.right

        # Top row: BEST Score
        self.typo.draw_text(screen, "BEST", self.typo.label, THEME.TEXT_MUTED, (rx - 65, rz.top + 4), anchor="topright")
        self.typo.draw_text(screen, f"{self._game.high_score:,}", self.typo.score, THEME.ACCENT_GOLD, (rx, rz.top + 2), anchor="topright")

        # Middle row: ACCURACY & Mute icon
        acc_y = rz.top + 28
        self.typo.draw_text(screen, f"{self._game.stats.accuracy:.1f}% ACCURACY", self.typo.body_small, THEME.TEXT_SECONDARY, (rx - 26, acc_y), anchor="topright")
        draw_vector_speaker(screen, rx - 8, acc_y + 6, radius=7, muted=self.audio.muted)

        # Bottom row: Mode Status (Hearts / Timer / Mode Badge)
        status_y = rz.top + 50
        if mode.allow_life_loss:
            for i in range(mode.initial_lives):
                is_active = (i < self._game.stats.lives)
                draw_vector_heart(screen, rx - 48 + i * 20, status_y + 6, size=15, active=is_active)
        elif mode.time_limit_seconds is not None:
            rem = self._game.time_remaining or 0.0
            time_col = THEME.ACCENT_CORAL if rem < 10.0 else THEME.ACCENT_GOLD
            draw_vector_stopwatch(screen, rx - 60, status_y + 6, radius=7, color=time_col)
            self.typo.draw_text(screen, f"{rem:.1f}s", self.typo.score, time_col, (rx, status_y - 2), anchor="topright")
        else:
            if mode.mode == GameMode.CHILL:
                draw_vector_leaf(screen, rx - 65, status_y + 6, radius=7)
            else:
                draw_vector_target(screen, rx - 65, status_y + 6, radius=7)
            self.typo.draw_text(screen, mode.badge.capitalize(), self.typo.body_bold, THEME.ACCENT_EMERALD, (rx, status_y - 2), anchor="topright")

    def _draw_mode_select(
        self,
        screen: pygame.Surface,
        width: int,
        height: int,
    ) -> None:
        """Balanced 2x2 Grid Mode Selection Screen."""
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((*THEME.BG_DARK, 235))
        screen.blit(overlay, (0, 0))

        # Header Title
        self.typo.draw_text(screen, "HANDSHOT", self.typo.h1, THEME.ACCENT_CYAN, (width // 2, 45), anchor="center")
        self.typo.draw_text(screen, "CHOOSE YOUR MODE", self.typo.h2, THEME.TEXT_PRIMARY, (width // 2, 85), anchor="center")

        # 2x2 Grid Layout
        card_w = min(480, (width - 70) // 2)
        card_h = 105
        gap_x = 24
        gap_y = 20

        grid_w = card_w * 2 + gap_x
        start_x = (width - grid_w) // 2
        start_y = 135

        for i, mode in enumerate(ALL_MODES):
            row = i // 2
            col = i % 2
            card_x = start_x + col * (card_w + gap_x)
            card_y = start_y + row * (card_h + gap_y)

            is_selected = (i == self._selected_mode_idx)

            card_bg = THEME.BG_SURFACE_HIGHLIGHT if is_selected else THEME.BG_SURFACE
            border_col = THEME.BORDER_FOCUS if is_selected else THEME.BORDER_SUBTLE
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
            name_col = THEME.ACCENT_GOLD if is_selected else THEME.TEXT_PRIMARY
            self.typo.draw_text(screen, mode.name, self.typo.h2, name_col, (card_x + 52, card_y + 20), anchor="topleft")

            # Selection Tag
            if is_selected:
                draw_keycap(screen, "SELECTED", "", self.typo.label, self.typo.caption, card_x + card_w - 55, card_y + 30, active=True, active_color=THEME.ACCENT_EMERALD)

            # Mode Tagline
            desc_col = THEME.TEXT_SECONDARY if is_selected else THEME.TEXT_MUTED
            self.typo.draw_text(screen, mode.tagline, self.typo.body, desc_col, (card_x + 22, card_y + 54), anchor="topleft")

            # Best Score
            best = self._game.high_score if mode.mode == self._game.mode.mode else 0
            best_txt = f"BEST: {best:,}"
            self.typo.draw_text(screen, best_txt, self.typo.body_small, THEME.ACCENT_CYAN if is_selected else THEME.TEXT_MUTED, (card_x + 22, card_y + 80), anchor="topleft")

        # Footer controls
        self.typo.draw_text(
            screen,
            "[ Arrows / W S ] Select Mode    [ ENTER / SPACE ] Continue    [ M ] Mute    [ Q ] Quit",
            self.typo.body_small,
            THEME.TEXT_SECONDARY,
            (width // 2, height - 34),
            anchor="center",
        )

    def _draw_camera_select(
        self,
        screen: pygame.Surface,
        width: int,
        height: int,
    ) -> None:
        """Camera Source Setup screen supporting Local Webcam & Wireless Phone Camera QR pairing."""
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((*THEME.BG_DARK, 240))
        screen.blit(overlay, (0, 0))

        # Header
        self.typo.draw_text(screen, "CAMERA SETUP", self.typo.h1, THEME.ACCENT_CYAN, (width // 2, 45), anchor="center")
        self.typo.draw_text(screen, "CHOOSE VIDEO SOURCE", self.typo.h2, THEME.TEXT_PRIMARY, (width // 2, 85), anchor="center")

        # 2 Option Cards: [0] Built-in / USB Webcam  [1] Phone Camera
        card_w = min(500, (width - 70) // 2)
        card_h = 360
        gap_x = 24
        start_x = (width - (card_w * 2 + gap_x)) // 2
        start_y = 125

        # Card 0: Local Webcam
        is_local_sel = (self._selected_camera_idx == 0)
        c0_bg = THEME.BG_SURFACE_HIGHLIGHT if is_local_sel else THEME.BG_SURFACE
        c0_border = THEME.BORDER_FOCUS if is_local_sel else THEME.BORDER_SUBTLE
        draw_card(screen, (start_x, start_y, card_w, card_h), c0_bg, c0_border, border_width=2 if is_local_sel else 1, border_radius=14)

        draw_vector_webcam(screen, start_x + card_w // 2, start_y + 60, radius=22, color=THEME.ACCENT_CYAN if is_local_sel else THEME.TEXT_SECONDARY)
        self.typo.draw_text(screen, "Computer Webcam", self.typo.h2, THEME.TEXT_PRIMARY, (start_x + card_w // 2, start_y + 115), anchor="center")
        self.typo.draw_text(screen, "Built-in laptop or USB webcam", self.typo.body, THEME.TEXT_SECONDARY, (start_x + card_w // 2, start_y + 145), anchor="center")

        status_box_y = start_y + 190
        draw_card(screen, (start_x + 30, status_box_y, card_w - 60, 80), THEME.BG_SURFACE_ELEVATED, THEME.BORDER_SUBTLE, border_radius=8)

        local_active = (self.camera is not None and not self.camera.is_phone)
        st_txt = "Ready to Play" if local_active else "Select to activate"
        st_col = THEME.ACCENT_EMERALD if local_active else THEME.TEXT_MUTED
        self.typo.draw_text(screen, st_txt, self.typo.body_bold, st_col, (start_x + card_w // 2, status_box_y + 26), anchor="center")
        self.typo.draw_text(screen, f"Device Index: {self.camera.index if self.camera else 0}", self.typo.caption, THEME.TEXT_MUTED, (start_x + card_w // 2, status_box_y + 50), anchor="center")

        if is_local_sel:
            draw_keycap(screen, "ACTIVE", "", self.typo.label, self.typo.caption, start_x + card_w // 2, start_y + card_h - 40, active=True, active_color=THEME.ACCENT_EMERALD)

        # Card 1: Phone Camera (QR Pairing)
        c1_x = start_x + card_w + gap_x
        is_phone_sel = (self._selected_camera_idx == 1)
        c1_bg = THEME.BG_SURFACE_HIGHLIGHT if is_phone_sel else THEME.BG_SURFACE
        c1_border = THEME.BORDER_FOCUS if is_phone_sel else THEME.BORDER_SUBTLE
        draw_card(screen, (c1_x, start_y, card_w, card_h), c1_bg, c1_border, border_width=2 if is_phone_sel else 1, border_radius=14)

        draw_vector_phone(screen, c1_x + card_w // 2, start_y + 40, w=16, h=26, color=THEME.ACCENT_CYAN if is_phone_sel else THEME.TEXT_SECONDARY)
        self.typo.draw_text(screen, "Phone Camera (QR)", self.typo.h2, THEME.TEXT_PRIMARY, (c1_x + card_w // 2, start_y + 75), anchor="center")

        # QR Code Rendering
        url = self.camera.pairing_url if self.camera and self.camera.pairing_url else "http://127.0.0.1:8088/"
        if self._qr_surface is None or self._cached_qr_url != url:
            self._qr_surface = QRCode(url).to_surface(module_size=5, quiet_zone=4, bg_color=(255, 255, 255), fg_color=(0, 0, 0))
            self._cached_qr_url = url

        qr_x = c1_x + (card_w - self._qr_surface.get_width()) // 2
        qr_y = start_y + 90
        screen.blit(self._qr_surface, (qr_x, qr_y))

        # Connection status below QR
        phone_connected = (self.camera is not None and self.camera.is_phone and self.camera.source.is_connected)
        if phone_connected:
            p_stat, p_col = f"● Phone Connected ({self.camera.measured_fps:.0f} FPS)", THEME.ACCENT_EMERALD
        else:
            p_stat, p_col = "● Waiting for Phone • Same Wi-Fi Required", THEME.ACCENT_GOLD

        self.typo.draw_text(screen, url, self.typo.h2, THEME.ACCENT_CYAN, (c1_x + card_w // 2, qr_y + self._qr_surface.get_height() + 10), anchor="center")
        self.typo.draw_text(screen, p_stat, self.typo.body_small, p_col, (c1_x + card_w // 2, qr_y + self._qr_surface.get_height() + 32), anchor="center")

        if is_phone_sel:
            draw_keycap(screen, "ACTIVE", "", self.typo.label, self.typo.caption, c1_x + card_w // 2, start_y + card_h - 26, active=True, active_color=THEME.ACCENT_EMERALD)

        # Footer
        self.typo.draw_text(
            screen,
            "[ TAB / Left / Right ] Switch Camera    [ ENTER / SPACE ] Start Hand Calibration    [ ESC ] Back",
            self.typo.body_small,
            THEME.TEXT_SECONDARY,
            (width // 2, height - 34),
            anchor="center",
        )

    def _draw_ready(
        self,
        screen: pygame.Surface,
        has_hand: bool,
    ) -> None:
        """Hand Acquisition Screen with animated progress."""
        r = self.layout.ready_card_rect
        draw_card(screen, r, THEME.BG_SURFACE, THEME.BORDER_SUBTLE, border_width=2, border_radius=14)

        # Header Title & Subtitle
        self.typo.draw_text(screen, f"HANDSHOT • {self._game.mode.name}", self.typo.h1, THEME.ACCENT_CYAN, (r.centerx, r.top + 36), anchor="center")
        self.typo.draw_text(screen, "READY TO PLAY", self.typo.h2, THEME.ACCENT_GOLD, (r.centerx, r.top + 76), anchor="center")

        # Central Status Indicator Box
        box_w = 340
        box_h = 100
        box_x = r.centerx - box_w // 2
        box_y = r.top + 110

        draw_card(screen, (box_x, box_y, box_w, box_h), THEME.BG_SURFACE_ELEVATED, THEME.BORDER_SUBTLE, border_radius=8)

        if has_hand:
            progress = min(1.0, self._game.ready_hand_timer / max(settings.READY_HAND_STABLE_SECONDS, 1e-6))
            self.typo.draw_text(screen, "HAND DETECTED", self.typo.h2, THEME.ACCENT_EMERALD, (r.centerx, box_y + 24), anchor="center")
            self.typo.draw_text(screen, "Calibrating...", self.typo.body_small, THEME.TEXT_SECONDARY, (r.centerx, box_y + 50), anchor="center")

            # Progress Bar
            bar_w = 240
            bar_h = 8
            bar_x = r.centerx - bar_w // 2
            bar_y = box_y + 72
            pygame.draw.rect(screen, (28, 38, 54), (bar_x, bar_y, bar_w, bar_h), border_radius=4)
            fill_w = round(bar_w * progress)
            if fill_w > 0:
                pygame.draw.rect(screen, THEME.ACCENT_EMERALD, (bar_x, bar_y, fill_w, bar_h), border_radius=4)
            self.typo.draw_text(screen, f"{round(progress * 100)}%", self.typo.caption, THEME.ACCENT_EMERALD, (bar_x + bar_w + 10, bar_y - 2), anchor="topleft")
        else:
            self.typo.draw_text(screen, "SHOW YOUR HAND", self.typo.h2, THEME.ACCENT_GOLD, (r.centerx, box_y + 32), anchor="center")
            self.typo.draw_text(screen, "Waiting for camera tracking...", self.typo.body, THEME.TEXT_SECONDARY, (r.centerx, box_y + 64), anchor="center")

        # Bottom Hint
        self.typo.draw_text(screen, "Hold your index finger naturally in view to begin", self.typo.body_small, THEME.TEXT_MUTED, (r.centerx, r.top + 245), anchor="center")

    def _draw_countdown(
        self,
        screen: pygame.Surface,
        width: int,
        height: int,
    ) -> None:
        """Punchy single-numeral countdown."""
        text = self._game.countdown_text
        if not text:
            return

        is_go = (text == "GO!")
        clean_text = "GO" if is_go else text
        color = THEME.ACCENT_EMERALD if is_go else THEME.TEXT_PRIMARY

        if not is_go:
            self.typo.draw_text(screen, f"READY • {self._game.mode.name}", self.typo.h2, THEME.ACCENT_GOLD, (width // 2, (height // 2) - 80), anchor="center")

        self.typo.draw_text(screen, clean_text, self.typo.display, color, (width // 2, height // 2), anchor="center")

        sub_text = "POP THE DESCENDING TARGETS!" if is_go else "AIM WITH INDEX FINGER • PINCH TO SHOOT"
        self.typo.draw_text(screen, sub_text, self.typo.body, THEME.TEXT_SECONDARY, (width // 2, (height // 2) + 80), anchor="center")

    def _draw_paused(
        self,
        screen: pygame.Surface,
    ) -> None:
        """Clean modal Pause Screen."""
        w, h = screen.get_size()
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((*THEME.BG_DARK, 220))
        screen.blit(overlay, (0, 0))

        r = self.layout.pause_card_rect
        draw_card(screen, r, THEME.BG_SURFACE, THEME.BORDER_SUBTLE, border_width=2, border_radius=14)

        self.typo.draw_text(screen, "PAUSED", self.typo.h1, THEME.ACCENT_GOLD, (r.centerx, r.top + 36), anchor="center")
        self.typo.draw_text(screen, f"{self._game.mode.name.capitalize()} Mode  |  Score: {self._game.score.score:,}", self.typo.body, THEME.TEXT_SECONDARY, (r.centerx, r.top + 72), anchor="center")

        options = [
            ("P / SPACE", "Resume Game", THEME.ACCENT_EMERALD),
            ("R", "Restart Run", THEME.ACCENT_CYAN),
            ("M", "Change Mode", THEME.ACCENT_GOLD),
            ("Q / ESC", "Quit Game", THEME.ACCENT_CORAL),
        ]

        oy = r.top + 115
        for key_text, label, col in options:
            draw_keycap(screen, key_text, "", self.typo.label, self.typo.caption, r.left + 75, oy + 10, active=True, active_color=col)
            self.typo.draw_text(screen, label, self.typo.body, THEME.TEXT_PRIMARY, (r.left + 155, oy), anchor="topleft")
            oy += 36

    def _draw_game_over(
        self,
        screen: pygame.Surface,
        now: float,
    ) -> None:
        """Rewarding Results Card with score count-up and statistics breakdown."""
        w, h = screen.get_size()
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((*THEME.BG_DARK, 235))
        screen.blit(overlay, (0, 0))

        r = self.layout.results_card_rect
        draw_card(screen, r, THEME.BG_SURFACE, THEME.BORDER_SUBTLE, border_width=2, border_radius=14)

        mode = self._game.mode
        if mode.time_limit_seconds is not None:
            header_text, header_col = "TIME'S UP!", THEME.ACCENT_GOLD
        elif mode.allow_life_loss:
            header_text, header_col = "GAME OVER", THEME.ACCENT_CORAL
        else:
            header_text, header_col = "RUN COMPLETE", THEME.ACCENT_EMERALD

        self.typo.draw_text(screen, header_text, self.typo.h1, header_col, (r.centerx, r.top + 32), anchor="center")

        # Animated Score Count-up
        elapsed = max(0.0, now - self._game_over_entered_at)
        count_progress = min(1.0, elapsed / 0.8)
        display_score = round(self._game.score.score * count_progress)

        self.typo.draw_text(screen, f"{display_score:,}", self.typo.score_large, THEME.ACCENT_CYAN, (r.centerx, r.top + 70), anchor="center")
        self.typo.draw_text(screen, "FINAL SCORE", self.typo.label, THEME.TEXT_MUTED, (r.centerx, r.top + 106), anchor="center")

        # High Score Star Banner
        sy = r.top + 124
        if self._game.is_new_high_score:
            draw_vector_star(screen, r.centerx - 110, sy + 6, radius=8)
            draw_vector_star(screen, r.centerx + 110, sy + 6, radius=8)
            self.typo.draw_text(screen, "NEW HIGH SCORE", self.typo.label, THEME.ACCENT_GOLD, (r.centerx, sy), anchor="center")
            sy += 24

        # Statistics Table
        stats = self._game.stats
        stat_rows = [
            ("Mode", f"{mode.name.capitalize()}"),
            ("Best Score", f"{self._game.high_score:,}"),
            ("Accuracy", f"{stats.accuracy:.1f}%"),
            ("Targets Hit", f"{stats.targets_hit}"),
            ("Golden Hits", f"{stats.golden_targets_hit}"),
            ("Shots Fired", f"{stats.shots_fired}"),
            ("Highest Combo", f"x{stats.highest_combo}"),
        ]

        table_w = r.width - 70
        table_x = r.left + 35
        for i, (label, val) in enumerate(stat_rows):
            row_y = sy + i * 22
            if i % 2 == 0:
                pygame.draw.rect(screen, THEME.BG_SURFACE_ELEVATED, (table_x, row_y - 2, table_w, 20), border_radius=4)
            self.typo.draw_text(screen, label, self.typo.body_small, THEME.TEXT_SECONDARY, (table_x + 10, row_y), anchor="topleft")
            self.typo.draw_text(screen, val, self.typo.body_bold, THEME.TEXT_PRIMARY, (table_x + table_w - 10, row_y), anchor="topright")

        # Action Buttons
        by = r.top + r.height - 38
        self.typo.draw_text(screen, "[ R ] PLAY AGAIN    [ M ] CHANGE MODE    [ Q ] QUIT", self.typo.button, THEME.ACCENT_CYAN, (r.centerx, by), anchor="center")

    # -- Target & Crosshair Drawing ----------------------------------------

    def _draw_bubble(self, screen: pygame.Surface, bubble: Bubble, now: float) -> None:
        """Render refined minimal target design with clear tactile readability."""
        x, y = round(bubble.position[0]), round(bubble.position[1])
        radius = round(bubble.radius)
        tt = bubble.target_type

        if tt is BubbleType.GOLDEN:
            glow_rad = radius + 3 + round(math.sin(now * 5.0) * 1.5)
            pygame.draw.circle(screen, THEME.TARGET_GOLDEN_FILL, (x, y), glow_rad)
            pygame.draw.circle(screen, THEME.TARGET_GOLDEN_RING, (x, y), radius, 2)
            pygame.draw.circle(screen, (255, 240, 150), (x, y), max(2, radius // 3), 1)
            pygame.draw.circle(screen, (255, 255, 255), (x, y), 2)

        elif tt is BubbleType.SMALL:
            pygame.draw.circle(screen, THEME.TARGET_SMALL_FILL, (x, y), radius)
            pygame.draw.circle(screen, THEME.TARGET_SMALL_RING, (x, y), radius, 2)
            pygame.draw.circle(screen, (200, 250, 255), (x, y), 2)

        elif tt is BubbleType.LARGE:
            pygame.draw.circle(screen, THEME.TARGET_LARGE_FILL, (x, y), radius)
            pygame.draw.circle(screen, THEME.TARGET_LARGE_RING, (x, y), radius, 2)
            pygame.draw.circle(screen, (55, 100, 150), (x, y), max(4, radius - 10), 1)
            pygame.draw.circle(screen, (150, 210, 255), (x, y), 2)

        else:  # NORMAL
            pygame.draw.circle(screen, THEME.TARGET_NORMAL_FILL, (x, y), radius)
            pygame.draw.circle(screen, THEME.TARGET_NORMAL_RING, (x, y), radius, 2)
            pygame.draw.circle(screen, (120, 210, 255), (x, y), max(2, radius // 3), 1)
            pygame.draw.circle(screen, (255, 255, 255), (x, y), 2)

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
            ring_color = THEME.RETICLE_FIRE
            dot_color = (255, 255, 255)
            gap, arm_len = 5, 11
        elif hovered:
            scale = 1.05
            ring_color = THEME.RETICLE_HOVER
            dot_color = (180, 255, 210)
            gap, arm_len = 4, 9
        else:
            scale = 1.0
            ring_color = THEME.RETICLE_DEFAULT
            dot_color = THEME.TEXT_PRIMARY
            gap, arm_len = 4, 8

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
        r = self.layout.debug_panel_rect
        draw_card(screen, r, (10, 14, 22, 235), THEME.BORDER_SUBTLE, border_radius=8)

        cam_fps = self.camera.measured_fps if self.camera is not None else 0.0
        if self.camera and self.camera.is_phone:
            facing = getattr(self.camera.source, "facing_mode", "environment").upper()
            cam_text = f"CAM: PHONE ({facing}, {cam_fps:.0f} FPS)"
        elif self.camera is not None:
            cam_text = f"CAM: LOCAL ({self.camera.backend_name}, {cam_fps:.0f} FPS)"
        else:
            cam_text = "CAM: n/a"

        st = self._game.state
        if st is GameState.MODE_SELECT:
            st_text = f"STATE: SELECT ({ALL_MODES[self._selected_mode_idx].name})"
            st_color = THEME.ACCENT_GOLD
        elif st is GameState.CAMERA_SELECT:
            st_text = f"STATE: CAM SETUP ({'LOCAL' if self._selected_camera_idx==0 else 'PHONE'})"
            st_color = THEME.ACCENT_CYAN
        elif st is GameState.READY:
            st_text = f"STATE: READY ({self._game.ready_hand_timer:.2f}s/{settings.READY_HAND_STABLE_SECONDS:.2f}s)"
            st_color = THEME.ACCENT_GOLD
        elif st is GameState.COUNTDOWN:
            st_text = f"STATE: COUNTDOWN ({self._game.countdown_text or '...'})"
            st_color = THEME.ACCENT_CYAN
        elif st is GameState.PLAYING:
            st_text = f"STATE: PLAY ({self._game.mode.name} t={self._game.gameplay_time:.1f}s)"
            st_color = THEME.ACCENT_EMERALD
        elif st is GameState.PAUSED:
            st_text = "STATE: PAUSED"
            st_color = THEME.ACCENT_GOLD
        else:
            st_text = "STATE: GAME OVER"
            st_color = THEME.ACCENT_CORAL

        if self.tracker is None:
            hand_text, hand_color = "HAND: disabled", THEME.TEXT_MUTED
        elif result is None:
            hand_text, hand_color = "HAND: starting...", THEME.TEXT_SECONDARY
        elif result.fresh and result.hand is not None:
            tip = result.hand.index_tip_norm
            hand_text = f"HAND: tracked ({tip[0]:.2f}, {tip[1]:.2f})"
            hand_color = THEME.ACCENT_EMERALD
        elif result.coasting and result.hand is not None:
            hand_text = f"HAND: coasting ({result.stale_frames}f held)"
            hand_color = THEME.ACCENT_GOLD
        else:
            hand_text, hand_color = "HAND: lost", THEME.ACCENT_CORAL

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
            shot_text, shot_color = f"SHOT: FIRED! (#{self._game.stats.shots_fired})", THEME.ACCENT_GOLD
        elif self._game.state is not GameState.PLAYING:
            shot_text, shot_color = f"SHOT: blocked ({self._game.state.name})", THEME.TEXT_MUTED
        elif pinch is not None and pinch.phase is PinchPhase.READY:
            shot_text, shot_color = "SHOT: ready for pinch", THEME.TEXT_SECONDARY
        else:
            shot_text, shot_color = "SHOT: pinched / hold", THEME.ACCENT_PURPLE

        stats_text = f"LIVES: {self._game.stats.lives}  HITS: {self._game.stats.targets_hit}  SHOTS: {self._game.stats.shots_fired}"

        y = r.top + 8
        for line, col in [
            (cam_text, THEME.ACCENT_CYAN),
            (st_text, st_color),
            (hand_text, hand_color),
            (aim_text, THEME.TEXT_PRIMARY),
            (dist_text, THEME.ACCENT_GOLD),
            (shot_text, shot_color),
            (stats_text, THEME.ACCENT_CYAN),
        ]:
            self.typo.draw_text(screen, line, self.typo.monospace_debug, col, (r.left + 10, y), anchor="topleft")
            y += 20

        # Gauge bar at bottom of panel
        gauge_x = r.left + 10
        gauge_y = r.top + r.height - 16
        gauge_w = r.width - 20
        gauge_h = 6
        pygame.draw.rect(screen, (24, 34, 48), (gauge_x, gauge_y, gauge_w, gauge_h))

        max_disp = 1.20
        close_x = gauge_x + round(min(1.0, settings.PINCH_CLOSE_THRESHOLD / max_disp) * gauge_w)
        open_x = gauge_x + round(min(1.0, settings.PINCH_RELEASE_THRESHOLD / max_disp) * gauge_w)
        pygame.draw.line(screen, THEME.ACCENT_EMERALD, (close_x, gauge_y - 2), (close_x, gauge_y + gauge_h + 2), 2)
        pygame.draw.line(screen, THEME.ACCENT_GOLD, (open_x, gauge_y - 2), (open_x, gauge_y + gauge_h + 2), 2)

        if dist_val is not None:
            cur_x = gauge_x + round(min(1.0, max(0.0, dist_val / max_disp)) * gauge_w)
            pygame.draw.circle(screen, THEME.TEXT_PRIMARY, (cur_x, gauge_y + gauge_h // 2), 4)
