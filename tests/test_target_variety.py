"""Unit tests for Phase 9 Target Variety, attributes, scoring, and mode-specific spawning."""

from __future__ import annotations

import random
import unittest

from config import settings
from game.bubble import Bubble, BubbleType
from game.bubble_game import BubbleGame, GameState
from game.game_mode import get_chill_mode, get_classic_mode, get_practice_mode, get_timed_mode
from game.target_manager import TargetManager

BOUNDS = (20.0, 100.0, 980.0, 620.0)


class TargetVarietyTests(unittest.TestCase):
    def test_target_type_base_scores(self) -> None:
        normal = Bubble((100.0, 100.0), (0.0, 0.0), 30.0, target_type=BubbleType.NORMAL)
        small = Bubble((100.0, 100.0), (0.0, 0.0), 20.0, target_type=BubbleType.SMALL)
        large = Bubble((100.0, 100.0), (0.0, 0.0), 45.0, target_type=BubbleType.LARGE)
        golden = Bubble((100.0, 100.0), (0.0, 0.0), 35.0, target_type=BubbleType.GOLDEN)

        self.assertEqual(normal.base_score, 10)
        self.assertEqual(small.base_score, 20)
        self.assertEqual(large.base_score, 5)
        self.assertEqual(golden.base_score, 50)

    def test_target_type_hit_sound_names(self) -> None:
        normal = Bubble((100.0, 100.0), (0.0, 0.0), 30.0, target_type=BubbleType.NORMAL)
        small = Bubble((100.0, 100.0), (0.0, 0.0), 20.0, target_type=BubbleType.SMALL)
        large = Bubble((100.0, 100.0), (0.0, 0.0), 45.0, target_type=BubbleType.LARGE)
        golden = Bubble((100.0, 100.0), (0.0, 0.0), 35.0, target_type=BubbleType.GOLDEN)

        self.assertEqual(normal.hit_sound_name, "bubble_hit")
        self.assertEqual(small.hit_sound_name, "bubble_hit_small")
        self.assertEqual(large.hit_sound_name, "bubble_hit_large")
        self.assertEqual(golden.hit_sound_name, "bubble_hit_golden")

    def test_target_radii_and_speed_multipliers(self) -> None:
        mgr = TargetManager(rng=random.Random(42))

        # Check radius helper
        r_small = mgr._get_target_radius(BubbleType.SMALL)
        self.assertTrue(settings.RADIUS_SMALL_MIN <= r_small <= settings.RADIUS_SMALL_MAX)

        r_normal = mgr._get_target_radius(BubbleType.NORMAL)
        self.assertTrue(settings.RADIUS_NORMAL_MIN <= r_normal <= settings.RADIUS_NORMAL_MAX)

        r_large = mgr._get_target_radius(BubbleType.LARGE)
        self.assertTrue(settings.RADIUS_LARGE_MIN <= r_large <= settings.RADIUS_LARGE_MAX)

        r_golden = mgr._get_target_radius(BubbleType.GOLDEN)
        self.assertTrue(settings.RADIUS_GOLDEN_MIN <= r_golden <= settings.RADIUS_GOLDEN_MAX)

        # Check speed multipliers
        self.assertEqual(mgr._get_target_speed_multiplier(BubbleType.NORMAL), 1.00)
        self.assertEqual(mgr._get_target_speed_multiplier(BubbleType.SMALL), 1.35)
        self.assertEqual(mgr._get_target_speed_multiplier(BubbleType.LARGE), 0.70)
        self.assertEqual(mgr._get_target_speed_multiplier(BubbleType.GOLDEN), 1.05)

    def test_spawn_probabilities_per_mode(self) -> None:
        classic = get_classic_mode()
        self.assertAlmostEqual(sum(classic.spawn_probabilities), 1.0)
        self.assertEqual(classic.spawn_probabilities[3], 0.03)  # Golden is 3%

        chill = get_chill_mode()
        self.assertAlmostEqual(sum(chill.spawn_probabilities), 1.0)
        self.assertEqual(chill.spawn_probabilities[2], 0.45)  # Large is 45%

        timed = get_timed_mode()
        self.assertAlmostEqual(sum(timed.spawn_probabilities), 1.0)
        self.assertEqual(timed.spawn_probabilities[1], 0.25)  # Small is 25%

        practice = get_practice_mode()
        self.assertAlmostEqual(sum(practice.spawn_probabilities), 1.0)
        self.assertEqual(practice.spawn_probabilities[1], 0.00)  # No fast small targets

    def test_golden_target_hit_scoring_and_stats(self) -> None:
        game = BubbleGame(random.Random(1))
        game.reset(BOUNDS, start_state=GameState.PLAYING)

        golden_bubble = Bubble((400.0, 300.0), (0.0, 0.0), 35.0, target_type=BubbleType.GOLDEN)
        game.targets.bubbles = [golden_bubble]

        hit, points = game.shoot((400.0, 300.0))
        self.assertIsNotNone(hit)
        self.assertEqual(hit.target_type, BubbleType.GOLDEN)
        self.assertEqual(points, 50)
        self.assertEqual(game.score.score, 50)
        self.assertEqual(game.stats.golden_targets_hit, 1)
        self.assertEqual(game.stats.targets_hit, 1)


if __name__ == "__main__":
    unittest.main()
