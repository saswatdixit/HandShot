"""Unit tests for Phase 12 QR Code generation, LAN IP detection, and PhoneStreamServer."""

from __future__ import annotations

import unittest
import urllib.request
import cv2
import numpy as np
import pygame

from camera.phone_server import PhoneStreamServer, get_lan_ip
from camera.qr_generator import QRCode


class PhoneServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()

    @classmethod
    def tearDownClass(cls) -> None:
        pygame.quit()

    def test_lan_ip_detection(self) -> None:
        ip = get_lan_ip()
        self.assertIsInstance(ip, str)
        self.assertGreater(len(ip.split(".")), 1)

    def test_qr_code_generation(self) -> None:
        url = "http://192.168.1.50:8088/"
        qr = QRCode(url)
        self.assertGreater(qr.size, 20)

        surf = qr.to_surface(module_size=4)
        self.assertIsInstance(surf, pygame.Surface)
        self.assertGreater(surf.get_width(), 80)
        self.assertGreater(surf.get_height(), 80)

    def test_phone_stream_server_lifecycle_and_frame_post(self) -> None:
        server = PhoneStreamServer(port=18088)
        server.start()
        try:
            self.assertIn("http://", server.pairing_url)
            self.assertFalse(server.is_connected)

            # Test GET / (HTML delivery)
            req = urllib.request.Request(f"http://127.0.0.1:{server.port}/")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                self.assertEqual(resp.status, 200)
                html = resp.read().decode("utf-8")
                self.assertIn("HANDSHOT", html)
                self.assertIn("Mobile Webcam", html)

            # Test POST /api/stream/frame with synthetic JPEG frame
            dummy_img = np.zeros((240, 320, 3), dtype=np.uint8)
            cv2.putText(dummy_img, "TEST", (50, 120), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
            _, jpeg_data = cv2.imencode(".jpg", dummy_img)

            post_req = urllib.request.Request(
                f"http://127.0.0.1:{server.port}/api/stream/frame",
                data=jpeg_data.tobytes(),
                headers={"Content-Type": "image/jpeg", "X-Camera-Facing": "environment"},
                method="POST",
            )
            with urllib.request.urlopen(post_req, timeout=2.0) as post_resp:
                self.assertEqual(post_resp.status, 200)

            # Check latest frame
            frame, seq = server.get_latest_frame()
            self.assertIsNotNone(frame)
            self.assertEqual(frame.shape, (240, 320, 3))
            self.assertGreater(seq, 0)
            self.assertTrue(server.is_connected)
        finally:
            server.stop()


if __name__ == "__main__":
    unittest.main()
