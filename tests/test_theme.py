"""Unit tests for Phase 12 Theme and Visual Design System."""

from __future__ import annotations

import unittest
from game.theme import THEME, ThemeColors


class ThemeTests(unittest.TestCase):
    def test_theme_palette_integrity(self) -> None:
        self.assertIsInstance(THEME, ThemeColors)
        # Backgrounds
        self.assertEqual(len(THEME.BG_DARK), 3)
        self.assertEqual(len(THEME.BG_SURFACE), 3)
        self.assertEqual(len(THEME.BG_SURFACE_ELEVATED), 3)

        # Accents
        self.assertEqual(len(THEME.ACCENT_CYAN), 3)
        self.assertEqual(len(THEME.ACCENT_EMERALD), 3)
        self.assertEqual(len(THEME.ACCENT_GOLD), 3)
        self.assertEqual(len(THEME.ACCENT_CORAL), 3)

        # Typography colors
        self.assertEqual(len(THEME.TEXT_PRIMARY), 3)
        self.assertEqual(len(THEME.TEXT_SECONDARY), 3)
        self.assertEqual(len(THEME.TEXT_MUTED), 3)


if __name__ == "__main__":
    unittest.main()
