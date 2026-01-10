import subprocess
import time
import socket
import re
import json
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# --- Network Configuration ---
# Network interface to use for FX3110 communication (set to None for auto-detect)
# On Raspberry Pi with ethernet + WiFi, set this to "eth0" to force FX3110 traffic over ethernet
BIND_INTERFACE = None  # e.g., "eth0" for Raspberry Pi ethernet

# --- Targets ---
DEST = "8.8.8.8"

# --- Public IP providers ---
PUBLIC_IP_URLS = [
    "https://ifconfig.me/ip",
    "https://api.ipify.org",
    "https://checkip.amazonaws.com",
]
PUBLIC_IP_REFRESH_SECONDS = 60

# --- Local failover device endpoints (based on your curl output) ---
DEVICE_BASE = "http://192.168.1.1"
STATUS_PAGE_URL = f"{DEVICE_BASE}/"                         # HTML page with IDs like simStatus, internetStatus, etc.
DEVICES_REFRESH_URL = f"{DEVICE_BASE}/apps_home/devicesrefresh/"  # JSON (wifiDevicesCount, connectedDevicesList)

# Polling intervals
STATUS_REFRESH_SECONDS = 5
DEVICES_REFRESH_SECONDS = 10

# Keep device-name list compact so logs stay readable
MAX_DEVICE_NAMES = 5


def get_source_ip(dest: str) -> str:
    """Ask the OS routing table which local IP would be used to reach dest."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # No packets need to be sent; connect() just selects route + source IP.
        s.connect((dest, 80))
        return s.getsockname()[0]
    finally:
        s.close()


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


def get_device_status_snapshot():
    """Pull key fields from the failover device home/status HTML page."""
    html = fetch_text(STATUS_PAGE_URL, timeout_seconds=3.0)

    return {
        # General / SIM
        "WanStatus": extract_by_id(html, "internetStatus"),
        "SimStatus": extract_by_id(html, "simStatus"),

        # Cellular / connection details
        "Tech": extract_by_id(html, "technology"),
        "Band": extract_by_id(html, "band"),
        "Bandwidth": extract_by_id(html, "bandwidth"),
        "DeviceIPv4": extract_by_id(html, "internetStatusIPAddress"),
        "Carrier": extract_by_id(html, "networkName"),
        "APN": extract_by_id(html, "internetAPN"),
        "ICCID": extract_by_id(html, "internetInfoICCID"),

        # RF / cell-ish metrics
        "ECGI": extract_by_id(html, "internetStatusECGI"),
        "PCI": extract_by_id(html, "pci"),
        "RSRP": extract_by_id(html, "internetStatusRSRP"),
        "RSRQ": extract_by_id(html, "internetStatusRSRQ"),
        "SNR": extract_by_id(html, "snr"),
    }


def get_connected_devices_snapshot():
    """Pull connected device count/list from the JSON endpoint used by the UI."""
    data = fetch_json(DEVICES_REFRESH_URL, timeout_seconds=3.0)

    count = data.get("wifiDevicesCount", "")
    devs = data.get("connectedDevicesList", []) or []

    names = []
    for d in devs:
        # UI logic: prefer name, then hostname, else Unknown
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


# --- Header ---
print(
    "Timestamp\tSourceIP\tDestIP\tSuccess\tLatency_ms\tPublicIP\t"
    "WanStatus\tSimStatus\tTech\tBand\tBandwidth\tDeviceIPv4\tCarrier\tAPN\tICCID\t"
    "ECGI\tPCI\tRSRP\tRSRQ\tSNR\t"
    "ConnDevCount\tConnDevNames"
)

# Cached values (so a temporary fetch failure doesn't blank your logs)
last_public_ip = ""
next_public_ip_refresh = 0.0

status = {
    "WanStatus": "", "SimStatus": "", "Tech": "", "Band": "", "Bandwidth": "",
    "DeviceIPv4": "", "Carrier": "", "APN": "", "ICCID": "",
    "ECGI": "", "PCI": "", "RSRP": "", "RSRQ": "", "SNR": "",
}
next_status_refresh = 0.0

devices = {"ConnDevCount": "", "ConnDevNames": ""}
next_devices_refresh = 0.0

while True:
    now = time.time()

    # Refresh public IP (slow)
    if now >= next_public_ip_refresh:
        last_public_ip = safe_call(lambda: fetch_public_ip() or last_public_ip, last_public_ip)
        next_public_ip_refresh = now + PUBLIC_IP_REFRESH_SECONDS

    # Refresh local status (medium)
    if now >= next_status_refresh:
        status = safe_call(get_device_status_snapshot, status)
        next_status_refresh = now + STATUS_REFRESH_SECONDS

    # Refresh connected devices (slow)
    if now >= next_devices_refresh:
        devices = safe_call(get_connected_devices_snapshot, devices)
        next_devices_refresh = now + DEVICES_REFRESH_SECONDS

    # Ping once
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    src_ip = get_source_ip(DEST)

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

    print(
        f"{ts}\t{src_ip}\t{DEST}\t{success}\t{latency}\t{last_public_ip}\t"
        f"{status.get('WanStatus','')}\t{status.get('SimStatus','')}\t{status.get('Tech','')}\t"
        f"{status.get('Band','')}\t{status.get('Bandwidth','')}\t{status.get('DeviceIPv4','')}\t"
        f"{status.get('Carrier','')}\t{status.get('APN','')}\t{status.get('ICCID','')}\t"
        f"{status.get('ECGI','')}\t{status.get('PCI','')}\t{status.get('RSRP','')}\t"
        f"{status.get('RSRQ','')}\t{status.get('SNR','')}\t"
        f"{devices.get('ConnDevCount','')}\t{devices.get('ConnDevNames','')}",
        flush=True,
    )

    time.sleep(1)
