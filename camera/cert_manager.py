"""Development SSL Certificate Manager with Subject Alternative Name (SAN) support for HANDSHOT (Phase 13)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

CERT_DIR = Path(__file__).parent / "certs"
CERT_FILE = CERT_DIR / "cert.pem"
KEY_FILE = CERT_DIR / "key.pem"


def is_cert_valid_for_ip(cert_path: Path, lan_ip: str) -> bool:
    """Check if existing certificate contains the target LAN IP in its Subject Alternative Name."""
    if not cert_path.exists() or cert_path.stat().st_size == 0:
        return False
    try:
        cmd = ["openssl", "x509", "-in", str(cert_path), "-noout", "-text"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5.0)
        if res.returncode == 0:
            out = res.stdout
            if f"IP Address:{lan_ip}" in out or f"IP:{lan_ip}" in out:
                return True
    except Exception:
        pass
    return False


def ensure_dev_certificate(lan_ip: str) -> tuple[Path, Path]:
    """Ensure a valid self-signed SSL certificate with SAN containing lan_ip is present."""
    CERT_DIR.mkdir(parents=True, exist_ok=True)

    if CERT_FILE.exists() and KEY_FILE.exists() and is_cert_valid_for_ip(CERT_FILE, lan_ip):
        return CERT_FILE, KEY_FILE

    # Generate fresh certificate via OpenSSL
    cmd = [
        "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
        "-out", str(CERT_FILE),
        "-keyout", str(KEY_FILE),
        "-days", "365",
        "-subj", f"/CN={lan_ip}",
        "-addext", f"subjectAltName=IP:{lan_ip},IP:127.0.0.1,DNS:localhost",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=10.0)
    if res.returncode != 0 or not CERT_FILE.exists() or not KEY_FILE.exists():
        raise RuntimeError(f"Failed to generate SSL certificate with OpenSSL:\n{res.stderr}")

    return CERT_FILE, KEY_FILE
