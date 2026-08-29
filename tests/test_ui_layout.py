"""Unit tests for Phase 10.5 Typography, Vector UI rendering, and Layout bounding boxes."""

from __future__ import annotations

import unittest
import pygame

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
        surf = pygame.Surface((300, 300))
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

        keycap_rect = draw_keycap(surf, "ENTER", pygame.font.Font(None, 20), 100, 260)
        self.assertGreater(keycap_rect.width, 30)

    def test_hud_zone_separation_across_resolutions(self) -> None:
        """Verify Left, Center, and Right HUD zones never collide."""
        for width, height in [(1280, 720), (1024, 768), (960, 540)]:
            typo = Typography((width, height))

            # Left Zone bounds
            lx = 24
            brand_w, _ = typo.measure_text("HANDSHOT", typo.title)
            left_zone_right = lx + brand_w

            # Center Zone bounds
            cx = width // 2
            score_w, _ = typo.measure_text("SCORE: 999,990", typo.score)
            center_zone_left = cx - score_w // 2
            center_zone_right = cx + score_w // 2

            # Right Zone bounds
            rx = width - 24
            best_w, _ = typo.measure_text("BEST: 999,990", typo.hud_value)
            right_zone_left = rx - best_w - 90

            # Verify no horizontal collisions between zones
            self.assertLess(
                left_zone_right,
                center_zone_left,
                f"Left zone collided with Center zone at resolution {width}x{height}",
            )
            self.assertLess(
                center_zone_right,
                right_zone_left,
                f"Center zone collided with Right zone at resolution {width}x{height}",
            )


if __name__ == "__main__":
    unittest.main()
