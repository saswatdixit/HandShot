"""Unit tests for Phase 8 Audio Manager and procedural sound generation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from audio.audio_manager import AudioManager
from audio.sound_generator import ensure_audio_assets


class AudioManagerTests(unittest.TestCase):
    def test_audio_assets_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sfx_dir = Path(temp_dir) / "sfx"
            music_dir = Path(temp_dir) / "music"
            ensure_audio_assets(sfx_dir, music_dir)

            # Verify SFX generated
            expected_sfx = [
                "pinch.wav",
                "bubble_hit.wav",
                "bubble_miss.wav",
                "bubble_escape.wav",
                "countdown_tick.wav",
                "countdown_go.wav",
                "life_lost.wav",
                "combo.wav",
                "game_over.wav",
                "high_score.wav",
                "menu_move.wav",
                "menu_select.wav",
            ]
            for sfx_name in expected_sfx:
                file_path = sfx_dir / sfx_name
                self.assertTrue(file_path.exists(), f"Missing {sfx_name}")
                self.assertGreater(file_path.stat().st_size, 100)

            # Verify Music generated
            expected_music = ["classic.wav", "chill.wav", "timed.wav", "practice.wav"]
            for music_name in expected_music:
                file_path = music_dir / music_name
                self.assertTrue(file_path.exists(), f"Missing {music_name}")
                self.assertGreater(file_path.stat().st_size, 1000)

    def test_audio_manager_safe_when_disabled_or_headless(self) -> None:
        mgr = AudioManager(enabled=False)
        self.assertFalse(mgr.enabled)
        # Calling methods must never raise exceptions
        mgr.play_sfx("bubble_hit")
        mgr.play_music("classic")
        mgr.stop_music()
        mgr.set_master_volume(0.5)
        mgr.set_sfx_volume(0.5)
        mgr.set_music_volume(0.5)
        self.assertFalse(mgr.muted)
        is_muted = mgr.toggle_mute()
        self.assertTrue(is_muted)
        self.assertTrue(mgr.muted)
        mgr.close()

    def test_audio_manager_handles_missing_sound_gracefully(self) -> None:
        with tempfile.TemporaryDirectory() as empty_dir:
            mgr = AudioManager(
                enabled=True,
                sfx_dir=Path(empty_dir) / "empty_sfx",
                music_dir=Path(empty_dir) / "empty_music",
            )
            # Must not crash when querying a non-existent sound or music track
            mgr.play_sfx("non_existent_sfx")
            mgr.play_music("non_existent_track")
            mgr.close()


if __name__ == "__main__":
    unittest.main()
