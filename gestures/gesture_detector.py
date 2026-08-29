"""Comprehensive Multi-Hand-Gesture Detection and State Machine for HANDSHOT."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

from config import settings
from gestures.pinch_detector import PinchDetector, PinchPhase, PinchResult, PinchSettings

if TYPE_CHECKING:
    from camera.hand_tracker import Hand


class HandGesture(Enum):
    """Explicit recognized hand gestures in HANDSHOT."""

    NO_HAND = "no_hand"
    POINTING = "pointing"        # ☝️ Default aiming / open hand
    PINCH = "pinch"              # 🤏 Firing
    CLOSED_PALM = "closed_palm"  # ✋ Fist / closed hand -> Pause / Resume toggle
    TWO_FINGERS = "two_fingers"  # ✌️ Peace sign -> Weapon switch placeholder
    THUMBS_UP = "thumbs_up"      # 👍 Thumbs up -> Reload placeholder
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class GestureSettings:
    """Tuning parameters for multi-gesture recognition, debouncing, and hysteresis."""

    confirm_frames: int = settings.GESTURE_CONFIRM_FRAMES
    release_frames: int = settings.GESTURE_RELEASE_FRAMES
    palm_close_threshold: float = settings.PALM_CLOSE_THRESHOLD
    palm_open_threshold: float = settings.PALM_OPEN_THRESHOLD
    cooldown_seconds: float = settings.GESTURE_COOLDOWN_SECONDS
    pinch_settings: PinchSettings | None = None

    def __post_init__(self) -> None:
        if self.palm_close_threshold <= 0 or self.palm_open_threshold <= self.palm_close_threshold:
            raise ValueError("palm_open_threshold must be greater than palm_close_threshold")
        if self.confirm_frames < 1:
            raise ValueError("confirm_frames must be at least 1")
        if self.cooldown_seconds < 0:
            raise ValueError("cooldown_seconds cannot be negative")


@dataclass(frozen=True)
class GestureResult:
    """Snapshot of gesture recognition state after one tracking update."""

    gesture: HandGesture
    candidate_gesture: HandGesture
    confirm_count: int
    confidence: float
    pinch_result: PinchResult
    shot: bool
    pause_toggle: bool
    weapon_switch: bool
    reload: bool
    palm_metric: float | None
    finger_curls: dict[str, float] | None


class GestureDetector:
    """Detects and debounces hand gestures while managing event triggers.

    Priorities & Conflict Resolution:
    1. Full fist / all 4 fingers curled -> CLOSED_PALM (or THUMBS_UP if thumb extended up)
    2. Pinch (thumb & index touching while other fingers are open/relaxed) -> PINCH (fires shot)
    3. Peace / V-sign (index + middle extended, ring + pinky curled) -> TWO_FINGERS
    4. Default open/pointing -> POINTING
    """

    def __init__(self, settings_: GestureSettings | None = None) -> None:
        self.settings = settings_ or GestureSettings()
        self.pinch_detector = PinchDetector(self.settings.pinch_settings)
        self.reset()

    def reset(self) -> None:
        """Reset all gesture buffers, candidate counters, and trigger states."""
        self.pinch_detector.reset()
        self._current_gesture = HandGesture.NO_HAND
        self._candidate_gesture = HandGesture.NO_HAND
        self._confirm_count = 0
        self._last_pause_toggle_time = -math.inf
        self._last_weapon_switch_time = -math.inf
        self._last_reload_time = -math.inf
        self._palm_held = False
        self._two_fingers_held = False
        self._thumbs_up_held = False

    @property
    def current_gesture(self) -> HandGesture:
        return self._current_gesture

    @property
    def is_palm_closed(self) -> bool:
        return self._current_gesture is HandGesture.CLOSED_PALM

    def update(self, hand: Hand | None, now: float) -> GestureResult:
        """Evaluate one tracking frame at monotonic timestamp ``now``."""
        if hand is None:
            self.reset()
            empty_pinch = PinchResult(PinchPhase.READY, False, False, None, None)
            return GestureResult(
                gesture=HandGesture.NO_HAND,
                candidate_gesture=HandGesture.NO_HAND,
                confirm_count=0,
                confidence=0.0,
                pinch_result=empty_pinch,
                shot=False,
                pause_toggle=False,
                weapon_switch=False,
                reload=False,
                palm_metric=None,
                finger_curls=None,
            )

        # 1. Evaluate Pinch Subsystem
        pinch_res = self.pinch_detector.update(hand, now)
        shot = pinch_res.shot

        # 2. Extract Geometric Metrics & Finger Extension States
        metrics = self._calculate_metrics(hand)
        palm_metric = metrics["palm_metric"]
        finger_curls = {
            "index": metrics["d_index"],
            "middle": metrics["d_middle"],
            "ring": metrics["d_ring"],
            "pinky": metrics["d_pinky"],
            "thumb": metrics["d_thumb"],
        }

        # 3. Classify Raw Candidate Gesture with strict conflict resolution
        raw_candidate = self._classify_raw_gesture(pinch_res, metrics)

        # 4. Debounce Candidate Gesture
        if raw_candidate == self._candidate_gesture:
            self._confirm_count += 1
        else:
            self._candidate_gesture = raw_candidate
            self._confirm_count = 1

        # Pointing and Pinch transition immediately (0-lag cursor/shot response)
        # Action gestures (CLOSED_PALM, TWO_FINGERS, THUMBS_UP) require confirm_frames
        is_confirmed = False
        if self._candidate_gesture in (HandGesture.PINCH, HandGesture.POINTING):
            is_confirmed = True
        elif self._confirm_count >= self.settings.confirm_frames:
            is_confirmed = True

        if is_confirmed:
            self._current_gesture = self._candidate_gesture

        # 5. Hysteresis & Re-arm Logic for Action Gestures
        if palm_metric >= self.settings.palm_open_threshold or self._current_gesture is HandGesture.POINTING:
            self._palm_held = False

        if self._current_gesture not in (HandGesture.TWO_FINGERS, HandGesture.PINCH):
            self._two_fingers_held = False

        if self._current_gesture not in (HandGesture.THUMBS_UP, HandGesture.PINCH):
            self._thumbs_up_held = False

        # 6. Generate Discrete Single-Fire Action Events
        pause_toggle = False
        weapon_switch = False
        reload = False

        # Closed palm pause trigger (only when confirmed CLOSED_PALM and not held)
        if self._current_gesture is HandGesture.CLOSED_PALM and not self._palm_held:
            if now - self._last_pause_toggle_time >= self.settings.cooldown_seconds:
                pause_toggle = True
                self._last_pause_toggle_time = now
                self._palm_held = True

        # Two fingers weapon switch trigger
        if self._current_gesture is HandGesture.TWO_FINGERS and not self._two_fingers_held:
            if now - self._last_weapon_switch_time >= self.settings.cooldown_seconds:
                weapon_switch = True
                self._last_weapon_switch_time = now
                self._two_fingers_held = True

        # Thumbs up reload trigger
        if self._current_gesture is HandGesture.THUMBS_UP and not self._thumbs_up_held:
            if now - self._last_reload_time >= self.settings.cooldown_seconds:
                reload = True
                self._last_reload_time = now
                self._thumbs_up_held = True

        hand_score = getattr(hand, "score", 0.90)

        return GestureResult(
            gesture=self._current_gesture,
            candidate_gesture=self._candidate_gesture,
            confirm_count=self._confirm_count,
            confidence=float(hand_score),
            pinch_result=pinch_res,
            shot=shot,
            pause_toggle=pause_toggle,
            weapon_switch=weapon_switch,
            reload=reload,
            palm_metric=palm_metric,
            finger_curls=finger_curls,
        )

    def _classify_raw_gesture(self, pinch_res: PinchResult, m: dict[str, Any]) -> HandGesture:
        """Classify gesture based on geometry and priority."""
        # 1. Check Full Fist / Closed Palm (all 4 long fingers curled into palm)
        all_four_curled = (
            m["index_curled"]
            and m["middle_curled"]
            and m["ring_curled"]
            and m["pinky_curled"]
        )

        if all_four_curled and m["palm_metric"] <= self.settings.palm_close_threshold:
            # If thumb is extended up while 4 fingers are curled -> Thumbs Up
            if m["thumb_up"]:
                return HandGesture.THUMBS_UP
            return HandGesture.CLOSED_PALM

        # 2. Check Thumbs Up
        if m["thumb_up"] and m["middle_curled"] and m["ring_curled"] and m["pinky_curled"]:
            return HandGesture.THUMBS_UP

        # 3. Check Pinch (thumb and index touching, but other fingers relaxed/open)
        if pinch_res.is_pinched:
            return HandGesture.PINCH

        # 4. Check Two Fingers (Peace / V-sign: index + middle extended, ring + pinky curled)
        if (
            m["index_extended"]
            and m["middle_extended"]
            and m["ring_curled"]
            and m["pinky_curled"]
            and m["v_spread"] >= 0.12
        ):
            return HandGesture.TWO_FINGERS

        # 5. Default Pointing / Aiming
        if m["index_extended"]:
            return HandGesture.POINTING

        if m["palm_metric"] <= self.settings.palm_close_threshold:
            return HandGesture.CLOSED_PALM

        return HandGesture.POINTING

    @staticmethod
    def _calculate_metrics(hand: Hand) -> dict[str, Any]:
        """Compute scale-normalized finger extensions and spatial relationships."""
        if hasattr(hand, "landmarks_px") and hand.landmarks_px is not None and len(hand.landmarks_px) == 21:
            pts = hand.landmarks_px
        else:
            pts = hand.landmarks_norm

        def pt(idx: int) -> tuple[float, float]:
            return float(pts[idx][0]), float(pts[idx][1])

        wrist = pt(settings.WRIST)
        middle_mcp = pt(settings.MIDDLE_MCP)
        index_mcp = pt(settings.INDEX_MCP)
        pinky_mcp = pt(settings.PINKY_MCP)

        palm_len = math.dist(wrist, middle_mcp)
        palm_wid = math.dist(index_mcp, pinky_mcp)
        scale = max(palm_len, palm_wid * 1.15, 1e-4)

        # Measure 4 long fingers (Index, Middle, Ring, Pinky)
        def finger_metrics(mcp_idx: int, pip_idx: int, tip_idx: int) -> tuple[float, bool, bool]:
            mcp_p = pt(mcp_idx)
            pip_p = pt(pip_idx)
            tip_p = pt(tip_idx)

            d_mcp = math.dist(tip_p, mcp_p) / scale
            d_wrist = math.dist(tip_p, wrist) / scale
            pip_wrist = math.dist(pip_p, wrist) / scale

            extended = (d_mcp >= 0.70) and (d_wrist >= pip_wrist * 0.90)
            curled = (d_mcp <= 0.60) and (d_wrist <= pip_wrist * 1.15)
            return d_mcp, extended, curled

        d_idx, idx_ext, idx_curl = finger_metrics(settings.INDEX_MCP, settings.INDEX_PIP, settings.INDEX_TIP)
        d_mid, mid_ext, mid_curl = finger_metrics(settings.MIDDLE_MCP, settings.MIDDLE_PIP, settings.MIDDLE_TIP)
        d_rng, rng_ext, rng_curl = finger_metrics(settings.RING_MCP, settings.RING_PIP, settings.RING_TIP)
        d_pnk, pnk_ext, pnk_curl = finger_metrics(settings.PINKY_MCP, settings.PINKY_PIP, settings.PINKY_TIP)

        # Measure Thumb
        thumb_tip = pt(settings.THUMB_TIP)
        thumb_mcp = pt(settings.THUMB_MCP)
        d_thb = math.dist(thumb_tip, thumb_mcp) / scale
        d_thb_wrist = math.dist(thumb_tip, wrist) / scale

        # Thumbs up criteria: thumb tip extended away from wrist, pointing in forearm direction
        is_thumb_extended = (d_thb_wrist >= 0.80) and (d_thb >= 0.45)
        hand_up_y = middle_mcp[1] - wrist[1]
        thumb_dir_y = thumb_tip[1] - thumb_mcp[1]
        thumb_up = is_thumb_extended and (thumb_dir_y * hand_up_y > 0)

        palm_metric = (d_idx + d_mid + d_rng + d_pnk) / 4.0
        v_spread = math.dist(pt(settings.INDEX_TIP), pt(settings.MIDDLE_TIP)) / scale

        return {
            "scale": scale,
            "palm_metric": palm_metric,
            "d_index": d_idx,
            "d_middle": d_mid,
            "d_ring": d_rng,
            "d_pinky": d_pnk,
            "d_thumb": d_thb,
            "index_extended": idx_ext,
            "index_curled": idx_curl,
            "middle_extended": mid_ext,
            "middle_curled": mid_curl,
            "ring_extended": rng_ext,
            "ring_curled": rng_curl,
            "pinky_extended": pnk_ext,
            "pinky_curled": pnk_curl,
            "thumb_extended": is_thumb_extended,
            "thumb_up": thumb_up,
            "v_spread": v_spread,
        }
