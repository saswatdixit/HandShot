"""Unit tests for Phase 13 HTTPS PhoneStreamServer lifecycle, SSL SAN certificates, endpoints, and idempotency."""

from __future__ import annotations

import json
import ssl
import unittest
import urllib.request
import cv2
import numpy as np
import pygame

from camera.cert_manager import ensure_dev_certificate, is_cert_valid_for_ip
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

    def test_dev_certificate_generation_with_san(self) -> None:
        lan_ip = get_lan_ip()
        cert_path, key_path = ensure_dev_certificate(lan_ip)
        self.assertTrue(cert_path.exists())
        self.assertTrue(key_path.exists())
        self.assertGreater(cert_path.stat().st_size, 500)
        self.assertGreater(key_path.stat().st_size, 500)
        self.assertTrue(is_cert_valid_for_ip(cert_path, lan_ip))

    def test_qr_code_generation_with_https_url(self) -> None:
        url = "https://10.59.78.34:8443/"
        qr = QRCode(url)
        self.assertGreater(qr.size, 20)

        surf = qr.to_surface(module_size=6, quiet_zone=4)
        self.assertIsInstance(surf, pygame.Surface)
        self.assertGreater(surf.get_width(), 150)
        self.assertGreater(surf.get_height(), 150)

    def test_https_server_socket_binding_and_health_diagnostics(self) -> None:
        """Verify that server actively binds HTTPS to 0.0.0.0 and /health returns comprehensive diagnostics."""
        server = PhoneStreamServer(port=18443)
        self.assertFalse(server.is_running)

        server.start(print_banner=False)
        ssl_ctx = ssl._create_unverified_context()
        try:
            self.assertTrue(server.is_running)
            self.assertIn("https://", server.pairing_url)
            self.assertIn(f":{server.port}/", server.pairing_url)

            # 1. Query /health on 127.0.0.1 over HTTPS
            health_url = f"https://127.0.0.1:{server.port}/health"
            with urllib.request.urlopen(health_url, context=ssl_ctx, timeout=3.0) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(data["status"], "ok")
                self.assertEqual(data["service"], "handshot-phone-camera")
                self.assertEqual(data["protocol"], "https")
                self.assertTrue(data["secure_context"])
                self.assertEqual(data["port"], server.port)
                self.assertEqual(data["listening_on"], f"0.0.0.0:{server.port}")
                self.assertIn("lan_ip", data)
                self.assertIn("frames_received", data)
                self.assertFalse(data["connected"])

            # 2. Query HTML root / over HTTPS
            with urllib.request.urlopen(f"https://127.0.0.1:{server.port}/", context=ssl_ctx, timeout=3.0) as root_resp:
                self.assertEqual(root_resp.status, 200)
                html = root_resp.read().decode("utf-8")
                self.assertIn("HANDSHOT", html)
                self.assertIn("START CAMERA", html)
                self.assertIn("btn-toggle-cam", html)
                self.assertIn("HTTPS (Secure)", html)

            # 3. Test Frame Ingestion over HTTPS POST
            dummy_img = np.zeros((240, 320, 3), dtype=np.uint8)
            cv2.putText(dummy_img, "TEST", (50, 120), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
            _, jpeg_data = cv2.imencode(".jpg", dummy_img)

            post_req = urllib.request.Request(
                f"https://127.0.0.1:{server.port}/api/stream/frame",
                data=jpeg_data.tobytes(),
                headers={"Content-Type": "image/jpeg", "X-Camera-Facing": "environment"},
                method="POST",
            )
            with urllib.request.urlopen(post_req, context=ssl_ctx, timeout=3.0) as post_resp:
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
        server = PhoneStreamServer(port=18444)
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
        server1 = PhoneStreamServer(port=18445)
        server1.start(print_banner=False)
        server1.stop()
        self.assertFalse(server1.is_running)

        # Port 18445 should now be free for another server instance
        server2 = PhoneStreamServer(port=18445)
        server2.start(print_banner=False)
        self.assertTrue(server2.is_running)
        self.assertEqual(server2.port, 18445)
        server2.stop()


if __name__ == "__main__":
    unittest.main()
