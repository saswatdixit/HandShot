"""Focused, camera-free checks for pinch state, rapid firing, and release."""

import unittest
from types import SimpleNamespace

import numpy as np

from config import settings
from gestures import PinchDetector, PinchPhase, PinchSettings


def hand_px(
    distance_px: float,
    palm_len: float = 140.0,
    angle_rad: float = 0.0,
) -> SimpleNamespace:
    """Build pixel landmarks with isotropic Euclidean coordinates rotated by angle_rad."""
    cos_a, sin_a = np.cos(angle_rad), np.sin(angle_rad)
    rot = np.array([[cos_a, -sin_a], [sin_a, cos_a]])

    raw_px = np.zeros((21, 2), dtype=np.int32)
    # Wrist at (640, 360)
    raw_px[settings.WRIST] = np.rint(rot @ np.array([0.0, 0.0]) + np.array([640, 360]))
    # Middle MCP along primary axis
    raw_px[settings.MIDDLE_MCP] = np.rint(rot @ np.array([0.0, palm_len]) + np.array([640, 360]))
    # Index MCP and Pinky MCP across knuckles
    raw_px[settings.INDEX_MCP] = np.rint(rot @ np.array([-40.0, palm_len * 0.9]) + np.array([640, 360]))
    raw_px[settings.PINKY_MCP] = np.rint(rot @ np.array([45.0, palm_len * 0.8]) + np.array([640, 360]))
    # Thumb tip and Index tip separated by distance_px
    raw_px[settings.THUMB_TIP] = np.rint(rot @ np.array([-20.0, palm_len * 0.5]) + np.array([640, 360]))
    raw_px[settings.INDEX_TIP] = np.rint(
        rot @ np.array([-20.0 + distance_px, palm_len * 0.5]) + np.array([640, 360])
    )

    return SimpleNamespace(landmarks_px=raw_px, landmarks_norm=raw_px / 1280.0)


def hand_norm(distance: float, scale: float = 1.0) -> SimpleNamespace:
    """Build normalized landmarks for normalized-only test scenarios."""
    landmarks = np.zeros((21, 3), dtype=np.float32)
    landmarks[settings.WRIST] = (0.0, 0.0, 0.0)
    landmarks[settings.MIDDLE_MCP] = (scale, 0.0, 0.0)
    landmarks[settings.INDEX_MCP] = (scale / 2.0, 0.0, 0.0)
    landmarks[settings.PINKY_MCP] = (-scale / 2.0, 0.0, 0.0)
    landmarks[settings.THUMB_TIP] = (0.0, 0.0, 0.0)
    landmarks[settings.INDEX_TIP] = (distance * scale, 0.0, 0.0)
    return SimpleNamespace(landmarks_norm=landmarks, landmarks_px=None)


class PinchDetectorTests(unittest.TestCase):
    def test_relaxed_natural_pinch_fires_immediate_shot(self) -> None:
        pinch = PinchDetector()
        # Palm len 140px, relaxed thumb+index distance 35px -> metric = 35/140 = 0.25 <= 0.40
        result = pinch.update(hand_px(35.0, palm_len=140.0), 0.00)
        self.assertTrue(result.shot)
        self.assertEqual(result.phase, PinchPhase.PINCHED)
        self.assertTrue(result.is_pinched)
        self.assertAlmostEqual(result.normalized_distance, 0.25, delta=0.03)

    def test_tight_pinch_fires_shot(self) -> None:
        pinch = PinchDetector()
        # Tight pinch: 15px distance -> metric = 15/140 = 0.107 <= 0.40
        result = pinch.update(hand_px(15.0, palm_len=140.0), 0.00)
        self.assertTrue(result.shot)
        self.assertEqual(result.phase, PinchPhase.PINCHED)

    def test_partial_near_pinch_does_not_fire(self) -> None:
        pinch = PinchDetector()
        # Partial pinch (fingers still 75px apart) -> metric = 75/140 = 0.535 > 0.40
        result = pinch.update(hand_px(75.0, palm_len=140.0), 0.00)
        self.assertFalse(result.shot)
        self.assertEqual(result.phase, PinchPhase.READY)

    def test_held_pinch_produces_exactly_one_shot(self) -> None:
        pinch = PinchDetector()
        self.assertTrue(pinch.update(hand_px(25.0), 0.00).shot)
        self.assertFalse(pinch.update(hand_px(25.0), 0.03).shot)
        self.assertFalse(pinch.update(hand_px(25.0), 0.06).shot)
        self.assertFalse(pinch.update(hand_px(25.0), 0.10).shot)
        self.assertTrue(pinch.update(hand_px(25.0), 0.12).is_pinched)

    def test_pinch_release_pinch_produces_two_shots(self) -> None:
        pinch = PinchDetector()
        # Shot 1
        res1 = pinch.update(hand_px(25.0), 0.00)
        self.assertTrue(res1.shot)
        # Release (distance 95px -> metric = 95/140 = 0.678 >= 0.55)
        res_open = pinch.update(hand_px(95.0), 0.04)
        self.assertFalse(res_open.is_pinched)
        self.assertEqual(res_open.phase, PinchPhase.READY)
        # Shot 2 (after 0.05s cooldown)
        res2 = pinch.update(hand_px(25.0), 0.08)
        self.assertTrue(res2.shot)
        self.assertEqual(res2.phase, PinchPhase.PINCHED)

    def test_very_fast_pinch_release_cycles(self) -> None:
        pinch = PinchDetector()
        # Rapid cycle 1
        self.assertTrue(pinch.update(hand_px(20.0), 0.00).shot)
        self.assertEqual(pinch.update(hand_px(90.0), 0.03).phase, PinchPhase.READY)
        # Rapid cycle 2
        self.assertTrue(pinch.update(hand_px(20.0), 0.06).shot)
        self.assertEqual(pinch.update(hand_px(90.0), 0.09).phase, PinchPhase.READY)
        # Rapid cycle 3
        self.assertTrue(pinch.update(hand_px(20.0), 0.12).shot)

    def test_tracking_loss_resets_state_without_phantom_shots(self) -> None:
        pinch = PinchDetector()
        # Pinched when hand visible
        pinch.update(hand_px(20.0), 0.00)
        self.assertEqual(pinch.phase, PinchPhase.PINCHED)
        # Tracking loss
        res_lost = pinch.update(None, 0.03)
        self.assertFalse(res_lost.is_pinched)
        self.assertFalse(res_lost.shot)
        self.assertEqual(pinch.phase, PinchPhase.READY)
        # Hand returns open -> no phantom shot
        res_return = pinch.update(hand_px(100.0), 0.10)
        self.assertFalse(res_return.shot)
        self.assertEqual(pinch.phase, PinchPhase.READY)

    def test_hand_rotation_invariance(self) -> None:
        pinch = PinchDetector()
        # Test across vertical, diagonal (45 deg), horizontal (90 deg), and inverted angles
        for angle in [0.0, np.pi / 4, np.pi / 2, np.pi * 3 / 4, np.pi]:
            h = hand_px(30.0, palm_len=140.0, angle_rad=angle)
            pinch.reset()
            res = pinch.update(h, 0.00)
            self.assertTrue(
                res.shot,
                f"Pinch failed to trigger at rotation angle {np.degrees(angle):.0f} degrees",
            )

    def test_hand_distance_scale_invariance(self) -> None:
        pinch = PinchDetector()
        # Close to camera (palm len 240px, tip dist 48px -> ratio 0.20)
        self.assertTrue(pinch.update(hand_px(48.0, palm_len=240.0), 0.00).shot)
        pinch.reset()
        # Far from camera (palm len 70px, tip dist 14px -> ratio 0.20)
        self.assertTrue(pinch.update(hand_px(14.0, palm_len=70.0), 0.00).shot)

    def test_hysteresis_boundary_stability(self) -> None:
        pinch = PinchDetector()
        # Trigger pinch with close distance (<0.45)
        self.assertTrue(pinch.update(hand_norm(0.30), 0.00).shot)
        self.assertEqual(pinch.phase, PinchPhase.PINCHED)

        # Move to hover zone (0.52): above close (0.45) but below release (0.62)
        res_hover = pinch.update(hand_norm(0.52), 0.05)
        self.assertFalse(res_hover.shot)
        # Must remain in PINCHED phase due to hysteresis
        self.assertEqual(res_hover.phase, PinchPhase.PINCHED)
        self.assertTrue(res_hover.is_pinched)

        # Further hover jitter (0.48 -> 0.55 -> 0.50) never oscillates or re-arms
        self.assertEqual(pinch.update(hand_norm(0.48), 0.08).phase, PinchPhase.PINCHED)
        self.assertEqual(pinch.update(hand_norm(0.55), 0.11).phase, PinchPhase.PINCHED)
        self.assertEqual(pinch.update(hand_norm(0.50), 0.14).phase, PinchPhase.PINCHED)

        # Cross release threshold (0.75 / 1.15 = 0.652 >= 0.62) -> re-arms to READY
        res_rel = pinch.update(hand_norm(0.75), 0.17)
        self.assertEqual(res_rel.phase, PinchPhase.READY)
        self.assertFalse(res_rel.is_pinched)

    def test_debounce_frames_rejects_single_frame_spike(self) -> None:
        pinch = PinchDetector(PinchSettings(debounce_frames=2))
        # Frame 1: spike to 0.30 -> not confirmed yet
        res1 = pinch.update(hand_norm(0.30), 0.00)
        self.assertFalse(res1.shot)
        self.assertEqual(res1.phase, PinchPhase.READY)

        # Frame 2: confirmed at 0.30 -> fires shot
        res2 = pinch.update(hand_norm(0.30), 0.03)
        self.assertTrue(res2.shot)
        self.assertEqual(res2.phase, PinchPhase.PINCHED)


if __name__ == "__main__":
    unittest.main()


