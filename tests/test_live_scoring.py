"""Regression tests for the LIVE scoring path (AimScreen._handle_shot).

These deliberately exercise the production entry point rather than
``BubbleGame.shoot()``, because the live path is what a player actually hits and
it is the path that previously reported >100% accuracy for multi-pellet weapons.

Key detail: ``_handle_shot`` fires from the pre-pinch *anchored* aim position
(``AimController.get_anchored_position``), not from the current aim position, so
targets must be planted there for a shot to connect.
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.aim_screen import AimScreen
from game.bubble import Bubble, BubbleType
from game.bubble_game import GameState
from game.weapon import PISTOL_SPEC, SHOTGUN_SPEC, WeaponSpec

NOW = 100.0


class LiveScoringTests(unittest.TestCase):
    """Fire real shots through AimScreen._handle_shot and audit the accounting."""

    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()

    @classmethod
    def tearDownClass(cls) -> None:
        pygame.quit()

    def _screen(self, spec: WeaponSpec) -> AimScreen:
        screen = AimScreen(camera=None, tracker=None)
        screen.audio.muted = True
        screen._game.state = GameState.PLAYING
        screen._game.weapons.select_weapon(spec)
        return screen

    @staticmethod
    def _plant(screen: AimScreen, count: int, radius: float = 16.0,
               target_type: BubbleType = BubbleType.NORMAL) -> tuple[float, float]:
        """Clear the field and cluster `count` targets on the shot origin."""
        cx, cy = screen._aim.get_anchored_position(NOW)
        screen._game.targets.bubbles.clear()
        for i in range(count):
            screen._game.targets.bubbles.append(
                Bubble(
                    position=(cx + i * 9.0 - 20.0, cy),
                    radius=radius,
                    target_type=target_type,
                    velocity=(0.0, 0.0),
                )
            )
        return cx, cy

    def _assert_consistent(self, screen: AimScreen) -> None:
        """Invariants that must hold after any sequence of live shots."""
        stats = screen._game.stats
        self.assertLessEqual(
            stats.accuracy, 100.0,
            f"accuracy exceeded 100%: {stats.accuracy}",
        )
        self.assertGreaterEqual(stats.accuracy, 0.0)
        self.assertLessEqual(
            stats.shots_hit, stats.shots_fired,
            "connecting shots cannot exceed shots fired",
        )
        self.assertGreaterEqual(stats.shots_fired, 0)
        self.assertGreaterEqual(stats.targets_hit, stats.shots_hit)
        self.assertLessEqual(stats.golden_targets_hit, stats.targets_hit)

    # ── Single-shot weapon ────────────────────────────────────────────

    def test_single_pellet_hit_counts_one_shot_one_hit(self) -> None:
        screen = self._screen(PISTOL_SPEC)
        self._plant(screen, 1)
        before_ammo = screen._game.weapons.mag_ammo

        screen._handle_shot(NOW)

        stats = screen._game.stats
        self.assertEqual(stats.shots_fired, 1)
        self.assertEqual(stats.shots_hit, 1)
        self.assertEqual(stats.targets_hit, 1)
        self.assertEqual(stats.accuracy, 100.0)
        self.assertEqual(before_ammo - screen._game.weapons.mag_ammo, 1)
        self.assertGreater(screen._game.score.score, 0)
        self._assert_consistent(screen)

    def test_single_pellet_miss_counts_shot_but_no_hit(self) -> None:
        screen = self._screen(PISTOL_SPEC)
        self._plant(screen, 0)
        before_ammo = screen._game.weapons.mag_ammo

        screen._handle_shot(NOW)

        stats = screen._game.stats
        self.assertEqual(stats.shots_fired, 1)
        self.assertEqual(stats.shots_hit, 0)
        self.assertEqual(stats.targets_hit, 0)
        self.assertEqual(stats.accuracy, 0.0)
        self.assertEqual(screen._game.score.score, 0)
        self.assertEqual(before_ammo - screen._game.weapons.mag_ammo, 1)
        self._assert_consistent(screen)

    def test_hit_then_miss_gives_fifty_percent(self) -> None:
        screen = self._screen(PISTOL_SPEC)
        self._plant(screen, 1)
        screen._handle_shot(NOW)
        self._plant(screen, 0)
        screen._handle_shot(NOW + 1.0)

        stats = screen._game.stats
        self.assertEqual((stats.shots_fired, stats.shots_hit), (2, 1))
        self.assertEqual(stats.accuracy, 50.0)
        self._assert_consistent(screen)

    # ── Multi-pellet weapon ───────────────────────────────────────────

    def test_shotgun_one_pull_is_one_shot_and_one_round(self) -> None:
        """Regression: a single shotgun pull previously reported up to 600%."""
        screen = self._screen(SHOTGUN_SPEC)
        self.assertGreater(SHOTGUN_SPEC.pellet_count, 1, "fixture must be multi-pellet")
        self._plant(screen, SHOTGUN_SPEC.pellet_count)
        before_ammo = screen._game.weapons.mag_ammo

        screen._handle_shot(NOW)

        stats = screen._game.stats
        self.assertEqual(stats.shots_fired, 1, "one trigger pull is one shot")
        self.assertEqual(before_ammo - screen._game.weapons.mag_ammo, 1,
                         "one trigger pull consumes one round")
        self.assertEqual(stats.shots_hit, 1, "a connecting pull counts once")
        self.assertGreater(stats.targets_hit, 1,
                           "clustered targets should yield multiple kills")
        self.assertEqual(stats.accuracy, 100.0)
        self._assert_consistent(screen)

    def test_shotgun_accuracy_never_exceeds_one_hundred_over_many_pulls(self) -> None:
        screen = self._screen(SHOTGUN_SPEC)
        now = NOW
        for _ in range(SHOTGUN_SPEC.magazine_size):
            self._plant(screen, SHOTGUN_SPEC.pellet_count)
            screen._handle_shot(now)
            self._assert_consistent(screen)
            now += SHOTGUN_SPEC.fire_cooldown_seconds + 0.01

        stats = screen._game.stats
        self.assertEqual(stats.shots_fired, SHOTGUN_SPEC.magazine_size)
        self.assertGreater(stats.targets_hit, stats.shots_fired,
                           "multi-pellet fire should destroy more targets than pulls")
        self.assertEqual(stats.accuracy, 100.0)

    def test_shotgun_miss_does_not_credit_a_hit(self) -> None:
        screen = self._screen(SHOTGUN_SPEC)
        self._plant(screen, 0)

        screen._handle_shot(NOW)

        stats = screen._game.stats
        self.assertEqual((stats.shots_fired, stats.shots_hit, stats.targets_hit), (1, 0, 0))
        self.assertEqual(stats.accuracy, 0.0)
        self._assert_consistent(screen)

    # ── Ammo / cooldown gating must not corrupt the counters ──────────

    def test_blocked_shots_do_not_count(self) -> None:
        """Cooldown, empty magazine, and reloading must not record a shot."""
        screen = self._screen(PISTOL_SPEC)
        self._plant(screen, 1)
        screen._handle_shot(NOW)
        self.assertEqual(screen._game.stats.shots_fired, 1)

        # Immediate second pull is inside the fire cooldown.
        self._plant(screen, 1)
        screen._handle_shot(NOW)
        self.assertEqual(screen._game.stats.shots_fired, 1, "cooldown must block")

        # Empty magazine.
        screen._game.weapons._mag_ammo = 0
        screen._handle_shot(NOW + 10.0)
        self.assertEqual(screen._game.stats.shots_fired, 1, "empty magazine must block")

        # Mid-reload.
        screen._game.weapons.start_reload(NOW + 11.0)
        screen._handle_shot(NOW + 11.1)
        self.assertEqual(screen._game.stats.shots_fired, 1, "reload must block")
        self._assert_consistent(screen)

    def test_golden_targets_tracked_on_live_path(self) -> None:
        screen = self._screen(PISTOL_SPEC)
        self._plant(screen, 1, target_type=BubbleType.GOLDEN)

        screen._handle_shot(NOW)

        stats = screen._game.stats
        self.assertEqual(stats.golden_targets_hit, 1)
        self.assertEqual(stats.targets_hit, 1)
        self._assert_consistent(screen)

    # ── Shared source of truth ────────────────────────────────────────

    def test_live_path_and_bubble_game_shoot_agree_for_single_pellet(self) -> None:
        """Both entry points route through BubbleGame.register_impact()."""
        live = self._screen(PISTOL_SPEC)
        cx, cy = self._plant(live, 1)
        live._handle_shot(NOW)

        direct = self._screen(PISTOL_SPEC)
        self._plant(direct, 1)
        direct._game.shoot((cx - 20.0, cy))

        for field in ("shots_fired", "shots_hit", "targets_hit"):
            self.assertEqual(
                getattr(live._game.stats, field),
                getattr(direct._game.stats, field),
                f"{field} diverged between the live path and BubbleGame.shoot()",
            )
        self.assertEqual(live._game.score.score, direct._game.score.score)
        self.assertEqual(live._game.stats.accuracy, direct._game.stats.accuracy)

    def test_reset_clears_the_connected_shot_flag(self) -> None:
        screen = self._screen(PISTOL_SPEC)
        self._plant(screen, 1)
        screen._handle_shot(NOW)
        self.assertEqual(screen._game.stats.shots_hit, 1)

        screen._game.stats.reset()
        self.assertEqual(screen._game.stats.shots_hit, 0)
        self.assertEqual(screen._game.stats.accuracy, 0.0)

        # A miss immediately after reset must not inherit stale hit credit.
        self._plant(screen, 0)
        screen._handle_shot(NOW + 5.0)
        self.assertEqual(screen._game.stats.shots_hit, 0)
        self.assertEqual(screen._game.stats.accuracy, 0.0)
        self._assert_consistent(screen)


if __name__ == "__main__":
    unittest.main()
