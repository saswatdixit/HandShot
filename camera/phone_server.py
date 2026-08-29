"""High-performance, low-latency LAN & ADB USB phone streaming server for HANDSHOT (Phase 13)."""

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

from camera.adb_manager import ADBManager

if TYPE_CHECKING:
    pass

HTML_PATH = Path(__file__).parent / "web" / "phone_camera.html"


def list_network_interfaces() -> tuple[str, list[dict[str, str]]]:
    """Enumerate all active non-loopback network interfaces and select the primary reachable IP."""
    primary_ip = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        s.connect(("8.8.8.8", 80))
        primary_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    found_ips: list[str] = []
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127.") and not ip.startswith("169.254."):
                found_ips.append(ip)
    except Exception:
        pass

    if primary_ip and primary_ip not in found_ips and not primary_ip.startswith("127."):
        found_ips.insert(0, primary_ip)

    selected_ip = primary_ip or (found_ips[0] if found_ips else "127.0.0.1")

    interfaces_info: list[dict[str, str]] = []
    for ip in found_ips:
        if ip.startswith("10.") or ip.startswith("192.168.42."):
            iface_type = "USB Tethering / LAN"
        elif ip.startswith("192.168."):
            iface_type = "Wi-Fi / LAN"
        else:
            iface_type = "Local Network"
        interfaces_info.append({"ip": ip, "type": iface_type, "is_primary": str(ip == selected_ip)})

    return selected_ip, interfaces_info


def get_lan_ip() -> str:
    """Return primary active network IP address."""
    primary, _ = list_network_interfaces()
    return primary


class PhoneStreamServer:
    """Manages local HTTP web app serving and real-time mobile frame ingestion via USB/ADB or LAN."""

    _instance: PhoneStreamServer | None = None
    _instance_lock = threading.Lock()

    @classmethod
    def get_instance(cls, port: int = 8088) -> PhoneStreamServer:
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = PhoneStreamServer(port=port)
            return cls._instance

    def __init__(self, port: int = 8088) -> None:
        self.preferred_port = port
        self.port = port
        self.lan_ip, self.interfaces = list_network_interfaces()
        self.adb = ADBManager(port=port)
        self._server: http.server.ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._banner_printed = False

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
    def is_running(self) -> bool:
        return self._running and self._server is not None

    @property
    def is_adb_mode(self) -> bool:
        return self.adb.reverse_active

    @property
    def pairing_url(self) -> str:
        """Return pairing URL: http://127.0.0.1:<port>/ if ADB reverse is active, else http://<LAN_IP>:<port>/"""
        if self.adb.reverse_active:
            return f"http://127.0.0.1:{self.port}/"
        return f"http://{self.lan_ip}:{self.port}/"

    @property
    def is_connected(self) -> bool:
        return (time.perf_counter() - self.last_frame_time) < 3.0

    def refresh_adb(self) -> bool:
        """Probe and configure ADB reverse port mapping."""
        return self.adb.setup_reverse()

    def start(self, print_banner: bool = True) -> None:
        """Start the HTTP server on 0.0.0.0 and establish ADB reverse if device is present."""
        with self._lock:
            if self._running and self._server is not None:
                return

            self.lan_ip, self.interfaces = list_network_interfaces()
            bound = False
            for p in range(self.preferred_port, self.preferred_port + 20):
                try:
                    server = http.server.ThreadingHTTPServer(("0.0.0.0", p), self._make_handler())
                    self.port = p
                    self._server = server
                    self.adb.port = p
                    bound = True
                    break
                except OSError:
                    continue

            if not bound or self._server is None:
                raise RuntimeError(
                    f"Could not bind phone streaming server to ports {self.preferred_port}..{self.preferred_port+20}."
                )

            self._running = True
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True, name="PhoneStreamHTTPServer")
            self._thread.start()

            # Attempt ADB reverse port mapping
            self.adb.setup_reverse()

            if print_banner and not self._banner_printed:
                self._banner_printed = True
                conn_desc = "USB / ADB REVERSE (Native Secure Context)" if self.adb.reverse_active else f"Wi-Fi / LAN ({self.lan_ip})"
                print("\n" + "=" * 64)
                print("  HANDSHOT PHONE CAMERA SERVER ACTIVE")
                print("=" * 64)
                print(f"  Server Status      : RUNNING (0.0.0.0:{self.port})")
                print(f"  Connection Mode    : {conn_desc}")
                print(f"  Webcam Pairing URL : {self.pairing_url}")
                print(f"  Health Check       : http://{self.lan_ip}:{self.port}/health")
                print(f"  Diagnostics Page   : http://{self.lan_ip}:{self.port}/diagnostics")
                print("=" * 64 + "\n")

    def stop(self) -> None:
        """Stop the HTTP server and clean up ADB reverse mappings cleanly."""
        with self._lock:
            self._running = False
            self.adb.remove_reverse()
            if self._server is not None:
                try:
                    self._server.shutdown()
                    self._server.server_close()
                except Exception:
                    pass
                self._server = None
            if self._thread is not None:
                try:
                    self._thread.join(timeout=1.0)
                except Exception:
                    pass
                self._thread = None
            self._banner_printed = False

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
                # Silence normal HTTP request logs to keep console output clean
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
                elif self.path in ("/health", "/api/health"):
                    data = json.dumps({
                        "status": "ok",
                        "service": "handshot-phone-camera",
                        "protocol": "http",
                        "lan_ip": server_inst.lan_ip,
                        "port": server_inst.port,
                        "listening_on": f"0.0.0.0:{server_inst.port}",
                        "pairing_url": server_inst.pairing_url,
                        "connection_mode": "usb_adb" if server_inst.adb.reverse_active else "lan_wifi",
                        "adb_status": server_inst.adb.get_status(),
                        "secure_context": True,
                        "connected": server_inst.is_connected,
                        "fps": round(server_inst.measured_fps, 1),
                        "frames_received": server_inst.frames_received,
                        "facing_mode": server_inst.facing_mode,
                        "client_ip": server_inst.client_ip,
                    }).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(data)
                elif self.path == "/diagnostics":
                    data = json.dumps({
                        "service": "handshot-phone-camera",
                        "status": "RUNNING",
                        "protocol": "HTTP",
                        "listening": f"0.0.0.0:{server_inst.port}",
                        "pairing_url": server_inst.pairing_url,
                        "connection_mode": "USB_ADB" if server_inst.adb.reverse_active else "LAN_WIFI",
                        "adb": server_inst.adb.get_status(),
                        "detected_ip": server_inst.lan_ip,
                        "network_interfaces": server_inst.interfaces,
                        "client_ip": server_inst.client_ip or "None",
                        "connection": "CONNECTED" if server_inst.is_connected else "WAITING_FOR_PHONE",
                        "secure_context": "NATIVE_LOCALHOST" if server_inst.adb.reverse_active else "LAN_ORIGIN",
                        "frames_received": server_inst.frames_received,
                        "fps": round(server_inst.measured_fps, 1),
                        "facing_mode": server_inst.facing_mode,
                    }, indent=2).encode("utf-8")
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
