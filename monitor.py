#!/usr/bin/env python3
"""
Cellular Router Monitor - Modular Version
Supports Inseego FX-series and Teltonika RUT-series routers.
"""
import os
import time
from datetime import datetime
from dotenv import load_dotenv

from collectors import InseegoCollector, TeltonikaCollector, RPiNetworkCollector

load_dotenv()

# --- Configuration from Environment ---
DEVICE_TYPE = os.getenv("DEVICE_TYPE", "fx3110").strip().lower()
BIND_INTERFACE = os.getenv("BIND_INTERFACE") or None
DEST = os.getenv("DEST", "8.8.8.8")

# Polling intervals
MAIN_LOOP_INTERVAL = int(os.getenv("MAIN_LOOP_INTERVAL", "5"))
PUBLIC_IP_REFRESH_SECONDS = int(os.getenv("PUBLIC_IP_REFRESH_SECONDS", "0"))


def build_cellular_collector():
    """Factory function to create the appropriate cellular collector."""
    if DEVICE_TYPE == "rutm50":
        # Check if collector script mode is enabled
        use_script = os.getenv("RUTM50_USE_COLLECTOR_SCRIPT", "false").lower() in ("true", "1", "yes")
        script_path = os.getenv("RUTM50_COLLECTOR_SCRIPT_PATH", "/tmp/teltonika_collector.sh")

        return TeltonikaCollector(
            ssh_host=os.getenv("RUTM50_SSH_HOST", ""),
            ssh_user=os.getenv("RUTM50_SSH_USER", "root"),
            ssh_port=int(os.getenv("RUTM50_SSH_PORT", "22")),
            ssh_password=os.getenv("RUTM50_SSH_PASSWORD"),
            ssh_key=os.getenv("RUTM50_SSH_KEY"),
            ssh_strict=os.getenv("RUTM50_SSH_STRICT", "accept-new"),
            ssh_timeout=float(os.getenv("RUTM50_SSH_TIMEOUT", "5")),
            cell_iface=os.getenv("RUTM50_CELL_IFACE", "mob1s1a1"),
            use_collector_script=use_script,
            collector_script_path=script_path,
        )
    else:
        # Default to Inseego FX-series
        return InseegoCollector(
            base_url=os.getenv("DEVICE_BASE", "http://192.168.1.1")
        )


def safe_get(fn, default=None):
    """Safely call a function, returning default on exception."""
    try:
        return fn()
    except Exception:
        return default if default is not None else {}


def main():
    """Main monitoring loop."""
    # Initialize collectors
    cellular = build_cellular_collector()
    network = RPiNetworkCollector()

    # Print TSV header
    print(
        "Timestamp\tSourceIP\tActiveInterface\tDestIP\tSuccess\tLatency_ms\tPublicIP\t"
        "WanStatus\tWanSource\tSimStatus\tTech\tBand\tBandwidth\tDeviceIPv4\tCarrier\tAPN\tICCID\t"
        "RSRP\tRSRQ\tSNR\tRSSI\tModel\tManufacturer\tFirmware\tIMEI\tSerial",
        flush=True,
    )

    # Cached values
    last_public_ip = ""
    next_public_ip_refresh = 0.0

    while True:
        now = time.time()

        # Refresh public IP periodically
        if now >= next_public_ip_refresh:
            public_ip = safe_get(network.get_public_ip, last_public_ip)
            if public_ip:
                last_public_ip = public_ip
            next_public_ip_refresh = now + PUBLIC_IP_REFRESH_SECONDS

        # Refresh cellular data (single SSH call if collector script enabled)
        if hasattr(cellular, 'refresh_data'):
            cellular.refresh_data()

        # Collect cellular metrics
        signal = safe_get(cellular.get_signal_metrics, {})
        net_info = safe_get(cellular.get_network_info, {})
        connection = safe_get(cellular.get_connection_status, {})
        sim_info = safe_get(cellular.get_sim_info, {})
        device_info = safe_get(cellular.get_device_info, {})

        # Perform ping test
        ping_result = safe_get(lambda: network.ping(DEST, BIND_INTERFACE), {})
        active_if = safe_get(lambda: network.get_active_interface(DEST), "unknown")

        # Format timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        # Output TSV line
        print(
            f"{timestamp}\t"
            f"{ping_result.get('source_ip', '')}\t"
            f"{active_if}\t"
            f"{DEST}\t"
            f"{ping_result.get('success', False)}\t"
            f"{ping_result.get('latency_ms') or ''}\t"
            f"{last_public_ip}\t"
            f"{connection.get('wan_status', '')}\t"
            f"{connection.get('wan_source', '')}\t"
            f"{sim_info.get('sim_status', '')}\t"
            f"{net_info.get('technology', '')}\t"
            f"{net_info.get('band', '')}\t"
            f"{net_info.get('bandwidth', '')}\t"
            f"{connection.get('device_ipv4', '')}\t"
            f"{net_info.get('carrier', '')}\t"
            f"{sim_info.get('apn', '')}\t"
            f"{sim_info.get('iccid', '')}\t"
            f"{signal.get('rsrp') or ''}\t"
            f"{signal.get('rsrq') or ''}\t"
            f"{signal.get('snr') or ''}\t"
            f"{signal.get('rssi') or ''}\t"
            f"{device_info.get('model', '')}\t"
            f"{device_info.get('manufacturer', '')}\t"
            f"{device_info.get('firmware', '')}\t"
            f"{device_info.get('imei', '')}\t"
            f"{device_info.get('serial', '')}",
            flush=True,
        )

        time.sleep(MAIN_LOOP_INTERVAL)


if __name__ == "__main__":
    main()
