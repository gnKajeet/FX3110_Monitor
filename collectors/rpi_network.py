"""
Raspberry Pi network connectivity collector.
"""
import re
import socket
import subprocess
from typing import Dict, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from .base import NetworkCollector


class RPiNetworkCollector(NetworkCollector):
    """Collector for Raspberry Pi network diagnostics and connectivity testing."""

    def __init__(self, public_ip_urls: list = None):
        """
        Initialize network collector.

        Args:
            public_ip_urls: List of URLs to check for public IP
        """
        self.public_ip_urls = public_ip_urls or [
            "https://ifconfig.me/ip",
            "https://api.ipify.org",
            "https://checkip.amazonaws.com",
        ]

    def ping(self, dest: str, interface: Optional[str] = None) -> Dict:
        """
        Ping a destination and return metrics.

        Args:
            dest: Destination IP or hostname
            interface: Optional interface to bind to

        Returns:
            Dict with success, latency_ms, source_ip
        """
        cmd = ["ping", "-c", "1"]
        if interface:
            cmd.extend(["-I", interface])
        cmd.append(dest)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            success = result.returncode == 0

            # Extract latency
            latency_ms = None
            if success:
                match = re.search(r"time[=<]\s*(\d+(?:\.\d+)?)\s*ms", result.stdout)
                if match:
                    latency_ms = int(float(match.group(1)))

            # Get source IP
            source_ip = self._get_source_ip(dest)

            return {
                "success": success,
                "latency_ms": latency_ms,
                "source_ip": source_ip,
            }
        except Exception:
            return {
                "success": False,
                "latency_ms": None,
                "source_ip": "",
            }

    def get_active_interface(self, dest: str) -> str:
        """
        Determine which network interface would be used to reach dest.

        Args:
            dest: Destination IP or hostname

        Returns:
            Interface name (e.g., "eth0", "wlan0") or "unknown"
        """
        try:
            result = subprocess.run(
                ["ip", "route", "get", dest],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                match = re.search(r"\bdev\s+(\S+)", result.stdout)
                if match:
                    return match.group(1)
        except Exception:
            pass
        return "unknown"

    def get_public_ip(self) -> Optional[str]:
        """
        Get the public IP address.

        Returns:
            Public IP address as string, or None if unavailable
        """
        headers = {"User-Agent": "FX3110-Monitor/2.0"}
        for url in self.public_ip_urls:
            try:
                req = Request(url, headers=headers)
                with urlopen(req, timeout=3) as resp:
                    ip = resp.read().decode("utf-8", errors="replace").strip()
                    # Basic sanity check: IPv4 or IPv6
                    if ip and (":" in ip or re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip)):
                        return ip
            except (URLError, HTTPError, TimeoutError, OSError):
                continue
        return None

    def _get_source_ip(self, dest: str) -> str:
        """Get the local IP that would be used to reach dest."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((dest, 80))
            source_ip = s.getsockname()[0]
            s.close()
            return source_ip
        except Exception:
            return ""
