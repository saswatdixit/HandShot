"""Unit tests for Phase 13 PhoneStreamServer lifecycle, ADB USB reverse support, endpoints, and idempotency."""

from __future__ import annotations

import json
import unittest
import urllib.request
from unittest.mock import MagicMock, patch
import cv2
import numpy as np
import pygame

from camera.phone_server import PhoneStreamServer, get_lan_ip, list_network_interfaces
from camera.qr_generator import QRCode


class PhoneServerLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()

    @classmethod
    def tearDownClass(cls) -> None:
        pygame.quit()

    def test_lan_ip_and_interface_detection(self) -> None:
        primary_ip, ifaces = list_network_interfaces()
        self.assertIsInstance(primary_ip, str)
        self.assertFalse(primary_ip.startswith("127."))
        self.assertFalse(primary_ip.startswith("169.254."))
        self.assertGreater(len(ifaces), 0)

    def test_qr_code_generation_with_localhost_url(self) -> None:
        url = "http://127.0.0.1:8088/"
        qr = QRCode(url)
        self.assertGreater(qr.size, 20)

        surf = qr.to_surface(module_size=6, quiet_zone=4)
        self.assertIsInstance(surf, pygame.Surface)
        self.assertGreater(surf.get_width(), 150)
        self.assertGreater(surf.get_height(), 150)

    def test_http_server_socket_binding_and_endpoints(self) -> None:
        """Verify that server actively binds to 0.0.0.0 and all endpoints work over HTTP."""
        server = PhoneStreamServer(port=18088)
        self.assertFalse(server.is_running)

        server.start(print_banner=False)
        try:
            self.assertTrue(server.is_running)
            self.assertIn("http://", server.pairing_url)
            self.assertIn(f":{server.port}/", server.pairing_url)

            # 1. Query /health over HTTP
            health_url = f"http://127.0.0.1:{server.port}/health"
            with urllib.request.urlopen(health_url, timeout=3.0) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(data["status"], "ok")
                self.assertEqual(data["service"], "handshot-phone-camera")
                self.assertEqual(data["protocol"], "http")
                self.assertTrue(data["secure_context"])
                self.assertEqual(data["port"], server.port)
                self.assertEqual(data["listening_on"], f"0.0.0.0:{server.port}")
                self.assertIn("lan_ip", data)
                self.assertIn("frames_received", data)
                self.assertFalse(data["connected"])

            # 2. Query /diagnostics over HTTP
            diag_url = f"http://127.0.0.1:{server.port}/diagnostics"
            with urllib.request.urlopen(diag_url, timeout=3.0) as diag_resp:
                self.assertEqual(diag_resp.status, 200)
                diag_data = json.loads(diag_resp.read().decode("utf-8"))
                self.assertEqual(diag_data["service"], "handshot-phone-camera")
                self.assertEqual(diag_data["status"], "RUNNING")
                self.assertIn("network_interfaces", diag_data)

            # 3. Query HTML root / over HTTP
            with urllib.request.urlopen(f"http://127.0.0.1:{server.port}/", timeout=3.0) as root_resp:
                self.assertEqual(root_resp.status, 200)
                html = root_resp.read().decode("utf-8")
                self.assertIn("HANDSHOT", html)
                self.assertIn("START CAMERA", html)
                self.assertIn("btn-toggle-cam", html)
                self.assertIn("Test Server", html)
                self.assertIn("Test Camera", html)

            # 4. Test Frame Ingestion over HTTP POST
            dummy_img = np.zeros((240, 320, 3), dtype=np.uint8)
            cv2.putText(dummy_img, "TEST", (50, 120), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
            _, jpeg_data = cv2.imencode(".jpg", dummy_img)

            post_req = urllib.request.Request(
                f"http://127.0.0.1:{server.port}/api/stream/frame",
                data=jpeg_data.tobytes(),
                headers={"Content-Type": "image/jpeg", "X-Camera-Facing": "environment"},
                method="POST",
            )
            with urllib.request.urlopen(post_req, timeout=3.0) as post_resp:
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
