"""Comprehensive unit tests for the multi-hand-gesture detection system."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

import numpy as np

from config import settings
from gestures.gesture_detector import GestureDetector, GestureSettings, HandGesture


def build_hand(
    pose: str = "open",
    scale_px: float = 140.0,
    handedness: str = "Right",
    score: float = 0.95,
) -> SimpleNamespace:
    """Construct mock 21-landmark hand in pixel and normalized space for various gestures."""
    raw_px = np.zeros((21, 2), dtype=np.float32)
    wrist = np.array([640.0, 480.0])
    raw_px[settings.WRIST] = wrist

    # Middle MCP defines primary palm direction (upwards in camera image)
    middle_mcp = wrist + np.array([0.0, -scale_px])
    raw_px[settings.MIDDLE_MCP] = middle_mcp

    index_mcp = wrist + np.array([-scale_px * 0.35, -scale_px * 0.90])
    raw_px[settings.INDEX_MCP] = index_mcp

    ring_mcp = wrist + np.array([scale_px * 0.25, -scale_px * 0.85])
    raw_px[settings.RING_MCP] = ring_mcp

    pinky_mcp = wrist + np.array([scale_px * 0.50, -scale_px * 0.75])
    raw_px[settings.PINKY_MCP] = pinky_mcp

    thumb_cmc = wrist + np.array([-scale_px * 0.30, -scale_px * 0.20])
    thumb_mcp = wrist + np.array([-scale_px * 0.45, -scale_px * 0.45])
    raw_px[settings.THUMB_CMC] = thumb_cmc
    raw_px[settings.THUMB_MCP] = thumb_mcp

    if pose == "open" or pose == "pointing":
        # All fingers extended upward
        raw_px[settings.INDEX_PIP] = index_mcp + np.array([0.0, -scale_px * 0.35])
        raw_px[settings.INDEX_DIP] = index_mcp + np.array([0.0, -scale_px * 0.65])
        raw_px[settings.INDEX_TIP] = index_mcp + np.array([0.0, -scale_px * 0.95])

        raw_px[settings.MIDDLE_PIP] = middle_mcp + np.array([0.0, -scale_px * 0.40])
        raw_px[settings.MIDDLE_DIP] = middle_mcp + np.array([0.0, -scale_px * 0.70])
        raw_px[settings.MIDDLE_TIP] = middle_mcp + np.array([0.0, -scale_px * 1.05])

        raw_px[settings.RING_PIP] = ring_mcp + np.array([0.0, -scale_px * 0.35])
        raw_px[settings.RING_DIP] = ring_mcp + np.array([0.0, -scale_px * 0.65])
        raw_px[settings.RING_TIP] = ring_mcp + np.array([0.0, -scale_px * 0.95])

        raw_px[settings.PINKY_PIP] = pinky_mcp + np.array([0.0, -scale_px * 0.30])
        raw_px[settings.PINKY_DIP] = pinky_mcp + np.array([0.0, -scale_px * 0.55])
        raw_px[settings.PINKY_TIP] = pinky_mcp + np.array([0.0, -scale_px * 0.80])

        raw_px[settings.THUMB_IP] = thumb_mcp + np.array([-scale_px * 0.20, -scale_px * 0.20])
        raw_px[settings.THUMB_TIP] = thumb_mcp + np.array([-scale_px * 0.35, -scale_px * 0.35])

    elif pose == "closed_palm":
        # All long fingers curled tightly into palm
        for mcp_idx, pip_idx, dip_idx, tip_idx in [
            (settings.INDEX_MCP, settings.INDEX_PIP, settings.INDEX_DIP, settings.INDEX_TIP),
            (settings.MIDDLE_MCP, settings.MIDDLE_PIP, settings.MIDDLE_DIP, settings.MIDDLE_TIP),
            (settings.RING_MCP, settings.RING_PIP, settings.RING_DIP, settings.RING_TIP),
            (settings.PINKY_MCP, settings.PINKY_PIP, settings.PINKY_DIP, settings.PINKY_TIP),
        ]:
            mcp = raw_px[mcp_idx]
            raw_px[pip_idx] = mcp + np.array([0.0, -scale_px * 0.20])
            raw_px[dip_idx] = mcp + np.array([0.0, -scale_px * 0.10])
            raw_px[tip_idx] = mcp + np.array([0.0, scale_px * 0.15])  # curled down into palm

        # Thumb folded across fingers
        raw_px[settings.THUMB_IP] = thumb_mcp + np.array([scale_px * 0.10, -scale_px * 0.10])
        raw_px[settings.THUMB_TIP] = thumb_mcp + np.array([scale_px * 0.25, 0.0])

    elif pose == "pinch":
        # Thumb and Index tip close together
        raw_px[settings.INDEX_PIP] = index_mcp + np.array([-scale_px * 0.10, -scale_px * 0.25])
        raw_px[settings.INDEX_DIP] = index_mcp + np.array([-scale_px * 0.15, -scale_px * 0.35])
        raw_px[settings.INDEX_TIP] = index_mcp + np.array([-scale_px * 0.15, -scale_px * 0.40])

        raw_px[settings.THUMB_IP] = thumb_mcp + np.array([0.0, -scale_px * 0.20])
        raw_px[settings.THUMB_TIP] = raw_px[settings.INDEX_TIP] + np.array([5.0, 0.0])

        # Middle, Ring, Pinky extended
        raw_px[settings.MIDDLE_PIP] = middle_mcp + np.array([0.0, -scale_px * 0.40])
        raw_px[settings.MIDDLE_DIP] = middle_mcp + np.array([0.0, -scale_px * 0.70])
        raw_px[settings.MIDDLE_TIP] = middle_mcp + np.array([0.0, -scale_px * 1.05])

        raw_px[settings.RING_PIP] = ring_mcp + np.array([0.0, -scale_px * 0.35])
        raw_px[settings.RING_DIP] = ring_mcp + np.array([0.0, -scale_px * 0.65])
        raw_px[settings.RING_TIP] = ring_mcp + np.array([0.0, -scale_px * 0.95])

        raw_px[settings.PINKY_PIP] = pinky_mcp + np.array([0.0, -scale_px * 0.30])
        raw_px[settings.PINKY_DIP] = pinky_mcp + np.array([0.0, -scale_px * 0.55])
        raw_px[settings.PINKY_TIP] = pinky_mcp + np.array([0.0, -scale_px * 0.80])

    elif pose == "two_fingers":
        # Index and Middle extended with spread, Ring and Pinky curled
        raw_px[settings.INDEX_PIP] = index_mcp + np.array([-scale_px * 0.15, -scale_px * 0.35])
        raw_px[settings.INDEX_DIP] = index_mcp + np.array([-scale_px * 0.25, -scale_px * 0.65])
        raw_px[settings.INDEX_TIP] = index_mcp + np.array([-scale_px * 0.35, -scale_px * 0.95])

        raw_px[settings.MIDDLE_PIP] = middle_mcp + np.array([scale_px * 0.15, -scale_px * 0.40])
        raw_px[settings.MIDDLE_DIP] = middle_mcp + np.array([scale_px * 0.25, -scale_px * 0.70])
        raw_px[settings.MIDDLE_TIP] = middle_mcp + np.array([scale_px * 0.35, -scale_px * 1.05])

        # Ring & Pinky curled
        for mcp_idx, pip_idx, dip_idx, tip_idx in [
            (settings.RING_MCP, settings.RING_PIP, settings.RING_DIP, settings.RING_TIP),
            (settings.PINKY_MCP, settings.PINKY_PIP, settings.PINKY_DIP, settings.PINKY_TIP),
        ]:
            mcp = raw_px[mcp_idx]
            raw_px[pip_idx] = mcp + np.array([0.0, -scale_px * 0.20])
            raw_px[dip_idx] = mcp + np.array([0.0, -scale_px * 0.10])
            raw_px[tip_idx] = mcp + np.array([0.0, scale_px * 0.15])

        # Thumb folded
        raw_px[settings.THUMB_IP] = thumb_mcp + np.array([scale_px * 0.10, -scale_px * 0.10])
        raw_px[settings.THUMB_TIP] = thumb_mcp + np.array([scale_px * 0.25, 0.0])

    elif pose == "thumbs_up":
        # Thumb extended upwards
        raw_px[settings.THUMB_IP] = thumb_mcp + np.array([-scale_px * 0.15, -scale_px * 0.35])
        raw_px[settings.THUMB_TIP] = thumb_mcp + np.array([-scale_px * 0.20, -scale_px * 0.70])

        # Index, Middle, Ring, Pinky curled
        for mcp_idx, pip_idx, dip_idx, tip_idx in [
            (settings.INDEX_MCP, settings.INDEX_PIP, settings.INDEX_DIP, settings.INDEX_TIP),
            (settings.MIDDLE_MCP, settings.MIDDLE_PIP, settings.MIDDLE_DIP, settings.MIDDLE_TIP),
            (settings.RING_MCP, settings.RING_PIP, settings.RING_DIP, settings.RING_TIP),
            (settings.PINKY_MCP, settings.PINKY_PIP, settings.PINKY_DIP, settings.PINKY_TIP),
        ]:
            mcp = raw_px[mcp_idx]
            raw_px[pip_idx] = mcp + np.array([0.0, -scale_px * 0.20])
            raw_px[dip_idx] = mcp + np.array([0.0, -scale_px * 0.10])
            raw_px[tip_idx] = mcp + np.array([0.0, scale_px * 0.15])

    return SimpleNamespace(
        landmarks_px=raw_px,
        landmarks_norm=raw_px / 1280.0,
        handedness=handedness,
        score=score,
    )


class GestureDetectorTests(unittest.TestCase):
    def test_open_hand_is_pointing(self) -> None:
        detector = GestureDetector()
        hand = build_hand("open")
        res = detector.update(hand, 0.00)
        self.assertEqual(res.gesture, HandGesture.POINTING)
        self.assertFalse(res.pause_toggle)
        self.assertFalse(res.shot)

    def test_closed_palm_detection_and_pause_toggle(self) -> None:
        detector = GestureDetector(GestureSettings(confirm_frames=2))
        open_h = build_hand("open")
        closed_h = build_hand("closed_palm")

        # Frame 1: Open
        detector.update(open_h, 0.00)
        self.assertEqual(detector.current_gesture, HandGesture.POINTING)

        # Frame 2: Closed candidate frame 1 (confirm 1/2) -> still POINTING
        res2 = detector.update(closed_h, 0.03)
        self.assertEqual(res2.candidate_gesture, HandGesture.CLOSED_PALM)
        self.assertEqual(res2.confirm_count, 1)
        self.assertFalse(res2.pause_toggle)

        # Frame 3: Closed confirmed (confirm 2/2) -> CLOSED_PALM and emits pause_toggle=True
        res3 = detector.update(closed_h, 0.06)
        self.assertEqual(res3.gesture, HandGesture.CLOSED_PALM)
        self.assertTrue(res3.pause_toggle)

        # Frame 4: Held closed palm -> remains CLOSED_PALM but does NOT re-emit pause_toggle
        res4 = detector.update(closed_h, 0.09)
        self.assertEqual(res4.gesture, HandGesture.CLOSED_PALM)
        self.assertFalse(res4.pause_toggle)

    def test_closed_palm_release_and_rearm(self) -> None:
        detector = GestureDetector(GestureSettings(confirm_frames=2, cooldown_seconds=0.10))
        open_h = build_hand("open")
        closed_h = build_hand("closed_palm")

        # Trigger first pause
        detector.update(closed_h, 0.00)
        res_pause1 = detector.update(closed_h, 0.03)
        self.assertTrue(res_pause1.pause_toggle)

        # Release hand to open
        detector.update(open_h, 0.06)
        detector.update(open_h, 0.09)
        self.assertEqual(detector.current_gesture, HandGesture.POINTING)

        # Close palm again after cooldown -> emits pause_toggle=True again
        detector.update(closed_h, 0.20)
        res_pause2 = detector.update(closed_h, 0.23)
        self.assertTrue(res_pause2.pause_toggle)

    def test_left_and_right_hands_both_work(self) -> None:
        detector = GestureDetector(GestureSettings(confirm_frames=1))
        h_left = build_hand("closed_palm", handedness="Left")
        h_right = build_hand("closed_palm", handedness="Right")

        res_left = detector.update(h_left, 0.00)
        self.assertEqual(res_left.gesture, HandGesture.CLOSED_PALM)

        detector.reset()
        res_right = detector.update(h_right, 0.00)
        self.assertEqual(res_right.gesture, HandGesture.CLOSED_PALM)

    def test_different_hand_scales_work(self) -> None:
        detector = GestureDetector(GestureSettings(confirm_frames=1))
        # Small hand far away (scale 60px)
        h_far = build_hand("closed_palm", scale_px=60.0)
        self.assertEqual(detector.update(h_far, 0.00).gesture, HandGesture.CLOSED_PALM)

        detector.reset()
        # Large hand close to camera (scale 260px)
        h_close = build_hand("closed_palm", scale_px=260.0)
        self.assertEqual(detector.update(h_close, 0.00).gesture, HandGesture.CLOSED_PALM)

    def test_pinch_priority_and_shooting(self) -> None:
        detector = GestureDetector()
        h_pinch = build_hand("pinch")
        # Pinch fires shot immediately and has PINCH gesture
        res = detector.update(h_pinch, 0.00)
        self.assertEqual(res.gesture, HandGesture.PINCH)
        self.assertTrue(res.shot)
        self.assertFalse(res.pause_toggle)

    def test_two_fingers_gesture_recognized(self) -> None:
        detector = GestureDetector(GestureSettings(confirm_frames=2))
        h_two = build_hand("two_fingers")
        detector.update(h_two, 0.00)
        res = detector.update(h_two, 0.03)
        self.assertEqual(res.gesture, HandGesture.TWO_FINGERS)
        self.assertTrue(res.weapon_switch)

    def test_thumbs_up_gesture_recognized(self) -> None:
        detector = GestureDetector(GestureSettings(confirm_frames=2))
        h_thumb = build_hand("thumbs_up")
        detector.update(h_thumb, 0.00)
        res = detector.update(h_thumb, 0.03)
        self.assertEqual(res.gesture, HandGesture.THUMBS_UP)
        self.assertTrue(res.reload)

    def test_tracking_loss_resets_state_safely(self) -> None:
        detector = GestureDetector(GestureSettings(confirm_frames=2))
        closed_h = build_hand("closed_palm")
        detector.update(closed_h, 0.00)
        detector.update(closed_h, 0.03)
        self.assertEqual(detector.current_gesture, HandGesture.CLOSED_PALM)

        # Tracking lost
        res_loss = detector.update(None, 0.06)
        self.assertEqual(res_loss.gesture, HandGesture.NO_HAND)
        self.assertFalse(res_loss.pause_toggle)
        self.assertFalse(res_loss.shot)

        # Hand returns (frame 1) -> candidate initialized, not confirmed yet
        res_ret1 = detector.update(closed_h, 0.09)
        self.assertEqual(res_ret1.gesture, HandGesture.NO_HAND)
        self.assertFalse(res_ret1.pause_toggle)


if __name__ == "__main__":
    unittest.main()
