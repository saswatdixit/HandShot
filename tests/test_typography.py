"""Regression tests for the Typography font-resolution cascade.

The cascade used to be a no-op: `pygame.font.SysFont()` never returns None and
never raises for a missing family -- it silently substitutes the built-in default
font -- so probing candidates one at a time always "succeeded" on the first name
and every display/body style rendered in the default font at roughly half the
intended glyph height.
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from game.typography import Typography

# A family name that will not be installed anywhere.
MISSING = "ZzNotARealFontFamily123"


class FontCascadeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.font.init()

    def setUp(self) -> None:
        self.typo = Typography((1280, 720))

    def test_sysfont_silent_fallback_assumption_still_holds(self) -> None:
        """Documents the pygame behaviour this cascade must defend against.

        If a future pygame starts returning None or raising for missing families,
        this test fails and the workaround can be simplified.
        """
        self.assertIsNone(pygame.font.match_font(MISSING))
        self.assertIsNotNone(
            pygame.font.SysFont(MISSING, 32),
            "SysFont is expected to silently substitute the default font",
        )

    def test_missing_leading_candidate_does_not_win(self) -> None:
        """The real regression: a missing first candidate must be skipped.

        The "display" list starts with webfonts (Outfit, Inter) that are usually
        absent. If any later candidate is installed, the resolved font must not
        be the built-in default -- which is what the broken cascade returned.
        """
        display_candidates = ["Outfit", "Inter", "Segoe UI Semibold", "Segoe UI",
                              "Arial", "Trebuchet MS"]
        installed = [n for n in display_candidates if pygame.font.match_font(n) is not None]
        if not installed:
            self.skipTest("none of the display candidates are installed here")
        if installed[0] == display_candidates[0]:
            self.skipTest("first candidate is installed; cascade is not exercised")

        default_h = pygame.font.Font(None, 40).get_height()
        expected_h = pygame.font.SysFont(",".join(installed), 40, bold=True).get_height()
        if expected_h == default_h:
            self.skipTest("installed candidate is metrically identical to the default")

        resolved = self.typo._get_font("display", 40, bold=True)
        self.assertEqual(
            resolved.get_height(), expected_h,
            "cascade did not resolve to the first installed candidate",
        )
        self.assertNotEqual(
            resolved.get_height(), default_h,
            "cascade silently fell back to the default font",
        )

    def test_hierarchy_is_monotonic_and_nonzero(self) -> None:
        """Larger styles must actually render larger, whichever family resolves."""
        order = [
            self.typo.caption,
            self.typo.body,
            self.typo.heading,
            self.typo.title,
            self.typo.display,
            self.typo.countdown,
        ]
        heights = [f.get_height() for f in order]
        for h in heights:
            self.assertGreater(h, 0)
        self.assertEqual(
            heights, sorted(heights),
            f"typography hierarchy is not monotonically increasing: {heights}",
        )

    def test_fonts_are_cached_by_family_size_and_weight(self) -> None:
        a = self.typo._get_font("ui", 20, bold=False)
        b = self.typo._get_font("ui", 20, bold=False)
        self.assertIs(a, b, "identical requests should hit the cache")

        bold = self.typo._get_font("ui", 20, bold=True)
        self.assertIsNot(a, bold, "bold and regular must be cached separately")

    def test_set_screen_size_rebuilds_fonts(self) -> None:
        big = self.typo.display.get_height()
        self.typo.set_screen_size((640, 480))
        small = self.typo.display.get_height()
        self.assertLess(small, big, "scaling down should reduce the display font")

    def test_public_api_surface_is_intact(self) -> None:
        """The design system depends on every one of these attributes existing."""
        for name in (
            "display", "title", "heading", "body", "body_bold", "body_small",
            "label", "caption", "score_large", "countdown", "monospace_debug",
            "h1", "h2", "display_xl", "display_l", "hud_label", "hud_value",
            "subtitle", "small", "small_bold", "button", "score", "debug",
        ):
            font = getattr(self.typo, name, None)
            self.assertIsInstance(font, pygame.font.Font, f"typo.{name} missing")


if __name__ == "__main__":
    unittest.main()
