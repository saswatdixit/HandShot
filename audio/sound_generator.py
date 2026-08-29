"""Procedural procedural audio synthesis for HANDSHOT (Phase 8).

Generates clean 16-bit 44.1kHz WAV sound effects and ambient musical loops
using only Python standard library modules (math, struct, wave).
Zero external asset downloads or copyright concerns.
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

from config import settings

SAMPLE_RATE = 44100


def _clamp_sample(sample: float) -> int:
    return max(-32767, min(32767, round(sample * 32767.0)))


def _write_wav_mono(filepath: Path, samples: list[float]) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(filepath), "w") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(SAMPLE_RATE)
        data = bytearray()
        for s in samples:
            val = _clamp_sample(s)
            data.extend(struct.pack("<h", val))
        wav_file.writeframes(data)


def _write_wav_stereo(filepath: Path, left: list[float], right: list[float]) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(filepath), "w") as wav_file:
        wav_file.setnchannels(2)  # Stereo
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(SAMPLE_RATE)
        data = bytearray()
        for l, r in zip(left, right):
            data.extend(struct.pack("<hh", _clamp_sample(l), _clamp_sample(r)))
        wav_file.writeframes(data)


# --------------------------------------------------------------------------
# SFX Synthesizers
# --------------------------------------------------------------------------


def _synth_pinch() -> list[float]:
    duration = 0.055
    count = int(SAMPLE_RATE * duration)
    out = []
    for i in range(count):
        t = i / SAMPLE_RATE
        freq = 600.0 + (t / duration) * 700.0
        env = math.exp(-t * 40.0)
        s = math.sin(2.0 * math.pi * freq * t) * env * 0.75
        out.append(s)
    return out


def _synth_bubble_hit() -> list[float]:
    duration = 0.13
    count = int(SAMPLE_RATE * duration)
    out = []
    for i in range(count):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 22.0)
        s1 = math.sin(2.0 * math.pi * 880.0 * t) * 0.55
        s2 = math.sin(2.0 * math.pi * 1320.0 * t) * 0.35
        s3 = math.sin(2.0 * math.pi * 1760.0 * t) * 0.15
        out.append((s1 + s2 + s3) * env * 0.85)
    return out


def _synth_bubble_hit_small() -> list[float]:
    """Sharp, higher-frequency crisp pop for small targets."""
    duration = 0.09
    count = int(SAMPLE_RATE * duration)
    out = []
    for i in range(count):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 35.0)
        s1 = math.sin(2.0 * math.pi * 1320.0 * t) * 0.60
        s2 = math.sin(2.0 * math.pi * 1980.0 * t) * 0.35
        out.append((s1 + s2) * env * 0.90)
    return out


def _synth_bubble_hit_large() -> list[float]:
    """Deep, resonant, low-end punchy pop for large targets."""
    duration = 0.18
    count = int(SAMPLE_RATE * duration)
    out = []
    for i in range(count):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 15.0)
        s1 = math.sin(2.0 * math.pi * 440.0 * t) * 0.65
        s2 = math.sin(2.0 * math.pi * 660.0 * t) * 0.30
        out.append((s1 + s2) * env * 0.85)
    return out


def _synth_bubble_hit_golden() -> list[float]:
    """Brilliant, multi-harmonic celebratory chime for rare golden targets."""
    duration = 0.38
    count = int(SAMPLE_RATE * duration)
    out = []
    notes = [1046.50, 1318.51, 1567.98, 2093.00]
    for i in range(count):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 7.5)
        # Sparkle frequency modulation
        sparkle = 1.0 + 0.08 * math.sin(2.0 * math.pi * 18.0 * t)
        s = sum(math.sin(2.0 * math.pi * freq * sparkle * t) * (0.35 - idx * 0.05) for idx, freq in enumerate(notes))
        out.append(s * env * 0.85)
    return out


def _synth_combo_streak() -> list[float]:
    """Sparkly arpeggio chime for 10+ hit combo streaks."""
    duration = 0.30
    count = int(SAMPLE_RATE * duration)
    out = []
    notes = [880.0, 1174.66, 1479.98, 1760.00]
    step_samples = count // len(notes)
    for i in range(count):
        idx = min(len(notes) - 1, i // step_samples)
        freq = notes[idx]
        t = i / SAMPLE_RATE
        t_note = (i % step_samples) / SAMPLE_RATE
        env = math.exp(-t_note * 16.0)
        s = math.sin(2.0 * math.pi * freq * t) * env * 0.75
        out.append(s)
    return out


def _synth_pause() -> list[float]:
    """Clean subtle menu pause click."""
    duration = 0.06
    count = int(SAMPLE_RATE * duration)
    out = []
    for i in range(count):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 40.0)
        s = math.sin(2.0 * math.pi * (520.0 - t * 140.0) * t) * env * 0.55
        out.append(s)
    return out


def _synth_bubble_miss() -> list[float]:
    duration = 0.075
    count = int(SAMPLE_RATE * duration)
    out = []
    for i in range(count):
        t = i / SAMPLE_RATE
        freq = 380.0 - (t / duration) * 180.0
        env = math.sin(math.pi * (t / duration))
        s = math.sin(2.0 * math.pi * freq * t) * env * 0.40
        out.append(s)
    return out


def _synth_bubble_escape() -> list[float]:
    duration = 0.16
    count = int(SAMPLE_RATE * duration)
    out = []
    for i in range(count):
        t = i / SAMPLE_RATE
        freq = 440.0 - (t / duration) * 220.0
        env = math.exp(-t * 14.0)
        s = math.sin(2.0 * math.pi * freq * t) * env * 0.65
        out.append(s)
    return out


def _synth_countdown_tick() -> list[float]:
    duration = 0.040
    count = int(SAMPLE_RATE * duration)
    out = []
    for i in range(count):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 70.0)
        s = math.sin(2.0 * math.pi * 1050.0 * t) * env * 0.60
        out.append(s)
    return out


def _synth_countdown_go() -> list[float]:
    duration = 0.28
    count = int(SAMPLE_RATE * duration)
    out = []
    for i in range(count):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 9.0)
        c = math.sin(2.0 * math.pi * 523.25 * t) * 0.40
        e = math.sin(2.0 * math.pi * 659.25 * t) * 0.35
        g = math.sin(2.0 * math.pi * 783.99 * t) * 0.30
        c2 = math.sin(2.0 * math.pi * 1046.50 * t) * 0.20
        out.append((c + e + g + c2) * env * 0.85)
    return out


def _synth_life_lost() -> list[float]:
    duration = 0.22
    count = int(SAMPLE_RATE * duration)
    out = []
    for i in range(count):
        t = i / SAMPLE_RATE
        freq = 180.0 - (t / duration) * 100.0
        env = math.exp(-t * 12.0)
        s = math.sin(2.0 * math.pi * freq * t) * env * 0.80
        out.append(s)
    return out


def _synth_combo() -> list[float]:
    duration = 0.20
    count = int(SAMPLE_RATE * duration)
    out = []
    for i in range(count):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 11.0)
        s1 = math.sin(2.0 * math.pi * 1046.50 * t) * 0.45
        s2 = math.sin(2.0 * math.pi * 1318.51 * t) * 0.40
        s3 = math.sin(2.0 * math.pi * 1567.98 * t) * 0.25
        out.append((s1 + s2 + s3) * env * 0.80)
    return out


def _synth_game_over() -> list[float]:
    duration = 0.45
    count = int(SAMPLE_RATE * duration)
    out = []
    notes = [440.0, 392.0, 349.23, 293.66]
    step_samples = count // len(notes)
    for i in range(count):
        idx = min(len(notes) - 1, i // step_samples)
        freq = notes[idx]
        t = i / SAMPLE_RATE
        t_note = (i % step_samples) / SAMPLE_RATE
        env = math.exp(-t_note * 12.0)
        s = math.sin(2.0 * math.pi * freq * t) * env * 0.70
        out.append(s)
    return out


def _synth_high_score() -> list[float]:
    duration = 0.50
    count = int(SAMPLE_RATE * duration)
    out = []
    notes = [523.25, 659.25, 783.99, 1046.50]
    step_samples = count // len(notes)
    for i in range(count):
        idx = min(len(notes) - 1, i // step_samples)
        freq = notes[idx]
        t = i / SAMPLE_RATE
        t_note = (i % step_samples) / SAMPLE_RATE
        env = math.exp(-t_note * 9.0)
        s = math.sin(2.0 * math.pi * freq * t) * env * 0.75
        out.append(s)
    return out


def _synth_menu_move() -> list[float]:
    duration = 0.035
    count = int(SAMPLE_RATE * duration)
    out = []
    for i in range(count):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 80.0)
        s = math.sin(2.0 * math.pi * 880.0 * t) * env * 0.50
        out.append(s)
    return out


def _synth_menu_select() -> list[float]:
    duration = 0.090
    count = int(SAMPLE_RATE * duration)
    out = []
    for i in range(count):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 25.0)
        s = math.sin(2.0 * math.pi * 1200.0 * t) * env * 0.65
        out.append(s)
    return out


# --------------------------------------------------------------------------
# Music Loops (Stereo, seamless loops)
# --------------------------------------------------------------------------


def _synth_classic_music(duration: float = 6.0) -> tuple[list[float], list[float]]:
    count = int(SAMPLE_RATE * duration)
    left, right = [], []
    bass_notes = [130.81, 164.81, 196.00, 220.00]  # C3, E3, G3, A3
    arp_notes = [261.63, 329.63, 392.00, 523.25, 392.00, 329.63]
    for i in range(count):
        t = i / SAMPLE_RATE
        # Bass pulse
        bass_idx = int((t / duration) * len(bass_notes) * 4) % len(bass_notes)
        bass_freq = bass_notes[bass_idx]
        b_env = 0.40 + 0.15 * math.sin(2.0 * math.pi * 4.0 * t)
        bass = math.sin(2.0 * math.pi * bass_freq * t) * b_env * 0.35

        # Melody arpeggio
        arp_idx = int(t * 8.0) % len(arp_notes)
        arp_freq = arp_notes[arp_idx]
        arp_env = (1.0 - (t * 8.0 % 1.0)) * 0.25
        arp = math.sin(2.0 * math.pi * arp_freq * t) * arp_env

        left.append(bass * 0.8 + arp * 0.7)
        right.append(bass * 0.8 + arp * 0.9)
    return left, right


def _synth_chill_music(duration: float = 8.0) -> tuple[list[float], list[float]]:
    count = int(SAMPLE_RATE * duration)
    left, right = [], []
    chords = [
        (261.63, 329.63, 392.00),  # C Maj
        (220.00, 261.63, 329.63),  # A Min
        (174.61, 220.00, 261.63),  # F Maj
        (196.00, 246.94, 293.66),  # G Maj
    ]
    for i in range(count):
        t = i / SAMPLE_RATE
        chord_idx = int((t / duration) * len(chords)) % len(chords)
        f1, f2, f3 = chords[chord_idx]
        env = 0.50 + 0.30 * math.sin(2.0 * math.pi * (1.0 / (duration / len(chords))) * t)
        s1 = math.sin(2.0 * math.pi * f1 * t) * 0.18
        s2 = math.sin(2.0 * math.pi * f2 * t) * 0.16
        s3 = math.sin(2.0 * math.pi * f3 * t) * 0.14
        left.append((s1 + s2 + s3) * env)
        right.append((s1 * 0.9 + s2 * 1.1 + s3) * env)
    return left, right


def _synth_timed_music(duration: float = 4.0) -> tuple[list[float], list[float]]:
    count = int(SAMPLE_RATE * duration)
    left, right = [], []
    for i in range(count):
        t = i / SAMPLE_RATE
        # Driving 16th note beat
        beat = (t * 8.0) % 1.0
        kick = math.exp(-beat * 25.0) * math.sin(2.0 * math.pi * 90.0 * t) * 0.35
        tick = math.exp(-((t * 16.0) % 1.0) * 45.0) * math.sin(2.0 * math.pi * 3200.0 * t) * 0.12
        bass = math.sin(2.0 * math.pi * 146.83 * t) * 0.22  # D3
        left.append(kick + tick * 0.8 + bass * 0.7)
        right.append(kick + tick * 1.1 + bass * 0.7)
    return left, right


def _synth_practice_music(duration: float = 8.0) -> tuple[list[float], list[float]]:
    count = int(SAMPLE_RATE * duration)
    left, right = [], []
    for i in range(count):
        t = i / SAMPLE_RATE
        # Calm ambient drone
        drone = (
            math.sin(2.0 * math.pi * 110.0 * t) * 0.18
            + math.sin(2.0 * math.pi * 220.0 * t) * 0.12
            + math.sin(2.0 * math.pi * 330.0 * t) * 0.08
        )
        l_mod = 0.5 + 0.2 * math.sin(2.0 * math.pi * 0.25 * t)
        r_mod = 0.5 + 0.2 * math.cos(2.0 * math.pi * 0.25 * t)
        left.append(drone * l_mod)
        right.append(drone * r_mod)
    return left, right


# --------------------------------------------------------------------------
# Weapon SFX Synthesizers (Polished Target-Range Arcade Aesthetic)
# --------------------------------------------------------------------------


def _synth_fire_pistol() -> list[float]:
    """Sharp, light, precision pistol crack with fast transient."""
    duration = 0.08
    count = int(SAMPLE_RATE * duration)
    out = []
    for i in range(count):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 52.0)
        snap = math.sin(2.0 * math.pi * 1650.0 * (1.0 - t * 4.0) * t) * 0.65
        body = math.sin(2.0 * math.pi * 310.0 * t) * 0.45
        out.append((snap + body) * env * 0.90)
    return out


def _synth_fire_rifle() -> list[float]:
    """Tight, snappy, rapid assault rifle crack for fast-paced firing."""
    duration = 0.065
    count = int(SAMPLE_RATE * duration)
    out = []
    for i in range(count):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 62.0)
        crack = math.sin(2.0 * math.pi * 2100.0 * (1.0 - t * 5.0) * t) * 0.70
        thump = math.sin(2.0 * math.pi * 420.0 * t) * 0.40
        out.append((crack + thump) * env * 0.90)
    return out


def _synth_fire_shotgun() -> list[float]:
    """Heavy pump-shotgun blast: deep sub-bass thump + multi-frequency pellet scatter."""
    duration = 0.19
    count = int(SAMPLE_RATE * duration)
    out = []
    for i in range(count):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 19.0)
        boom = math.sin(2.0 * math.pi * 110.0 * math.exp(-t * 8.0) * t) * 0.75
        scatter1 = math.sin(2.0 * math.pi * 920.0 * t) * 0.25
        scatter2 = math.sin(2.0 * math.pi * 1480.0 * t) * 0.20
        out.append((boom + scatter1 + scatter2) * env * 0.95)
    return out


def _synth_fire_sniper() -> list[float]:
    """Heavy supersonic high-caliber sniper discharge with resounding acoustic boom."""
    duration = 0.29
    count = int(SAMPLE_RATE * duration)
    out = []
    for i in range(count):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 8.5)
        snap = math.sin(2.0 * math.pi * 2600.0 * math.exp(-t * 32.0) * t) * 0.55
        thump = math.sin(2.0 * math.pi * 85.0 * t) * 0.70
        sub_tail = math.sin(2.0 * math.pi * 190.0 * t) * 0.25
        out.append((snap + thump + sub_tail) * env * 0.95)
    return out


def _synth_reload_start() -> list[float]:
    """Dual mechanical magazine slide ejection/insertion click."""
    duration = 0.12
    count = int(SAMPLE_RATE * duration)
    out = []
    for i in range(count):
        t = i / SAMPLE_RATE
        env = math.exp(-((t - 0.04) ** 2) * 900.0) if t > 0.02 else math.exp(-t * 45.0)
        click = math.sin(2.0 * math.pi * 1750.0 * t) * 0.6 + math.sin(2.0 * math.pi * 880.0 * t) * 0.4
        out.append(click * env * 0.75)
    return out


def _synth_reload_done() -> list[float]:
    """Crisp, satisfying bolt chamber lock snap."""
    duration = 0.13
    count = int(SAMPLE_RATE * duration)
    out = []
    for i in range(count):
        t = i / SAMPLE_RATE
        env1 = math.exp(-t * 45.0) * 0.5
        env2 = math.exp(-max(0.0, t - 0.04) * 55.0) * 0.75 if t >= 0.04 else 0.0
        click1 = math.sin(2.0 * math.pi * 1350.0 * t) * env1
        click2 = math.sin(2.0 * math.pi * 2400.0 * t) * env2
        out.append((click1 + click2) * 0.85)
    return out


def _synth_empty_click() -> list[float]:
    """Dry metallic trigger hammer click when magazine is empty."""
    duration = 0.045
    count = int(SAMPLE_RATE * duration)
    out = []
    for i in range(count):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 85.0)
        click = math.sin(2.0 * math.pi * 3100.0 * t) * 0.7 + math.sin(2.0 * math.pi * 4600.0 * t) * 0.3
        out.append(click * env * 0.70)
    return out


# --------------------------------------------------------------------------
# Asset Generation & Verification
# --------------------------------------------------------------------------


def ensure_audio_assets(sfx_dir: Path = settings.AUDIO_SFX_DIR, music_dir: Path = settings.AUDIO_MUSIC_DIR) -> None:
    """Generate all default SFX and music WAV files if not already present."""
    sfx_dir.mkdir(parents=True, exist_ok=True)
    music_dir.mkdir(parents=True, exist_ok=True)

    sfx_map = {
        "pinch.wav": _synth_pinch,
        "fire_pistol.wav": _synth_fire_pistol,
        "fire_rifle.wav": _synth_fire_rifle,
        "fire_shotgun.wav": _synth_fire_shotgun,
        "fire_sniper.wav": _synth_fire_sniper,
        "reload_start.wav": _synth_reload_start,
        "reload_done.wav": _synth_reload_done,
        "empty_click.wav": _synth_empty_click,
        "bubble_hit.wav": _synth_bubble_hit,
        "bubble_hit_small.wav": _synth_bubble_hit_small,
        "bubble_hit_large.wav": _synth_bubble_hit_large,
        "bubble_hit_golden.wav": _synth_bubble_hit_golden,
        "bubble_miss.wav": _synth_bubble_miss,
        "bubble_escape.wav": _synth_bubble_escape,
        "countdown_tick.wav": _synth_countdown_tick,
        "countdown_go.wav": _synth_countdown_go,
        "life_lost.wav": _synth_life_lost,
        "combo.wav": _synth_combo,
        "combo_streak.wav": _synth_combo_streak,
        "pause.wav": _synth_pause,
        "game_over.wav": _synth_game_over,
        "high_score.wav": _synth_high_score,
        "menu_move.wav": _synth_menu_move,
        "menu_select.wav": _synth_menu_select,
    }

    for filename, synth_fn in sfx_map.items():
        file_path = sfx_dir / filename
        if not file_path.exists() or file_path.stat().st_size == 0:
            samples = synth_fn()
            _write_wav_mono(file_path, samples)

    music_map = {
        "classic.wav": _synth_classic_music,
        "chill.wav": _synth_chill_music,
        "timed.wav": _synth_timed_music,
        "practice.wav": _synth_practice_music,
    }

    for filename, synth_fn in music_map.items():
        file_path = music_dir / filename
        if not file_path.exists() or file_path.stat().st_size == 0:
            left, right = synth_fn()
            _write_wav_stereo(file_path, left, right)
