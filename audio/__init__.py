"""Audio system package for HANDSHOT."""

from audio.audio_manager import AudioManager
from audio.sound_generator import ensure_audio_assets

__all__ = ["AudioManager", "ensure_audio_assets"]
