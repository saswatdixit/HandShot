"""HANDSHOT - entry point.

Current milestone: Phase 1 (OpenCV webcam) + Phase 2 (MediaPipe hand tracking)
+ Phase 3 (Pygame crosshair aim screen) + Phase 4 (pinch shooting) + Phase 5
(blue-bubble game).

Usage:
    py main.py                         # Phase 5 Pygame blue-bubble game
    py main.py --preview               # Phase 1+2 OpenCV development preview
    python main.py --list-cameras      # show detected devices
    python main.py --select            # choose a camera interactively
    python main.py --camera 1          # use a specific device index
    python main.py --check             # headless diagnostics, prints a report
    python main.py --snapshot out.png  # save one annotated frame
    python main.py --no-tracking       # Phase 1 only (camera, no MediaPipe)

Keys in the preview window:
    q / Esc  quit            m  toggle mirror        l  toggle landmarks
    h        toggle help     r  reset tracking       s  save snapshot
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2

from camera import preview
from camera.camera_manager import (
    BACKEND_NAMES,
    CameraError,
    CameraManager,
    select_camera_interactively,
)
from camera.hand_tracker import HandTracker, HandTrackerError, TrackingResult
from config import settings

SNAPSHOT_DIR = settings.PROJECT_ROOT / "data" / "snapshots"


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="handshot",
        description="HANDSHOT - Phase 5 hand-controlled blue-bubble game.",
    )
    parser.add_argument("-c", "--camera", type=int, default=settings.DEFAULT_CAMERA_INDEX,
                        help="camera device index (default: %(default)s)")
    parser.add_argument("--list-cameras", action="store_true",
                        help="list detected cameras and exit")
    parser.add_argument("--select", action="store_true",
                        help="pick a camera interactively before starting")
    parser.add_argument("--width", type=int, default=settings.CAMERA_WIDTH,
                        help="requested capture width (default: %(default)s)")
    parser.add_argument("--height", type=int, default=settings.CAMERA_HEIGHT,
                        help="requested capture height (default: %(default)s)")
    parser.add_argument("--no-mirror", action="store_true",
                        help="disable the mirrored camera view")
    parser.add_argument("--backend", default=None, metavar="NAME",
                        help="force an OpenCV backend (%s). Try this if capture "
                             "fps is low on your webcam." % ", ".join(BACKEND_NAMES))
    parser.add_argument("--no-threaded-capture", action="store_true",
                        help="grab frames inline instead of on a background "
                             "thread (slower; for comparison/debugging)")
    parser.add_argument("--no-tracking", action="store_true",
                        help="camera only, skip MediaPipe (tests Phase 1 alone)")
    parser.add_argument("--preview", action="store_true",
                        help="open the interactive tracking laboratory preview")
    parser.add_argument("--check", nargs="?", type=int, const=90, default=None,
                        metavar="FRAMES",
                        help="run headless diagnostics over FRAMES frames (default 90)")
    parser.add_argument("--snapshot", nargs="?", const="auto", default=None,
                        metavar="PATH", help="save one annotated frame and exit")
    parser.add_argument("--debug-gestures", action="store_true",
                        help="open game with live gesture diagnostics HUD enabled")
    parser.add_argument("--ui-preview", choices=["select", "ready", "countdown", "playing", "paused", "results"],
                        default=None, help="directly preview a specific UI screen state")
    parser.add_argument("--duration", type=float, default=0.0, metavar="SECONDS",
                        help="auto-close the preview after N seconds (0 = manual)")
    return parser.parse_args(argv)


# --------------------------------------------------------------------------
# Shared setup
# --------------------------------------------------------------------------


def open_camera(args: argparse.Namespace) -> CameraManager:
    index = select_camera_interactively() if args.select else args.camera
    camera = CameraManager(
        index=index,
        width=args.width,
        height=args.height,
        mirror=not args.no_mirror,
        backend=args.backend,
        threaded=not args.no_threaded_capture,
    )
    camera.open()
    return camera


def create_tracker(args: argparse.Namespace) -> HandTracker | None:
    return None if args.no_tracking else HandTracker()


def read_frame_blocking(camera: CameraManager, attempts: int = 10):
    """Read a frame, tolerating a few dropped ones."""
    for _ in range(attempts):
        frame = camera.read()
        if frame is not None:
            return frame
    return None


# --------------------------------------------------------------------------
# Overlay composition (shared by the preview loop and --snapshot)
# --------------------------------------------------------------------------


def render_overlay(
    frame,
    camera: CameraManager,
    tracker: HandTracker | None,
    result: TrackingResult | None,
    loop_fps: float,
    capture_ms: float,
    show_landmarks: bool,
    show_help: bool,
) -> None:
    """Draw landmarks, fingertip and status text onto `frame` in place."""
    if result is not None and result.hand is not None and show_landmarks:
        preview.draw_hand(frame, result.hand, coasting=result.coasting)
        preview.draw_index_fingertip(frame, result.hand, coasting=result.coasting)

    lines: list[tuple[str, tuple[int, int, int]]] = [
        (f"Camera: {camera.index} ({camera.backend_name})  {camera.width}x{camera.height}",
         preview.WHITE),
        (f"Capture: {camera.measured_fps:5.1f} fps   Loop: {loop_fps:5.1f} fps",
         preview.WHITE),
    ]

    if tracker is None:
        lines.append(("Hand tracking: disabled (--no-tracking)", preview.GREY))
    elif result is None:
        lines.append(("Hand tracking: starting...", preview.GREY))
    elif result.fresh and result.hand is not None:
        hand = result.hand
        lines.append((f"Hand: DETECTED  {hand.handedness} ({hand.score:.2f})", preview.GREEN))
        lines.append((f"Index tip: {hand.index_tip_px}", preview.YELLOW))
    elif result.coasting:
        lines.append((f"Hand: tracking lost - holding last "
                      f"({result.stale_frames}/{tracker.grace_frames})", preview.ORANGE))
    else:
        lines.append(("Hand: not detected", preview.RED))

    if tracker is not None and result is not None:
        lines.append((f"Frame cost: capture {capture_ms:4.1f} ms | "
                      f"track {result.process_ms:4.1f} ms", preview.GREY))
        lines.append((f"Detection rate: {tracker.detection_rate * 100:5.1f}%", preview.GREY))

    lines.append((f"Mirror: {'ON' if camera.mirror else 'OFF'}   "
                  f"Landmarks: {'ON' if show_landmarks else 'OFF'}", preview.GREY))

    preview.draw_status(frame, lines)

    no_hand = tracker is not None and (result is None or result.hand is None)
    if no_hand:
        preview.draw_center_message(
            frame, "Hand not detected", "Please move your hand into view."
        )

    if show_help:
        preview.draw_help(frame, [
            "q / Esc  quit          m  mirror",
            "l  landmarks           r  reset tracking",
            "s  snapshot            h  hide this help",
        ])


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------


def cmd_list_cameras(args: argparse.Namespace) -> int:
    print(f"Probing camera indices 0..{settings.CAMERA_PROBE_LIMIT - 1} ...")
    cameras = CameraManager.list_cameras()
    if not cameras:
        print("\nNo camera detected.\n\nPlease connect a webcam and try again.")
        return 1
    print(f"\nFound {len(cameras)} camera(s):")
    for info in cameras:
        print(f"  {info}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Headless pipeline diagnostics - the automated Phase 1+2 test."""
    target_frames = max(1, args.check)
    print("HANDSHOT - Phase 1+2 diagnostics")
    print("-" * 52)

    camera = open_camera(args)
    tracker = create_tracker(args)

    capture_times: list[float] = []
    track_times: list[float] = []
    detected = coasting = lost = 0
    last_result: TrackingResult | None = None

    started = time.perf_counter()
    try:
        for _ in range(target_frames):
            read_started = time.perf_counter()
            frame = read_frame_blocking(camera)
            read_ms = (time.perf_counter() - read_started) * 1000.0
            if frame is None:
                break
            capture_times.append(read_ms)

            if tracker is not None:
                result = tracker.process(frame, mirrored=camera.mirror)
                track_times.append(result.process_ms)
                last_result = result
                if result.fresh:
                    detected += 1
                elif result.coasting:
                    coasting += 1
                else:
                    lost += 1
        elapsed = time.perf_counter() - started
    finally:
        if tracker is not None:
            tracker.close()
        camera.release()

    processed = len(capture_times)
    print(f"Camera .............. index {camera.index} via {camera.backend_name} "
          f"(opened in {camera.open_seconds:.1f}s)")
    print(f"Resolution .......... {camera.width}x{camera.height} "
          f"(requested {args.width}x{args.height})")
    print(f"Mirror .............. {'on' if camera.mirror else 'off'}")
    if tracker is not None:
        size_mb = tracker.model_path.stat().st_size / 1_000_000
        print(f"Model ............... {tracker.model_path.name} ({size_mb:.1f} MB)")
    print()
    print(f"Frames .............. {camera.frames_read} read, "
          f"{camera.frames_failed} dropped, {camera.frames_stalled} stalled")
    print(f"Capture mode ........ "
          f"{'threaded' if camera.threaded else 'inline (blocking)'}")
    if capture_times:
        print(f"Capture time ........ avg {_avg(capture_times):5.1f} ms  "
              f"max {max(capture_times):5.1f} ms")
    if track_times:
        print(f"Tracking time ....... avg {_avg(track_times):5.1f} ms  "
              f"max {max(track_times):5.1f} ms")
    if elapsed > 0 and processed:
        print(f"Pipeline ............ {processed / elapsed:5.1f} fps end-to-end")

    if tracker is not None:
        rate = (detected / processed * 100.0) if processed else 0.0
        print(f"Hand detected ....... {detected}/{processed} frames ({rate:.1f}%)")
        print(f"Coasting frames ..... {coasting} (held last known hand)")
        print(f"No-hand frames ...... {lost}")
        if last_result is not None and last_result.hand is not None:
            hand = last_result.hand
            norm = hand.index_tip_norm
            print(f"Index tip (last) .... px {hand.index_tip_px}  "
                  f"norm ({norm[0]:.3f}, {norm[1]:.3f})  hand {hand.handedness}")

    # Pass/fail is about the pipeline, not about whether a hand happened to be
    # in view - the camera may be pointing at an empty room.
    problems: list[str] = []
    if processed < target_frames:
        problems.append(f"only {processed}/{target_frames} frames captured")
    if camera.frames_read and camera.frames_failed / max(1, camera.frames_read) > 0.10:
        problems.append("more than 10% of reads failed")
    if tracker is not None and not track_times:
        problems.append("hand tracker never ran")

    print()
    if problems:
        print("RESULT: FAIL - " + "; ".join(problems))
        return 1
    print("RESULT: PASS - camera and tracking pipeline are healthy")

    # A slow backend is not a code fault, but it destroys aim feel, so say so.
    effective_fps = processed / elapsed if elapsed > 0 else 0.0
    if effective_fps and effective_fps < 0.6 * settings.CAMERA_FPS:
        alternatives = [n for n in BACKEND_NAMES if n != camera.backend_name]
        print(f"WARN:   only {effective_fps:.1f} fps end-to-end (target "
              f"{settings.CAMERA_FPS}). Try a different backend, e.g. "
              f"--backend {alternatives[0].lower() if alternatives else 'any'}, "
              f"or a lower --width/--height.")
    if tracker is not None and detected == 0:
        print("NOTE:   no hand was seen. Hold a hand in view and re-run to "
              "verify detection.")
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    """Grab one annotated frame and write it to disk."""
    if args.snapshot == "auto":
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        path = SNAPSHOT_DIR / f"snapshot_{int(time.time())}.png"
    else:
        path = Path(args.snapshot)
        path.parent.mkdir(parents=True, exist_ok=True)

    camera = open_camera(args)
    tracker = create_tracker(args)
    try:
        result = None
        frame = None
        # A few frames give MediaPipe's video tracker a chance to lock on.
        for _ in range(12):
            frame = read_frame_blocking(camera)
            if frame is None:
                break
            if tracker is not None:
                result = tracker.process(frame, mirrored=camera.mirror)
        if frame is None:
            print("Could not capture a frame.", file=sys.stderr)
            return 1
        render_overlay(frame, camera, tracker, result, camera.measured_fps, 0.0,
                       settings.SHOW_LANDMARKS, show_help=False)
        cv2.imwrite(str(path), frame)
    finally:
        if tracker is not None:
            tracker.close()
        camera.release()

    print(f"Saved snapshot: {path}")
    return 0


def run_preview(args: argparse.Namespace) -> int:
    """Real-time Camera & Hand Tracking Laboratory."""
    try:
        from camera.preview_screen import CameraPreviewScreen
    except ModuleNotFoundError as exc:
        if exc.name != "pygame":
            raise
        print("Pygame is required. Install with: py -m pip install -r requirements.txt", file=sys.stderr)
        return 1

    camera = open_camera(args)
    tracker = create_tracker(args)
    print("HANDSHOT Camera & Tracking Laboratory:")
    print("Controls: [C] Mirror  [L] Landmarks  [D] Diagnostics  [R] Reset  [ESC] Exit")

    try:
        screen_app = CameraPreviewScreen(camera, tracker, debug_hud=args.debug_gestures or True)
        return screen_app.run(args.duration)
    finally:
        if tracker is not None:
            tracker.close()
        if camera is not None:
            camera.release()
            print(f"closed cleanly - {camera.frames_read} frames read, {camera.frames_failed} dropped")


def run_game(args: argparse.Namespace) -> int:
    """Pygame arcade blue-bubble game."""
    try:
        from game.aim_screen import AimScreen
        from game.bubble_game import GameState
    except ModuleNotFoundError as exc:
        if exc.name != "pygame":
            raise
        print("Pygame is required for the Phase 3 aim screen. Install project "
              "dependencies with: py -m pip install -r requirements.txt", file=sys.stderr)
        return 1

    camera = None if args.ui_preview else open_camera(args)
    tracker = None if args.ui_preview else create_tracker(args)
    if camera:
        print(camera.describe())
    print("HANDSHOT Arcade: pinch thumb + index to shoot | P pause | R restart | M mute | Q quit")
    try:
        screen_app = AimScreen(camera, tracker, debug_hud=args.debug_gestures)
        if args.ui_preview:
            preview_state_map = {
                "select": GameState.MODE_SELECT,
                "ready": GameState.READY,
                "countdown": GameState.COUNTDOWN,
                "playing": GameState.PLAYING,
                "paused": GameState.PAUSED,
                "results": GameState.GAME_OVER,
            }
            target_st = preview_state_map.get(args.ui_preview, GameState.MODE_SELECT)
            screen_app._game.state = target_st
            if target_st is GameState.COUNTDOWN:
                screen_app._game.countdown_text = "2"
            elif target_st is GameState.GAME_OVER:
                screen_app._game.score.score = 1420
                screen_app._game.high_score = 1420
                screen_app._game.is_new_high_score = True
                screen_app._game.stats.shots_fired = 52
                screen_app._game.stats.targets_hit = 48
                screen_app._game.stats.golden_targets_hit = 4
                screen_app._game.stats.highest_combo = 4
        return screen_app.run(args.duration)
    finally:
        if tracker is not None:
            tracker.close()
        if camera is not None:
            camera.release()
            print(f"closed cleanly - {camera.frames_read} frames read, "
                  f"{camera.frames_failed} dropped")


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.list_cameras:
            return cmd_list_cameras(args)
        if args.check is not None:
            return cmd_check(args)
        if args.snapshot is not None:
            return cmd_snapshot(args)
        if args.preview:
            return run_preview(args)
        return run_game(args)
    except (CameraError, HandTrackerError) as exc:
        print(f"\n{exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\ninterrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main())
