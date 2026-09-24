#!/usr/bin/env python3
"""Cloudflare Tunnel Manager for vPS Share by PSTECH.

Creates zero-configuration public HTTPS tunnels via trycloudflare.com
without requiring open ports, DNS changes, or a Cloudflare account.
"""
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional


def find_cloudflared() -> Optional[Path]:
    """Locate the cloudflared executable across standard system locations."""
    is_windows = platform.system() == "Windows"
    bin_name = "cloudflared.exe" if is_windows else "cloudflared"

    # 1. System PATH
    found = shutil.which(bin_name) or shutil.which("cloudflared")
    if found:
        return Path(found)

    # 2. Known local directories
    candidates = [
        Path.cwd() / bin_name,
        Path.home() / ".cloudflared/bin" / bin_name,
        Path.home() / "bin" / bin_name,
        Path("/usr/local/bin/cloudflared"),
        Path("/usr/bin/cloudflared"),
    ]
    if is_windows:
        candidates.extend([
            Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "cloudflared" / bin_name,
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "cloudflared" / bin_name,
        ])

    for c in candidates:
        if c.is_file() and (is_windows or os.access(c, os.X_OK)):
            return c
    return None


class CloudflareTunnel:
    def __init__(self, port: int, host: str = "127.0.0.1"):
        self.port = port
        self.host = host
        self.process: Optional[subprocess.Popen] = None
        self.tunnel_url: Optional[str] = None
        self.log_file = Path(tempfile.gettempdir()) / f"vps_share_tunnel_{port}.log"

    def start(self, timeout: int = 35) -> str:
        """Launch the tunnel and extract the public https://*.trycloudflare.com URL."""
        bin_path = find_cloudflared()
        if not bin_path:
            raise FileNotFoundError(
                "cloudflared binary not found! Download from:\n"
                "https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
            )

        if self.log_file.exists():
            try:
                self.log_file.unlink()
            except OSError:
                pass

        cmd = [
            str(bin_path),
            "tunnel",
            "--url",
            f"http://{self.host}:{self.port}",
            "--no-autoupdate",
        ]

        log_handle = open(self.log_file, "w", encoding="utf-8", errors="replace")
        self.process = subprocess.Popen(
            cmd,
            stdout=log_handle,
            stderr=log_handle,
        )

        start_time = time.time()
        while time.time() - start_time < timeout:
            time.sleep(1)
            if self.process.poll() is not None:
                log_handle.close()
                err = self.log_file.read_text(encoding="utf-8", errors="replace") if self.log_file.exists() else ""
                raise RuntimeError(f"Cloudflare tunnel process exited unexpectedly:\n{err}")

            if self.log_file.exists():
                try:
                    text = self.log_file.read_text(encoding="utf-8", errors="replace")
                    matches = re.findall(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", text)
                    for u in matches:
                        if "api.trycloudflare.com" not in u:
                            self.tunnel_url = u
                            return self.tunnel_url
                except Exception:
                    pass

        self.stop()
        raise TimeoutError(f"Cloudflare tunnel connection timed out after {timeout}s")

    def stop(self):
        """Cleanly terminate the tunnel process and remove temp files."""
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
        if self.log_file.exists():
            try:
                self.log_file.unlink()
            except OSError:
                pass
