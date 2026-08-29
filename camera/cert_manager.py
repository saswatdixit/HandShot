"""Development SSL Certificate Authority & Server Certificate Manager for HANDSHOT (Phase 13)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

CERT_DIR = Path(__file__).parent / "certs"
CA_CERT_FILE = CERT_DIR / "ca.crt"
CA_KEY_FILE = CERT_DIR / "ca.key"
SERVER_CERT_FILE = CERT_DIR / "cert.pem"
SERVER_KEY_FILE = CERT_DIR / "key.pem"
SERVER_CSR_FILE = CERT_DIR / "server.csr"
SERVER_EXT_FILE = CERT_DIR / "server_ext.cnf"


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
    """Ensure a valid Root CA and Server Certificate with SAN containing lan_ip are present."""
    CERT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Generate Root CA if missing
    if not CA_CERT_FILE.exists() or not CA_KEY_FILE.exists() or CA_CERT_FILE.stat().st_size == 0:
        cmd_ca = [
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", str(CA_KEY_FILE),
            "-out", str(CA_CERT_FILE),
            "-days", "3650",
            "-subj", "/CN=Handshot Local CA/O=Handshot/OU=Development",
        ]
        res_ca = subprocess.run(cmd_ca, capture_output=True, text=True, timeout=10.0)
        if res_ca.returncode != 0 or not CA_CERT_FILE.exists():
            raise RuntimeError(f"Failed to generate Root CA certificate:\n{res_ca.stderr}")

    # 2. Return existing server cert if it's already valid for current LAN IP
    if SERVER_CERT_FILE.exists() and SERVER_KEY_FILE.exists() and is_cert_valid_for_ip(SERVER_CERT_FILE, lan_ip):
        return SERVER_CERT_FILE, SERVER_KEY_FILE

    # 3. Create extension config with SAN for current LAN IP, loopback, and local hostnames
    ext_content = f"""authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
subjectAltName = @alt_names

[alt_names]
IP.1 = {lan_ip}
IP.2 = 127.0.0.1
DNS.1 = localhost
DNS.2 = handshot.local
"""
    SERVER_EXT_FILE.write_text(ext_content)

    # 4. Generate Server Key & CSR
    cmd_csr = [
        "openssl", "req", "-newkey", "rsa:2048", "-nodes",
        "-keyout", str(SERVER_KEY_FILE),
        "-out", str(SERVER_CSR_FILE),
        "-subj", f"/CN={lan_ip}/O=Handshot/OU=Server",
    ]
    res_csr = subprocess.run(cmd_csr, capture_output=True, text=True, timeout=10.0)
    if res_csr.returncode != 0:
        raise RuntimeError(f"Failed to generate Server CSR:\n{res_csr.stderr}")

    # 5. Sign Server CSR with Root CA
    cmd_sign = [
        "openssl", "x509", "-req", "-in", str(SERVER_CSR_FILE),
        "-CA", str(CA_CERT_FILE),
        "-CAkey", str(CA_KEY_FILE),
        "-CAcreateserial",
        "-out", str(SERVER_CERT_FILE),
        "-days", "365",
        "-extfile", str(SERVER_EXT_FILE),
    ]
    res_sign = subprocess.run(cmd_sign, capture_output=True, text=True, timeout=10.0)
    if res_sign.returncode != 0 or not SERVER_CERT_FILE.exists():
        raise RuntimeError(f"Failed to sign Server certificate:\n{res_sign.stderr}")

    return SERVER_CERT_FILE, SERVER_KEY_FILE
