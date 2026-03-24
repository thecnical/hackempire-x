"""
TLS certificate manager for HackEmpire X web interface.

Generates a self-signed certificate for HTTPS if one does not already exist.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def ensure_tls_cert(base_dir: str = ".hackempire/tls") -> tuple[str, str]:
    """Ensure a self-signed TLS certificate exists, generating one if needed.

    Args:
        base_dir: Directory where cert.pem and key.pem are stored.

    Returns:
        (cert_path, key_path) as strings.

    Raises:
        RuntimeError: If openssl is not available or certificate generation fails.
    """
    cert_path = os.path.join(base_dir, "cert.pem")
    key_path = os.path.join(base_dir, "key.pem")

    # Reuse existing cert/key if both already present
    if os.path.isfile(cert_path) and os.path.isfile(key_path):
        return cert_path, key_path

    # Create directory if needed
    Path(base_dir).mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            "openssl", "req",
            "-x509",
            "-newkey", "rsa:4096",
            "-keyout", key_path,
            "-out", cert_path,
            "-days", "365",
            "-nodes",
            "-subj", "/CN=hackempire",
        ],
        shell=False,
        capture_output=True,
    )

    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace").strip()
        raise RuntimeError(
            f"Failed to generate TLS certificate using openssl. "
            f"Ensure openssl is installed and accessible. Details: {stderr}"
        )

    return cert_path, key_path
