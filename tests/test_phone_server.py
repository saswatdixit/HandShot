"""Unit tests for Phase 13 PhoneStreamServer lifecycle, socket binding, endpoints, and idempotency."""

from __future__ import annotations

import json
import socket
import unittest
import urllib.request
import cv2
import numpy as np
import pygame

from camera.phone_server import PhoneStreamServer, get_lan_ip
from camera.qr_generator import QRCode


class PhoneServerLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()

    @classmethod
    def tearDownClass(cls) -> None:
        pygame.quit()

    def test_lan_ip_detection(self) -> None:
        ip = get_lan_ip()
        self.assertIsInstance(ip, str)
        self.assertFalse(ip.startswith("127."))
        self.assertFalse(ip.startswith("169.254."))

    def test_qr_code_generation_and_quiet_zone(self) -> None:
        url = "http://10.59.78.34:8088/"
        qr = QRCode(url)
        self.assertGreater(qr.size, 20)

        surf = qr.to_surface(module_size=6, quiet_zone=4)
        self.assertIsInstance(surf, pygame.Surface)
        self.assertGreater(surf.get_width(), 150)
        self.assertGreater(surf.get_height(), 150)

    def test_server_socket_binding_and_health_diagnostics(self) -> None:
        """Verify that server actively binds to 0.0.0.0 and /health returns comprehensive diagnostics."""
        server = PhoneStreamServer(port=18088)
        self.assertFalse(server.is_running)

        server.start(print_banner=False)
        try:
            self.assertTrue(server.is_running)
            self.assertIn("http://", server.pairing_url)
            self.assertIn(f":{server.port}/", server.pairing_url)

            # Query /health on 127.0.0.1
            health_url = f"http://127.0.0.1:{server.port}/health"
            with urllib.request.urlopen(health_url, timeout=2.0) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(data["status"], "ok")
                self.assertEqual(data["service"], "handshot-phone-camera")
                self.assertEqual(data["port"], server.port)
                self.assertEqual(data["listening_on"], f"0.0.0.0:{server.port}")
                self.assertIn("lan_ip", data)
                self.assertIn("frames_received", data)
                self.assertFalse(data["connected"])

            # Query HTML root /
            with urllib.request.urlopen(f"http://127.0.0.1:{server.port}/", timeout=2.0) as root_resp:
                self.assertEqual(root_resp.status, 200)
                html = root_resp.read().decode("utf-8")
                self.assertIn("HANDSHOT", html)
                self.assertIn("START CAMERA", html)
                self.assertIn("btn-toggle-cam", html)

            # Test Frame Ingestion
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

            frame, seq = server.get_latest_frame()
            self.assertIsNotNone(frame)
            self.assertEqual(frame.shape, (240, 320, 3))
            self.assertGreater(seq, 0)
            self.assertTrue(server.is_connected)
        finally:
            server.stop()
            self.assertFalse(server.is_running)

    def test_duplicate_startup_idempotency(self) -> None:
        """Verify calling start() multiple times does not raise errors or create duplicate threads."""
        server = PhoneStreamServer(port=18089)
        server.start(print_banner=False)
        try:
            thread1 = server._thread
            # Second start should be a safe no-op
            server.start(print_banner=False)
            self.assertEqual(server._thread, thread1)
            self.assertTrue(server.is_running)
        finally:
            server.stop()
            self.assertFalse(server.is_running)

    def test_clean_shutdown_releases_port(self) -> None:
        """Verify that stop() cleanly releases the bound socket so the port can be immediately reused."""
        server1 = PhoneStreamServer(port=18092)
        server1.start(print_banner=False)
        server1.stop()
        self.assertFalse(server1.is_running)

        # Port 18092 should now be free for another server instance
        server2 = PhoneStreamServer(port=18092)
        server2.start(print_banner=False)
        self.assertTrue(server2.is_running)
        self.assertEqual(server2.port, 18092)
        server2.stop()


if __name__ == "__main__":
    unittest.main()
