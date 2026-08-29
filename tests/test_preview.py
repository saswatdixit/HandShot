"""Unit tests for CameraPreviewScreen laboratory (Phase 13)."""

from __future__ import annotations

import unittest
import numpy as np
import pygame

from camera.camera_manager import CameraManager
from camera.hand_tracker import Hand, TrackingResult
from camera.preview_screen import CameraPreviewScreen
from tests.test_camera_sources import MockCameraSource


class PreviewScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()

    @classmethod
    def tearDownClass(cls) -> None:
        pygame.quit()

    def test_preview_screen_initialization_and_render_without_hand(self) -> None:
        mock = MockCameraSource()
        manager = CameraManager(source=mock)
        preview_app = CameraPreviewScreen(manager, tracker=None, debug_hud=True)

        screen = pygame.Surface((1280, 720))
        dummy_frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        # Render frame with no hand
        preview_app._draw(screen, dummy_frame, None, None, (640, 360), now=0.0)

        # Test key event toggles
        k_w = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_w)
        self.assertTrue(preview_app._handle_key(k_w))

        k_c = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_c)
        self.assertTrue(preview_app._handle_key(k_c))

        k_l = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_l)
        self.assertTrue(preview_app._handle_key(k_l))

        k_d = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d)
        self.assertTrue(preview_app._handle_key(k_d))

        k_esc = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
        self.assertFalse(preview_app._handle_key(k_esc))

    def test_preview_screen_render_with_hand_landmarks_3d(self) -> None:
        """Verify that 3D (21, 3) landmark coordinates are safely rendered without unpacking errors."""
        mock = MockCameraSource()
        manager = CameraManager(source=mock)
        preview_app = CameraPreviewScreen(manager, tracker=None, debug_hud=True)

        screen = pygame.Surface((1280, 720))
        dummy_frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        # Create synthetic Hand with (21, 3) normalized coordinates
        norm_landmarks = np.zeros((21, 3), dtype=np.float32)
        for i in range(21):
            norm_landmarks[i] = [0.1 + i * 0.04, 0.2 + (i % 5) * 0.1, 0.05]

        px_landmarks = np.zeros((21, 2), dtype=np.int32)
        for i in range(21):
            px_landmarks[i] = [int(norm_landmarks[i][0] * 1280), int(norm_landmarks[i][1] * 720)]

        hand = Hand(
            landmarks_norm=norm_landmarks,
            landmarks_px=px_landmarks,
            handedness="Right",
            score=0.98,
            frame_size=(1280, 720),
        )

        tracking_res = TrackingResult(
            hand=hand,
            fresh=True,
            stale_frames=0,
            process_ms=12.5,
        )

        # This should execute cleanly without "too many values to unpack" exception
        preview_app._draw(screen, dummy_frame, tracking_res, None, (640, 360), now=1.0)


if __name__ == "__main__":
    unittest.main()
