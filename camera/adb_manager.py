"""ADB USB reverse port forwarding manager for HANDSHOT (Phase 13)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


class ADBManager:
    """Manages Android Debug Bridge (ADB) device detection and USB reverse port forwarding."""

    def __init__(self, port: int = 8088) -> None:
        self.port = port
        self.adb_bin = self._find_adb()
        self.device_serial: str | None = None
        self.device_authorized: bool = False
        self.reverse_active: bool = False

    @staticmethod
    def _find_adb() -> str | None:
        """Locate the adb executable across PATH, WinGet, and Android SDK directories."""
        # 1. Check system PATH
        which_path = shutil.which("adb")
        if which_path:
            return which_path

        # 2. Check WinGet & Android SDK paths
        local_app_data = Path(os.environ.get("LOCALAPPDATA", "C:/Users/saswa/AppData/Local"))
        user_profile = Path(os.environ.get("USERPROFILE", "C:/Users/saswa"))

        candidates = [
            local_app_data / "Microsoft" / "WinGet" / "Packages" / "Google.PlatformTools_Microsoft.Winget.Source_8wekyb3d8bbwe" / "platform-tools" / "adb.exe",
            local_app_data / "Android" / "Sdk" / "platform-tools" / "adb.exe",
            local_app_data / "Android" / "platform-tools" / "adb.exe",
            user_profile / "AppData" / "Local" / "Android" / "Sdk" / "platform-tools" / "adb.exe",
            Path("C:/Android/platform-tools/adb.exe"),
            Path("C:/platform-tools/adb.exe"),
            Path("C:/Program Files/Android/platform-tools/adb.exe"),
        ]

        for c in candidates:
            if c.exists():
                return str(c)

        # 3. Search local_app_data for adb.exe as fallback
        try:
            for p in (local_app_data / "Microsoft" / "WinGet" / "Packages").rglob("adb.exe"):
                if p.exists():
                    return str(p)
        except Exception:
            pass

        return None

    @property
    def is_available(self) -> bool:
        return self.adb_bin is not None

    def get_connected_devices(self) -> list[dict[str, str]]:
        """Return list of connected Android devices and their authorization status."""
        if not self.adb_bin:
            return []

        try:
            res = subprocess.run(
                [self.adb_bin, "devices"],
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            if res.returncode != 0:
                return []

            devices = []
            for line in res.stdout.splitlines():
                line = line.strip()
                if not line or line.startswith("List of devices") or line.startswith("*"):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    devices.append({"serial": parts[0], "status": parts[1]})
            return devices
        except Exception:
            return []

    def setup_reverse(self) -> bool:
        """Establish adb reverse tcp:<port> tcp:<port> for connected Android device."""
        if not self.adb_bin:
            return False

        devices = self.get_connected_devices()
        authorized = [d for d in devices if d["status"] == "device"]

        if not authorized:
            self.device_serial = devices[0]["serial"] if devices else None
            self.device_authorized = False
            self.reverse_active = False
            return False

        self.device_serial = authorized[0]["serial"]
        self.device_authorized = True

        try:
            cmd = [self.adb_bin, "reverse", f"tcp:{self.port}", f"tcp:{self.port}"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5.0)
            if res.returncode == 0:
                self.reverse_active = True
                return True
        except Exception:
            pass

        self.reverse_active = False
        return False

    def remove_reverse(self) -> None:
        """Clean up reverse port mapping on shutdown."""
        if not self.adb_bin or not self.reverse_active:
            return

        try:
            cmd = [self.adb_bin, "reverse", "--remove", f"tcp:{self.port}"]
            subprocess.run(cmd, capture_output=True, text=True, timeout=3.0)
        except Exception:
            pass
        self.reverse_active = False

    def get_status(self) -> dict[str, object]:
        """Return current ADB diagnostic dictionary."""
        devices = self.get_connected_devices()
        authorized = any(d["status"] == "device" for d in devices)
        return {
            "adb_available": self.is_available,
            "adb_path": self.adb_bin,
            "devices_found": len(devices),
            "device_serial": self.device_serial or (devices[0]["serial"] if devices else None),
            "device_authorized": authorized,
            "reverse_active": self.reverse_active,
            "forwarded_port": self.port,
        }
