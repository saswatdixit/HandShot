"""Focused, camera-free checks for the crosshair controller."""

import unittest

from aim import AimController, AimSettings


def default_settings(**overrides) -> AimSettings:
    values = dict(
        input_left=0.0,
        input_top=0.0,
        input_right=1.0,
        input_bottom=1.0,
        deadzone=0.0,
        smoothing_hz=1_000.0,
        margin=20,
        pre_shot_anchor_seconds=0.08,
    )
    values.update(overrides)
    return AimSettings(**values)


def controller(**overrides) -> AimController:
    return AimController((1000, 500), default_settings(**overrides))


def smooth_controller() -> AimController:
    return AimController(
        (1000, 500),
        default_settings(deadzone=0.0, smoothing_hz=8.0),
    )


class AimControllerTests(unittest.TestCase):
    def test_first_sample_anchors_without_teleporting(self) -> None:
        aim = controller()
        self.assertEqual(aim.update((1.0, 0.0), 1 / 60), (980.0, 20.0))

    def test_direct_mapping_moves_crosshair(self) -> None:
        aim = controller()
        aim.update((0.5, 0.5), 1 / 60)
        x, y = aim.update((0.6, 0.4), 1 / 60)
        self.assertAlmostEqual(x, 596.0, delta=5.0)
        self.assertAlmostEqual(y, 204.0, delta=5.0)

    def test_deadzone_ignores_jitter_when_configured(self) -> None:
        aim = controller(deadzone=0.01)
        aim.update((0.5, 0.5), 1 / 60)
        self.assertEqual(aim.update((0.505, 0.505), 1 / 60), (500.0, 250.0))

    def test_zero_deadzone_allows_continuous_micro_movement(self) -> None:
        aim = controller(deadzone=0.0)
        aim.update((0.5, 0.5), 1 / 60)
        x, y = aim.update((0.502, 0.502), 1 / 60)
        self.assertNotEqual((x, y), (500.0, 250.0))
        self.assertAlmostEqual(x, 501.9, delta=0.5)

    def test_crosshair_is_clamped_to_visible_bounds(self) -> None:
        aim = controller()
        aim.update((0.5, 0.5), 1 / 60)
        x, y = aim.update((10.0, -10.0), 1 / 60)
        self.assertAlmostEqual(x, 980.0, places=1)
        self.assertAlmostEqual(y, 20.0, places=1)

    def test_smoothing_damps_jitter_without_large_lag(self) -> None:
        aim = smooth_controller()
        aim.update((0.5, 0.5), 0.01)
        jittered_x, _ = aim.update((0.52, 0.5), 0.01)
        self.assertLess(jittered_x, 510.0)
        settled_x, _ = aim.update((0.5, 0.5), 0.25)
        self.assertAlmostEqual(settled_x, 500.0, places=0)

    def test_slow_movement_tracks_steadily(self) -> None:
        aim = controller(smoothing_hz=60.0)
        aim.update((0.5, 0.5), 1 / 60)
        positions = []
        for step in range(10):
            t = 0.5 + step * 0.01
            positions.append(aim.update((t, 0.5), 1 / 60)[0])
        self.assertGreater(positions[-1], positions[0])
        self.assertLess(positions[-1], 600.0)

    def test_fast_motion_reaches_screen_edge_quickly(self) -> None:
        aim = controller(smoothing_hz=120.0)
        aim.update((0.1, 0.5), 1 / 60)
        for _ in range(12):
            x, _ = aim.update((1.0, 0.5), 1 / 60)
        self.assertAlmostEqual(x, 980.0, delta=8.0)

    def test_comfortable_input_region_covers_full_playfield(self) -> None:
        aim = controller(
            input_left=0.20,
            input_top=0.18,
            input_right=0.80,
            input_bottom=0.78,
        )
        left_x, top_y = aim.update((0.20, 0.18), 1 / 60)
        self.assertAlmostEqual(left_x, 20.0, places=0)
        self.assertAlmostEqual(top_y, 20.0, places=0)
        right_x, bottom_y = aim.update((0.80, 0.78), 1 / 60)
        self.assertAlmostEqual(right_x, 980.0, places=0)
        self.assertAlmostEqual(bottom_y, 480.0, places=0)

    def test_pre_shot_anchor_retrieves_prior_position(self) -> None:
        aim = controller(pre_shot_anchor_seconds=0.08)
        # Time 0.00: Aiming directly at target (500, 250)
        aim.update((0.5, 0.5), 0.01, now=0.00)
        # Time 0.04: Finger starts closing towards pinch
        aim.update((0.52, 0.52), 0.04, now=0.04)
        # Time 0.08: Pinch closure causes finger to jerk to (0.55, 0.55)
        aim.update((0.55, 0.55), 0.04, now=0.08)

        # Current live position has jerked
        current_x, current_y = aim.position
        self.assertAlmostEqual(current_x, 548.0, delta=5.0)

        # Pre-shot anchor retrieves the pre-jerk aim position at 0.00 (0.08s ago)
        anchored_x, anchored_y = aim.get_anchored_position(now=0.08)
        self.assertAlmostEqual(anchored_x, 500.0, delta=5.0)
        self.assertAlmostEqual(anchored_y, 250.0, delta=5.0)

    def test_none_input_holds_position(self) -> None:
        aim = controller()
        anchored = aim.update((0.5, 0.5), 1 / 60)
        self.assertEqual(aim.update(None, 1 / 60), anchored)

    def test_resize_keeps_mapping_valid(self) -> None:
        aim = controller()
        aim.update((0.5, 0.5), 1 / 60)
        aim.set_screen_size((800, 400))
        x, y = aim.update((0.75, 0.25), 1 / 60)
        self.assertAlmostEqual(x, 590.0, delta=2.0)
        self.assertAlmostEqual(y, 110.0, delta=2.0)


if __name__ == "__main__":
    unittest.main()

