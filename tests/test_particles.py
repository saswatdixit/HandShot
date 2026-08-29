"""Unit tests for Phase 9 Particle and visual effects system."""

from __future__ import annotations

import random
import unittest

from game.bubble import BubbleType
from game.particles import ParticleSystem


class ParticleSystemTests(unittest.TestCase):
    def test_emit_target_burst_and_update(self) -> None:
        ps = ParticleSystem(rng=random.Random(1))
        self.assertEqual(len(ps._particles), 0)
        self.assertEqual(len(ps._shockwaves), 0)

        # Emit burst for normal target
        ps.emit_target_burst(100.0, 100.0, BubbleType.NORMAL, now=0.0)
        self.assertGreater(len(ps._particles), 0)
        self.assertGreater(len(ps._shockwaves), 0)

        # Update at t = 0.1s -> particles move
        p_init_x = ps._particles[0].x
        ps.update(0.10, now=0.10)
        self.assertNotEqual(ps._particles[0].x, p_init_x)

        # Update at t = 1.0s -> expired particles pruned
        ps.update(0.90, now=1.00)
        self.assertEqual(len(ps._particles), 0)
        self.assertEqual(len(ps._shockwaves), 0)

    def test_golden_target_burst(self) -> None:
        ps = ParticleSystem(rng=random.Random(1))
        ps.emit_target_burst(200.0, 200.0, BubbleType.GOLDEN, now=0.0)
        self.assertGreater(len(ps._particles), 15)
        # Golden targets produce diamond-shaped particles
        self.assertEqual(ps._particles[0].shape, "diamond")

    def test_clear_particles(self) -> None:
        ps = ParticleSystem(rng=random.Random(1))
        ps.emit_target_burst(100.0, 100.0, BubbleType.NORMAL, now=0.0)
        self.assertGreater(len(ps._particles), 0)
        ps.clear()
        self.assertEqual(len(ps._particles), 0)
        self.assertEqual(len(ps._shockwaves), 0)


if __name__ == "__main__":
    unittest.main()
