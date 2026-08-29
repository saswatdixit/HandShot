"""High-performance, lightweight particle effects for target destruction and celebrations."""

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
        # Gentle air resistance drag
        self.vx *= 0.94
        self.vy *= 0.94


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
        self._shockwaves: list[Shockwave] = []

    def clear(self) -> None:
        self._particles.clear()
        self._shockwaves.clear()

    def emit_target_burst(self, x: float, y: float, target_type: BubbleType, now: float) -> None:
        """Create a tailored burst of particles and shockwaves on target hit."""
        if target_type is BubbleType.SMALL:
            count = settings.PARTICLE_COUNT_SMALL
            lifespan = settings.PARTICLE_LIFESPAN_NORMAL * 0.8
            speed_range = (120.0, 240.0)
            rad_range = (2.0, 3.5)
            colors = [(80, 235, 255), (190, 250, 255), (255, 255, 255)]
            shockwave_rad = 32.0
            shock_col = (110, 245, 255)
        elif target_type is BubbleType.LARGE:
            count = settings.PARTICLE_COUNT_LARGE
            lifespan = settings.PARTICLE_LIFESPAN_NORMAL * 1.2
            speed_range = (60.0, 160.0)
            rad_range = (3.5, 6.0)
            colors = [(35, 110, 195), (65, 150, 235), (140, 205, 255)]
            shockwave_rad = 56.0
            shock_col = (75, 160, 245)
        elif target_type is BubbleType.GOLDEN:
            count = settings.PARTICLE_COUNT_GOLDEN
            lifespan = settings.PARTICLE_LIFESPAN_GOLDEN
            speed_range = (90.0, 220.0)
            rad_range = (2.5, 5.0)
            colors = [(255, 215, 50), (255, 240, 130), (255, 170, 20), (255, 255, 255)]
            shockwave_rad = 50.0
            shock_col = (255, 225, 80)
        else:  # NORMAL
            count = settings.PARTICLE_COUNT_NORMAL
            lifespan = settings.PARTICLE_LIFESPAN_NORMAL
            speed_range = (80.0, 190.0)
            rad_range = (2.5, 4.5)
            colors = [(55, 170, 255), (105, 205, 255), (220, 245, 255)]
            shockwave_rad = 42.0
            shock_col = (95, 210, 255)

        # Spawn radial particles
        for _ in range(count):
            if len(self._particles) >= settings.MAX_ACTIVE_PARTICLES:
                break
            angle = self._rng.uniform(0, 2 * math.pi)
            speed = self._rng.uniform(*speed_range)
            radius = self._rng.uniform(*rad_range)
            color = self._rng.choice(colors)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            particle = Particle(
                x=x,
                y=y,
                vx=vx,
                vy=vy,
                radius=radius,
                color=color,
                created_at=now,
                expires_at=now + lifespan * self._rng.uniform(0.75, 1.25),
                shape="diamond" if target_type is BubbleType.GOLDEN else "circle",
            )
            self._particles.append(particle)

        # Spawn expanding shockwave ring
        if len(self._shockwaves) < 30:
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
        """Update physics and prune dead particles."""
        for p in self._particles:
            p.update(delta_seconds)
        self._particles = [p for p in self._particles if p.is_alive(now)]
        self._shockwaves = [sw for sw in self._shockwaves if sw.is_alive(now)]

    def draw(self, screen: pygame.Surface, now: float) -> None:
        """Render shockwaves and particles with smooth fade."""
        # Draw shockwaves
        for sw in self._shockwaves:
            duration = max(1e-6, sw.expires_at - sw.created_at)
            progress = min(1.0, max(0.0, (now - sw.created_at) / duration))
            radius = round(sw.max_radius * progress)
            alpha = max(0, min(255, round((1.0 - progress) * 220)))
            if radius > 1 and alpha > 0:
                # Create subtle alpha circle ring
                ring_surf = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
                r_col = (*sw.color, alpha)
                pygame.draw.circle(ring_surf, r_col, (radius + 2, radius + 2), radius, sw.width)
                screen.blit(ring_surf, (round(sw.x - radius - 2), round(sw.y - radius - 2)))

        # Draw particles
        for p in self._particles:
            duration = max(1e-6, p.expires_at - p.created_at)
            progress = min(1.0, max(0.0, (now - p.created_at) / duration))
            alpha = max(0, min(255, round((1.0 - progress) * 255)))
            rad = max(1, round(p.radius * (1.0 - progress * 0.4)))
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
