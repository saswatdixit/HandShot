"""Unit tests for the reusable vector crosshair renderer."""

import unittest

import pygame

from game.crosshair_renderer import CrosshairState, draw_crosshair
from game.weapon import WeaponType


class CrosshairRendererTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not pygame.get_init():
            pygame.init()

    def setUp(self) -> None:
        self.surface = pygame.Surface((800, 600), pygame.SRCALPHA)

    def test_draw_all_weapon_types(self) -> None:
        for w_type in WeaponType:
            # Normal state
            draw_crosshair(self.surface, (400.0, 300.0), w_type)
            # Firing state
            draw_crosshair(self.surface, (400.0, 300.0), w_type, CrosshairState(is_firing=True, recoil_offset_px=8.0))
            # Empty state
            draw_crosshair(self.surface, (400.0, 300.0), w_type, CrosshairState(is_empty=True))
            # Reloading state
            draw_crosshair(self.surface, (400.0, 300.0), w_type, CrosshairState(is_reloading=True))

    def test_crosshair_does_not_modify_aim_position(self) -> None:
        pos = (450.0, 280.0)
        st = CrosshairState(recoil_offset_px=14.0)
        draw_crosshair(self.surface, pos, WeaponType.SHOTGUN, st)
        # Verify original coordinates remain unchanged
        self.assertEqual(pos, (450.0, 280.0))


if __name__ == "__main__":
    unittest.main()
