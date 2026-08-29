"""Unit tests for the modular weapon system, infinite reserves, and Arcade mode."""

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
        self.assertEqual(ws.mag_ammo, 20)
        self.assertEqual(ws.reserve_ammo, -1)
        self.assertEqual(ws.ammo_display_str, "20 / ∞")
        self.assertFalse(ws.is_reloading)
        self.assertFalse(ws.is_empty)

    def test_weapon_firing_consumes_ammo(self) -> None:
        ws = WeaponSystem()
        self.assertTrue(ws.can_fire(now=0.0))
        pellets = ws.fire(now=0.0, aim_pos=(500.0, 300.0))
        self.assertEqual(len(pellets), 1)
        self.assertEqual(pellets[0], (500.0, 300.0))
        self.assertEqual(ws.mag_ammo, 19)

    def test_fire_cooldown_enforced(self) -> None:
        ws = WeaponSystem(PISTOL_SPEC)  # 0.18s cooldown
        ws.fire(now=0.0, aim_pos=(500.0, 300.0))
        # Attempt to fire at 0.08s (before 0.18s cooldown) -> blocked
        self.assertFalse(ws.can_fire(now=0.08))
        self.assertEqual(ws.fire(now=0.08, aim_pos=(500.0, 300.0)), [])
        # Fire at 0.19s (after cooldown) -> fires
        self.assertTrue(ws.can_fire(now=0.19))
        self.assertEqual(len(ws.fire(now=0.19, aim_pos=(500.0, 300.0))), 1)
        self.assertEqual(ws.mag_ammo, 18)

    def test_shotgun_multi_pellet_generation(self) -> None:
        ws = WeaponSystem(SHOTGUN_SPEC)
        rng = random.Random(42)
        pellets = ws.fire(now=0.0, aim_pos=(600.0, 400.0), rng=rng)
        self.assertEqual(len(pellets), 6)
        # Center pellet must be exact
        self.assertEqual(pellets[0], (600.0, 400.0))
        # Other pellets must disperse within spread radius
        for p in pellets[1:]:
            dist = ((p[0] - 600.0) ** 2 + (p[1] - 400.0) ** 2) ** 0.5
            self.assertLessEqual(dist, 36.01)

    def test_empty_magazine_prevents_firing(self) -> None:
        ws = WeaponSystem(SNIPER_SPEC)  # 8 rounds
        for i in range(8):
            self.assertTrue(ws.can_fire(now=float(i)))
            ws.fire(now=float(i), aim_pos=(500.0, 300.0))
        self.assertEqual(ws.mag_ammo, 0)
        self.assertTrue(ws.is_empty)
        self.assertFalse(ws.can_fire(now=10.0))
        self.assertEqual(ws.fire(now=10.0, aim_pos=(500.0, 300.0)), [])

    def test_reload_transfers_ammo_with_infinite_reserves(self) -> None:
        ws = WeaponSystem(PISTOL_SPEC)  # Mag: 20, Res: -1, Reload: 1.1s
        # Fire 4 rounds -> 16 in mag
        for i in range(4):
            ws.fire(now=i * 0.25, aim_pos=(500.0, 300.0))
        self.assertEqual(ws.mag_ammo, 16)

        # Start reload at t=2.0
        self.assertTrue(ws.can_reload())
        self.assertTrue(ws.start_reload(now=2.0))
        self.assertTrue(ws.is_reloading)
        self.assertFalse(ws.can_fire(now=2.5))  # Cannot fire while reloading

        # Update at t=2.55 (0.55s / 1.1s = 50%)
        finished = ws.update(delta_seconds=0.55, now=2.55)
        self.assertFalse(finished)
        self.assertAlmostEqual(ws.reload_progress, 0.50, places=2)
        self.assertEqual(ws.mag_ammo, 16)

        # Update at t=3.15 (1.15s >= 1.1s -> reload complete)
        finished = ws.update(delta_seconds=0.60, now=3.15)
        self.assertTrue(finished)
        self.assertFalse(ws.is_reloading)
        self.assertEqual(ws.mag_ammo, 20)
        self.assertEqual(ws.reserve_ammo, -1)  # Infinite reserve preserved

    def test_arcade_mode_infinite_magazine(self) -> None:
        ws = WeaponSystem(PISTOL_SPEC, infinite_magazine=True, reload_enabled=False)
        self.assertEqual(ws.ammo_display_str, "∞")
        self.assertFalse(ws.is_empty)
        self.assertFalse(ws.can_reload())

        # Fire multiple shots: mag_ammo never depletes
        for i in range(25):
            pellets = ws.fire(now=i * 0.20, aim_pos=(400.0, 300.0))
            self.assertEqual(len(pellets), 1)
        self.assertEqual(ws.mag_ammo, 20)
        self.assertFalse(ws.is_empty)

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
        self.assertEqual(ws.mag_ammo, 60)
        self.assertEqual(ws.reserve_ammo, -1)
        self.assertFalse(ws.is_reloading)


if __name__ == "__main__":
    unittest.main()
