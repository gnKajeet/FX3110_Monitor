#!/usr/bin/env python3
"""
Cellular Router Monitor - Modular Version
Supports Inseego FX3110, Inseego FX4200, and Teltonika RUT-series routers.
"""
import time
from datetime import datetime

from config import load_config, get_device_config
from collectors import InseegoCollector, InseegoFX4200Collector, TeltonikaCollector, RPiNetworkCollector


def build_cellular_collector(config: dict):
    """Factory function to create the appropriate cellular collector."""
    device_type = config.get("device_type", "fx3110").strip().lower()
    dev_cfg = get_device_config(config)

    if device_type == "fx4200":
        return InseegoFX4200Collector(
            base_url=dev_cfg.get("base_url", "https://192.168.1.1"),
            password=dev_cfg.get("password", ""),
            verify_ssl=dev_cfg.get("verify_ssl", False),
            session_refresh=dev_cfg.get("session_refresh", 500),
        )
    elif device_type == "rutm50":
        ssh_cfg = dev_cfg.get("ssh", {})
        script_cfg = dev_cfg.get("collector_script", {})
        return TeltonikaCollector(
            ssh_host=ssh_cfg.get("host", ""),
            ssh_user=ssh_cfg.get("user", "root"),
            ssh_port=int(ssh_cfg.get("port", 22)),
            ssh_password=ssh_cfg.get("password"),
            ssh_key=ssh_cfg.get("key"),
            ssh_strict=ssh_cfg.get("strict_host_key", "accept-new"),
            ssh_timeout=float(ssh_cfg.get("timeout", 5)),
            cell_iface=dev_cfg.get("cell_interface", "mob1s1a1"),
            use_collector_script=script_cfg.get("enabled", False),
            collector_script_path=script_cfg.get("path", "/tmp/teltonika_collector.sh"),
        )
    else:
        # Default to Inseego FX3110
        return InseegoCollector(
            base_url=dev_cfg.get("base_url", "http://192.168.1.1")
        )


def safe_get(fn, default=None):
    """Safely call a function, returning default on exception."""
    try:
        return fn()
    except Exception:
        return default if default is not None else {}


def main():
    """Main monitoring loop."""
    config = load_config()
    net_cfg = config.get("network", {})
    mon_cfg = config.get("monitor", {})

    device_type = config.get("device_type", "fx3110")
    bind_interface = net_cfg.get("bind_interface") or None
    dest = net_cfg.get("ping_target", "8.8.8.8")
    loop_interval = mon_cfg.get("interval", 5)
    public_ip_refresh = net_cfg.get("public_ip_refresh", 0)

    # Initialize collectors
    cellular = build_cellular_collector(config)
    network = RPiNetworkCollector()

    print(f"[Monitor] Device type: {device_type}", flush=True)

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
            next_public_ip_refresh = now + public_ip_refresh

        # Refresh cellular data (batch API calls)
        cellular.refresh_data()

        # Collect cellular metrics
        signal = safe_get(cellular.get_signal_metrics, {})
        net_info = safe_get(cellular.get_network_info, {})
        connection = safe_get(cellular.get_connection_status, {})
        sim_info = safe_get(cellular.get_sim_info, {})
        device_info = safe_get(cellular.get_device_info, {})

        # Perform ping test
        ping_result = safe_get(lambda: network.ping(dest, bind_interface), {})
        active_if = safe_get(lambda: network.get_active_interface(dest), "unknown")

        # Format timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        # Output TSV line
        print(
            f"{timestamp}\t"
            f"{ping_result.get('source_ip', '')}\t"
            f"{active_if}\t"
            f"{dest}\t"
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

        time.sleep(loop_interval)


if __name__ == "__main__":
    main()
