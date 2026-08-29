"""Comprehensive unit tests for Phase 11 UI Layout, Typography, and Collision-Free Zone Separation."""

from __future__ import annotations

import unittest
import pygame

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
)


class UILayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()

    @classmethod
    def tearDownClass(cls) -> None:
        pygame.quit()

    def test_typography_scaling_and_measuring(self) -> None:
        typo = Typography((1280, 720))
        self.assertIsNotNone(typo.title)
        self.assertIsNotNone(typo.hud_label)
        self.assertIsNotNone(typo.score)

        # Measurement helper
        w, h = typo.measure_text("HANDSHOT", typo.title)
        self.assertGreater(w, 50)
        self.assertGreater(h, 10)

        # Resizing updates fonts
        typo.set_screen_size((960, 540))
        w_small, h_small = typo.measure_text("HANDSHOT", typo.title)
        self.assertLessEqual(w_small, w)

    def test_vector_icons_drawing(self) -> None:
        surf = pygame.Surface((400, 400))
        draw_vector_heart(surf, 50, 50, size=18, active=True)
        draw_vector_heart(surf, 80, 50, size=18, active=False)
        draw_vector_stopwatch(surf, 120, 50, radius=10)
        draw_vector_target(surf, 160, 50, radius=10)
        draw_vector_leaf(surf, 200, 50, radius=10)
        draw_vector_star(surf, 240, 50, radius=12)
        draw_vector_speaker(surf, 50, 100, radius=9, muted=False)
        draw_vector_speaker(surf, 80, 100, radius=9, muted=True)

        card_rect = draw_card(surf, (10, 150, 200, 80), (20, 30, 45, 200), (60, 90, 130))
        self.assertEqual(card_rect.width, 200)

        typo = Typography((1280, 720))
        keycap_rect = draw_keycap(surf, "P", "PAUSE", typo.small_bold, typo.small, 100, 260)
        self.assertGreater(keycap_rect.width, 30)

        ctrl_rect = pygame.Rect(10, 320, 380, 40)
        draw_control_bar(surf, ctrl_rect, typo, muted=False, debug_on=True)

    def test_hud_zone_separation_and_playfield_bounds(self) -> None:
        """Verify Left, Center, and Right HUD zones, playfield bounds, and debug panel across resolutions."""
        for width, height in [(1280, 720), (1024, 768), (960, 540)]:
            layout = UILayout((width, height))

            # Verify HUD zones do not horizontally collide
            self.assertTrue(
                layout.check_hud_zones_separated(),
                f"HUD zones overlapped at resolution {width}x{height}",
            )

            # Verify active playfield is strictly below Top HUD and above Bottom Control Bar
            self.assertTrue(
                layout.check_playfield_separated(),
                f"Playfield collided with HUD or Control Bar at resolution {width}x{height}",
            )

            # Verify Debug Panel is strictly below Top HUD
            self.assertGreaterEqual(
                layout.debug_panel_rect.top,
                layout.top_bar_rect.bottom,
                f"Debug panel overlapped Top HUD at resolution {width}x{height}",
            )

            # Verify Debug Panel fits within right screen border
            self.assertLessEqual(
                layout.debug_panel_rect.right,
                width,
                f"Debug panel exceeded screen width at resolution {width}x{height}",
            )


if __name__ == "__main__":
    unittest.main()
