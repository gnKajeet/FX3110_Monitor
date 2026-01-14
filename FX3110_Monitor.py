import subprocess
import time
import socket
import re
import json
import os
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# --- Network Configuration ---
# Read from environment or use defaults
BIND_INTERFACE = os.getenv("BIND_INTERFACE") or None  # e.g., "eth0" for Raspberry Pi ethernet
DEVICE_TYPE = (os.getenv("DEVICE_TYPE") or "fx3110").strip().lower()

# --- Targets ---
DEST = os.getenv("DEST", "8.8.8.8")

# --- Public IP providers ---
PUBLIC_IP_URLS = [
    "https://ifconfig.me/ip",
    "https://api.ipify.org",
    "https://checkip.amazonaws.com",
]
# Check public IP every cycle to ensure all IPs are synchronized
PUBLIC_IP_REFRESH_SECONDS = int(os.getenv("PUBLIC_IP_REFRESH_SECONDS", "0"))  # 0 = every cycle

# Polling intervals
MAIN_LOOP_INTERVAL = int(os.getenv("MAIN_LOOP_INTERVAL", "5"))  # Main loop runs every 5 seconds
STATUS_REFRESH_SECONDS = int(os.getenv("STATUS_REFRESH_SECONDS", "0"))  # 0 = every cycle
DEVICES_REFRESH_SECONDS = int(os.getenv("DEVICES_REFRESH_SECONDS", "0"))  # 0 = every cycle

# Keep device-name list compact so logs stay readable
MAX_DEVICE_NAMES = int(os.getenv("MAX_DEVICE_NAMES", "5"))

# FX3110 device endpoints (HTML/JSON)
DEVICE_BASE = os.getenv("DEVICE_BASE", "http://192.168.1.1")
STATUS_PAGE_URL = f"{DEVICE_BASE}/"
DEVICES_REFRESH_URL = f"{DEVICE_BASE}/apps_home/devicesrefresh/"

# RUTM50 SSH configuration
RUTM50_SSH_HOST = os.getenv("RUTM50_SSH_HOST", "")
RUTM50_SSH_USER = os.getenv("RUTM50_SSH_USER", "root")
RUTM50_SSH_PORT = os.getenv("RUTM50_SSH_PORT", "22")
RUTM50_SSH_KEY = os.getenv("RUTM50_SSH_KEY", "")
RUTM50_SSH_PASSWORD = os.getenv("RUTM50_SSH_PASSWORD", "")
RUTM50_SSH_STRICT = os.getenv("RUTM50_SSH_STRICT", "accept-new")
RUTM50_SSH_TIMEOUT = float(os.getenv("RUTM50_SSH_TIMEOUT", "3"))
RUTM50_CELL_IFACE = os.getenv("RUTM50_CELL_IFACE", "mob1s1a1")

RUTM50_CMD_SIGNAL = os.getenv("RUTM50_CMD_SIGNAL", "gsmctl -q")
RUTM50_CMD_OPERATOR = os.getenv("RUTM50_CMD_OPERATOR", "gsmctl -o")
RUTM50_CMD_TECH = os.getenv("RUTM50_CMD_TECH", "gsmctl -t")
RUTM50_CMD_CONNSTATE = os.getenv("RUTM50_CMD_CONNSTATE", "gsmctl -j")
RUTM50_CMD_PSSTATE = os.getenv("RUTM50_CMD_PSSTATE", "gsmctl -P")
RUTM50_CMD_NETSTATE = os.getenv("RUTM50_CMD_NETSTATE", "gsmctl -g")
RUTM50_CMD_CELLID = os.getenv("RUTM50_CMD_CELLID", "gsmctl -C")
RUTM50_CMD_OPERNUM = os.getenv("RUTM50_CMD_OPERNUM", "gsmctl -f")
RUTM50_CMD_NETWORK = os.getenv("RUTM50_CMD_NETWORK", "gsmctl -F")
RUTM50_CMD_SERVING = os.getenv("RUTM50_CMD_SERVING", "gsmctl -K")
RUTM50_CMD_NEIGHBOUR = os.getenv("RUTM50_CMD_NEIGHBOUR", "gsmctl -I")
RUTM50_CMD_VOLTE = os.getenv("RUTM50_CMD_VOLTE", "gsmctl -v")
RUTM50_CMD_BAND = os.getenv("RUTM50_CMD_BAND", "gsmctl -b")
RUTM50_CMD_INFO = os.getenv("RUTM50_CMD_INFO", "gsmctl --info")
RUTM50_CMD_WAN = os.getenv("RUTM50_CMD_WAN", "ubus call network.interface.wan status")
RUTM50_CMD_LAN = os.getenv("RUTM50_CMD_LAN", "ubus call network.interface.lan status")
RUTM50_CMD_APN = os.getenv("RUTM50_CMD_APN", "uci get network.mobile.apn")
RUTM50_CMD_ICCID = os.getenv("RUTM50_CMD_ICCID", "gsmctl -i")


def get_source_ip(dest: str) -> str:
    """Ask the OS routing table which local IP would be used to reach dest."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # No packets need to be sent; connect() just selects route + source IP.
        s.connect((dest, 80))
        return s.getsockname()[0]
    finally:
        s.close()


def get_active_interface(dest: str) -> str:
    """Detect which network interface is being used to reach dest."""
    try:
        # Use ip route to determine the interface
        result = subprocess.run(
            ["ip", "route", "get", dest],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            # Parse output like: "8.8.8.8 via 192.168.1.1 dev eth0 src 192.168.1.14"
            match = re.search(r'\bdev\s+(\S+)', result.stdout)
            if match:
                return match.group(1)
    except Exception:
        pass
    return "unknown"


def get_latency_ms(ping_output: str) -> str:
    """Extract RTT from ping output (Windows or Linux)."""
    # Windows formats: time=14ms, time<1ms
    # Linux formats: time=14.2 ms, time=0.123 ms
    m = re.search(r"time[=<]\s*(\d+(?:\.\d+)?)\s*ms", ping_output)
    if m:
        # Round to integer milliseconds for consistency
        return str(int(float(m.group(1))))
    return ""


def fetch_text(url: str, timeout_seconds: float = 3.0) -> str:
    headers = {"User-Agent": "status-poller/1.0", "Accept": "*/*"}
    req = Request(url, headers=headers)
    with urlopen(req, timeout=timeout_seconds) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_json(url: str, timeout_seconds: float = 3.0):
    return json.loads(fetch_text(url, timeout_seconds=timeout_seconds))


def fetch_public_ip(timeout_seconds: float = 3.0) -> str:
    headers = {"User-Agent": "public-ip-check/1.0"}
    for url in PUBLIC_IP_URLS:
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=timeout_seconds) as resp:
                ip = resp.read().decode("utf-8", errors="replace").strip()
                # Basic sanity: IPv4 or IPv6 shape
                if ip and (":" in ip or re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip)):
                    return ip
        except (URLError, HTTPError, TimeoutError, OSError):
            continue
    return ""


def extract_by_id(html: str, element_id: str) -> str:
    """Extract inner text for elements like <span id="foo">VALUE</span>."""
    m = re.search(
        rf'id="{re.escape(element_id)}"\s*[^>]*>\s*([^<]*)\s*<',
        html,
        flags=re.IGNORECASE,
    )
    return m.group(1).strip() if m else ""


def safe_call(fn, default):
    try:
        return fn()
    except Exception:
        return default


class FX3110Client:
    def __init__(self, base_url: str):
        self.status_url = f"{base_url}/"
        self.devices_url = f"{base_url}/apps_home/devicesrefresh/"

    def get_status_snapshot(self):
        """Pull key fields from the FX3110 status HTML page."""
        html = fetch_text(self.status_url, timeout_seconds=3.0)
        return {
            "WanStatus": extract_by_id(html, "internetStatus"),
            "SimStatus": extract_by_id(html, "simStatus"),
            "Tech": extract_by_id(html, "technology"),
            "Band": extract_by_id(html, "band"),
            "Bandwidth": extract_by_id(html, "bandwidth"),
            "DeviceIPv4": extract_by_id(html, "internetStatusIPAddress"),
            "Carrier": extract_by_id(html, "networkName"),
            "APN": extract_by_id(html, "internetAPN"),
            "ICCID": extract_by_id(html, "internetInfoICCID"),
            "ECGI": extract_by_id(html, "internetStatusECGI"),
            "PCI": extract_by_id(html, "pci"),
            "RSRP": extract_by_id(html, "internetStatusRSRP"),
            "RSRQ": extract_by_id(html, "internetStatusRSRQ"),
            "SNR": extract_by_id(html, "snr"),
        }

    def get_connected_devices_snapshot(self):
        """Pull connected device count/list from the JSON endpoint used by the UI."""
        data = fetch_json(self.devices_url, timeout_seconds=3.0)
        count = data.get("wifiDevicesCount", "")
        devs = data.get("connectedDevicesList", []) or []

        names = []
        for d in devs:
            name = (d.get("name") or "").strip()
            hostname = (d.get("hostname") or "").strip()
            display = name or hostname or "Unknown"
            names.append(display)

        if MAX_DEVICE_NAMES and len(names) > MAX_DEVICE_NAMES:
            names_compact = ",".join(names[:MAX_DEVICE_NAMES]) + f",+{len(names) - MAX_DEVICE_NAMES} more"
        else:
            names_compact = ",".join(names)

        return {
            "ConnDevCount": str(count),
            "ConnDevNames": names_compact,
        }


class RUTM50Client:
    def __init__(self):
        self.host = RUTM50_SSH_HOST
        self.user = RUTM50_SSH_USER
        self.port = RUTM50_SSH_PORT
        self.key = RUTM50_SSH_KEY
        self.password = RUTM50_SSH_PASSWORD
        self.strict = RUTM50_SSH_STRICT
        self.timeout = RUTM50_SSH_TIMEOUT
        self.cell_iface = RUTM50_CELL_IFACE

    def _ssh_exec(self, command: str) -> str:
        if not self.host:
            raise RuntimeError("RUTM50_SSH_HOST is not set")

        # Build SSH command - don't use BatchMode with password auth
        cmd = ["ssh", "-p", str(self.port), "-o", f"StrictHostKeyChecking={self.strict}",
               "-o", f"ConnectTimeout={int(self.timeout)}"]

        if self.key:
            cmd.extend(["-i", self.key, "-o", "BatchMode=yes"])  # BatchMode only with key auth

        cmd.append(f"{self.user}@{self.host}")
        cmd.append(command)

        if self.password and not self.key:
            if subprocess.run(["sshpass", "-V"], capture_output=True, text=True).returncode != 0:
                raise RuntimeError("sshpass is required for password-based SSH")
            cmd = ["sshpass", "-p", self.password] + cmd

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout + 2)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "SSH command failed")
        return result.stdout.strip()

    def _ssh_exec_safe(self, command: str) -> str:
        try:
            return self._ssh_exec(command)
        except Exception:
            return ""

    def _clean_text(self, text: str) -> str:
        # Keep TSV safe: collapse whitespace and strip tabs/newlines.
        return re.sub(r"\s+", " ", text).strip()

    def _parse_gsmctl(self, text: str):
        def grab(label: str):
            m = re.search(rf"{re.escape(label)}\\s*:\\s*([^\\n\\r]+)", text, re.IGNORECASE)
            return m.group(1).strip() if m else ""

        return {
            "Carrier": grab("Operator"),
            "Tech": grab("Network type"),
            "Band": grab("LTE band"),
            "RSRP": grab("RSRP"),
            "RSRQ": grab("RSRQ"),
            "SNR": grab("SINR") or grab("SNR"),
            "SimStatus": grab("SIM state"),
            "ECGI": grab("Cell ID") or grab("ECGI"),
            "PCI": grab("PCI"),
        }

    def _parse_ubus_status(self, text: str):
        data = json.loads(text)
        ipv4 = ""
        if isinstance(data, dict):
            addrs = data.get("ipv4-address") or []
            if addrs:
                ipv4 = addrs[0].get("address", "")
        return {
            "up": str(data.get("up", "")),
            "device": str(data.get("device", "")),
            "ipv4": ipv4,
        }

    def _parse_gsmctl_info(self, text: str):
        data = json.loads(text)
        cache = data.get("cache", {}) if isinstance(data, dict) else {}
        cell_info = (cache.get("cell_info") or [{}])[0] if isinstance(cache, dict) else {}
        ca_info = (cache.get("ca_info") or [{}])[0] if isinstance(cache, dict) else {}

        def grab(dct, key):
            val = dct.get(key, "")
            return str(val) if val is not None else ""

        return {
            "ModemModel": grab(data, "model"),
            "ModemManuf": grab(data, "manuf"),
            "ModemFirmware": grab(cache, "firmware"),
            "ModemSerial": grab(cache, "serial_num"),
            "ModemIMEI": grab(cache, "imei"),
            "ModemState": grab(cache, "modem_state"),
            "ModemRegStat": grab(cache, "reg_stat_str"),
            "ModemNetMode": grab(cache, "net_mode_str"),
            "ModemBand": grab(cache, "band_str"),
            "ModemCellId": grab(cell_info, "cellid") or grab(cache, "reg_ci"),
            "ModemTac": grab(cell_info, "tac") or grab(cache, "reg_tac"),
            "ModemPcid": grab(cell_info, "pcid"),
            "ModemRssi": grab(cache, "rssi_value"),
            "ModemRsrp": grab(cache, "rsrp_value"),
            "ModemRsrq": grab(cache, "rsrq_value"),
            "ModemSinr": grab(cache, "sinr_value"),
            "ModemVolteReady": grab(cache, "volte_ready"),
        }

    def get_status_snapshot(self):
        signal_text = self._ssh_exec(RUTM50_CMD_SIGNAL)
        signal = self._parse_gsmctl(signal_text)

        op = self._ssh_exec_safe(RUTM50_CMD_OPERATOR)
        if op:
            signal["Carrier"] = op.strip()

        tech = self._ssh_exec_safe(RUTM50_CMD_TECH)
        if tech:
            signal["Tech"] = tech.strip()

        band = self._ssh_exec_safe(RUTM50_CMD_BAND)
        if band:
            signal["Band"] = band.strip()

        wan_status = {}
        try:
            wan_status = self._parse_ubus_status(self._ssh_exec(RUTM50_CMD_WAN))
        except Exception:
            wan_status = {}

        lan_status = {}
        try:
            lan_status = self._parse_ubus_status(self._ssh_exec(RUTM50_CMD_LAN))
        except Exception:
            lan_status = {}

        wan_up = wan_status.get("up", "")
        wan_device = wan_status.get("device", "")
        wan_source = ""
        if wan_device:
            wan_source = "Cellular" if self.cell_iface and self.cell_iface in wan_device else "Ethernet"

        apn = ""
        apn = self._ssh_exec_safe(RUTM50_CMD_APN)

        iccid = ""
        if RUTM50_CMD_ICCID:
            iccid = self._ssh_exec_safe(RUTM50_CMD_ICCID)

        connstate = self._ssh_exec_safe(RUTM50_CMD_CONNSTATE)
        psstate = self._ssh_exec_safe(RUTM50_CMD_PSSTATE)
        netstate = self._ssh_exec_safe(RUTM50_CMD_NETSTATE)
        cellid = self._ssh_exec_safe(RUTM50_CMD_CELLID)
        opernum = self._ssh_exec_safe(RUTM50_CMD_OPERNUM)
        network_info = self._ssh_exec_safe(RUTM50_CMD_NETWORK)
        serving_info = self._ssh_exec_safe(RUTM50_CMD_SERVING)
        neighbour_info = self._ssh_exec_safe(RUTM50_CMD_NEIGHBOUR)
        volte_state = self._ssh_exec_safe(RUTM50_CMD_VOLTE)
        info_text = self._ssh_exec_safe(RUTM50_CMD_INFO)
        info_fields = {}
        if info_text:
            try:
                info_fields = self._parse_gsmctl_info(info_text)
            except Exception:
                info_fields = {}

        device_ipv4 = wan_status.get("ipv4", "") or lan_status.get("ipv4", "")

        return {
            "WanStatus": "Connected" if str(wan_up).lower() == "true" else "Disconnected",
            "WanSource": wan_source,
            "SimStatus": signal.get("SimStatus", ""),
            "Tech": signal.get("Tech", ""),
            "Band": signal.get("Band", ""),
            "Bandwidth": "",
            "DeviceIPv4": device_ipv4,
            "Carrier": signal.get("Carrier", ""),
            "APN": apn,
            "ICCID": iccid,
            "ECGI": signal.get("ECGI", ""),
            "PCI": signal.get("PCI", ""),
            "RSRP": signal.get("RSRP", ""),
            "RSRQ": signal.get("RSRQ", ""),
            "SNR": signal.get("SNR", ""),
            "ConnState": self._clean_text(connstate),
            "PSState": self._clean_text(psstate),
            "NetState": self._clean_text(netstate),
            "CellId": self._clean_text(cellid),
            "OperNum": self._clean_text(opernum),
            "NetworkInfo": self._clean_text(network_info),
            "ServingInfo": self._clean_text(serving_info),
            "NeighbourInfo": self._clean_text(neighbour_info),
            "VolteState": self._clean_text(volte_state),
            **info_fields,
        }

    def get_connected_devices_snapshot(self):
        return {
            "ConnDevCount": "",
            "ConnDevNames": "",
        }


def build_device_client():
    if DEVICE_TYPE == "rutm50":
        return RUTM50Client()
    return FX3110Client(DEVICE_BASE)


# --- Header ---
print(
    "Timestamp\tSourceIP\tActiveInterface\tDestIP\tSuccess\tLatency_ms\tPublicIP\t"
    "WanStatus\tWanSource\tSimStatus\tTech\tBand\tBandwidth\tDeviceIPv4\tCarrier\tAPN\tICCID\t"
    "ECGI\tPCI\tRSRP\tRSRQ\tSNR\t"
    "ConnDevCount\tConnDevNames\t"
    "ConnState\tPSState\tNetState\tCellId\tOperNum\tNetworkInfo\tServingInfo\tNeighbourInfo\tVolteState\t"
    "ModemModel\tModemManuf\tModemFirmware\tModemSerial\tModemIMEI\tModemState\tModemRegStat\t"
    "ModemNetMode\tModemBand\tModemCellId\tModemTac\tModemPcid\tModemRssi\tModemRsrp\tModemRsrq\t"
    "ModemSinr\tModemVolteReady"
)

# Cached values (so a temporary fetch failure doesn't blank your logs)
last_public_ip = ""
next_public_ip_refresh = 0.0

status = {
    "WanStatus": "", "WanSource": "", "SimStatus": "", "Tech": "", "Band": "", "Bandwidth": "",
    "DeviceIPv4": "", "Carrier": "", "APN": "", "ICCID": "",
    "ECGI": "", "PCI": "", "RSRP": "", "RSRQ": "", "SNR": "",
    "ConnState": "", "PSState": "", "NetState": "", "CellId": "", "OperNum": "",
    "NetworkInfo": "", "ServingInfo": "", "NeighbourInfo": "", "VolteState": "",
    "ModemModel": "", "ModemManuf": "", "ModemFirmware": "", "ModemSerial": "", "ModemIMEI": "",
    "ModemState": "", "ModemRegStat": "", "ModemNetMode": "", "ModemBand": "", "ModemCellId": "",
    "ModemTac": "", "ModemPcid": "", "ModemRssi": "", "ModemRsrp": "", "ModemRsrq": "",
    "ModemSinr": "", "ModemVolteReady": "",
}
next_status_refresh = 0.0

devices = {"ConnDevCount": "", "ConnDevNames": ""}
next_devices_refresh = 0.0

device_client = build_device_client()

while True:
    now = time.time()

    # Refresh public IP (slow)
    if now >= next_public_ip_refresh:
        last_public_ip = safe_call(lambda: fetch_public_ip() or last_public_ip, last_public_ip)
        next_public_ip_refresh = now + PUBLIC_IP_REFRESH_SECONDS

    # Refresh local status (medium)
    if now >= next_status_refresh:
        status = safe_call(device_client.get_status_snapshot, status)
        next_status_refresh = now + STATUS_REFRESH_SECONDS

    # Refresh connected devices (slow)
    if now >= next_devices_refresh:
        devices = safe_call(device_client.get_connected_devices_snapshot, devices)
        next_devices_refresh = now + DEVICES_REFRESH_SECONDS

    # Ping once
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    src_ip = get_source_ip(DEST)
    active_interface = get_active_interface(DEST)

    # Build ping command with optional interface binding
    ping_cmd = ["ping", "-c", "1"]
    if BIND_INTERFACE:
        ping_cmd.extend(["-I", BIND_INTERFACE])
    ping_cmd.append(DEST)

    proc = subprocess.run(
        ping_cmd,
        capture_output=True,
        text=True,
    )

    success = proc.returncode == 0
    latency = get_latency_ms(proc.stdout)

    # Determine WAN source based on Technology field
    # When FX3110 uses Ethernet WAN, technology field shows "Ethernet"
    # When using cellular WAN, technology shows "4G LTE", "5G", etc.
    wan_source = status.get("WanSource", "").strip()
    if not wan_source:
        tech = status.get('Tech', '').strip()
        if tech.lower() == 'ethernet':
            wan_source = "Ethernet"
        elif tech:
            wan_source = "Cellular"
        else:
            wan_source = "Unknown"

    print(
        f"{ts}\t{src_ip}\t{active_interface}\t{DEST}\t{success}\t{latency}\t{last_public_ip}\t"
        f"{status.get('WanStatus','')}\t{wan_source}\t{status.get('SimStatus','')}\t{status.get('Tech','')}\t"
        f"{status.get('Band','')}\t{status.get('Bandwidth','')}\t{status.get('DeviceIPv4','')}\t"
        f"{status.get('Carrier','')}\t{status.get('APN','')}\t{status.get('ICCID','')}\t"
        f"{status.get('ECGI','')}\t{status.get('PCI','')}\t{status.get('RSRP','')}\t"
        f"{status.get('RSRQ','')}\t{status.get('SNR','')}\t"
        f"{devices.get('ConnDevCount','')}\t{devices.get('ConnDevNames','')}\t"
        f"{status.get('ConnState','')}\t{status.get('PSState','')}\t{status.get('NetState','')}\t"
        f"{status.get('CellId','')}\t{status.get('OperNum','')}\t{status.get('NetworkInfo','')}\t"
        f"{status.get('ServingInfo','')}\t{status.get('NeighbourInfo','')}\t{status.get('VolteState','')}\t"
        f"{status.get('ModemModel','')}\t{status.get('ModemManuf','')}\t{status.get('ModemFirmware','')}\t"
        f"{status.get('ModemSerial','')}\t{status.get('ModemIMEI','')}\t{status.get('ModemState','')}\t"
        f"{status.get('ModemRegStat','')}\t{status.get('ModemNetMode','')}\t{status.get('ModemBand','')}\t"
        f"{status.get('ModemCellId','')}\t{status.get('ModemTac','')}\t{status.get('ModemPcid','')}\t"
        f"{status.get('ModemRssi','')}\t{status.get('ModemRsrp','')}\t{status.get('ModemRsrq','')}\t"
        f"{status.get('ModemSinr','')}\t{status.get('ModemVolteReady','')}",
        flush=True,
    )

    time.sleep(MAIN_LOOP_INTERVAL)
