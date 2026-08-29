"""High-performance, low-latency LAN HTTP phone streaming server for HANDSHOT (Phase 13)."""

from __future__ import annotations

import http.server
import json
import socket
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    pass

HTML_PATH = Path(__file__).parent / "web" / "phone_camera.html"


def get_lan_ip() -> str:
    """Dynamically determine the host computer's active local network LAN IP."""
    # Strategy 1: Connect UDP socket to gateway (no packet sent, determines route interface)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127.") and not ip.startswith("169.254."):
            return ip
    except Exception:
        pass

    # Strategy 2: Probe local hostname addresses
    try:
        hostname = socket.gethostname()
        candidates = socket.gethostbyname_ex(hostname)[2]
        # Prioritize standard LAN subnets (192.168.x.x, 10.x.x.x, 172.16-31.x.x)
        for ip in candidates:
            if ip.startswith("192.168.") or ip.startswith("10."):
                return ip
        for ip in candidates:
            if not ip.startswith("127.") and not ip.startswith("169.254."):
                return ip
    except Exception:
        pass

    return "127.0.0.1"


class PhoneStreamServer:
    """Manages local HTTP web app serving and real-time mobile frame ingestion."""

    def __init__(self, port: int = 8088) -> None:
        self.preferred_port = port
        self.port = port
        self.lan_ip = get_lan_ip()
        self._server: http.server.ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._running = False

        # Ingested Frame State (Single-slot latest-frame-wins)
        self._lock = threading.Lock()
        self._latest_frame: np.ndarray | None = None
        self._sequence = 0
        self.frames_received = 0
        self.last_frame_time = 0.0
        self.facing_mode = "environment"
        self.client_ip: str | None = None
        self.measured_fps = 0.0
        self._fps_window_start = time.perf_counter()
        self._fps_frame_count = 0

    @property
    def pairing_url(self) -> str:
        return f"http://{self.lan_ip}:{self.port}/"

    @property
    def is_connected(self) -> bool:
        return (time.perf_counter() - self.last_frame_time) < 3.0

    def start(self) -> None:
        if self._running:
            return

        # Refresh LAN IP on start
        self.lan_ip = get_lan_ip()

        # Attempt binding to preferred port, scanning upwards on collision
        bound = False
        for p in range(self.preferred_port, self.preferred_port + 20):
            try:
                server = http.server.ThreadingHTTPServer(("0.0.0.0", p), self._make_handler())
                self.port = p
                self._server = server
                bound = True
                break
            except OSError:
                continue

        if not bound or self._server is None:
            raise RuntimeError(
                f"Could not bind phone streaming server to ports {self.preferred_port}..{self.preferred_port+20}"
            )

        self._running = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

        # Print prominent terminal banner for debugging
        print("\n" + "=" * 62)
        print("  HANDSHOT WIRELESS PHONE CAMERA SERVER ACTIVE")
        print("=" * 62)
        print(f"  Webcam Pairing URL : {self.pairing_url}")
        print(f"  Health Check       : http://{self.lan_ip}:{self.port}/health")
        print("  Requirement        : Phone & PC must be on SAME Wi-Fi")
        print("=" * 62 + "\n")

    def stop(self) -> None:
        self._running = False
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def get_latest_frame(self) -> tuple[np.ndarray | None, int]:
        """Return (frame, sequence_id) for latest received mobile camera frame."""
        with self._lock:
            if self._latest_frame is None:
                return None, self._sequence
            return self._latest_frame.copy(), self._sequence

    def _make_handler(self):
        server_inst = self

        class StreamHandler(http.server.BaseHTTPRequestHandler):
            def log_message(self, format: str, *args) -> None:
                # Silence normal HTTP request logs to keep terminal clean
                pass

            def do_GET(self) -> None:
                if self.path in ("/", "/index.html", "/phone"):
                    try:
                        content = HTML_PATH.read_bytes()
                        self.send_response(200)
                        self.send_header("Content-Type", "text/html; charset=utf-8")
                        self.send_header("Content-Length", str(len(content)))
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                        self.end_headers()
                        self.wfile.write(content)
                    except Exception as e:
                        self.send_error(500, f"Error loading phone camera UI: {e}")
                elif self.path == "/health":
                    data = json.dumps({
                        "status": "ok",
                        "service": "handshot-phone-camera",
                        "lan_ip": server_inst.lan_ip,
                        "port": server_inst.port,
                        "connected": server_inst.is_connected,
                        "fps": round(server_inst.measured_fps, 1),
                        "frames_received": server_inst.frames_received,
                    }).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(data)
                else:
                    self.send_error(404, "Not Found")

            def do_POST(self) -> None:
                if self.path == "/api/stream/frame":
                    length = int(self.headers.get("Content-Length", 0))
                    if length <= 0 or length > 5_000_000:
                        self.send_error(400, "Invalid frame payload length")
                        return

                    body = self.rfile.read(length)
                    facing = self.headers.get("X-Camera-Facing", "environment")

                    # Decode JPEG directly in memory
                    nparr = np.frombuffer(body, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                    if frame is not None:
                        now = time.perf_counter()
                        with server_inst._lock:
                            server_inst._latest_frame = frame
                            server_inst._sequence += 1
                            server_inst.frames_received += 1
                            server_inst.last_frame_time = now
                            server_inst.facing_mode = facing
                            server_inst.client_ip = self.client_address[0]

                            server_inst._fps_frame_count += 1
                            if now - server_inst._fps_window_start >= 1.0:
                                server_inst.measured_fps = server_inst._fps_frame_count / (
                                    now - server_inst._fps_window_start
                                )
                                server_inst._fps_frame_count = 0
                                server_inst._fps_window_start = now

                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.end_headers()
                        self.wfile.write(b'{"status":"ok"}')
                    else:
                        self.send_error(422, "Corrupted JPEG frame")
                else:
                    self.send_error(404, "Not Found")

            def do_OPTIONS(self) -> None:
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "*")
                self.end_headers()

        return StreamHandler
