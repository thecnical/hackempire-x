from __future__ import annotations

import socket
import subprocess
import time


class TorManager:
    """Manages Tor service lifecycle and proxied connectivity."""

    def start(self) -> bool:
        """Start the Tor service and wait up to 30 seconds for port 9050 to become available."""
        try:
            subprocess.run(["service", "tor", "start"], shell=False, check=False)
            for _ in range(30):
                try:
                    with socket.create_connection(("127.0.0.1", 9050), timeout=1):
                        return True
                except OSError:
                    time.sleep(1)
            return False
        except Exception:
            return False

    def stop(self) -> None:
        """Stop the Tor service."""
        try:
            subprocess.run(["service", "tor", "stop"], shell=False, check=False)
        except Exception:
            pass

    def verify_connectivity(self) -> bool:
        """Verify Tor connectivity via the Tor Project check API."""
        try:
            import requests

            proxies = {
                "http": "socks5h://127.0.0.1:9050",
                "https": "socks5h://127.0.0.1:9050",
            }
            response = requests.get(
                "https://check.torproject.org/api/ip",
                proxies=proxies,
                timeout=10,
            )
            data = response.json()
            return data.get("IsTor") is True
        except Exception:
            return False

    def get_new_identity(self) -> None:
        """Request a new Tor identity via the control port."""
        try:
            with socket.create_connection(("127.0.0.1", 9051), timeout=5) as sock:
                sock.sendall(b'AUTHENTICATE ""\r\n')
                sock.recv(1024)
                sock.sendall(b"SIGNAL NEWNYM\r\n")
                sock.recv(1024)
        except Exception:
            pass

    def wrap_command(self, cmd: list[str]) -> list[str]:
        """Prepend proxychains4 to a command list without mutating the input."""
        return ["proxychains4", "-q"] + list(cmd)
