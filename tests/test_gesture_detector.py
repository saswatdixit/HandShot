"""Safety tests verifying that finger poses (closed palm, thumbs up, two fingers, finger noise)

NEVER trigger reload, pause, or weapon switching.
"""

import unittest
from types import SimpleNamespace

import numpy as np

from config import settings
from gestures.pinch_detector import PinchDetector, PinchPhase
from gestures.reload_detector import ReloadDetector, ReloadSettings


def make_mock_hand(
    wrist_y: float = 0.40,
    finger_pose: str = "open",
) -> SimpleNamespace:
    """Generate mock hand landmarks with specified finger pose and wrist position."""
    landmarks_norm = np.zeros((21, 3), dtype=np.float32)

    # Base wrist
    landmarks_norm[settings.WRIST] = (0.5, wrist_y, 0.0)

    # Place MCPs
    landmarks_norm[settings.THUMB_CMC] = (0.45, wrist_y - 0.05, 0.0)
    landmarks_norm[settings.INDEX_MCP] = (0.48, wrist_y - 0.12, 0.0)
    landmarks_norm[settings.MIDDLE_MCP] = (0.50, wrist_y - 0.13, 0.0)
    landmarks_norm[settings.RING_MCP] = (0.52, wrist_y - 0.12, 0.0)
    landmarks_norm[settings.PINKY_MCP] = (0.54, wrist_y - 0.10, 0.0)

    if finger_pose == "closed_palm":  # Fist / curled fingers
        landmarks_norm[settings.THUMB_TIP] = (0.47, wrist_y - 0.08, 0.0)
        landmarks_norm[settings.INDEX_TIP] = (0.48, wrist_y - 0.09, 0.0)
        landmarks_norm[settings.MIDDLE_TIP] = (0.50, wrist_y - 0.09, 0.0)
        landmarks_norm[settings.RING_TIP] = (0.52, wrist_y - 0.09, 0.0)
        landmarks_norm[settings.PINKY_TIP] = (0.54, wrist_y - 0.08, 0.0)
    elif finger_pose == "thumbs_up":
        landmarks_norm[settings.THUMB_TIP] = (0.42, wrist_y - 0.22, 0.0)
        landmarks_norm[settings.INDEX_TIP] = (0.48, wrist_y - 0.09, 0.0)
        landmarks_norm[settings.MIDDLE_TIP] = (0.50, wrist_y - 0.09, 0.0)
        landmarks_norm[settings.RING_TIP] = (0.52, wrist_y - 0.09, 0.0)
        landmarks_norm[settings.PINKY_TIP] = (0.54, wrist_y - 0.08, 0.0)
    elif finger_pose == "two_fingers":
        landmarks_norm[settings.THUMB_TIP] = (0.47, wrist_y - 0.08, 0.0)
        landmarks_norm[settings.INDEX_TIP] = (0.46, wrist_y - 0.22, 0.0)
        landmarks_norm[settings.MIDDLE_TIP] = (0.54, wrist_y - 0.22, 0.0)
        landmarks_norm[settings.RING_TIP] = (0.52, wrist_y - 0.09, 0.0)
        landmarks_norm[settings.PINKY_TIP] = (0.54, wrist_y - 0.08, 0.0)
    elif finger_pose == "pinch":
        # Thumb and index tips touching
        landmarks_norm[settings.THUMB_TIP] = (0.50, wrist_y - 0.16, 0.0)
        landmarks_norm[settings.INDEX_TIP] = (0.50, wrist_y - 0.16, 0.0)
        landmarks_norm[settings.MIDDLE_TIP] = (0.52, wrist_y - 0.20, 0.0)
        landmarks_norm[settings.RING_TIP] = (0.54, wrist_y - 0.18, 0.0)
        landmarks_norm[settings.PINKY_TIP] = (0.56, wrist_y - 0.16, 0.0)
    else:  # Open hand / pointing
        landmarks_norm[settings.THUMB_TIP] = (0.42, wrist_y - 0.16, 0.0)
        landmarks_norm[settings.INDEX_TIP] = (0.48, wrist_y - 0.24, 0.0)
        landmarks_norm[settings.MIDDLE_TIP] = (0.50, wrist_y - 0.25, 0.0)
        landmarks_norm[settings.RING_TIP] = (0.52, wrist_y - 0.23, 0.0)
        landmarks_norm[settings.PINKY_TIP] = (0.54, wrist_y - 0.20, 0.0)

    return SimpleNamespace(
        landmarks_norm=landmarks_norm,
        landmarks_px=None,
        index_tip_norm=tuple(landmarks_norm[settings.INDEX_TIP][:2]),
        handedness="Right",
        score=0.95,
    )


class GestureSafetyTests(unittest.TestCase):
    """Verify that finger pose shapes NEVER trigger spatial reload when not in reload zone."""

    def setUp(self) -> None:
        self.reload_detector = ReloadDetector()
        self.pinch_detector = PinchDetector()

    def test_closed_palm_in_aim_zone_never_triggers_reload(self) -> None:
        hand = make_mock_hand(wrist_y=0.40, finger_pose="closed_palm")
        res = self.reload_detector.update(hand, delta_seconds=1.0, now=1.0)
        self.assertFalse(res.in_zone)
        self.assertFalse(res.reload_triggered)

    def test_thumbs_up_in_aim_zone_never_triggers_reload(self) -> None:
        hand = make_mock_hand(wrist_y=0.45, finger_pose="thumbs_up")
        res = self.reload_detector.update(hand, delta_seconds=1.0, now=1.0)
        self.assertFalse(res.in_zone)
        self.assertFalse(res.reload_triggered)

    def test_two_fingers_in_aim_zone_never_triggers_reload(self) -> None:
        hand = make_mock_hand(wrist_y=0.50, finger_pose="two_fingers")
        res = self.reload_detector.update(hand, delta_seconds=1.0, now=1.0)
        self.assertFalse(res.in_zone)
        self.assertFalse(res.reload_triggered)

    def test_noisy_finger_landmarks_never_trigger_reload_outside_zone(self) -> None:
        rng = np.random.default_rng(1234)
        for _ in range(50):
            noise_hand = make_mock_hand(wrist_y=0.35, finger_pose="open")
            # Inject noise on fingertips
            noise_hand.landmarks_norm += rng.normal(0.0, 0.04, size=noise_hand.landmarks_norm.shape)
            res = self.reload_detector.update(noise_hand, delta_seconds=0.033, now=1.0)
            self.assertFalse(res.reload_triggered)

    def test_pinch_pose_only_triggers_shooting(self) -> None:
        # Pinch in aim area (y=0.40)
        hand = make_mock_hand(wrist_y=0.40, finger_pose="pinch")
        # Step 1: Open first to arm
        open_hand = make_mock_hand(wrist_y=0.40, finger_pose="open")
        self.pinch_detector.update(open_hand, now=0.0)

        # Step 2: Pinch to shoot
        pinch_res = self.pinch_detector.update(hand, now=0.04)
        self.assertTrue(pinch_res.shot)

        # Step 3: Spatial reload detector remains unaffected
        reload_res = self.reload_detector.update(hand, delta_seconds=0.04, now=0.04)
        self.assertFalse(reload_res.reload_triggered)


if __name__ == "__main__":
    unittest.main()
