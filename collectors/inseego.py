"""
Inseego cellular router collector (FX3110, FX2000, etc.)
"""
import re
import json
from typing import Dict, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from .base import CellularCollector


class InseegoCollector(CellularCollector):
    """Collector for Inseego FX-series routers via HTTP/HTML scraping."""

    def __init__(self, base_url: str = "http://192.168.1.1"):
        """
        Initialize Inseego collector.

        Args:
            base_url: Base URL of the device web interface
        """
        self.base_url = base_url.rstrip("/")
        self.status_url = f"{self.base_url}/"
        self.devices_url = f"{self.base_url}/apps_home/devicesrefresh/"

    def _fetch_text(self, url: str, timeout: float = 3.0) -> str:
        """Fetch text content from URL."""
        headers = {"User-Agent": "FX3110-Monitor/2.0", "Accept": "*/*"}
        req = Request(url, headers=headers)
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str, timeout: float = 3.0) -> dict:
        """Fetch and parse JSON from URL."""
        return json.loads(self._fetch_text(url, timeout))

    def _extract_by_id(self, html: str, element_id: str) -> str:
        """Extract inner text from HTML element by ID."""
        pattern = rf'id="{re.escape(element_id)}"\s*[^>]*>\s*([^<]*)\s*<'
        match = re.search(pattern, html, flags=re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def get_signal_metrics(self) -> Dict:
        """Get signal quality metrics from device status page."""
        html = self._fetch_text(self.status_url)
        return {
            "rsrp": self._extract_by_id(html, "internetStatusRSRP") or None,
            "rsrq": self._extract_by_id(html, "internetStatusRSRQ") or None,
            "snr": self._extract_by_id(html, "snr") or None,
            "rssi": None,  # FX3110 doesn't expose RSSI separately
        }

    def get_network_info(self) -> Dict:
        """Get network and carrier information."""
        html = self._fetch_text(self.status_url)
        return {
            "carrier": self._extract_by_id(html, "networkName") or "",
            "technology": self._extract_by_id(html, "technology") or "",
            "band": self._extract_by_id(html, "band") or "",
            "bandwidth": self._extract_by_id(html, "bandwidth") or "",
        }

    def get_connection_status(self) -> Dict:
        """Get WAN connection status."""
        html = self._fetch_text(self.status_url)
        wan_status = self._extract_by_id(html, "internetStatus")
        tech = self._extract_by_id(html, "technology")

        # Determine WAN source from technology field
        wan_source = ""
        if tech:
            wan_source = "Ethernet" if tech.lower() == "ethernet" else "Cellular"

        return {
            "wan_status": wan_status or "",
            "wan_source": wan_source,
            "device_ipv4": self._extract_by_id(html, "internetStatusIPAddress") or "",
        }

    def get_sim_info(self) -> Dict:
        """Get SIM card information."""
        html = self._fetch_text(self.status_url)
        return {
            "apn": self._extract_by_id(html, "internetAPN") or "",
            "iccid": self._extract_by_id(html, "internetInfoICCID") or "",
            "sim_status": self._extract_by_id(html, "simStatus") or "",
        }

    def get_device_info(self) -> Dict:
        """Get device/modem information."""
        # FX3110 doesn't expose detailed modem info via web interface
        return {
            "model": "FX3110",  # Could be detected dynamically
            "manufacturer": "Inseego",
            "firmware": "",
            "imei": "",
            "serial": "",
        }

    def get_connected_devices(self, max_names: int = 5) -> Dict:
        """
        Get list of connected devices.

        Args:
            max_names: Maximum number of device names to return

        Returns:
            Dict with count and comma-separated names
        """
        try:
            data = self._fetch_json(self.devices_url)
            count = data.get("wifiDevicesCount", 0)
            devs = data.get("connectedDevicesList", []) or []

            names = []
            for d in devs:
                name = (d.get("name") or "").strip()
                hostname = (d.get("hostname") or "").strip()
                display = name or hostname or "Unknown"
                names.append(display)

            if max_names and len(names) > max_names:
                names_str = ",".join(names[:max_names]) + f",+{len(names) - max_names} more"
            else:
                names_str = ",".join(names) if names else ""

            return {
                "count": str(count),
                "names": names_str,
            }
        except Exception:
            return {"count": "0", "names": ""}
