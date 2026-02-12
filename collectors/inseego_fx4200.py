"""
Inseego FX4200 collector via ubus JSON-RPC over HTTPS.
"""
import json
import ssl
import sys
import time
from typing import Any, Dict, List, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from .base import CellularCollector

# Technology code mapping from FX4200 ubus API
TECH_CODES = {
    0: "No Service",
    2: "CDMA",
    3: "GSM/GPRS",
    4: "HDR",
    5: "WCDMA",
    6: "GPS",
    8: "WCDMA/GSM",
    9: "LTE",
    11: "LTE",
    12: "HPDA",
    17: "5G NSA",
    18: "5G SA",
}

# SIM status codes
SIM_STATUS_CODES = {
    0: "Unknown",
    1: "Not Inserted",
    2: "Initializing",
    3: "PIN Required",
    4: "PUK Required",
    5: "Check Failure",
    6: "Illegal",
    7: "Ready",
}

# WAN type codes
WAN_TYPE_CODES = {
    1: "WiFi",
    2: "USB",
    3: "Cellular",
    4: "Ethernet",
}


class InseegoFX4200Collector(CellularCollector):
    """Collector for Inseego FX4200 router via ubus JSON-RPC API."""

    def __init__(
        self,
        base_url: str = "https://192.168.1.1",
        password: str = "",
        verify_ssl: bool = False,
        session_refresh: int = 500,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/ubus"
        self.password = password
        self.session_refresh = session_refresh

        # SSL context for self-signed certs
        self._ssl_ctx = None
        if not verify_ssl:
            self._ssl_ctx = ssl.create_default_context()
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

        # Session state
        self._session_token: Optional[str] = None
        self._session_created: float = 0.0
        self._rpc_id: int = 0

        # Cached data from refresh_data()
        self._cached: Dict[str, Any] = {}

    # --- Session Management ---

    def _next_id(self) -> int:
        self._rpc_id += 1
        return self._rpc_id

    def _is_session_valid(self) -> bool:
        if not self._session_token:
            return False
        return (time.time() - self._session_created) < self.session_refresh

    def _authenticate(self) -> str:
        """Login and obtain session token."""
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "call",
            "params": [
                "00000000000000000000000000000000",
                "webui.login",
                "authenticate",
                {"password": self.password},
            ],
        }
        resp = self._raw_post(payload)
        result = resp.get("result", [])
        if len(result) >= 2 and isinstance(result[1], dict):
            token = result[1].get("session_token")
            if token:
                self._session_token = token
                self._session_created = time.time()
                return token
        raise RuntimeError(f"FX4200 authentication failed: {resp}")

    def _ensure_session(self) -> str:
        if not self._is_session_valid():
            self._authenticate()
        return self._session_token

    # --- HTTP Transport ---

    def _raw_post(self, payload: dict, timeout: float = 10.0) -> dict:
        """POST JSON-RPC to ubus endpoint."""
        data = json.dumps(payload).encode("utf-8")
        req = Request(
            self.api_url,
            data=data,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "FX4200-Monitor/1.0",
            },
            method="POST",
        )
        with urlopen(req, timeout=timeout, context=self._ssl_ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _ubus_call(self, namespace: str, method: str, params: Optional[dict] = None) -> dict:
        """Make an authenticated ubus JSON-RPC call. Retries once on auth failure."""
        token = self._ensure_session()
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "call",
            "params": [token, namespace, method, params or {}],
        }
        resp = self._raw_post(payload)

        # Check for error (session expired, permission denied)
        if "error" in resp:
            self._session_token = None
            token = self._ensure_session()
            payload["params"][0] = token
            payload["id"] = self._next_id()
            resp = self._raw_post(payload)

        result = resp.get("result", [])
        if len(result) >= 2 and isinstance(result[1], dict):
            return result[1]
        # Return code only (no data dict)
        if len(result) >= 1 and result[0] != 0:
            # Non-zero return code = permission denied or method error
            # Try re-auth once
            self._session_token = None
            token = self._ensure_session()
            payload["params"][0] = token
            payload["id"] = self._next_id()
            resp = self._raw_post(payload)
            result = resp.get("result", [])
            if len(result) >= 2 and isinstance(result[1], dict):
                return result[1]
        return {}

    # --- Batch Data Refresh ---

    def refresh_data(self) -> bool:
        """Fetch all data from the FX4200 in a batch. Called once per cycle."""
        try:
            self._ensure_session()
            data = {}

            data["cell_stats"] = self._ubus_call(
                "sysinterface.modem", "get_cellular_service_stats"
            )
            data["cell_5g_stats"] = self._ubus_call(
                "sysinterface.modem", "get_cellular_5g_service_stats"
            )
            data["hw_info"] = self._ubus_call(
                "sysinterface.modem", "get_hardware_info"
            )
            data["model_name"] = self._ubus_call(
                "sysinterface.modem", "get_device_model_name"
            )
            data["sys_version"] = self._ubus_call(
                "sysinterface.modem", "get_system_version"
            )
            data["ecgi"] = self._ubus_call(
                "sysinterface.modem", "get_ecgi"
            )
            data["wan_stats"] = self._ubus_call(
                "sysinterface.modem", "get_active_wan_data_connection_stats"
            )
            data["conn_state"] = self._ubus_call(
                "sysinterface.modem", "get_cellular_data_connection_state"
            )
            data["sim_status"] = self._ubus_call(
                "sysinterface.sim", "get_status"
            )
            data["subscriber"] = self._ubus_call(
                "sysinterface.sim", "get_subscriber_info"
            )
            data["active_sim"] = self._ubus_call(
                "sysinterface.sim", "get_active_sim"
            )
            data["sim_slots"] = self._ubus_call(
                "sysinterface.sim.slot", "get_all_slots_info"
            )
            data["wan_iface"] = self._ubus_call(
                "sysinterface.wan", "get_active_wan_interface"
            )

            self._cached = data
            return True
        except Exception as e:
            print(f"[FX4200] refresh error: {e}", file=sys.stderr)
            return False

    def clear_cache(self):
        self._cached = {}

    # --- CellularCollector Interface ---

    def get_signal_metrics(self) -> Dict:
        stats = self._cached.get("cell_stats", {})
        stats_5g = self._cached.get("cell_5g_stats", {})

        tech_code = stats.get("tech", 0)
        is_5g = tech_code in (17, 18)

        src = stats_5g if (is_5g and stats_5g) else stats
        return {
            "rsrp": src.get("rsrp"),
            "rsrq": src.get("rsrq"),
            "snr": src.get("snr"),
            "rssi": src.get("rssi") or stats.get("rssi"),
        }

    def get_network_info(self) -> Dict:
        stats = self._cached.get("cell_stats", {})
        stats_5g = self._cached.get("cell_5g_stats", {})
        ecgi_data = self._cached.get("ecgi", {})

        tech_code = stats.get("tech", 0)
        technology = TECH_CODES.get(tech_code, f"Unknown({tech_code})")

        carrier = (stats.get("oper_name") or "").strip()
        pci = stats.get("pci", "")
        cell_id = stats.get("cell_id", "") or ecgi_data.get("ecgi", "")

        band = ""
        if tech_code in (17, 18) and stats_5g:
            endc = stats_5g.get("endc", 0)
            if endc:
                band = f"ENDC"
            nr_earfcn = stats_5g.get("earfcn_5g_dl")
            if nr_earfcn:
                band = f"{band}+NR-EARFCN:{nr_earfcn}" if band else f"NR-EARFCN:{nr_earfcn}"

        return {
            "carrier": carrier,
            "technology": technology,
            "band": band,
            "bandwidth": "",
            "pci": str(pci),
            "cell_id": str(cell_id),
        }

    def get_connection_status(self) -> Dict:
        conn = self._cached.get("conn_state", {})
        wan_stats = self._cached.get("wan_stats", {})
        wan_iface = self._cached.get("wan_iface", {})

        ipv4_connected = conn.get("ipv4_cs", 0) == 1
        ipv6_connected = conn.get("ipv6_cs", 0) == 1
        is_connected = ipv4_connected or ipv6_connected

        device_ipv4 = wan_stats.get("ipv4_address", "")

        wan_type_code = wan_iface.get("active_wan_type", 0)
        wan_source = WAN_TYPE_CODES.get(wan_type_code, "Unknown")

        return {
            "wan_status": "Connected" if is_connected else "Disconnected",
            "wan_source": wan_source,
            "device_ipv4": device_ipv4,
        }

    def get_sim_info(self) -> Dict:
        subscriber = self._cached.get("subscriber", {})
        sim_status = self._cached.get("sim_status", {})
        sim_slots_data = self._cached.get("sim_slots", {})

        status_code = sim_status.get("status", 0)
        status_str = SIM_STATUS_CODES.get(status_code, f"Code({status_code})")

        iccid = subscriber.get("iccid", "")

        # Find active slot info for APN (not directly available, use carrier as proxy)
        slots = sim_slots_data.get("slots_info", [])
        active_slot = None
        for slot in slots:
            if slot.get("sim_status") == 1:  # 1 = active
                active_slot = slot
                break

        return {
            "apn": "",
            "iccid": iccid,
            "sim_status": status_str,
        }

    def get_device_info(self) -> Dict:
        hw = self._cached.get("hw_info", {})
        model_data = self._cached.get("model_name", {})
        ver = self._cached.get("sys_version", {})

        fw = ver.get("modem_fw_version", "")
        webui_ver = ver.get("webui_version", "")
        firmware = fw if fw else webui_ver

        return {
            "model": model_data.get("model", hw.get("model", "FX4200")),
            "manufacturer": hw.get("manufacturer", "Inseego"),
            "firmware": firmware,
            "imei": hw.get("imei", ""),
            "serial": hw.get("fid", ""),
        }

    # --- Extended: Dual SIM Info ---

    def get_sim_slots_detail(self) -> List[Dict]:
        """Get detailed info for all SIM slots."""
        data = self._cached.get("sim_slots", {})
        if not data:
            data = self._ubus_call("sysinterface.sim.slot", "get_all_slots_info")
        return data.get("slots_info", [])

    def get_active_sim_imsi(self) -> str:
        """Get the IMSI of the currently active SIM."""
        data = self._cached.get("active_sim", {})
        return data.get("imsi", "")

    # --- SIM Switching ---

    def switch_sim_by_iccid(self, iccid: str) -> Dict:
        """Switch active SIM by ICCID."""
        return self._ubus_call("sysinterface.sim", "sim_switch_iccid", {"iccid": iccid})

    def switch_sim_by_imsi(self, imsi: str) -> Dict:
        """Switch active SIM by IMSI."""
        return self._ubus_call("sysinterface.sim", "set_active_sim", {"imsi": imsi})
