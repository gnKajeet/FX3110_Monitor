"""
Teltonika cellular router collector (RUTM50, RUTX series, etc.)
"""
import re
import json
import subprocess
from typing import Dict, Optional

from .base import CellularCollector


class TeltonikaCollector(CellularCollector):
    """Collector for Teltonika RUT-series routers via SSH/gsmctl."""

    def __init__(
        self,
        ssh_host: str,
        ssh_user: str = "root",
        ssh_port: int = 22,
        ssh_password: Optional[str] = None,
        ssh_key: Optional[str] = None,
        ssh_strict: str = "accept-new",
        ssh_timeout: float = 5.0,
        cell_iface: str = "mob1s1a1",
    ):
        """
        Initialize Teltonika collector.

        Args:
            ssh_host: Hostname or IP address
            ssh_user: SSH username
            ssh_port: SSH port
            ssh_password: SSH password (requires sshpass)
            ssh_key: Path to SSH private key file
            ssh_strict: StrictHostKeyChecking value
            ssh_timeout: SSH connection timeout in seconds
            cell_iface: Cellular interface name (e.g., mob1s1a1)
        """
        self.host = ssh_host
        self.user = ssh_user
        self.port = ssh_port
        self.password = ssh_password
        self.key = ssh_key
        self.strict = ssh_strict
        self.timeout = ssh_timeout
        self.cell_iface = cell_iface

    def _ssh_exec(self, command: str) -> str:
        """Execute SSH command and return stdout."""
        if not self.host:
            raise RuntimeError("SSH host not configured")

        # Build SSH command - don't use BatchMode with password auth
        cmd = [
            "ssh",
            "-p", str(self.port),
            "-o", f"StrictHostKeyChecking={self.strict}",
            "-o", f"ConnectTimeout={int(self.timeout)}",
        ]

        if self.key:
            cmd.extend(["-i", self.key, "-o", "BatchMode=yes"])

        cmd.append(f"{self.user}@{self.host}")
        cmd.append(command)

        if self.password and not self.key:
            # Check for sshpass
            if subprocess.run(["sshpass", "-V"], capture_output=True).returncode != 0:
                raise RuntimeError("sshpass is required for password-based SSH")
            cmd = ["sshpass", "-p", self.password] + cmd

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=self.timeout + 2
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "SSH command failed")
        return result.stdout.strip()

    def _ssh_exec_safe(self, command: str) -> str:
        """Execute SSH command, return empty string on error."""
        try:
            return self._ssh_exec(command)
        except Exception:
            return ""

    def get_signal_metrics(self) -> Dict:
        """
        Get cellular signal quality metrics from gsmctl -E (JSON format).

        This is the FIXED version that correctly reads from cache.rsrp_value, etc.
        """
        try:
            info_json = self._ssh_exec("gsmctl -E")
            data = json.loads(info_json)
            cache = data.get("cache", {})

            return {
                "rsrp": cache.get("rsrp_value"),  # Correct: from cache
                "rsrq": cache.get("rsrq_value"),  # Correct: from cache
                "snr": cache.get("sinr_value"),   # Correct: from cache (SINR)
                "rssi": cache.get("rssi_value"),  # Correct: from cache
            }
        except Exception:
            return {"rsrp": None, "rsrq": None, "snr": None, "rssi": None}

    def get_network_info(self) -> Dict:
        """Get network and carrier information."""
        carrier = self._ssh_exec_safe("gsmctl -o")
        tech = self._ssh_exec_safe("gsmctl -t")
        band = self._ssh_exec_safe("gsmctl -b")

        return {
            "carrier": carrier.strip(),
            "technology": tech.strip(),
            "band": band.strip(),
            "bandwidth": "",  # Not readily available via gsmctl
        }

    def get_connection_status(self) -> Dict:
        """Get WAN connection status using `mwan3 status` when available.

        Checks active routing policy to determine which interface is actually
        being used for WAN traffic, not just which interfaces are online.
        """
        try:
            # Prefer mwan3 for a failover-aware status
            mwan_text = self._ssh_exec_safe("mwan3 status")
            wan_up = False
            wan_device = ""
            wan_source = ""

            if mwan_text:
                # First, parse active policy to see which interface is routing traffic
                # Look for lines like "mob1s1a1 (100%)" or "wan (100%)"
                # Find ALL interface percentages, then pick the one with 100%
                for match in re.finditer(r"^\s*(\w+)\s*\((\d+)%\)", mwan_text, re.MULTILINE):
                    iface = match.group(1)
                    percent = int(match.group(2))

                    # If this interface has 100%, it's the active route
                    if percent == 100:
                        wan_device = iface
                        wan_up = True
                        break
                else:
                    # Fallback: check which interfaces are online
                    iface_status = {}
                    for m in re.finditer(r"^\s*interface\s+(?P<iface>\S+)\s+is\s+(?P<status>\w+)",
                                        mwan_text, re.IGNORECASE | re.MULTILINE):
                        iface_status[m.group('iface')] = m.group('status').lower()

                    # Pick first online interface (wan preferred over cellular for consistency)
                    if iface_status:
                        # Check wan first
                        if iface_status.get('wan') in ('online', 'up'):
                            wan_device = 'wan'
                            wan_up = True
                        # Then check cellular
                        elif self.cell_iface and iface_status.get(self.cell_iface) in ('online', 'up'):
                            wan_device = self.cell_iface
                            wan_up = True

                # Determine source based on device name
                if wan_device:
                    if self.cell_iface and self.cell_iface in wan_device:
                        wan_source = "Cellular"
                    elif 'eth' in wan_device.lower() or 'lan' in wan_device.lower():
                        wan_source = "Ethernet"
                    elif 'wan' in wan_device.lower():
                        wan_source = "Ethernet"  # 'wan' typically means ethernet WAN
                    else:
                        wan_source = "Unknown"

            # If we still need an IP address, try ubus (ubus gives structured IP info)
            device_ipv4 = ""
            try:
                wan_json = self._ssh_exec("ubus call network.interface.wan status")
                wan_data = json.loads(wan_json)
                addrs = wan_data.get("ipv4-address", [])
                if addrs:
                    device_ipv4 = addrs[0].get("address", "")
            except Exception:
                device_ipv4 = ""

            return {
                "wan_status": "Connected" if wan_up else "Disconnected",
                "wan_source": wan_source,
                "device_ipv4": device_ipv4,
            }
        except Exception:
            # Fallback to the previous ubus/route-based logic
            try:
                wan_json = self._ssh_exec("ubus call network.interface.wan status")
                wan_data = json.loads(wan_json)
                wan_up = wan_data.get("up", False)
                wan_device = wan_data.get("device", "")

                # Determine WAN source by checking both device name and route
                wan_source = ""
                if wan_device:
                    if self.cell_iface and self.cell_iface in wan_device:
                        wan_source = "Cellular"
                    else:
                        # Check routing table to verify actual path
                        try:
                            route_check = self._ssh_exec(f"ip route get 8.8.8.8 | grep -o 'dev [^ ]*'")
                            if route_check and self.cell_iface in route_check:
                                wan_source = "Cellular"
                            else:
                                wan_source = "Ethernet"
                        except Exception:
                            wan_source = "Ethernet"

                # Get IP address
                device_ipv4 = ""
                addrs = wan_data.get("ipv4-address", [])
                if addrs:
                    device_ipv4 = addrs[0].get("address", "")

                return {
                    "wan_status": "Connected" if wan_up else "Disconnected",
                    "wan_source": wan_source,
                    "device_ipv4": device_ipv4,
                }
            except Exception:
                return {"wan_status": "", "wan_source": "", "device_ipv4": ""}

    def get_sim_info(self) -> Dict:
        """Get SIM card information."""
        apn = self._ssh_exec_safe(f"uci get network.{self.cell_iface}.apn")
        iccid = self._ssh_exec_safe("gsmctl -J")
        sim_status = self._ssh_exec_safe("gsmctl -z")

        return {
            "apn": apn.strip(),
            "iccid": iccid.strip(),
            "sim_status": sim_status.strip(),
        }

    def get_device_info(self) -> Dict:
        """Get device/modem information."""
        try:
            # Get modem info from gsmctl -E
            info_json = self._ssh_exec("gsmctl -E")
            data = json.loads(info_json)
            cache = data.get("cache", {})

            # Use router model as primary, include modem model in manufacturer field
            router_model = "RUTM50"
            modem_model = data.get("model", "")
            modem_manufacturer = data.get("manuf", "")

            return {
                "model": router_model,
                "manufacturer": f"Teltonika/{modem_manufacturer}" if modem_manufacturer else "Teltonika",
                "firmware": cache.get("firmware", ""),
                "imei": cache.get("imei", ""),
                "serial": cache.get("serial_num", ""),
            }
        except Exception:
            return {
                "model": "RUTM50",
                "manufacturer": "Teltonika",
                "firmware": "",
                "imei": "",
                "serial": "",
            }
