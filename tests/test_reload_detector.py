"""Unit tests for spatial bottom reload zone detection and hysteresis."""

import unittest
from types import SimpleNamespace

import numpy as np

from config import settings
from gestures.reload_detector import ReloadDetector, ReloadSettings


def hand_at_y(norm_y: float) -> SimpleNamespace:
    """Mock hand with normalized y position."""
    landmarks_norm = np.zeros((21, 3), dtype=np.float32)
    landmarks_norm[settings.WRIST] = (0.5, norm_y, 0.0)
    landmarks_norm[settings.MIDDLE_MCP] = (0.5, norm_y, 0.0)
    return SimpleNamespace(landmarks_norm=landmarks_norm, landmarks_px=None)


class ReloadDetectorTests(unittest.TestCase):
    def test_hand_above_zone_does_not_trigger(self) -> None:
        detector = ReloadDetector(ReloadSettings(zone_top=0.85, dwell_seconds=0.25))
        # Hand in aiming area (y=0.40)
        res = detector.update(hand_at_y(0.40), delta_seconds=0.50, now=0.50)
        self.assertFalse(res.in_zone)
        self.assertFalse(res.reload_triggered)
        self.assertEqual(res.progress, 0.0)

    def test_entering_and_dwelling_triggers_reload(self) -> None:
        detector = ReloadDetector(ReloadSettings(zone_top=0.85, zone_exit=0.75, dwell_seconds=0.25))
        # Hand moves down into reload zone (y=0.90)
        # Step 1: 0.10s -> progress 40%
        res1 = detector.update(hand_at_y(0.90), delta_seconds=0.10, now=0.10)
        self.assertTrue(res1.in_zone)
        self.assertFalse(res1.reload_triggered)
        self.assertAlmostEqual(res1.progress, 0.40, places=1)

        # Step 2: +0.10s (total 0.20s) -> progress 80%
        res2 = detector.update(hand_at_y(0.90), delta_seconds=0.10, now=0.20)
        self.assertTrue(res2.in_zone)
        self.assertFalse(res2.reload_triggered)

        # Step 3: +0.10s (total 0.30s >= 0.25s) -> triggers reload!
        res3 = detector.update(hand_at_y(0.90), delta_seconds=0.10, now=0.30)
        self.assertTrue(res3.in_zone)
        self.assertTrue(res3.reload_triggered)

        # Step 4: Held in zone -> does NOT trigger again
        res4 = detector.update(hand_at_y(0.90), delta_seconds=0.10, now=0.40)
        self.assertTrue(res4.in_zone)
        self.assertFalse(res4.reload_triggered)

    def test_must_exit_zone_to_rearm(self) -> None:
        detector = ReloadDetector(ReloadSettings(zone_top=0.85, zone_exit=0.75, dwell_seconds=0.25, cooldown_seconds=0.10))
        # Trigger first reload
        detector.update(hand_at_y(0.90), delta_seconds=0.30, now=0.30)

        # Hand hovers in hysteresis zone (y=0.80) -> not exited yet (needs <= 0.75)
        detector.update(hand_at_y(0.80), delta_seconds=0.10, now=0.40)
        # Move back to 0.90 without exiting -> does not re-trigger
        res_fail = detector.update(hand_at_y(0.90), delta_seconds=0.30, now=0.70)
        self.assertFalse(res_fail.reload_triggered)

        # Hand fully exits above zone (y=0.60 <= 0.75) -> re-arms
        detector.update(hand_at_y(0.60), delta_seconds=0.10, now=0.80)

        # Lower back down to 0.90 and dwell -> triggers second reload
        detector.update(hand_at_y(0.90), delta_seconds=0.15, now=0.95)
        res_rearm = detector.update(hand_at_y(0.90), delta_seconds=0.15, now=1.10)
        self.assertTrue(res_rearm.reload_triggered)

    def test_tracking_loss_resets_dwell(self) -> None:
        detector = ReloadDetector(ReloadSettings(zone_top=0.85, dwell_seconds=0.25))
        # In zone for 0.15s
        detector.update(hand_at_y(0.90), delta_seconds=0.15, now=0.15)
        self.assertAlmostEqual(detector.dwell_time, 0.15)

        # Tracking lost
        res_loss = detector.update(None, delta_seconds=0.05, now=0.20)
        self.assertFalse(res_loss.in_zone)
        self.assertEqual(res_loss.dwell_time, 0.0)

        # Hand returns -> must dwell fresh 0.25s
        res_ret = detector.update(hand_at_y(0.90), delta_seconds=0.10, now=0.30)
        self.assertFalse(res_ret.reload_triggered)
        self.assertAlmostEqual(res_ret.dwell_time, 0.10)


if __name__ == "__main__":
    unittest.main()
