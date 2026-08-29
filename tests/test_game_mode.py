"""Unit tests for Phase 8 Game Modes configurations and presets."""

from __future__ import annotations

import unittest

from config import settings
from game.game_mode import (
    ALL_MODES,
    GameMode,
    ModeConfig,
    get_chill_mode,
    get_classic_mode,
    get_default_mode,
    get_practice_mode,
    get_timed_mode,
)


class GameModeTests(unittest.TestCase):
    def test_default_mode_is_classic(self) -> None:
        mode = get_default_mode()
        self.assertEqual(mode.mode, GameMode.CLASSIC)
        self.assertEqual(mode.initial_lives, 3)
        self.assertTrue(mode.allow_life_loss)
        self.assertTrue(mode.difficulty_scaling)
        self.assertIsNone(mode.time_limit_seconds)

    def test_classic_mode_configuration(self) -> None:
        classic = get_classic_mode()
        self.assertEqual(classic.name, "CLASSIC")
        self.assertEqual(classic.initial_lives, 3)
        self.assertTrue(classic.allow_life_loss)
        self.assertTrue(classic.allow_combo)
        self.assertTrue(classic.difficulty_scaling)
        self.assertEqual(classic.speed_min_start, settings.BUBBLE_SPEED_MIN_START)
        self.assertEqual(classic.theme_music_track, "classic")

    def test_chill_mode_configuration(self) -> None:
        chill = get_chill_mode()
        self.assertEqual(chill.name, "CHILL")
        self.assertEqual(chill.initial_lives, 0)
        self.assertFalse(chill.allow_life_loss)
        self.assertFalse(chill.difficulty_scaling)
        self.assertIsNone(chill.time_limit_seconds)
        self.assertEqual(chill.bubble_initial_count, 2)
        self.assertEqual(chill.max_active_start, 3)
        self.assertLess(chill.speed_min_start, settings.BUBBLE_SPEED_MIN_START)
        self.assertEqual(chill.theme_music_track, "chill")

    def test_timed_mode_configuration(self) -> None:
        timed = get_timed_mode()
        self.assertEqual(timed.name, "TIMED")
        self.assertEqual(timed.initial_lives, 0)
        self.assertFalse(timed.allow_life_loss)
        self.assertEqual(timed.time_limit_seconds, 60.0)
        self.assertTrue(timed.difficulty_scaling)
        self.assertEqual(timed.theme_music_track, "timed")

    def test_practice_mode_configuration(self) -> None:
        practice = get_practice_mode()
        self.assertEqual(practice.name, "PRACTICE")
        self.assertEqual(practice.initial_lives, 0)
        self.assertFalse(practice.allow_life_loss)
        self.assertFalse(practice.difficulty_scaling)
        self.assertIsNone(practice.time_limit_seconds)
        self.assertEqual(practice.max_active_start, 2)
        self.assertEqual(practice.theme_music_track, "practice")

    def test_all_modes_contains_four_distinct_modes(self) -> None:
        self.assertEqual(len(ALL_MODES), 4)
        names = [m.name for m in ALL_MODES]
        self.assertEqual(names, ["CLASSIC", "CHILL", "TIMED", "PRACTICE"])


if __name__ == "__main__":
    unittest.main()
