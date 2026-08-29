"""High-performance, lightweight particle effects for target destruction and hit flashes."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import pygame

from config import settings
from game.bubble import BubbleType


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    radius: float
    color: tuple[int, int, int]
    created_at: float
    expires_at: float
    shape: str = "circle"

    def is_alive(self, now: float) -> bool:
        return now < self.expires_at

    def update(self, delta_seconds: float) -> None:
        self.x += self.vx * delta_seconds
        self.y += self.vy * delta_seconds
        # Gentle drag
        self.vx *= 0.92
        self.vy *= 0.92


@dataclass
class TargetHitFlash:
    x: float
    y: float
    radius: float
    created_at: float
    expires_at: float

    def is_alive(self, now: float) -> bool:
        return now < self.expires_at


@dataclass
class Shockwave:
    x: float
    y: float
    max_radius: float
    color: tuple[int, int, int]
    created_at: float
    expires_at: float
    width: int = 2

    def is_alive(self, now: float) -> bool:
        return now < self.expires_at


class ParticleSystem:
    """Bounded, memory-friendly particle emitter and renderer."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng = rng or random.Random()
        self._particles: list[Particle] = []
        self._flashes: list[TargetHitFlash] = []
        self._shockwaves: list[Shockwave] = []

    def clear(self) -> None:
        self._particles.clear()
        self._flashes.clear()
        self._shockwaves.clear()

    def emit_target_burst(
        self,
        x: float,
        y: float,
        radius_or_type: float | BubbleType = 30.0,
        target_type: BubbleType | None = None,
        now: float = 0.0,
    ) -> None:
        """Create tailored hit flash, 6-12 small particles, and subtle shockwave on target hit."""
        if isinstance(radius_or_type, BubbleType):
            actual_type = radius_or_type
            actual_radius = 30.0
        else:
            actual_radius = float(radius_or_type)
            actual_type = target_type or BubbleType.NORMAL

        # 1. Hit Flash (White -> Orange -> Disappear over 0.12s)
        self._flashes.append(
            TargetHitFlash(
                x=x,
                y=y,
                radius=actual_radius,
                created_at=now,
                expires_at=now + settings.TARGET_HIT_FLASH_SECONDS,
            )
        )

        # 2. Minimal 6-12 particles
        if actual_type is BubbleType.SMALL:
            count = self._rng.randint(6, 8)
            lifespan = 0.28
            speed_range = (100.0, 200.0)
            rad_range = (2.0, 3.2)
            colors = [(80, 235, 255), (190, 250, 255), (255, 255, 255)]
            shockwave_rad = 28.0
            shock_col = (110, 245, 255)
        elif actual_type is BubbleType.LARGE:
            count = self._rng.randint(8, 12)
            lifespan = 0.38
            speed_range = (60.0, 150.0)
            rad_range = (2.5, 4.5)
            colors = [(35, 110, 195), (65, 150, 235), (140, 205, 255)]
            shockwave_rad = 48.0
            shock_col = (75, 160, 245)
        elif actual_type is BubbleType.GOLDEN:
            count = self._rng.randint(9, 12)
            lifespan = 0.40
            speed_range = (80.0, 180.0)
            rad_range = (2.5, 4.0)
            colors = [(255, 215, 50), (255, 240, 130), (255, 170, 20), (255, 255, 255)]
            shockwave_rad = 42.0
            shock_col = (255, 225, 80)
        else:  # NORMAL
            count = self._rng.randint(7, 10)
            lifespan = 0.32
            speed_range = (70.0, 160.0)
            rad_range = (2.2, 3.8)
            colors = [(55, 170, 255), (105, 205, 255), (220, 245, 255)]
            shockwave_rad = 36.0
            shock_col = (95, 210, 255)

        for _ in range(count):
            if len(self._particles) >= settings.MAX_ACTIVE_PARTICLES:
                break
            angle = self._rng.uniform(0, 2 * math.pi)
            speed = self._rng.uniform(*speed_range)
            p_rad = self._rng.uniform(*rad_range)
            color = self._rng.choice(colors)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            particle = Particle(
                x=x,
                y=y,
                vx=vx,
                vy=vy,
                radius=p_rad,
                color=color,
                created_at=now,
                expires_at=now + lifespan * self._rng.uniform(0.8, 1.2),
                shape="diamond" if actual_type is BubbleType.GOLDEN else "circle",
            )
            self._particles.append(particle)

        # 3. Expanding shockwave ring
        if len(self._shockwaves) < 25:
            self._shockwaves.append(
                Shockwave(
                    x=x,
                    y=y,
                    max_radius=shockwave_rad,
                    color=shock_col,
                    created_at=now,
                    expires_at=now + lifespan * 0.7,
                )
            )

    def update(self, delta_seconds: float, now: float) -> None:
        """Update physics and prune dead particles and flashes."""
        for p in self._particles:
            p.update(delta_seconds)
        self._particles = [p for p in self._particles if p.is_alive(now)]
        self._flashes = [f for f in self._flashes if f.is_alive(now)]
        self._shockwaves = [sw for sw in self._shockwaves if sw.is_alive(now)]

    def draw(self, screen: pygame.Surface, now: float) -> None:
        """Render target hit flashes, shockwaves, and particles with smooth fade."""
        # 1. Draw Hit Flashes (White -> Orange -> Fade)
        for f in self._flashes:
            dur = max(1e-6, f.expires_at - f.created_at)
            prog = min(1.0, max(0.0, (now - f.created_at) / dur))
            r = max(2, round(f.radius * (1.0 + prog * 0.15)))
            alpha = max(0, min(255, round((1.0 - prog) * 240)))
            if alpha > 0:
                flash_surf = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
                if prog < 0.35:
                    col = (255, 255, 255, alpha)
                else:
                    fade = (prog - 0.35) / 0.65
                    r_c = round(255 * (1.0 - fade * 0.1))
                    g_c = round(255 - fade * 115)
                    b_c = round(255 - fade * 215)
                    col = (r_c, max(0, g_c), max(0, b_c), alpha)
                pygame.draw.circle(flash_surf, col, (r + 2, r + 2), r)
                screen.blit(flash_surf, (round(f.x - r - 2), round(f.y - r - 2)))

        # 2. Draw shockwaves
        for sw in self._shockwaves:
            dur = max(1e-6, sw.expires_at - sw.created_at)
            prog = min(1.0, max(0.0, (now - sw.created_at) / dur))
            radius = round(sw.max_radius * prog)
            alpha = max(0, min(255, round((1.0 - prog) * 200)))
            if radius > 1 and alpha > 0:
                ring_surf = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
                r_col = (*sw.color, alpha)
                pygame.draw.circle(ring_surf, r_col, (radius + 2, radius + 2), radius, sw.width)
                screen.blit(ring_surf, (round(sw.x - radius - 2), round(sw.y - radius - 2)))

        # 3. Draw particles
        for p in self._particles:
            dur = max(1e-6, p.expires_at - p.created_at)
            prog = min(1.0, max(0.0, (now - p.created_at) / dur))
            alpha = max(0, min(255, round((1.0 - prog) * 255)))
            rad = max(1, round(p.radius * (1.0 - prog * 0.4)))
            if alpha > 0 and rad >= 1:
                p_surf = pygame.Surface((rad * 2 + 2, rad * 2 + 2), pygame.SRCALPHA)
                col = (*p.color, alpha)
                if p.shape == "diamond":
                    cx, cy = rad + 1, rad + 1
                    pts = [(cx, cy - rad), (cx + rad, cy), (cx, cy + rad), (cx - rad, cy)]
                    pygame.draw.polygon(p_surf, col, pts)
                else:
                    pygame.draw.circle(p_surf, col, (rad + 1, rad + 1), rad)
                screen.blit(p_surf, (round(p.x - rad - 1), round(p.y - rad - 1)))
