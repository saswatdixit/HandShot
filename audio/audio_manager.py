"""Central Audio Manager for HANDSHOT (Phase 8).

Provides safe sound effect triggering, mode-based background music playback,
mute toggling, and volume adjustments. Never crashes if sound files or audio
drivers are missing.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pygame

from audio.sound_generator import ensure_audio_assets
from config import settings

logger = logging.getLogger(__name__)


class AudioManager:
    """Manage SFX and music channels with graceful fallback for headless/silent modes."""

    def __init__(
        self,
        enabled: bool = settings.AUDIO_ENABLED,
        sfx_dir: Path = settings.AUDIO_SFX_DIR,
        music_dir: Path = settings.AUDIO_MUSIC_DIR,
        master_volume: float = settings.AUDIO_MASTER_VOLUME,
        sfx_volume: float = settings.AUDIO_SFX_VOLUME,
        music_volume: float = settings.AUDIO_MUSIC_VOLUME,
    ) -> None:
        self.enabled = enabled
        self.muted = False
        self.sfx_dir = sfx_dir
        self.music_dir = music_dir
        self.master_volume = max(0.0, min(1.0, master_volume))
        self.sfx_volume = max(0.0, min(1.0, sfx_volume))
        self.music_volume = max(0.0, min(1.0, music_volume))

        self._mixer_available = False
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self._current_music_track: str | None = None

        if self.enabled:
            self._init_mixer()

    def _init_mixer(self) -> None:
        """Initialize pygame.mixer and load sound assets safely."""
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            self._mixer_available = True
        except Exception as exc:
            logger.warning("Could not initialize pygame.mixer (audio disabled): %s", exc)
            self._mixer_available = False
            return

        # Ensure asset files exist on disk
        try:
            ensure_audio_assets(self.sfx_dir, self.music_dir)
        except Exception as exc:
            logger.warning("Could not generate audio assets: %s", exc)

        # Load all SFX
        if self.sfx_dir.exists():
            for wav_file in self.sfx_dir.glob("*.wav"):
                try:
                    sound = pygame.mixer.Sound(str(wav_file))
                    sound.set_volume(self._effective_sfx_volume())
                    self._sounds[wav_file.stem] = sound
                except Exception as exc:
                    logger.warning("Failed to load sound %s: %s", wav_file.name, exc)

        self._apply_volumes()

    # -- SFX Playback ------------------------------------------------------

    def play_sfx(self, name: str, volume: float = 1.0) -> None:
        """Play a registered sound effect by name (e.g. 'bubble_hit', 'pinch')."""
        if not self._mixer_available or not self.enabled or self.muted:
            return

        sound = self._sounds.get(name)
        if sound is not None:
            try:
                eff_vol = self._effective_sfx_volume() * max(0.0, min(1.0, volume))
                sound.set_volume(eff_vol)
                sound.play()
            except Exception as exc:
                logger.debug("Failed to play SFX %s: %s", name, exc)

    # -- Music Playback ----------------------------------------------------

    def play_music(self, track_name: str, loop: bool = True, fade_ms: int = 400) -> None:
        """Stream and loop mode background music (e.g. 'classic', 'chill', 'timed')."""
        if not self._mixer_available or not self.enabled:
            return

        if self._current_music_track == track_name and pygame.mixer.music.get_busy():
            return  # Already playing this track

        music_file = self.music_dir / f"{track_name}.wav"
        if not music_file.exists():
            return

        try:
            pygame.mixer.music.load(str(music_file))
            pygame.mixer.music.set_volume(self._effective_music_volume())
            loops = -1 if loop else 0
            if fade_ms > 0:
                pygame.mixer.music.play(loops=loops, fade_ms=fade_ms)
            else:
                pygame.mixer.music.play(loops=loops)
            self._current_music_track = track_name
        except Exception as exc:
            logger.warning("Failed to play music %s: %s", track_name, exc)

    def stop_music(self, fade_ms: int = 300) -> None:
        """Fade out or stop active background music."""
        if not self._mixer_available:
            return
        try:
            if fade_ms > 0:
                pygame.mixer.music.fadeout(fade_ms)
            else:
                pygame.mixer.music.stop()
            self._current_music_track = None
        except Exception:
            pass

    # -- Volume & Mute Controls --------------------------------------------

    def toggle_mute(self) -> bool:
        """Toggle mute state. Returns True if now muted."""
        self.muted = not self.muted
        self._apply_volumes()
        return self.muted

    def set_master_volume(self, volume: float) -> None:
        self.master_volume = max(0.0, min(1.0, volume))
        self._apply_volumes()

    def set_sfx_volume(self, volume: float) -> None:
        self.sfx_volume = max(0.0, min(1.0, volume))
        self._apply_volumes()

    def set_music_volume(self, volume: float) -> None:
        self.music_volume = max(0.0, min(1.0, volume))
        self._apply_volumes()

    def _effective_sfx_volume(self) -> float:
        if self.muted or not self.enabled:
            return 0.0
        return self.master_volume * self.sfx_volume

    def _effective_music_volume(self) -> float:
        if self.muted or not self.enabled:
            return 0.0
        return self.master_volume * self.music_volume

    def _apply_volumes(self) -> None:
        if not self._mixer_available:
            return
        sfx_vol = self._effective_sfx_volume()
        for sound in self._sounds.values():
            try:
                sound.set_volume(sfx_vol)
            except Exception:
                pass

        try:
            pygame.mixer.music.set_volume(self._effective_music_volume())
        except Exception:
            pass

    def close(self) -> None:
        """Release audio resources cleanly."""
        self.stop_music(fade_ms=0)
        self._sounds.clear()
        if self._mixer_available and pygame.mixer.get_init():
            try:
                pygame.mixer.quit()
            except Exception:
                pass
        self._mixer_available = False
