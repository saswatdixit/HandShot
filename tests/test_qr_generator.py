"""Unit tests for standard-compliant QR Code generation (Phase 13)."""

from __future__ import annotations

import unittest
import pygame
from camera.qr_generator import QRCode


class QRCodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()

    @classmethod
    def tearDownClass(cls) -> None:
        pygame.quit()

    def test_qr_versions_and_matrix_sizes(self) -> None:
        # V2: length <= 32
        qr_v2 = QRCode("http://192.168.1.10:8088/")
        self.assertEqual(qr_v2.size, 25)

        # V3: length > 32
        qr_v3 = QRCode("http://192.168.100.250:8088/phone_camera_stream")
        self.assertEqual(qr_v3.size, 29)

    def test_qr_finder_patterns_integrity(self) -> None:
        qr = QRCode("http://192.168.1.10:8088/")
        m = qr.matrix

        # Top-Left 7x7 finder pattern check
        for r in range(7):
            for c in range(7):
                expected = (
                    r in (0, 6)
                    or c in (0, 6)
                    or (2 <= r <= 4 and 2 <= c <= 4)
                )
                self.assertEqual(m[r][c], expected, f"Finder pattern mismatch at ({r}, {c})")

    def test_qr_surface_rendering_quality(self) -> None:
        qr = QRCode("http://192.168.1.10:8088/")
        surf = qr.to_surface(module_size=8, quiet_zone=4, bg_color=(255, 255, 255), fg_color=(0, 0, 0))
        self.assertIsInstance(surf, pygame.Surface)

        # Dimension should be (25 + 4*2) * 8 = 33 * 8 = 264
        self.assertEqual(surf.get_width(), 264)
        self.assertEqual(surf.get_height(), 264)

        # Quiet zone corners must be white
        self.assertEqual(surf.get_at((0, 0))[:3], (255, 255, 255))
        # Top-left finder module must be black at (4*8, 4*8) = (32, 32)
        self.assertEqual(surf.get_at((32, 32))[:3], (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
