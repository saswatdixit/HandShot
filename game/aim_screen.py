"""Pygame Aim Screen with minimalist design, modular weapon system, spatial reload zone, and local webcam tracking."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

from game.crosshair_renderer import CrosshairState, draw_crosshair

from aim.aim_controller import AimController, AimSettings
from audio.audio_manager import AudioManager
from camera.camera_manager import CameraManager
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
    draw_vector_speaker,
    draw_vector_star,
    draw_vector_stopwatch,
    draw_vector_target,
    draw_vector_webcam,
)
from game.weapon import (
    ALL_WEAPONS,
    ASSAULT_RIFLE_SPEC,
    PISTOL_SPEC,
    SHOTGUN_SPEC,
    SNIPER_SPEC,
    WeaponSpec,
    WeaponSystem,
    WeaponType,
)
from gestures import (
    PinchDetector,
    PinchPhase,
    PinchResult,
    ReloadDetector,
    ReloadResult,
)

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
    """Arcade Handshot Aim Trainer with local webcam tracking, modular weapons, and spatial reload."""

    def __init__(
        self,
        camera: CameraManager | None = None,
        tracker: HandTracker | None = None,
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
        self._reload = ReloadDetector()
        self._game = BubbleGame(start_state=GameState.MODE_SELECT)
        self.audio = AudioManager()
        self._particles = ParticleSystem()
        self._shots: list[ShotEffect] = []
        self._floating_scores: list[FloatingScore] = []
        self._fire_pulse_until = 0.0
        self._recoil_offset_px = 0.0
        self._life_lost_flash_until = 0.0
        self._empty_click_until = 0.0
        self._debug_hud = debug_hud
        self._last_pinch: PinchResult | None = None
        self._last_reload_result: ReloadResult | None = None
        self._last_shot_display_until = 0.0
        self._selected_mode_idx = 0
        self._selected_weapon_idx = 0
        self._last_countdown_number = 3
        self._audio_notify_until = 0.0
        self._audio_notify_text = ""
        self._game_over_entered_at = 0.0

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

                # Camera & Hand Tracking Update
                frame = self.camera.read() if self.camera else None
                pinch_result: PinchResult | None = None
                reload_result: ReloadResult | None = None
                has_hand = False

                if frame is not None and self.tracker is not None:
                    last_result = self.tracker.process(frame, mirrored=self.camera.mirror if self.camera else False)
                    has_hand = (last_result.hand is not None)
                    pinch_result = self._pinch.update(last_result.hand if has_hand else None, now)
                    reload_result = self._reload.update(last_result.hand if has_hand else None, delta_seconds, now)
                elif self.tracker is not None:
                    pinch_result = self._pinch.update(None, now)
                    reload_result = self._reload.update(None, delta_seconds, now)

                if pinch_result is not None:
                    self._last_pinch = pinch_result
                if reload_result is not None:
                    self._last_reload_result = reload_result

                # Update weapon reload progress timer
                reload_done = self._game.weapons.update(delta_seconds, now)
                if reload_done:
                    self.audio.play_sfx(self._game.weapons.spec.reload_done_sound)

                # Aim Tracking
                fingertip = (
                    last_result.hand.index_tip_norm
                    if last_result is not None and last_result.hand is not None
                    else None
                )
                aim_pos = self._aim.update(fingertip, delta_seconds, now=now)

                # Active Game Updates & Triggers
                self._update_simulation(delta_seconds, screen, has_hand, now)

                # Spatial Reload Trigger
                if reload_result and reload_result.reload_triggered and self._game.state is GameState.PLAYING:
                    self._handle_reload(now)

                # Handle Shooting Action (Pinch Only)
                if pinch_result and pinch_result.shot and self._game.state is GameState.PLAYING:
                    self._handle_shot(aim_pos, now)

                # Recoil decay
                if self._recoil_offset_px > 0.0:
                    self._recoil_offset_px = max(0.0, self._recoil_offset_px - delta_seconds * 40.0)

                # Particle System & Floating Scores Update
                self._particles.update(delta_seconds, now)
                self._floating_scores = [fs for fs in self._floating_scores if fs.visible(now)]
                self._shots = [s for s in self._shots if s.visible(now)]

                # Render Complete UI & Game Elements
                self._draw(screen, last_result, pinch_result, reload_result, aim_pos, now)
                pygame.display.flip()

                if duration and (time.perf_counter() - started) >= duration:
                    running = False
        except Exception as exc:
            import traceback
            traceback.print_exc()
            print(f"\nAimScreen Error: {exc}")
            exit_code = 1
        finally:
            self.audio.stop_music()
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
            elif st is GameState.WEAPON_SELECT:
                self._game.state = GameState.MODE_SELECT
                self.audio.play_sfx("menu_move")
                return True
            elif st is GameState.PLAYING:
                self._game.toggle_pause()
                self.audio.play_sfx("pause")
                return True
            elif st in (GameState.PAUSED, GameState.GAME_OVER):
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
                self._reload.reset()
                if self.tracker:
                    self.tracker.reset()

        elif event.key == pygame.K_d:
            self._debug_hud = not self._debug_hud

        # Mode Select Navigation
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
            elif event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_TAB):
                self._selected_mode_idx = (self._selected_mode_idx + 1) % len(ALL_MODES)
                self.audio.play_sfx("menu_move")
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                chosen_mode = ALL_MODES[self._selected_mode_idx]
                self._game.set_mode(chosen_mode, self.layout.playfield_bounds, start_state=GameState.WEAPON_SELECT)
                self._particles.clear()
                self.audio.play_sfx("menu_select")

        # Weapon Select Navigation
        elif st is GameState.WEAPON_SELECT:
            if event.key == pygame.K_1:
                self._selected_weapon_idx = 0
                self.audio.play_sfx("menu_move")
            elif event.key == pygame.K_2:
                self._selected_weapon_idx = 1
                self.audio.play_sfx("menu_move")
            elif event.key == pygame.K_3:
                self._selected_weapon_idx = 2
                self.audio.play_sfx("menu_move")
            elif event.key == pygame.K_4:
                self._selected_weapon_idx = 3
                self.audio.play_sfx("menu_move")
            elif event.key in (pygame.K_UP, pygame.K_w):
                self._selected_weapon_idx = (self._selected_weapon_idx - 2) % len(ALL_WEAPONS)
                self.audio.play_sfx("menu_move")
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self._selected_weapon_idx = (self._selected_weapon_idx + 2) % len(ALL_WEAPONS)
                self.audio.play_sfx("menu_move")
            elif event.key in (pygame.K_LEFT, pygame.K_a):
                self._selected_weapon_idx = (self._selected_weapon_idx - 1) % len(ALL_WEAPONS)
                self.audio.play_sfx("menu_move")
            elif event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_TAB):
                self._selected_weapon_idx = (self._selected_weapon_idx + 1) % len(ALL_WEAPONS)
                self.audio.play_sfx("menu_move")
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                chosen_weapon = ALL_WEAPONS[self._selected_weapon_idx]
                self._game.weapons.select_weapon(chosen_weapon)
                self._game.reset(self.layout.playfield_bounds, start_state=GameState.READY, now=now)
                self._particles.clear()
                self.audio.play_sfx("menu_select")
            elif event.key == pygame.K_ESCAPE:
                self._game.state = GameState.MODE_SELECT
                self.audio.play_sfx("menu_move")

        elif st is GameState.PLAYING:
            if event.key in (pygame.K_p, pygame.K_PAUSE):
                paused = self._game.toggle_pause()
                if paused:
                    self.audio.play_sfx("pause")
            elif event.key == pygame.K_r:
                self._handle_reload(now)
            elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                idx = event.key - pygame.K_1
                if 0 <= idx < len(ALL_WEAPONS):
                    self._game.weapons.select_weapon(ALL_WEAPONS[idx])
                    self.audio.play_sfx("menu_move")

        elif st is GameState.PAUSED:
            if event.key in (pygame.K_p, pygame.K_PAUSE, pygame.K_SPACE):
                self._game.toggle_pause()
                self.audio.play_sfx("menu_select")
            elif event.key == pygame.K_r:
                self._restart_run(now)
            elif event.key in (pygame.K_m, pygame.K_ESCAPE):
                self._game.state = GameState.MODE_SELECT
                self.audio.play_sfx("menu_move")

        elif st is GameState.GAME_OVER:
            if event.key in (pygame.K_r, pygame.K_RETURN, pygame.K_SPACE):
                self._restart_run(now)
            elif event.key in (pygame.K_m, pygame.K_ESCAPE):
                self._game.state = GameState.MODE_SELECT
                self.audio.play_sfx("menu_move")

        return True

    def _restart_run(self, now: float) -> None:
        self._aim.reset()
        self._pinch.reset()
        self._reload.reset()
        self._floating_scores.clear()
        self._particles.clear()
        self._shots.clear()
        self._game.reset(self.layout.playfield_bounds, start_state=GameState.READY, now=now)
        if self.tracker is not None:
            self.tracker.reset()
        self.audio.stop_music()
        self.audio.play_sfx("menu_select")

    # -- Simulation & Audio Triggers ---------------------------------------

    def _update_simulation(self, delta_seconds: float, screen: pygame.Surface, has_hand: bool, now: float) -> None:
        prev_state = self._game.state

        escaped = self._game.update(
            delta_seconds,
            self.layout.playfield_bounds,
            hand_tracked=has_hand,
            now=now,
        )

        if escaped and self._game.mode.allow_life_loss:
            self.audio.play_sfx("bubble_escape")
            self._life_lost_flash_until = now + 0.35

        if prev_state is GameState.READY and self._game.state is GameState.COUNTDOWN:
            self.audio.play_sfx("countdown_tick")
            self._last_countdown_number = 3

        if self._game.state is GameState.COUNTDOWN:
            if self._game.countdown_number != self._last_countdown_number:
                self._last_countdown_number = self._game.countdown_number
                if self._game.countdown_number == 0:
                    self.audio.play_sfx("countdown_go")
                else:
                    self.audio.play_sfx("countdown_tick")

        if prev_state is GameState.COUNTDOWN and self._game.state is GameState.PLAYING:
            self.audio.play_music(self._game.mode.theme_music_track)

        if prev_state is GameState.PLAYING and self._game.state is GameState.GAME_OVER:
            self._game_over_entered_at = now
            self.audio.stop_music()
            if self._game.is_new_high_score:
                self.audio.play_sfx("high_score")
            else:
                self.audio.play_sfx("game_over")

    def _handle_reload(self, now: float) -> None:
        """Centralized reload execution for both spatial hand-down and R key."""
        weapons = self._game.weapons
        if weapons.can_reload():
            started = weapons.start_reload(now)
            if started:
                self.audio.play_sfx(weapons.spec.reload_sound)
        elif weapons.is_empty and weapons.reserve_ammo <= 0:
            self.audio.play_sfx(weapons.spec.empty_sound)

    def _handle_shot(self, aim_pos: tuple[float, float], now: float) -> None:
        """Handle weapon discharge on pinch gesture."""
        weapons = self._game.weapons

        if weapons.is_reloading:
            return  # Block firing during reload

        if weapons.is_empty:
            # Trigger click sound and visual empty cue
            self.audio.play_sfx(weapons.spec.empty_sound)
            self._empty_click_until = now + 0.50
            return

        if not weapons.can_fire(now):
            return

        # Retrieve pre-pinch anchor position to cancel mechanical squeeze jerk
        impact_base = self._aim.get_anchored_position(now)

        impacts = weapons.fire(now, impact_base)
        if not impacts:
            return

        self._game.stats.record_shot()
        self._last_shot_display_until = now + 0.35
        self._fire_pulse_until = now + settings.CROSSHAIR_FIRE_PULSE_SECONDS
        self._recoil_offset_px = weapons.spec.recoil_px
        self.audio.play_sfx(weapons.spec.fire_sound)

        hit_any = False
        for imp in impacts:
            hit_bubble = self._game.targets.shoot(imp)
            if hit_bubble is not None:
                hit_any = True
                mult = self._game.combo.register_hit() if self._game.mode.allow_combo else 1
                pts = hit_bubble.base_score * mult
                self._game.score.add(pts)
                is_gold = (hit_bubble.target_type is BubbleType.GOLDEN)
                self._game.stats.record_hit(is_golden=is_gold)
                if self._game.combo.current_combo > self._game.stats.highest_combo:
                    self._game.stats.highest_combo = self._game.combo.current_combo

                if self._game.mode.allow_combo and self._game.combo.current_combo in (3, 5, 10, 15):
                    self.audio.play_sfx("combo_streak")

                # Spawn bubble burst particles and hit flash
                self._particles.emit_target_burst(
                    hit_bubble.position[0],
                    hit_bubble.position[1],
                    hit_bubble.radius,
                    hit_bubble.target_type,
                    now,
                )

                # Bullseye / Headshot detection (within inner 35% of bubble radius)
                is_headshot = math.dist(hit_bubble.position, imp) <= (hit_bubble.radius * 0.35)
                txt = f"+{pts}"
                if mult > 1:
                    txt += f" ({mult}x)"
                if is_headshot:
                    txt += " • HEADSHOT"

                self._floating_scores.append(
                    FloatingScore(
                        text=txt,
                        x=hit_bubble.position[0],
                        y=hit_bubble.position[1] - 12,
                        created_at=now,
                        expires_at=now + 0.85,
                        color=THEME.ACCENT_GOLD if (is_gold or is_headshot) else THEME.ACCENT_CYAN,
                    )
                )

                self.audio.play_sfx(hit_bubble.hit_sound_name)
                self._shots.append(ShotEffect(position=imp, created_at=now, expires_at=now + settings.SHOT_EFFECT_SECONDS, hit=True))
            else:
                self._shots.append(ShotEffect(position=imp, created_at=now, expires_at=now + settings.SHOT_EFFECT_SECONDS, hit=False))

        if not hit_any and self._game.mode.allow_combo:
            self._game.combo.register_miss()

    # -- Rendering Pipeline ------------------------------------------------

    def _draw_bubble(self, surface: pygame.Surface, bubble: Bubble) -> None:
        """Render target bubble with type-specific color and highlight shine."""
        x, y = round(bubble.position[0]), round(bubble.position[1])
        r = round(bubble.radius)

        if bubble.target_type is BubbleType.GOLDEN:
            body_col = THEME.ACCENT_GOLD
            inner_col = (255, 240, 150)
        elif bubble.target_type is BubbleType.SMALL:
            body_col = (110, 235, 255)
            inner_col = (200, 250, 255)
        elif bubble.target_type is BubbleType.LARGE:
            body_col = (45, 120, 220)
            inner_col = (90, 165, 250)
        else:  # NORMAL
            body_col = THEME.ACCENT_CYAN
            inner_col = (150, 225, 255)

        # Bubble body outline
        pygame.draw.circle(surface, body_col, (x, y), r, 2)
        # Highlight shine dot
        shine_r = max(2, r // 4)
        shine_x = x - round(r * 0.35)
        shine_y = y - round(r * 0.35)
        pygame.draw.circle(surface, inner_col, (shine_x, shine_y), shine_r)

    def _draw(
        self,
        screen: pygame.Surface,
        result: TrackingResult | None,
        pinch_result: PinchResult | None,
        reload_result: ReloadResult | None,
        aim_pos: tuple[float, float],
        now: float,
    ) -> None:
        w, h = screen.get_size()
        screen.fill(THEME.BG_DARK)

        # Draw Clean Grid Background
        self._draw_ambient_grid(screen, w, h)

        # Draw Playfield Safe Frame
        l, t, r_bound, b = self.layout.playfield_bounds
        pf_rect = pygame.Rect(round(l), round(t), round(r_bound - l), round(b - t))
        draw_card(screen, pf_rect, (10, 14, 20, 180), THEME.BORDER_SUBTLE, border_radius=12)

        # Draw Subtle Reload Zone Area Indicator
        self._draw_reload_zone_guide(screen, pf_rect, reload_result, now)

        # Render Active Targets & Particles
        if self._game.state in (GameState.PLAYING, GameState.PAUSED, GameState.COUNTDOWN):
            for bubble in self._game.targets.bubbles:
                self._draw_bubble(screen, bubble)
            self._particles.draw(screen, now)

            # Render Floating Scores
            for fs in self._floating_scores:
                alpha = max(0.0, min(1.0, (fs.expires_at - now) / 0.8))
                prog = 1.0 - alpha
                cur_y = fs.y - prog * 24
                self.typo.draw_text(
                    screen,
                    fs.text,
                    self.typo.h2,
                    fs.color,
                    (round(fs.x), round(cur_y)),
                    anchor="center",
                )

        # Render Shot Trails / Pellet Impact Rings
        for shot in self._shots:
            self._draw_shot_effect(screen, shot, now)

        # Render Crosshair Reticle (Weapon-Specific)
        if self._game.state in (GameState.PLAYING, GameState.COUNTDOWN, GameState.READY):
            self._draw_crosshair(screen, aim_pos, pinch_result, now)

        # Damage Screen Flash
        if now < self._life_lost_flash_until:
            flash_surf = pygame.Surface((w, h), pygame.SRCALPHA)
            flash_surf.fill((*THEME.ACCENT_CORAL, 40))
            screen.blit(flash_surf, (0, 0))

        # Empty Magazine Cue
        weapons = self._game.weapons
        if weapons.is_empty and not weapons.is_reloading and self._game.state is GameState.PLAYING:
            msg_rect = pygame.Rect(w // 2 - 100, h - 110, 200, 42)
            draw_card(screen, msg_rect, (24, 16, 20, 210), THEME.BORDER_SUBTLE, border_radius=8)
            self.typo.draw_text(screen, "RELOAD", self.typo.body_bold, THEME.ACCENT_CORAL, (msg_rect.centerx, msg_rect.top + 12), anchor="center")
            self.typo.draw_text(screen, "move hand down", self.typo.caption, THEME.TEXT_MUTED, (msg_rect.centerx, msg_rect.bottom - 10), anchor="center")

        # Render Top HUD
        has_hand = (result is not None and result.has_hand)
        if self._game.state not in (GameState.MODE_SELECT, GameState.WEAPON_SELECT):
            self._draw_hud(screen, result, reload_result, now)

        # Render State Screens
        if self._game.state is GameState.MODE_SELECT:
            self._draw_mode_select(screen, w, h)
        elif self._game.state is GameState.WEAPON_SELECT:
            self._draw_weapon_select(screen, w, h)
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
        if self._game.state not in (GameState.MODE_SELECT, GameState.WEAPON_SELECT, GameState.PAUSED):
            draw_control_bar(screen, self.layout.control_bar_rect, self.typo, muted=self.audio.muted, debug_on=self._debug_hud)

        # Debug HUD (toggled with D)
        if self._debug_hud:
            self._draw_debug_hud(screen, result, pinch_result, reload_result, now)

    # -- UI Screens & HUD Layout -------------------------------------------

    def _draw_reload_zone_guide(
        self,
        screen: pygame.Surface,
        pf_rect: pygame.Rect,
        reload_result: ReloadResult | None,
        now: float,
    ) -> None:
        """Render subtle bottom reload zone indicator."""
        zone_y = round(pf_rect.top + pf_rect.height * settings.RELOAD_ZONE_TOP)
        zone_h = pf_rect.bottom - zone_y
        if zone_h <= 0:
            return

        in_zone = reload_result is not None and reload_result.in_zone
        weapons = self._game.weapons

        # Subtle bottom zone tint when relevant
        if in_zone or weapons.is_empty or weapons.is_reloading:
            alpha = 35 if in_zone else 15
            zone_surf = pygame.Surface((pf_rect.width, zone_h), pygame.SRCALPHA)
            col = (*THEME.ACCENT_CYAN, alpha) if not weapons.is_empty else (*THEME.ACCENT_GOLD, alpha)
            zone_surf.fill(col)
            screen.blit(zone_surf, (pf_rect.left, zone_y))

            # Dwell progress line
            if in_zone and reload_result and reload_result.progress > 0.0:
                prog_w = round(pf_rect.width * reload_result.progress)
                pygame.draw.line(screen, THEME.ACCENT_CYAN, (pf_rect.centerx - prog_w // 2, zone_y), (pf_rect.centerx + prog_w // 2, zone_y), 2)

    def _draw_hud(
        self,
        screen: pygame.Surface,
        result: TrackingResult | None,
        reload_result: ReloadResult | None,
        now: float,
    ) -> None:
        """Render modern top HUD with score, timer, mode, weapon ammo, lives, and combo."""
        bar_r = self.layout.top_bar_rect
        draw_card(screen, bar_r, THEME.BG_SURFACE_ELEVATED, THEME.BORDER_SUBTLE, border_radius=10)

        # Zone A: Title, Mode & Weapon Badge
        z_a = self.layout.left_zone
        self.typo.draw_text(screen, "HANDSHOT", self.typo.h1, THEME.ACCENT_CYAN, (z_a.left + 14, z_a.centery - 2), anchor="left")
        mode_badge = self._game.mode.badge
        self.typo.draw_text(screen, mode_badge, self.typo.label, THEME.TEXT_SECONDARY, (z_a.left + 148, z_a.centery + 1), anchor="left")
        w_name = f"[ {self._game.weapons.spec.name} ]"
        self.typo.draw_text(screen, w_name, self.typo.label, THEME.TEXT_MUTED, (z_a.left + 230, z_a.centery + 1), anchor="left")

        # Zone B: Score
        z_b = self.layout.center_zone
        score_val = f"{self._game.score.score:,}"
        self.typo.draw_text(screen, "SCORE", self.typo.label, THEME.TEXT_MUTED, (z_b.centerx, z_b.top + 8), anchor="center")
        self.typo.draw_text(screen, score_val, self.typo.score_large, THEME.TEXT_PRIMARY, (z_b.centerx, z_b.bottom - 8), anchor="center")

        # Zone C: Weapon Ammunition & Lives / Timer
        z_c = self.layout.right_zone
        weapons = self._game.weapons
        ammo_str = weapons.ammo_display_str

        # Ammo Display
        if weapons.is_reloading:
            self.typo.draw_text(screen, "RELOADING...", self.typo.body_bold, THEME.ACCENT_GOLD, (z_c.left + 10, z_c.centery), anchor="left")
            # Mini reload progress bar
            bar_w = 60
            bar_h = 3
            bar_x = z_c.left + 130
            bar_y = z_c.centery - 1
            pygame.draw.rect(screen, (24, 34, 48), (bar_x, bar_y, bar_w, bar_h), border_radius=2)
            prog_w = round(bar_w * weapons.reload_progress)
            if prog_w > 0:
                pygame.draw.rect(screen, THEME.ACCENT_GOLD, (bar_x, bar_y, prog_w, bar_h), border_radius=2)
        elif weapons.is_empty:
            blink = int(now * 4) % 2 == 0
            empty_col = THEME.ACCENT_CORAL if blink else THEME.TEXT_MUTED
            self.typo.draw_text(screen, "RELOAD", self.typo.body_bold, empty_col, (z_c.left + 10, z_c.centery), anchor="left")
            self.typo.draw_text(screen, ammo_str, self.typo.label, THEME.TEXT_MUTED, (z_c.left + 90, z_c.centery), anchor="left")
        else:
            self.typo.draw_text(screen, ammo_str, self.typo.h2, THEME.TEXT_PRIMARY, (z_c.left + 10, z_c.centery), anchor="left")

        # Rightmost: Lives / Mode indicator
        if self._game.mode.allow_life_loss:
            lx = z_c.right - 18
            for i in range(self._game.mode.initial_lives):
                active = (i < self._game.stats.lives)
                draw_vector_heart(screen, lx, z_c.centery, size=16.0, active=active)
                lx -= 24
        elif self._game.time_remaining is not None:
            time_txt = f"{int(self._game.time_remaining):02d}s"
            self.typo.draw_text(screen, time_txt, self.typo.h2, THEME.ACCENT_GOLD, (z_c.right - 14, z_c.centery), anchor="right")
        elif self._game.mode.infinite_ammo:
            self.typo.draw_text(screen, "ARCADE", self.typo.label, THEME.ACCENT_PURPLE, (z_c.right - 14, z_c.centery), anchor="right")
        else:
            self.typo.draw_text(screen, "RELAXED", self.typo.label, THEME.ACCENT_EMERALD, (z_c.right - 14, z_c.centery), anchor="right")

    def _draw_mode_select(self, screen: pygame.Surface, width: int, height: int) -> None:
        """Render mode selection screen with modern aesthetic cards."""
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((*THEME.BG_DARK, 220))
        screen.blit(overlay, (0, 0))

        # Title
        self.typo.draw_text(screen, "HANDSHOT", self.typo.display, THEME.ACCENT_CYAN, (width // 2, 54), anchor="center")
        self.typo.draw_text(screen, "SELECT GAME MODE", self.typo.h2, THEME.TEXT_PRIMARY, (width // 2, 108), anchor="center")

        # 4 Mode Cards (2x2 Grid)
        card_w = min(420, (width - 80) // 2)
        card_h = min(142, (height - 250) // 2)
        start_x = (width - (card_w * 2 + 24)) // 2
        start_y = 140

        for i, m in enumerate(ALL_MODES):
            row = i // 2
            col = i % 2
            x = start_x + col * (card_w + 24)
            y = start_y + row * (card_h + 16)
            rect = pygame.Rect(x, y, card_w, card_h)

            is_sel = (i == self._selected_mode_idx)
            bg = THEME.BG_SURFACE_HIGHLIGHT if is_sel else THEME.BG_SURFACE
            border_col = THEME.BORDER_FOCUS if is_sel else THEME.BORDER_SUBTLE
            b_width = 2 if is_sel else 1

            draw_card(screen, rect, bg, border_col, border_width=b_width, border_radius=12)

            # Icon
            icon_x = x + 34
            icon_y = y + card_h // 2
            if m.mode is GameMode.CLASSIC:
                draw_vector_target(screen, icon_x, icon_y, radius=16, color=THEME.ACCENT_CYAN)
            elif m.mode is GameMode.ARCADE:
                draw_vector_star(screen, icon_x, icon_y, radius=16, color=THEME.ACCENT_PURPLE)
            elif m.mode is GameMode.CHILL:
                draw_vector_leaf(screen, icon_x, icon_y, radius=16, color=THEME.ACCENT_EMERALD)
            elif m.mode is GameMode.TIMED:
                draw_vector_stopwatch(screen, icon_x, icon_y, radius=16, color=THEME.ACCENT_GOLD)
            else:
                draw_vector_star(screen, icon_x, icon_y, radius=16, color=THEME.ACCENT_PURPLE)

            # Text
            text_x = x + 72
            self.typo.draw_text(screen, m.name.upper(), self.typo.h1, THEME.TEXT_PRIMARY, (text_x, y + 24), anchor="left")
            self.typo.draw_text(screen, m.tagline, self.typo.body_small, THEME.TEXT_SECONDARY, (text_x, y + 58), anchor="left")

            hi = self._game.high_score if self._game.mode.mode == m.mode else 0
            if hi > 0:
                self.typo.draw_text(screen, f"BEST: {hi:,}", self.typo.caption, THEME.ACCENT_GOLD, (text_x, y + 88), anchor="left")

            if is_sel:
                draw_keycap(screen, "READY", "", self.typo.label, self.typo.caption, x + card_w - 50, y + card_h // 2, active=True)

        # Footer Instruction
        self.typo.draw_text(
            screen,
            "[ WASD / Arrows / TAB ] Choose Mode    [ ENTER / SPACE ] Next: Choose Weapon    [ M ] Mute    [ ESC / Q ] Quit",
            self.typo.body_small,
            THEME.TEXT_SECONDARY,
            (width // 2, height - 32),
            anchor="center",
        )

    def _draw_weapon_select(self, screen: pygame.Surface, width: int, height: int) -> None:
        """Render dedicated minimalist weapon selection screen."""
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((*THEME.BG_DARK, 220))
        screen.blit(overlay, (0, 0))

        # Title
        self.typo.draw_text(screen, "HANDSHOT", self.typo.display, THEME.ACCENT_CYAN, (width // 2, 54), anchor="center")
        self.typo.draw_text(screen, "CHOOSE YOUR WEAPON", self.typo.h2, THEME.TEXT_PRIMARY, (width // 2, 108), anchor="center")

        card_w = min(420, (width - 80) // 2)
        card_h = min(142, (height - 250) // 2)
        start_x = (width - (card_w * 2 + 24)) // 2
        start_y = 140

        for i, w_spec in enumerate(ALL_WEAPONS):
            row = i // 2
            col = i % 2
            x = start_x + col * (card_w + 24)
            y = start_y + row * (card_h + 16)
            rect = pygame.Rect(x, y, card_w, card_h)

            is_sel = (i == self._selected_weapon_idx)
            bg = THEME.BG_SURFACE_HIGHLIGHT if is_sel else THEME.BG_SURFACE
            border_col = THEME.BORDER_FOCUS if is_sel else THEME.BORDER_SUBTLE
            b_width = 2 if is_sel else 1

            draw_card(screen, rect, bg, border_col, border_width=b_width, border_radius=12)

            # Number badge cap
            draw_keycap(screen, str(i + 1), "", self.typo.label, self.typo.caption, x + 32, y + 36, active=is_sel)

            # Text
            text_x = x + 68
            self.typo.draw_text(screen, w_spec.name, self.typo.h1, THEME.TEXT_PRIMARY, (text_x, y + 24), anchor="left")
            self.typo.draw_text(screen, f"{w_spec.tagline}   •   {w_spec.difficulty_rating}", self.typo.body_bold, THEME.ACCENT_CYAN if is_sel else THEME.TEXT_SECONDARY, (text_x, y + 54), anchor="left")
            ammo_desc = f"{w_spec.magazine_size} / ∞" if not self._game.mode.infinite_ammo else "∞ (Arcade)"
            self.typo.draw_text(screen, f"AMMO: {ammo_desc}   •   RELOAD: {w_spec.reload_time_seconds:.1f}s", self.typo.caption, THEME.TEXT_MUTED, (text_x, y + 84), anchor="left")

            if is_sel:
                draw_keycap(screen, "READY", "", self.typo.label, self.typo.caption, x + card_w - 50, y + card_h // 2, active=True)

        # Footer Instruction
        self.typo.draw_text(
            screen,
            "[ 1-4 / WASD / TAB ] Change Weapon    [ ENTER / SPACE ] Start Run    [ ESC ] Back to Modes",
            self.typo.body_small,
            THEME.TEXT_SECONDARY,
            (width // 2, height - 32),
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

        if has_hand:
            title_text = "HAND DETECTED"
            title_col = THEME.ACCENT_EMERALD
            sub_text = "Hold hand steady to begin countdown..."
            prog = min(1.0, self._game.ready_hand_timer / settings.READY_HAND_STABLE_SECONDS)
        else:
            title_text = "RAISE YOUR HAND"
            title_col = THEME.ACCENT_CYAN
            sub_text = "Position your hand in front of the camera"
            prog = 0.0

        self.typo.draw_text(screen, title_text, self.typo.h1, title_col, (r.centerx, r.top + 34), anchor="center")
        self.typo.draw_text(screen, sub_text, self.typo.body, THEME.TEXT_SECONDARY, (r.centerx, r.top + 70), anchor="center")

        # Progress bar
        bar_x = r.left + 36
        bar_y = r.top + 105
        bar_w = r.width - 72
        bar_h = 10
        pygame.draw.rect(screen, (20, 28, 42), (bar_x, bar_y, bar_w, bar_h), border_radius=5)
        if prog > 0.0:
            fill_w = round(bar_w * prog)
            pygame.draw.rect(screen, THEME.ACCENT_EMERALD, (bar_x, bar_y, fill_w, bar_h), border_radius=5)

    def _draw_countdown(self, screen: pygame.Surface, width: int, height: int) -> None:
        """Render dramatic 3-2-1-GO! countdown overlay."""
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((*THEME.BG_DARK, 180))
        screen.blit(overlay, (0, 0))

        num_str = self._game.countdown_text or "3"
        col = THEME.ACCENT_EMERALD if num_str == "GO!" else THEME.ACCENT_CYAN
        self.typo.draw_text(screen, num_str, self.typo.countdown, col, (width // 2, height // 2 - 20), anchor="center")
        reload_hint = "PINCH TO SHOOT" if self._game.mode.infinite_ammo else "PINCH TO SHOOT   •   MOVE HAND DOWN TO RELOAD"
        self.typo.draw_text(screen, reload_hint, self.typo.h2, THEME.TEXT_PRIMARY, (width // 2, height // 2 + 75), anchor="center")

    def _draw_paused(self, screen: pygame.Surface) -> None:
        """Render clean, modern pause overlay card."""
        w, h = screen.get_size()
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((*THEME.BG_DARK, 210))
        screen.blit(overlay, (0, 0))

        r = pygame.Rect(w // 2 - 200, h // 2 - 120, 400, 240)
        draw_card(screen, r, THEME.BG_SURFACE, THEME.BORDER_FOCUS, border_width=2, border_radius=14)

        self.typo.draw_text(screen, "PAUSED", self.typo.h1, THEME.ACCENT_GOLD, (r.centerx, r.top + 36), anchor="center")
        self.typo.draw_text(screen, "[ ESC / P ] Resume", self.typo.body_bold, THEME.TEXT_PRIMARY, (r.centerx, r.top + 90), anchor="center")
        self.typo.draw_text(screen, "[ R ] Restart Run", self.typo.body, THEME.TEXT_SECONDARY, (r.centerx, r.top + 128), anchor="center")
        self.typo.draw_text(screen, "[ M ] Main Menu", self.typo.body, THEME.TEXT_SECONDARY, (r.centerx, r.top + 166), anchor="center")

    def _draw_game_over(self, screen: pygame.Surface, now: float) -> None:
        """Render clean run results card including weapon & mode summary."""
        w, h = screen.get_size()
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((*THEME.BG_DARK, 220))
        screen.blit(overlay, (0, 0))

        r = self.layout.results_card_rect
        draw_card(screen, r, THEME.BG_SURFACE, THEME.BORDER_FOCUS, border_width=2, border_radius=14)

        title = "NEW HIGH SCORE!" if self._game.is_new_high_score else "RUN COMPLETE"
        title_col = THEME.ACCENT_GOLD if self._game.is_new_high_score else THEME.ACCENT_CYAN
        self.typo.draw_text(screen, title, self.typo.h1, title_col, (r.centerx, r.top + 32), anchor="center")

        score_txt = f"{self._game.score.score:,}"
        self.typo.draw_text(screen, score_txt, self.typo.display, THEME.TEXT_PRIMARY, (r.centerx, r.top + 78), anchor="center")

        # Stats summary
        acc = f"{self._game.stats.accuracy:.1f}%"
        hits = f"{self._game.stats.targets_hit}"
        shots = f"{self._game.stats.shots_fired}"
        w_name = self._game.weapons.spec.name
        m_name = self._game.mode.name
        time_s = f"{self._game.gameplay_time:.1f}s"

        self.typo.draw_text(screen, f"ACCURACY: {acc}   •   HITS: {hits}   •   SHOTS: {shots}", self.typo.body_bold, THEME.TEXT_SECONDARY, (r.centerx, r.top + 140), anchor="center")
        self.typo.draw_text(screen, f"WEAPON: {w_name}   •   MODE: {m_name}   •   TIME: {time_s}", self.typo.body_small, THEME.TEXT_MUTED, (r.centerx, r.top + 172), anchor="center")

        # Key actions
        self.typo.draw_text(screen, "[ ENTER / R ] Play Again    [ ESC / M ] Mode Select", self.typo.body_small, THEME.ACCENT_CYAN, (r.centerx, r.bottom - 24), anchor="center")

    def _draw_crosshair(
        self,
        screen: pygame.Surface,
        pos: tuple[float, float],
        pinch: PinchResult | None,
        now: float,
    ) -> None:
        """Render weapon-specific vector crosshair reticle using modular CrosshairRenderer."""
        is_firing = (now < self._fire_pulse_until)
        is_empty = (now < self._empty_click_until) or self._game.weapons.is_empty
        is_pinched = (pinch and pinch.phase is PinchPhase.PINCHED)
        is_reloading = self._game.weapons.is_reloading

        state = CrosshairState(
            is_firing=is_firing,
            is_empty=is_empty,
            is_pinched=is_pinched,
            is_reloading=is_reloading,
            recoil_offset_px=self._recoil_offset_px,
        )
        draw_crosshair(screen, pos, self._game.weapons.spec.weapon_type, state)

    def _draw_shot_effect(self, screen: pygame.Surface, shot: ShotEffect, now: float) -> None:
        """Render expanding pulse ring on pellet impact."""
        age = now - shot.created_at
        dur = shot.expires_at - shot.created_at
        prog = min(1.0, age / dur)
        alpha = round((1.0 - prog) * 200)

        rad = round(10 + prog * 30)
        ring_surf = pygame.Surface((rad * 2 + 4, rad * 2 + 4), pygame.SRCALPHA)
        col = (*THEME.ACCENT_EMERALD, alpha) if shot.hit else (*THEME.ACCENT_CORAL, alpha)
        pygame.draw.circle(ring_surf, col, (rad + 2, rad + 2), rad, 2)
        screen.blit(ring_surf, (round(shot.position[0] - rad - 2), round(shot.position[1] - rad - 2)))

    def _draw_ambient_grid(self, screen: pygame.Surface, width: int, height: int) -> None:
        """Draw subtle background grid lines."""
        step = 60
        grid_col = (14, 18, 26)
        for x in range(0, width, step):
            pygame.draw.line(screen, grid_col, (x, 0), (x, height), 1)
        for y in range(0, height, step):
            pygame.draw.line(screen, grid_col, (0, y), (width, y), 1)

    def _draw_debug_hud(
        self,
        screen: pygame.Surface,
        result: TrackingResult | None,
        pinch_result: PinchResult | None,
        reload_result: ReloadResult | None,
        now: float,
    ) -> None:
        """Render isolated, compact monospaced Debug Panel strictly below top HUD."""
        r = self.layout.debug_panel_rect
        draw_card(screen, r, (10, 14, 22, 235), THEME.BORDER_SUBTLE, border_radius=8)

        cam_fps = self.camera.measured_fps if self.camera is not None else 0.0
        if self.camera is not None:
            cam_text = f"CAM: LOCAL ({self.camera.backend_name}, {cam_fps:.0f} FPS)"
        else:
            cam_text = "CAM: n/a"

        weapons = self._game.weapons
        w_text = f"WEAPON: {weapons.spec.name} ({weapons.mag_ammo}/{weapons.reserve_ammo})"
        if weapons.is_reloading:
            w_state_text = f"WEAPON STATE: RELOADING ({int(weapons.reload_progress * 100)}%)"
            w_state_col = THEME.ACCENT_GOLD
        elif weapons.is_empty:
            w_state_text = "WEAPON STATE: EMPTY"
            w_state_col = THEME.ACCENT_CORAL
        else:
            w_state_text = "WEAPON STATE: READY"
            w_state_col = THEME.ACCENT_EMERALD

        if reload_result is not None and reload_result.in_zone:
            rel_zone_text = f"RELOAD ZONE: INSIDE (DWELL: {reload_result.dwell_time:.2f}/{settings.RELOAD_DWELL_SECONDS:.2f}s)"
            rel_zone_col = THEME.ACCENT_CYAN
        else:
            rel_zone_text = "RELOAD ZONE: OUTSIDE"
            rel_zone_col = THEME.TEXT_MUTED

        if self.tracker is None:
            hand_text, hand_color = "HAND: disabled", THEME.TEXT_MUTED
        elif result is None:
            hand_text, hand_color = "HAND: starting...", THEME.TEXT_SECONDARY
        elif result.fresh and result.hand is not None:
            hand_text = f"HAND: tracked {result.hand.handedness} ({result.hand.score:.2f})"
            hand_color = THEME.ACCENT_EMERALD
        elif result.coasting and result.hand is not None:
            hand_text = f"HAND: coasting ({result.stale_frames}f held)"
            hand_color = THEME.ACCENT_GOLD
        else:
            hand_text, hand_color = "HAND: lost", THEME.ACCENT_CORAL

        raw_in = self._aim.raw_input
        filt_in = self._aim.filtered_input
        vel = self._aim.velocity
        speed = math.hypot(vel[0], vel[1])
        fc = self._aim.current_cutoff_hz

        if raw_in is not None and filt_in is not None:
            raw_text = f"RAW/FILT: ({raw_in[0]:.2f},{raw_in[1]:.2f}) -> ({filt_in[0]:.2f},{filt_in[1]:.2f})"
        else:
            raw_text = "RAW/FILT: —"

        vel_text = f"VEL/FC: {speed:4.2f} norm/s (fc={fc:4.1f}Hz)"
        aim_x, aim_y = round(self._aim.position[0]), round(self._aim.position[1])
        aim_text = f"AIM PIXELS: x={aim_x}, y={aim_y}"

        pinch = pinch_result or self._last_pinch
        dist_val = pinch.normalized_distance if pinch is not None else None
        if dist_val is not None:
            dist_status = "PINCH" if dist_val <= settings.PINCH_CLOSE_THRESHOLD else ("OPEN" if dist_val >= settings.PINCH_RELEASE_THRESHOLD else "MID")
            dist_text = f"PINCH: {dist_val:.2f} ({dist_status}) [{pinch.phase.name}]"
        else:
            dist_text = "PINCH: —"

        stats_text = f"LIVES: {self._game.stats.lives}  HITS: {self._game.stats.targets_hit}/{self._game.stats.shots_fired} ({self._game.stats.accuracy:.0f}%)"

        y = r.top + 7
        for line, col in [
            (cam_text, THEME.ACCENT_CYAN),
            (w_text, THEME.TEXT_PRIMARY),
            (w_state_text, w_state_col),
            (rel_zone_text, rel_zone_col),
            (hand_text, hand_color),
            (dist_text, THEME.ACCENT_GOLD),
            (raw_text, THEME.TEXT_SECONDARY),
            (vel_text, THEME.ACCENT_PURPLE),
            (aim_text, THEME.TEXT_PRIMARY),
            (stats_text, THEME.ACCENT_CYAN),
        ]:
            self.typo.draw_text(screen, line, self.typo.monospace_debug, col, (r.left + 10, y), anchor="topleft")
            y += 18

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
