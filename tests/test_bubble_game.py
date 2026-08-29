"""Camera-free checks for Phase 6 gameplay, lives, game-over, combo, stats, and difficulty."""

import json
import random
import tempfile
import unittest
from pathlib import Path

from config import settings
from game.bubble import Bubble
from game.bubble_game import BubbleGame, GameState
from game.scoring import (
    ComboTracker,
    GameStats,
    load_high_score,
    save_high_score,
)
from game.target_manager import BubbleSettings, TargetManager


BOUNDS = (20.0, 100.0, 980.0, 620.0)


def manager() -> TargetManager:
    return TargetManager(
        BubbleSettings(
            initial_count=3,
            max_active=4,
            spawn_interval_seconds=1.0,
            radius_min=30.0,
            radius_max=30.0,
            speed_min=100.0,
            speed_max=100.0,
            spawn_attempts=100,
            spawn_separation=20.0,
        ),
        random.Random(4),
    )


class BubbleGameTests(unittest.TestCase):
    def test_starting_lives_is_three(self) -> None:
        game = BubbleGame(random.Random(1))
        game.reset(BOUNDS, start_state=GameState.PLAYING)
        self.assertEqual(game.stats.lives, 3)
        self.assertEqual(game.state, GameState.PLAYING)

    def test_initial_state_is_ready_and_no_bubbles_move(self) -> None:
        game = BubbleGame(random.Random(1))
        game.reset(BOUNDS, start_state=GameState.READY)
        self.assertEqual(game.state, GameState.READY)

        # Bubble placed at bottom hazard line does NOT escape during READY
        game.targets.bubbles = [Bubble((400.0, BOUNDS[3] - 5), (0.0, 100.0), 30.0)]
        escaped = game.update(0.10, BOUNDS, hand_tracked=False)
        self.assertEqual(len(escaped), 0)
        self.assertEqual(game.stats.lives, 3)

    def test_ready_state_advances_to_countdown_on_stable_hand(self) -> None:
        game = BubbleGame(random.Random(1))
        game.reset(BOUNDS, start_state=GameState.READY)

        # Hand tracked for half duration -> remains READY
        half_stable = settings.READY_HAND_STABLE_SECONDS * 0.5
        game.update(half_stable, BOUNDS, hand_tracked=True)
        self.assertEqual(game.state, GameState.READY)

        # Hand tracked for remaining duration (total >= READY_HAND_STABLE_SECONDS) -> transitions to COUNTDOWN
        game.update(half_stable + 0.05, BOUNDS, hand_tracked=True)
        self.assertEqual(game.state, GameState.COUNTDOWN)
        self.assertEqual(game.countdown_text, "3")

    def test_ready_state_resets_timer_on_hand_loss(self) -> None:
        game = BubbleGame(random.Random(1))
        game.reset(BOUNDS, start_state=GameState.READY)

        # Hand tracked for partial duration
        game.update(settings.READY_HAND_STABLE_SECONDS * 0.5, BOUNDS, hand_tracked=True)
        self.assertGreater(game.ready_hand_timer, 0.0)

        # Hand lost
        game.update(0.50, BOUNDS, hand_tracked=False)
        self.assertEqual(game.ready_hand_timer, 0.0)
        self.assertEqual(game.state, GameState.READY)

    def test_countdown_sequence_and_transition_to_playing(self) -> None:
        game = BubbleGame(random.Random(1))
        game.reset(BOUNDS, start_state=GameState.COUNTDOWN)

        # Step 1: 3
        game.update(0.20, BOUNDS)
        self.assertEqual(game.state, GameState.COUNTDOWN)
        self.assertEqual(game.countdown_text, "3")

        # Step 2: 2 (after 0.75s)
        game.update(0.60, BOUNDS)
        self.assertEqual(game.countdown_text, "2")

        # Step 3: 1 (after 1.50s)
        game.update(0.75, BOUNDS)
        self.assertEqual(game.countdown_text, "1")

        # Step 4: GO! (after 2.25s)
        game.update(0.75, BOUNDS)
        self.assertEqual(game.countdown_text, "GO!")

        # Step 5: Finish countdown (after 2.75s total) -> PLAYING
        game.update(0.55, BOUNDS)
        self.assertEqual(game.state, GameState.PLAYING)
        self.assertEqual(game.countdown_text, "")

    def test_paused_state_toggle_and_freezes_gameplay(self) -> None:
        game = BubbleGame(random.Random(1))
        game.reset(BOUNDS, start_state=GameState.PLAYING)

        # Toggle pause
        is_paused = game.toggle_pause()
        self.assertTrue(is_paused)
        self.assertEqual(game.state, GameState.PAUSED)

        # In PAUSED, shooting is blocked
        game.targets.bubbles = [Bubble((400.0, 300.0), (0.0, 0.0), 40.0)]
        hit, pts = game.shoot((400.0, 300.0))
        self.assertIsNone(hit)
        self.assertEqual(pts, 0)

        # In PAUSED, update returns [] and does not move targets
        escaped = game.update(1.0, BOUNDS, hand_tracked=True)
        self.assertEqual(len(escaped), 0)

        # Toggle resume
        is_paused = game.toggle_pause()
        self.assertFalse(is_paused)
        self.assertEqual(game.state, GameState.PLAYING)

    def test_shooting_blocked_in_non_playing_states(self) -> None:
        game = BubbleGame(random.Random(1))
        for state in (GameState.READY, GameState.COUNTDOWN, GameState.PAUSED, GameState.GAME_OVER):
            game.state = state
            game.targets.bubbles = [Bubble((400.0, 300.0), (0.0, 0.0), 40.0)]
            hit, pts = game.shoot((400.0, 300.0))
            self.assertIsNone(hit, f"Shot was not blocked in state {state}")
            self.assertEqual(pts, 0)
            self.assertEqual(game.stats.shots_fired, 0)

    def test_bubble_escape_removes_exactly_one_life_and_removes_target(self) -> None:
        game = BubbleGame(random.Random(1))
        game.reset(BOUNDS, start_state=GameState.PLAYING)
        # Position bubble right above bottom hazard line heading down
        game.targets.bubbles = [Bubble((400.0, BOUNDS[3] - 5), (0.0, 100.0), 30.0)]
        escaped = game.update(0.10, BOUNDS, hand_tracked=True)
        self.assertEqual(len(escaped), 1)
        self.assertEqual(game.stats.lives, 2)
        self.assertEqual(len(game.targets.bubbles), 0)

    def test_bubble_escape_when_hand_not_tracked_does_not_cost_life(self) -> None:
        game = BubbleGame(random.Random(1))
        game.reset(BOUNDS, start_state=GameState.PLAYING)
        game.targets.bubbles = [Bubble((400.0, BOUNDS[3] - 5), (0.0, 100.0), 30.0)]
        # Escape when hand is not tracked
        escaped = game.update(0.10, BOUNDS, hand_tracked=False)
        self.assertEqual(len(escaped), 1)
        self.assertEqual(game.stats.lives, 3)  # No life lost
        self.assertEqual(len(game.targets.bubbles), 0)

    def test_no_duplicate_life_loss_from_one_bubble(self) -> None:
        game = BubbleGame(random.Random(1))
        game.reset(BOUNDS, start_state=GameState.PLAYING)
        game.targets.bubbles = [Bubble((400.0, BOUNDS[3] - 5), (0.0, 100.0), 30.0)]
        # Escape in frame 1
        game.update(0.10, BOUNDS, hand_tracked=True)
        self.assertEqual(game.stats.lives, 2)
        # Frame 2: no extra life deducted
        game.update(0.10, BOUNDS, hand_tracked=True)
        self.assertEqual(game.stats.lives, 2)

    def test_game_over_at_zero_lives(self) -> None:
        game = BubbleGame(random.Random(1))
        game.reset(BOUNDS, start_state=GameState.PLAYING)
        # Escape 3 bubbles
        for i in range(3):
            game.targets.bubbles = [Bubble((400.0, BOUNDS[3] - 5), (0.0, 100.0), 30.0)]
            game.update(0.10, BOUNDS, hand_tracked=True)
            self.assertEqual(game.stats.lives, 3 - (i + 1))

        self.assertEqual(game.stats.lives, 0)
        self.assertEqual(game.state, GameState.GAME_OVER)

    def test_game_over_state_blocks_gameplay(self) -> None:
        game = BubbleGame(random.Random(1))
        game.reset(BOUNDS, start_state=GameState.GAME_OVER)
        game.stats.lives = 0
        game.targets.bubbles = [Bubble((400.0, 300.0), (0.0, 0.0), 40.0)]

        # Shooting in Game Over does not hit, fire, or increment shots
        hit, pts = game.shoot((400.0, 300.0))
        self.assertIsNone(hit)
        self.assertEqual(pts, 0)
        self.assertEqual(game.stats.shots_fired, 0)

        # Update in Game Over does not move targets or spawn
        game.update(1.0, BOUNDS, hand_tracked=True)
        self.assertEqual(len(game.targets.bubbles), 1)

    def test_restart_resets_everything(self) -> None:
        game = BubbleGame(random.Random(2))
        game.reset(BOUNDS, start_state=GameState.PLAYING)
        game.score.add(150)
        game.combo.register_hit()
        game.combo.register_hit()
        game.stats.record_shot()
        game.stats.record_hit()
        game.stats.lives = 1
        game.state = GameState.GAME_OVER

        # Reset returns to READY state
        game.reset(BOUNDS, start_state=GameState.READY)
        self.assertEqual(game.state, GameState.READY)
        self.assertEqual(game.score.score, 0)
        self.assertEqual(game.combo.current_combo, 0)
        self.assertEqual(game.stats.lives, 3)
        self.assertEqual(game.stats.shots_fired, 0)
        self.assertEqual(game.stats.targets_hit, 0)
        self.assertEqual(len(game.targets.bubbles), settings.BUBBLE_INITIAL_COUNT)

    def test_shot_statistics_and_accuracy(self) -> None:
        stats = GameStats()
        self.assertEqual(stats.accuracy, 0.0)

        stats.record_shot()  # Shot 1
        stats.record_hit()   # Hit 1
        self.assertEqual(stats.accuracy, 100.0)

        stats.record_shot()  # Shot 2 (miss)
        self.assertEqual(stats.accuracy, 50.0)

        stats.record_shot()  # Shot 3
        stats.record_hit()   # Hit 2
        self.assertAlmostEqual(stats.accuracy, 66.666, delta=0.01)

    def test_combo_progression_and_multipliers(self) -> None:
        game = BubbleGame(random.Random(1))
        game.reset(BOUNDS, start_state=GameState.PLAYING)

        # 6 consecutive hits
        expected_points = [10, 10, 20, 20, 30, 30]  # x1, x1, x2, x2, x3, x3
        for i, pts in enumerate(expected_points):
            game.targets.bubbles = [Bubble((400.0, 300.0), (0.0, 0.0), 40.0)]
            hit, awarded = game.shoot((400.0, 300.0))
            self.assertIsNotNone(hit)
            self.assertEqual(awarded, pts, f"Hit #{i+1} awarded {awarded} instead of {pts}")

        self.assertEqual(game.combo.current_combo, 6)
        self.assertEqual(game.combo.highest_combo, 6)
        self.assertEqual(game.score.score, sum(expected_points))

    def test_combo_resets_on_miss(self) -> None:
        game = BubbleGame(random.Random(1))
        game.reset(BOUNDS, start_state=GameState.PLAYING)

        # 3 hits -> combo 3 (x2 multiplier)
        for _ in range(3):
            game.targets.bubbles = [Bubble((400.0, 300.0), (0.0, 0.0), 40.0)]
            game.shoot((400.0, 300.0))
        self.assertEqual(game.combo.current_combo, 3)
        self.assertEqual(game.combo.multiplier, 2)

        # Miss shot
        game.targets.bubbles = [Bubble((400.0, 300.0), (0.0, 0.0), 40.0)]
        hit, awarded = game.shoot((100.0, 100.0))
        self.assertIsNone(hit)
        self.assertEqual(awarded, 0)
        self.assertEqual(game.combo.current_combo, 0)
        self.assertEqual(game.combo.multiplier, 1)

        # Next hit is at base 1x (+10)
        hit2, awarded2 = game.shoot((400.0, 300.0))
        self.assertIsNotNone(hit2)
        self.assertEqual(awarded2, 10)

    def test_combo_resets_on_escaped_bubble(self) -> None:
        game = BubbleGame(random.Random(1))
        game.reset(BOUNDS, start_state=GameState.PLAYING)

        # 4 hits -> combo 4
        for _ in range(4):
            game.targets.bubbles = [Bubble((400.0, 300.0), (0.0, 0.0), 40.0)]
            game.shoot((400.0, 300.0))
        self.assertEqual(game.combo.current_combo, 4)

        # Bubble escapes
        game.targets.bubbles = [Bubble((400.0, BOUNDS[3] - 5), (0.0, 100.0), 30.0)]
        game.update(0.10, BOUNDS, hand_tracked=True)
        self.assertEqual(game.combo.current_combo, 0)
        self.assertEqual(game.combo.multiplier, 1)

    def test_progressive_difficulty_scales_with_score(self) -> None:
        targets = TargetManager()
        # Initial score 0
        targets.set_difficulty_score(0)
        self.assertEqual(targets.current_speed_min, settings.BUBBLE_SPEED_MIN_START)
        self.assertEqual(targets.current_max_active, settings.BUBBLE_MAX_ACTIVE_START)

        # Mid score
        targets.set_difficulty_score(round(settings.DIFFICULTY_MAX_SCORE / 2))
        self.assertGreater(targets.current_speed_min, settings.BUBBLE_SPEED_MIN_START)
        self.assertLess(targets.current_spawn_interval, settings.BUBBLE_SPAWN_INTERVAL_START)

        # Max score
        targets.set_difficulty_score(round(settings.DIFFICULTY_MAX_SCORE))
        self.assertEqual(targets.current_speed_min, settings.BUBBLE_SPEED_MIN_END)
        self.assertEqual(targets.current_speed_max, settings.BUBBLE_SPEED_MAX_END)
        self.assertEqual(targets.current_max_active, settings.BUBBLE_MAX_ACTIVE_END)

    def test_high_score_save_and_load(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_file = Path(temp_dir) / "stats.json"
            self.assertEqual(load_high_score(save_file), 0)

            # Save high score 350
            saved = save_high_score(350, save_file)
            self.assertTrue(saved)
            self.assertEqual(load_high_score(save_file), 350)

            # Lower score does not overwrite
            saved_lower = save_high_score(200, save_file)
            self.assertFalse(saved_lower)
            self.assertEqual(load_high_score(save_file), 350)

            # Higher score overwrites
            saved_higher = save_high_score(500, save_file)
            self.assertTrue(saved_higher)
            self.assertEqual(load_high_score(save_file), 500)

    def test_corrupted_or_missing_high_score_data_falls_back_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            corrupt_file = Path(temp_dir) / "corrupt.json"
            corrupt_file.write_text("{not valid json syntax!@#}", encoding="utf-8")
            self.assertEqual(load_high_score(corrupt_file), 0)

    def test_hit_forgiveness_allows_near_miss(self) -> None:
        game = BubbleGame(random.Random(1))
        game.reset(BOUNDS, start_state=GameState.PLAYING)
        game.targets.bubbles = [Bubble((400.0, 300.0), (0.0, 0.0), 40.0)]
        hit, _ = game.shoot((448.0, 300.0))
        self.assertIsNotNone(hit)
        self.assertEqual(game.score.score, 10)

    def test_bubble_side_and_top_reflection(self) -> None:
        bubble = Bubble(
            position=(BOUNDS[2] - 35.0, BOUNDS[1] + 35.0),
            velocity=(100.0, -100.0),
            radius=30.0,
        )
        bubble.update(0.10, BOUNDS)
        # Should reflect without escaping
        self.assertFalse(bubble.escaped)
        self.assertLess(bubble.velocity[0], 0.0)
        self.assertGreater(bubble.velocity[1], 0.0)

    def test_timed_mode_expires_at_duration_and_triggers_game_over(self) -> None:
        from game.game_mode import get_timed_mode

        timed_mode = get_timed_mode()
        game = BubbleGame(random.Random(1), mode=timed_mode, start_state=GameState.PLAYING)
        self.assertEqual(game.time_remaining, 60.0)

        # 30 seconds advance
        game.update(30.0, BOUNDS, hand_tracked=True)
        self.assertEqual(game.state, GameState.PLAYING)
        self.assertEqual(game.time_remaining, 30.0)

        # Bubble escapes during timed mode -> no life loss
        game.targets.bubbles = [Bubble((400.0, BOUNDS[3] - 5), (0.0, 100.0), 30.0)]
        escaped = game.update(0.10, BOUNDS, hand_tracked=True)
        self.assertEqual(len(escaped), 1)
        self.assertEqual(game.state, GameState.PLAYING)

        # Remaining 30 seconds elapse -> GAME_OVER
        game.update(30.0, BOUNDS, hand_tracked=True)
        self.assertEqual(game.state, GameState.GAME_OVER)
        self.assertEqual(game.time_remaining, 0.0)

    def test_chill_mode_escaped_bubbles_never_lose_lives_or_end_game(self) -> None:
        from game.game_mode import get_chill_mode

        chill_mode = get_chill_mode()
        game = BubbleGame(random.Random(1), mode=chill_mode, start_state=GameState.PLAYING)
        self.assertIsNone(game.time_remaining)
        self.assertFalse(game.mode.allow_life_loss)

        # Escape 10 bubbles
        for _ in range(10):
            game.targets.bubbles = [Bubble((400.0, BOUNDS[3] - 5), (0.0, 100.0), 30.0)]
            escaped = game.update(0.10, BOUNDS, hand_tracked=True)
            self.assertEqual(len(escaped), 1)
            self.assertEqual(game.state, GameState.PLAYING)

    def test_practice_mode_spawns_controlled_targets_without_game_over(self) -> None:
        from game.game_mode import get_practice_mode

        practice_mode = get_practice_mode()
        game = BubbleGame(random.Random(1), mode=practice_mode, start_state=GameState.PLAYING)
        self.assertEqual(game.targets.current_max_active, 2)
        self.assertFalse(game.mode.allow_life_loss)

        # Score increases do not ramp difficulty in practice mode
        game.score.add(500)
        game.update(0.10, BOUNDS, hand_tracked=True)
        self.assertEqual(game.targets.current_max_active, 2)
        self.assertEqual(game.targets.current_speed_min, practice_mode.speed_min_start)

    def test_mode_switching_updates_config_and_loads_mode_high_score(self) -> None:
        from game.game_mode import get_chill_mode, get_classic_mode

        game = BubbleGame(random.Random(1), mode=get_classic_mode(), start_state=GameState.READY)
        self.assertEqual(game.mode.name, "CLASSIC")

        game.set_mode(get_chill_mode(), BOUNDS)
        self.assertEqual(game.mode.name, "RELAXED")
        self.assertEqual(game.state, GameState.READY)
        self.assertFalse(game.mode.allow_life_loss)

    def test_per_mode_high_scores_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_file = Path(temp_dir) / "mode_stats.json"
            save_high_score(200, save_file, mode_name="CLASSIC")
            save_high_score(450, save_file, mode_name="TIMED")
            save_high_score(120, save_file, mode_name="RELAXED")

            self.assertEqual(load_high_score(save_file, mode_name="CLASSIC"), 200)
            self.assertEqual(load_high_score(save_file, mode_name="TIMED"), 450)
            self.assertEqual(load_high_score(save_file, mode_name="RELAXED"), 120)
            self.assertEqual(load_high_score(save_file, mode_name="PRACTICE"), 0)


if __name__ == "__main__":
    unittest.main()

