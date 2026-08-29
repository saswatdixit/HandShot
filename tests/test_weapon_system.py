"""Unit tests for the modular weapon system and firing/reloading mechanics."""

import random
import unittest

from game.weapon import (
    ALL_WEAPONS,
    ASSAULT_RIFLE_SPEC,
    PISTOL_SPEC,
    SHOTGUN_SPEC,
    SNIPER_SPEC,
    WeaponSystem,
    WeaponType,
)


class WeaponSystemTests(unittest.TestCase):
    def test_default_weapon_initialization(self) -> None:
        ws = WeaponSystem()
        self.assertEqual(ws.spec.weapon_type, WeaponType.PISTOL)
        self.assertEqual(ws.mag_ammo, 12)
        self.assertEqual(ws.reserve_ammo, 36)
        self.assertFalse(ws.is_reloading)
        self.assertFalse(ws.is_empty)

    def test_weapon_firing_consumes_ammo(self) -> None:
        ws = WeaponSystem()
        self.assertTrue(ws.can_fire(now=0.0))
        pellets = ws.fire(now=0.0, aim_pos=(500.0, 300.0))
        self.assertEqual(len(pellets), 1)
        self.assertEqual(pellets[0], (500.0, 300.0))
        self.assertEqual(ws.mag_ammo, 11)

    def test_fire_cooldown_enforced(self) -> None:
        ws = WeaponSystem(PISTOL_SPEC)  # 0.20s cooldown
        ws.fire(now=0.0, aim_pos=(500.0, 300.0))
        # Attempt to fire at 0.10s (before 0.20s cooldown) -> blocked
        self.assertFalse(ws.can_fire(now=0.10))
        self.assertEqual(ws.fire(now=0.10, aim_pos=(500.0, 300.0)), [])
        # Fire at 0.21s (after cooldown) -> fires
        self.assertTrue(ws.can_fire(now=0.21))
        self.assertEqual(len(ws.fire(now=0.21, aim_pos=(500.0, 300.0))), 1)
        self.assertEqual(ws.mag_ammo, 10)

    def test_shotgun_multi_pellet_generation(self) -> None:
        ws = WeaponSystem(SHOTGUN_SPEC)
        rng = random.Random(42)
        pellets = ws.fire(now=0.0, aim_pos=(600.0, 400.0), rng=rng)
        self.assertEqual(len(pellets), 6)
        # Center pellet must be exact
        self.assertEqual(pellets[0], (600.0, 400.0))
        # Other pellets must disperse within spread radius (38px)
        for p in pellets[1:]:
            dist = ((p[0] - 600.0) ** 2 + (p[1] - 400.0) ** 2) ** 0.5
            self.assertLessEqual(dist, 38.01)

    def test_empty_magazine_prevents_firing(self) -> None:
        ws = WeaponSystem(SNIPER_SPEC)  # 5 rounds
        for i in range(5):
            self.assertTrue(ws.can_fire(now=float(i)))
            ws.fire(now=float(i), aim_pos=(500.0, 300.0))
        self.assertEqual(ws.mag_ammo, 0)
        self.assertTrue(ws.is_empty)
        self.assertFalse(ws.can_fire(now=6.0))
        self.assertEqual(ws.fire(now=6.0, aim_pos=(500.0, 300.0)), [])

    def test_reload_transfers_ammo_after_timer(self) -> None:
        ws = WeaponSystem(PISTOL_SPEC)  # Mag: 12, Res: 36, Reload: 1.2s
        # Fire 4 rounds -> 8 in mag
        for i in range(4):
            ws.fire(now=i * 0.25, aim_pos=(500.0, 300.0))
        self.assertEqual(ws.mag_ammo, 8)

        # Start reload at t=2.0
        self.assertTrue(ws.can_reload())
        self.assertTrue(ws.start_reload(now=2.0))
        self.assertTrue(ws.is_reloading)
        self.assertFalse(ws.can_fire(now=2.5))  # Cannot fire while reloading

        # Update at t=2.6 (0.6s / 1.2s = 50%)
        finished = ws.update(delta_seconds=0.6, now=2.6)
        self.assertFalse(finished)
        self.assertAlmostEqual(ws.reload_progress, 0.50, places=2)
        self.assertEqual(ws.mag_ammo, 8)

        # Update at t=3.25 (1.25s >= 1.2s -> reload complete)
        finished = ws.update(delta_seconds=0.65, now=3.25)
        self.assertTrue(finished)
        self.assertFalse(ws.is_reloading)
        self.assertEqual(ws.mag_ammo, 12)
        self.assertEqual(ws.reserve_ammo, 32)  # 36 - 4 = 32

    def test_cannot_reload_when_full(self) -> None:
        ws = WeaponSystem(PISTOL_SPEC)
        self.assertFalse(ws.can_reload())
        self.assertFalse(ws.start_reload(now=0.0))

    def test_weapon_switch_resets_and_cancels_reload(self) -> None:
        ws = WeaponSystem(PISTOL_SPEC)
        ws.fire(now=0.0, aim_pos=(500.0, 300.0))
        ws.start_reload(now=0.1)
        self.assertTrue(ws.is_reloading)

        # Switch to Assault Rifle
        ws.select_weapon(ASSAULT_RIFLE_SPEC)
        self.assertEqual(ws.spec.weapon_type, WeaponType.ASSAULT_RIFLE)
        self.assertEqual(ws.mag_ammo, 30)
        self.assertEqual(ws.reserve_ammo, 90)
        self.assertFalse(ws.is_reloading)


if __name__ == "__main__":
    unittest.main()
