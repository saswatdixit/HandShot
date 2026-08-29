"""Dedicated Real-Time Camera & Hand Tracking Laboratory for HANDSHOT.

Provides live video feed, full 21-landmark hand skeleton visualization, index fingertip
tracking, aim reticle response, pinch distance gauge, and camera diagnostics.
"""

from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING

import cv2
import numpy as np
import pygame

from aim.aim_controller import AimController, AimSettings
from camera.camera_manager import CameraManager
from config import settings
from game.theme import THEME
from game.typography import Typography
from game.ui_layout import UILayout
from game.ui_renderer import draw_card, draw_keycap
from gestures.pinch_detector import PinchDetector, PinchPhase, PinchResult

if TYPE_CHECKING:
    from camera.hand_tracker import HandTracker, Hand, TrackingResult

# MediaPipe Hand Landmark Connection Pairs
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),        # Thumb
    (0, 5), (5, 6), (6, 7), (7, 8),        # Index
    (5, 9), (9, 10), (10, 11), (11, 12),   # Middle
    (9, 13), (13, 14), (14, 15), (15, 16), # Ring
    (13, 17), (17, 18), (18, 19), (19, 20),# Pinky
    (0, 17),                                # Palm Base
]


class CameraPreviewScreen:
    """Real-time camera feed and MediaPipe hand tracking laboratory."""

    def __init__(
        self,
        camera: CameraManager,
        tracker: HandTracker | None,
        debug_hud: bool = True,
    ) -> None:
        if not pygame.get_init():
            pygame.init()
        if not pygame.font.get_init():
            pygame.font.init()

        self.camera = camera
        self.tracker = tracker
        self._debug_hud = debug_hud
        self._show_landmarks = True

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
        self._last_pinch: PinchResult | None = None
        self._last_shot_time = 0.0

    def run(self, duration: float = 0.0) -> int:
        screen = pygame.display.set_mode(
            (settings.GAME_WIDTH, settings.GAME_HEIGHT), pygame.RESIZABLE
        )
        pygame.display.set_caption("HANDSHOT — Camera & Hand Tracking Preview")
        clock = pygame.time.Clock()

        self._resize(screen.get_size())

        started = time.perf_counter()
        running = True
        exit_code = 0
        last_result: TrackingResult | None = None

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
                        running = self._handle_key(event)

                # Capture Frame
                frame = self.camera.read()
                pinch_result: PinchResult | None = None

                if frame is not None and self.tracker is not None:
                    last_result = self.tracker.process(frame, mirrored=self.camera.mirror)
                    if last_result.hand is not None:
                        pinch_result = self._pinch.update(last_result.hand, now)
                    else:
                        pinch_result = self._pinch.update(None, now)

                if pinch_result is not None:
                    self._last_pinch = pinch_result
                    if pinch_result.shot:
                        self._last_shot_time = now

                fingertip = (
                    last_result.hand.index_tip_norm
                    if last_result is not None and last_result.hand is not None
                    else None
                )
                position = self._aim.update(fingertip, delta_seconds, now=now)

                # Render Preview Laboratory Frame
                self._draw(screen, frame, last_result, pinch_result, position, now)
                pygame.display.flip()

                if duration and time.perf_counter() - started >= duration:
                    running = False
        except Exception as exc:
            import traceback
            traceback.print_exc()
            print(f"\nPreview Error: {exc}")
            exit_code = 1
        finally:
            pygame.quit()
        return exit_code

    def _resize(self, size: tuple[int, int]) -> None:
        self.layout.update_screen_size(size)
        self.typo.set_screen_size(size)
        self._aim.set_screen_size(size)

    def _handle_key(self, event: pygame.event.Event) -> bool:
        if event.key in (pygame.K_ESCAPE, pygame.K_q):
            return False

        if event.key == pygame.K_c:
            self.camera.toggle_mirror()
            self._aim.reset()
            self._pinch.reset()
            if self.tracker:
                self.tracker.reset()

        elif event.key == pygame.K_l:
            self._show_landmarks = not self._show_landmarks

        elif event.key == pygame.K_d:
            self._debug_hud = not self._debug_hud

        elif event.key == pygame.K_r:
            if self.tracker:
                self.tracker.reset()
            self._aim.reset()
            self._pinch.reset()

        return True

    def _draw(
        self,
        screen: pygame.Surface,
        frame: np.ndarray | None,
        result: TrackingResult | None,
        pinch_result: PinchResult | None,
        aim_pos: tuple[float, float],
        now: float,
    ) -> None:
        w, h = screen.get_size()
        screen.fill(THEME.BG_DARK)

        # 1. Draw Live Camera Feed (Centered with aspect ratio preservation)
        feed_rect = pygame.Rect(0, 0, w, h)
        if frame is not None:
            fh, fw = frame.shape[:2]
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            raw_surf = pygame.image.frombuffer(frame_rgb.tobytes(), (fw, fh), "RGB")

            scale = min(w / fw, h / fh)
            sw, sh = round(fw * scale), round(fh * scale)
            scaled_surf = pygame.transform.scale(raw_surf, (sw, sh))

            feed_x = (w - sw) // 2
            feed_y = (h - sh) // 2
            feed_rect = pygame.Rect(feed_x, feed_y, sw, sh)

            dark_filter = pygame.Surface((sw, sh), pygame.SRCALPHA)
            dark_filter.fill((10, 13, 18, 90))
            scaled_surf.blit(dark_filter, (0, 0))

            screen.blit(scaled_surf, (feed_x, feed_y))
        else:
            self.typo.draw_text(
                screen,
                "WAITING FOR CAMERA FEED...",
                self.typo.h2,
                THEME.TEXT_MUTED,
                (w // 2, h // 2),
                anchor="center",
            )

        # 2. Draw Hand Landmarks & Full Skeleton
        if self._show_landmarks and result is not None and result.hand is not None:
            self._draw_hand_skeleton(screen, result.hand, feed_rect, result.coasting)

        # 3. Draw Aim Reticle
        self._draw_aim_reticle(screen, aim_pos, now)

        # 4. Top Header Bar
        header_rect = pygame.Rect(0, 0, w, 56)
        draw_card(screen, header_rect, (12, 16, 24, 230), THEME.BORDER_SUBTLE, border_width=1, border_radius=0)

        self.typo.draw_text(screen, "HANDSHOT", self.typo.h1, THEME.ACCENT_CYAN, (24, 10), anchor="topleft")
        self.typo.draw_text(screen, "CAMERA & TRACKING LABORATORY", self.typo.body_bold, THEME.TEXT_PRIMARY, (175, 18), anchor="topleft")

        cam_name = f"Webcam ({self.camera.index})"
        fps_txt = f"{self.camera.measured_fps:.1f} FPS"
        self.typo.draw_text(screen, f"{cam_name}  •  {fps_txt}", self.typo.body_bold, THEME.ACCENT_GOLD, (w - 24, 18), anchor="topright")

        # 5. Bottom Control Strip
        controls_rect = pygame.Rect(20, h - 54, w - 40, 42)
        draw_card(screen, controls_rect, (12, 16, 24, 230), THEME.BORDER_SUBTLE, border_radius=8)

        items = [
            ("C", "MIRROR " + ("ON" if self.camera.mirror else "OFF"), self.camera.mirror, THEME.TEXT_PRIMARY),
            ("L", "LANDMARKS " + ("ON" if self._show_landmarks else "OFF"), self._show_landmarks, THEME.ACCENT_EMERALD),
            ("D", "DEBUG HUD", self._debug_hud, THEME.ACCENT_GOLD),
            ("R", "RESET", False, THEME.TEXT_PRIMARY),
            ("ESC", "EXIT", False, THEME.ACCENT_CORAL),
        ]

        spacing = controls_rect.width / (len(items) + 1)
        for i, (key, lbl, is_act, act_col) in enumerate(items, start=1):
            item_cx = controls_rect.left + i * spacing
            draw_keycap(
                screen,
                key,
                lbl,
                self.typo.label,
                self.typo.caption,
                item_cx,
                controls_rect.centery,
                active=is_act,
                active_color=act_col,
            )

        # 6. Live Debug Panel (if toggled)
        if self._debug_hud:
            self._draw_diagnostics(screen, result, pinch_result, aim_pos, now)

    def _draw_hand_skeleton(
        self,
        screen: pygame.Surface,
        hand: Hand,
        rect: pygame.Rect,
        coasting: bool,
    ) -> None:
        """Render complete 21-point hand skeleton with highlighted index fingertip."""
        points: list[tuple[int, int]] = []
        for pt in hand.landmarks_norm:
            nx = float(pt[0])
            ny = float(pt[1])
            px = round(rect.left + nx * rect.width)
            py = round(rect.top + ny * rect.height)
            points.append((px, py))

        # Bones
        bone_color = (180, 140, 50) if coasting else THEME.ACCENT_CYAN
        for p1_idx, p2_idx in HAND_CONNECTIONS:
            if p1_idx < len(points) and p2_idx < len(points):
                pygame.draw.line(screen, bone_color, points[p1_idx], points[p2_idx], 2)

        # Landmarks
        for i, (px, py) in enumerate(points):
            if i == 8:  # Index fingertip
                pygame.draw.circle(screen, (90, 215, 255, 80), (px, py), 12)
                pygame.draw.circle(screen, THEME.ACCENT_CYAN, (px, py), 7)
                pygame.draw.circle(screen, (255, 255, 255), (px, py), 3)
            elif i == 4:  # Thumb tip
                pygame.draw.circle(screen, THEME.ACCENT_GOLD, (px, py), 5)
            else:
                dot_col = THEME.ACCENT_EMERALD if not coasting else THEME.ACCENT_GOLD
                pygame.draw.circle(screen, dot_col, (px, py), 3)

    def _draw_aim_reticle(self, screen: pygame.Surface, pos: tuple[float, float], now: float) -> None:
        """Draw responsive crosshair reticle."""
        x, y = round(pos[0]), round(pos[1])
        is_fired = (now - self._last_shot_time < 0.25)

        ret_col = THEME.ACCENT_GOLD if is_fired else THEME.ACCENT_CYAN
        radius = 18 if is_fired else 14

        pygame.draw.circle(screen, (255, 255, 255), (x, y), 2)
        pygame.draw.circle(screen, ret_col, (x, y), radius, 2)
        pygame.draw.line(screen, ret_col, (x, y - radius - 8), (x, y - radius - 3), 2)
        pygame.draw.line(screen, ret_col, (x, y + radius + 3), (x, y + radius + 8), 2)
        pygame.draw.line(screen, ret_col, (x - radius - 8, y), (x - radius - 3, y), 2)
        pygame.draw.line(screen, ret_col, (x + radius + 3, y), (x + radius + 8, y), 2)

    def _draw_diagnostics(
        self,
        screen: pygame.Surface,
        result: TrackingResult | None,
        pinch_result: PinchResult | None,
        aim_pos: tuple[float, float],
        now: float,
    ) -> None:
        """Draw comprehensive tracking diagnostic panel."""
        w = screen.get_width()
        panel_w = 280
        panel_h = 240
        r = pygame.Rect(w - panel_w - 20, 68, panel_w, panel_h)
        draw_card(screen, r, (10, 14, 22, 235), THEME.BORDER_SUBTLE, border_radius=8)

        cam_fps = self.camera.measured_fps
        src_name = f"WEBCAM ({self.camera.backend_name})"

        if result is None:
            hand_stat, hand_col = "SEARCHING...", THEME.TEXT_MUTED
        elif result.fresh and result.hand is not None:
            hand_stat = f"TRACKED ({result.hand.handedness})"
            hand_col = THEME.ACCENT_EMERALD
        elif result.coasting:
            hand_stat = f"COASTING ({result.stale_frames}f held)"
            hand_col = THEME.ACCENT_GOLD
        else:
            hand_stat, hand_col = "LOST", THEME.ACCENT_CORAL

        pinch = pinch_result or self._last_pinch
        dist_val = pinch.normalized_distance if pinch is not None else None
        if dist_val is not None:
            is_pinched = (pinch.phase is PinchPhase.PINCHED or dist_val <= settings.PINCH_CLOSE_THRESHOLD)
            pinch_stat = "PINCHED" if is_pinched else "OPEN"
            pinch_col = THEME.ACCENT_EMERALD if is_pinched else THEME.ACCENT_GOLD
            dist_str = f"{dist_val:.2f} ({pinch_stat})"
        else:
            dist_str, pinch_col = "—", THEME.TEXT_MUTED

        lines = [
            ("CAMERA", src_name, THEME.ACCENT_CYAN),
            ("FPS", f"{cam_fps:.1f} FPS", THEME.TEXT_PRIMARY),
            ("TRACKING", hand_stat, hand_col),
            ("INDEX TIP", f"x={round(aim_pos[0])}, y={round(aim_pos[1])}", THEME.TEXT_PRIMARY),
            ("PINCH DIST", dist_str, pinch_col),
            ("SHOTS FIRED", "READY" if (now - self._last_shot_time > 0.4) else "FIRED!", THEME.ACCENT_GOLD),
        ]

        y = r.top + 10
        for label, val, col in lines:
            self.typo.draw_text(screen, label, self.typo.label, THEME.TEXT_MUTED, (r.left + 12, y), anchor="topleft")
            self.typo.draw_text(screen, val, self.typo.monospace_debug, col, (r.right - 12, y), anchor="topright")
            y += 24

        # Gauge bar at bottom
        gauge_x = r.left + 12
        gauge_y = r.bottom - 18
        gauge_w = r.width - 24
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
