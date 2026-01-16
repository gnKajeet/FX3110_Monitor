"""
Teltonika cellular router collector (RUTM50, RUTX series, etc.)

Supports two modes:
1. Individual SSH commands (legacy, ~20 SSH sessions per cycle)
2. Collector script mode (1 SSH session per cycle) - recommended
"""
import re
import json
import subprocess
import sys
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
        use_collector_script: bool = False,
        collector_script_path: str = "/tmp/teltonika_collector.sh",
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
            use_collector_script: If True, use single SSH call with collector script
            collector_script_path: Path to collector script on router
        """
        self.host = ssh_host
        self.user = ssh_user
        self.port = ssh_port
        self.password = ssh_password
        self.key = ssh_key
        self.strict = ssh_strict
        self.timeout = ssh_timeout
        self.cell_iface = cell_iface
        self.use_collector_script = use_collector_script
        self.collector_script_path = collector_script_path
        self._cached_data: Optional[Dict] = None

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

    def refresh_data(self) -> bool:
        """
        Refresh all data from router in a single SSH call.

        Call this once per collection cycle before accessing individual metrics.
        Returns True if data was successfully collected.
        """
        if not self.use_collector_script:
            self._cached_data = None
            return True

        try:
            output = self._ssh_exec(self.collector_script_path)
            self._cached_data = json.loads(output)
            return True
        except json.JSONDecodeError as e:
            print(f"[TeltonikaCollector] JSON parse error: {e}", file=sys.stderr)
            self._cached_data = None
            return False
        except Exception as e:
            print(f"[TeltonikaCollector] Collector script error: {e}", file=sys.stderr)
            self._cached_data = None
            return False

    def clear_cache(self):
        """Clear cached data, forcing fresh collection on next access."""
        self._cached_data = None

    def _get_cached(self, key: str, default: str = "") -> str:
        """Get a string value from cached data."""
        if self._cached_data is None:
            return default
        return str(self._cached_data.get(key, default))

    def _get_cached_json(self, key: str) -> dict:
        """Get a JSON object from cached data."""
        if self._cached_data is None:
            return {}
        val = self._cached_data.get(key, {})
        if isinstance(val, dict):
            return val
        return {}

    def _fetch_gsmctl_info(self) -> dict:
        """Fetch modem info JSON, trying multiple gsmctl commands."""
        # Use cached data if available (collector script mode)
        if self._cached_data is not None:
            return self._get_cached_json("modem_info")

        for cmd in ("gsmctl -E", "gsmctl --info"):
            text = self._ssh_exec_safe(cmd)
            if not text:
                continue
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                continue
        return {}

    def _parse_gsmctl_q(self, text: str) -> Dict:
        """Parse gsmctl -q text output for signal metrics."""
        def grab(label: str) -> Optional[int]:
            m = re.search(rf"{re.escape(label)}\s*:\s*(-?\d+)", text, re.IGNORECASE)
            return int(m.group(1)) if m else None

        return {
            "rsrp": grab("RSRP"),
            "rsrq": grab("RSRQ"),
            "snr": grab("SINR") or grab("SNR"),
            "rssi": grab("RSSI"),
        }

    def get_signal_metrics(self) -> Dict:
        """
        Get cellular signal quality metrics from gsmctl -E (JSON format).

        This is the FIXED version that correctly reads from cache.rsrp_value, etc.
        """
        data = self._fetch_gsmctl_info()
        cache = data.get("cache", {}) if isinstance(data, dict) else {}
        if cache:
            return {
                "rsrp": cache.get("rsrp_value"),
                "rsrq": cache.get("rsrq_value"),
                "snr": cache.get("sinr_value"),
                "rssi": cache.get("rssi_value"),
            }

        # Use cached signal_quality if available (collector script mode)
        if self._cached_data is not None:
            text = self._get_cached("signal_quality")
        else:
            text = self._ssh_exec_safe("gsmctl -q")

        if text:
            return self._parse_gsmctl_q(text)

        return {"rsrp": None, "rsrq": None, "snr": None, "rssi": None}

    def get_network_info(self) -> Dict:
        """Get network and carrier information."""
        # Use cached data if available (collector script mode)
        if self._cached_data is not None:
            carrier = self._get_cached("operator")
            tech = self._get_cached("technology")
            band = self._get_cached("band")
        else:
            carrier = self._ssh_exec_safe("gsmctl -o")
            tech = self._ssh_exec_safe("gsmctl -t")
            band = self._ssh_exec_safe("gsmctl -b")

        bandwidth = ""

        if not (carrier.strip() or tech.strip() or band.strip()):
            data = self._fetch_gsmctl_info()
            cache = data.get("cache", {}) if isinstance(data, dict) else {}
            carrier = carrier or cache.get("provider_name") or cache.get("operator") or ""
            tech = tech or cache.get("net_mode_str") or ""
            band = band or cache.get("band_str") or ""
            ca_info = cache.get("ca_info") or []
            if ca_info:
                bandwidth = str(ca_info[0].get("bandwidth", "")) or ""

        return {
            "carrier": carrier.strip(),
            "technology": tech.strip(),
            "band": band.strip(),
            "bandwidth": bandwidth,
        }

    def get_connection_status(self) -> Dict:
        """Get WAN connection status using `mwan3 status` when available.

        Checks active routing policy to determine which interface is actually
        being used for WAN traffic, not just which interfaces are online.
        """
        try:
            # Prefer mwan3 for a failover-aware status
            # Use cached data if available (collector script mode)
            if self._cached_data is not None:
                mwan_text = self._get_cached("mwan3_status")
            else:
                mwan_text = self._ssh_exec_safe("mwan3 status")

            wan_up = False
            wan_device = ""
            wan_source = ""

            if mwan_text:
                # First, parse active policy to see which interface is routing traffic
                # Look for lines like "mob1s1a1 (100%)" or "wan (100%)"
                # Find ALL interface percentages, then pick the one with 100%
                # Updated regex to work with both multiline and escaped/flattened output
                for match in re.finditer(r"(?:^|\s)(\w+)\s*\((\d+)%\)", mwan_text, re.MULTILINE):
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
                        # Then check either SIM's cellular interface
                        elif iface_status.get('mob1s1a1') in ('online', 'up'):
                            wan_device = 'mob1s1a1'
                            wan_up = True
                        elif iface_status.get('mob1s2a1') in ('online', 'up'):
                            wan_device = 'mob1s2a1'
                            wan_up = True

                # Determine source based on device name
                if wan_device:
                    if 'mob1s' in wan_device:
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
                # Use cached data if available (collector script mode)
                if self._cached_data is not None:
                    wan_data = self._get_cached_json("wan_status")
                else:
                    wan_json = self._ssh_exec("ubus call network.interface.wan status")
                    wan_data = json.loads(wan_json)
                addrs = wan_data.get("ipv4-address", [])
                if addrs:
                    device_ipv4 = addrs[0].get("address", "")
            except Exception:
                device_ipv4 = ""

            # Fallback: check cellular interface if WAN is down
            if not wan_up:
                try:
                    # Use cached data if available (collector script mode)
                    if self._cached_data is not None:
                        # Check cell1 first, then cell2
                        cell_data = self._get_cached_json("cell1_status")
                        if not cell_data.get("up"):
                            cell_data = self._get_cached_json("cell2_status")
                    else:
                        cell_json = self._ssh_exec(f"ubus call network.interface.{self.cell_iface} status")
                        cell_data = json.loads(cell_json)
                    cell_addrs = cell_data.get("ipv4-address", [])
                    if cell_data.get("up") or cell_addrs:
                        wan_up = True
                        wan_source = "Cellular"
                        if cell_addrs:
                            device_ipv4 = cell_addrs[0].get("address", device_ipv4)
                except Exception:
                    pass

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
                    if 'mob1s' in wan_device:
                        wan_source = "Cellular"
                    else:
                        # Check routing table to verify actual path
                        try:
                            route_check = self._ssh_exec(f"ip route get 8.8.8.8 | grep -o 'dev [^ ]*'")
                            if route_check and 'mob1s' in route_check:
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
        """Get SIM card information from the active SIM.

        Detects which SIM slot is active and retrieves APN from that interface.
        """
        # Get the active SIM slot (1 or 2)
        # Use cached data if available (collector script mode)
        if self._cached_data is not None:
            active_sim_slot = self._get_cached("active_sim").strip()
        else:
            active_sim_slot = self._ssh_exec_safe("gsmctl -L").strip()

        # Determine the active interface based on SIM slot
        active_iface = self.cell_iface  # Default fallback
        if active_sim_slot == "1":
            active_iface = "mob1s1a1"
        elif active_sim_slot == "2":
            active_iface = "mob1s2a1"
        else:
            # If we can't determine slot, try to find which interface is actually up
            try:
                # Check which mobile interface is up (has IP or is online)
                for iface in ["mob1s1a1", "mob1s2a1"]:
                    # Use cached data if available
                    if self._cached_data is not None:
                        cache_key = "cell1_status" if iface == "mob1s1a1" else "cell2_status"
                        iface_data = self._get_cached_json(cache_key)
                    else:
                        iface_json = self._ssh_exec(f"ubus call network.interface.{iface} status 2>/dev/null || echo '{{}}'")
                        iface_data = json.loads(iface_json)
                    # Interface is active if it's up OR has an IP address
                    if iface_data.get("up", False) or iface_data.get("ipv4-address"):
                        active_iface = iface
                        break
            except Exception:
                # Keep default fallback
                pass

        # Get APN from the active interface
        # Use cached data if available (collector script mode)
        if self._cached_data is not None:
            apn = self._get_cached("apn_sim1" if active_iface == "mob1s1a1" else "apn_sim2")
        else:
            apn = self._ssh_exec_safe(f"uci get network.{active_iface}.apn")

        # Get ICCID and status (these reflect the active SIM)
        # Use cached data if available (collector script mode)
        if self._cached_data is not None:
            iccid = self._get_cached("iccid")
            sim_status = self._get_cached("sim_status")
        else:
            iccid = self._ssh_exec_safe("gsmctl -J")
            sim_status = self._ssh_exec_safe("gsmctl -z")

        return {
            "apn": apn.strip(),
            "iccid": iccid.strip(),
            "sim_status": sim_status.strip(),
            "active_sim_slot": active_sim_slot,  # Add this for visibility
            "active_interface": active_iface,  # Add this for debugging
        }

    def get_device_info(self) -> Dict:
        """Get device/modem information."""
        data = self._fetch_gsmctl_info()
        cache = data.get("cache", {}) if isinstance(data, dict) else {}

        if data:
            router_model = "RUTM50"
            modem_manufacturer = data.get("manuf", "")
            return {
                "model": router_model,
                "manufacturer": f"Teltonika/{modem_manufacturer}" if modem_manufacturer else "Teltonika",
                "firmware": cache.get("firmware", ""),
                "imei": cache.get("imei", ""),
                "serial": cache.get("serial_num", ""),
            }

        return {
            "model": "RUTM50",
            "manufacturer": "Teltonika",
            "firmware": "",
            "imei": "",
            "serial": "",
        }
