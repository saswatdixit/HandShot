"""Development preview drawing for HANDSHOT (Phase 1+2).

Draws the webcam frame overlay used during development: the hand skeleton, the
index fingertip marker, and a small status panel. This is an OpenCV-only debug
view - the real game HUD will be built in Pygame in a later phase.
"""

from __future__ import annotations

import cv2
import numpy as np
from mediapipe.tasks.python import vision

from camera.hand_tracker import Hand
from config import settings

# Colours are BGR because OpenCV.
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREY = (150, 150, 150)
GREEN = (90, 220, 120)
RED = (70, 70, 255)
YELLOW = (0, 230, 255)
ORANGE = (60, 170, 255)
CYAN = (230, 220, 80)
MAGENTA = (200, 80, 220)
BLUE = (255, 170, 70)

_CONNECTIONS = vision.HandLandmarksConnections
_FINGER_GROUPS = (
    (_CONNECTIONS.HAND_PALM_CONNECTIONS, GREY),
    (_CONNECTIONS.HAND_THUMB_CONNECTIONS, ORANGE),
    (_CONNECTIONS.HAND_INDEX_FINGER_CONNECTIONS, YELLOW),
    (_CONNECTIONS.HAND_MIDDLE_FINGER_CONNECTIONS, GREEN),
    (_CONNECTIONS.HAND_RING_FINGER_CONNECTIONS, CYAN),
    (_CONNECTIONS.HAND_PINKY_FINGER_CONNECTIONS, MAGENTA),
)

_FONT = cv2.FONT_HERSHEY_SIMPLEX

# Halo offsets for readable text. Drawing the dark halo at a *different*
# thickness than the glyph (the usual putText trick) does not work here:
# OpenCV's Hershey glyph advances depend on thickness, so the two passes drift
# apart by several pixels across a long string and the tail of each line reads
# as doubled characters. Same thickness + small offsets keeps them aligned.
_HALO_OFFSETS = ((-1, -1), (1, -1), (-1, 1), (1, 1))


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _dim(color: tuple[int, int, int], factor: float = 0.45) -> tuple[int, int, int]:
    return tuple(int(channel * factor) for channel in color)  # type: ignore[return-value]


def _clamp_point(point: np.ndarray | tuple[int, int], width: int, height: int) -> tuple[int, int]:
    x, y = int(point[0]), int(point[1])
    return max(0, min(width - 1, x)), max(0, min(height - 1, y))


def _panel(frame: np.ndarray, x: int, y: int, width: int, height: int, alpha: float = 0.55) -> None:
    """Darken a rectangle so text stays readable over any background."""
    frame_height, frame_width = frame.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(frame_width, x + width), min(frame_height, y + height)
    if x1 <= x0 or y1 <= y0:
        return
    region = frame[y0:y1, x0:x1]
    overlay = np.zeros_like(region)
    cv2.addWeighted(overlay, alpha, region, 1.0 - alpha, 0, region)


def _text(
    frame: np.ndarray,
    label: str,
    origin: tuple[int, int],
    color: tuple[int, int, int] = WHITE,
    scale: float = 0.5,
    thickness: int = 1,
) -> None:
    """Draw text with a dark halo so it stays readable over any background."""
    x, y = origin
    for offset_x, offset_y in _HALO_OFFSETS:
        cv2.putText(frame, label, (x + offset_x, y + offset_y), _FONT, scale,
                    BLACK, thickness, cv2.LINE_AA)
    cv2.putText(frame, label, origin, _FONT, scale, color, thickness, cv2.LINE_AA)


def _text_size(label: str, scale: float, thickness: int = 1) -> tuple[int, int]:
    """Rendered (width, height) including the halo offsets."""
    width, height = cv2.getTextSize(label, _FONT, scale, thickness)[0]
    return width + 2, height + 2


# --------------------------------------------------------------------------
# Hand overlay
# --------------------------------------------------------------------------


def draw_hand(frame: np.ndarray, hand: Hand, coasting: bool = False) -> None:
    """Draw the 21-landmark skeleton. Dimmed while coasting on a lost hand."""
    height, width = frame.shape[:2]
    points = [_clamp_point(p, width, height) for p in hand.landmarks_px]

    for connections, color in _FINGER_GROUPS:
        line_color = _dim(color) if coasting else color
        for connection in connections:
            cv2.line(
                frame,
                points[connection.start],
                points[connection.end],
                line_color,
                2,
                cv2.LINE_AA,
            )

    joint_color = _dim(WHITE) if coasting else WHITE
    for position, point in enumerate(points):
        if position == settings.INDEX_TIP:
            continue  # drawn separately, larger
        radius = 4 if position in (settings.WRIST, settings.THUMB_TIP) else 3
        cv2.circle(frame, point, radius, joint_color, -1, cv2.LINE_AA)

    x_min, y_min, x_max, y_max = hand.bbox_px
    cv2.rectangle(
        frame,
        _clamp_point((x_min - 8, y_min - 8), width, height),
        _clamp_point((x_max + 8, y_max + 8), width, height),
        _dim(GREY, 0.7),
        1,
        cv2.LINE_AA,
    )


def draw_index_fingertip(frame: np.ndarray, hand: Hand, coasting: bool = False) -> None:
    """Emphasise the index fingertip - the future crosshair anchor."""
    height, width = frame.shape[:2]
    center = _clamp_point(hand.index_tip_px, width, height)
    color = _dim(RED) if coasting else RED

    cv2.circle(frame, center, 10, color, -1, cv2.LINE_AA)
    cv2.circle(frame, center, 16, WHITE if not coasting else GREY, 2, cv2.LINE_AA)
    cv2.drawMarker(frame, center, WHITE if not coasting else GREY,
                   cv2.MARKER_CROSS, 34, 1, cv2.LINE_AA)

    raw_x, raw_y = hand.index_tip_px
    norm = hand.index_tip_norm
    primary = f"INDEX TIP  px ({raw_x}, {raw_y})"
    secondary = f"norm ({norm[0]:+.3f}, {norm[1]:+.3f})  z {norm[2]:+.3f}"

    primary_w, _ = _text_size(primary, 0.5)
    secondary_w, _ = _text_size(secondary, 0.45)
    block_w = max(primary_w, secondary_w)

    # Keep the label inside the frame, and push it below the marker when the
    # fingertip is high up so it does not collide with the status panel.
    label_x = min(max(8, center[0] + 24), max(8, width - block_w - 16))
    if center[1] < 130:
        first_y, second_y = center[1] + 36, center[1] + 56
    else:
        first_y, second_y = center[1] - 8, center[1] + 12

    # The label lands on top of the hand and the skeleton lines, so give it a
    # dark backing - the fingertip readout is the point of this view.
    _panel(frame, label_x - 8, first_y - 16, block_w + 16, (second_y - first_y) + 26,
           alpha=0.5)
    _text(frame, primary, (label_x, first_y), YELLOW, 0.5)
    _text(frame, secondary, (label_x, second_y), YELLOW, 0.45)


# --------------------------------------------------------------------------
# Status panels
# --------------------------------------------------------------------------


def draw_status(frame: np.ndarray, lines: list[tuple[str, tuple[int, int, int]]]) -> None:
    """Top-left status block: one (text, colour) pair per line."""
    if not lines:
        return
    line_height = 22
    # Size the panel to the widest line so nothing spills onto the raw frame.
    width = max(_text_size(text, 0.5)[0] for text, _ in lines) + 24
    _panel(frame, 8, 8, width, 14 + line_height * len(lines))
    for position, (text, color) in enumerate(lines):
        _text(frame, text, (20, 32 + position * line_height), color, 0.5)


def draw_help(frame: np.ndarray, entries: list[str]) -> None:
    """Bottom-left key hints."""
    if not entries:
        return
    height = frame.shape[0]
    line_height = 20
    top = height - 12 - line_height * len(entries)
    width = max(_text_size(entry, 0.45)[0] for entry in entries) + 24
    _panel(frame, 8, top - 8, width, line_height * len(entries) + 14)
    for position, entry in enumerate(entries):
        _text(frame, entry, (20, top + 6 + position * line_height), GREY, 0.45)


def draw_center_message(frame: np.ndarray, title: str, subtitle: str = "") -> None:
    """Centered notice, e.g. 'Hand not detected' (main.md section 45)."""
    height, width = frame.shape[:2]
    title_size = _text_size(title, 0.8, 2)
    sub_size = _text_size(subtitle, 0.5) if subtitle else (0, 0)

    box_width = max(480, title_size[0] + 60, sub_size[0] + 60)
    box_height = 100 if subtitle else 64
    x = (width - box_width) // 2
    y = (height - box_height) // 2
    _panel(frame, x, y, box_width, box_height, alpha=0.6)

    _text(frame, title, ((width - title_size[0]) // 2, y + 40), YELLOW, 0.8, 2)
    if subtitle:
        _text(frame, subtitle, ((width - sub_size[0]) // 2, y + 74), WHITE, 0.5)
