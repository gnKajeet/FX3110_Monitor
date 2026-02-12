import os
import sys
import subprocess
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from pathlib import Path
import csv
from collections import deque

# Add parent directory so we can import config and collectors
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import load_config, get_device_config

app = FastAPI(title="FX3110 Monitor API", version="2.0.0")

# CORS middleware for web dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (prefer Docker paths when available)
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = Path("/app/static") if Path("/app/static").exists() else BASE_DIR / "static"
TEMPLATE_DIR = Path("/app/templates") if Path("/app/templates").exists() else BASE_DIR / "templates"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Load config
_config = load_config()

if os.getenv("LOG_FILE"):
    LOG_FILE = Path(os.getenv("LOG_FILE", ""))
elif Path("/logs").exists():
    LOG_FILE = Path("/logs/fx3110_log.tsv")
else:
    LOG_FILE = BASE_DIR.parent / "logs" / "fx3110_log.tsv"
MAX_CACHE_LINES = 1000  # Keep last 1000 lines in memory


class LogParser:
    """Parse and cache TSV log data with change detection."""

    def __init__(self):
        self.cache = deque(maxlen=MAX_CACHE_LINES)
        self.headers = []
        self.last_read_time = None
        self.last_values = {}

    def _parse_line(self, row: Dict[str, str]) -> Dict:
        """Parse a TSV row into structured data."""
        try:
            return {
                "timestamp": row.get("Timestamp", ""),
                "source_ip": row.get("SourceIP", ""),
                "active_interface": row.get("ActiveInterface", ""),
                "dest_ip": row.get("DestIP", ""),
                "success": row.get("Success", "").lower() == "true",
                "latency_ms": int(row.get("Latency_ms") or "0") if row.get("Latency_ms") else None,
                "public_ip": row.get("PublicIP", ""),
                "wan_status": row.get("WanStatus", ""),
                "wan_source": row.get("WanSource", ""),
                "sim_status": row.get("SimStatus", ""),
                "technology": row.get("Tech", ""),
                "band": row.get("Band", ""),
                "bandwidth": row.get("Bandwidth", ""),
                "device_ipv4": row.get("DeviceIPv4", ""),
                "carrier": row.get("Carrier", ""),
                "apn": row.get("APN", ""),
                "iccid": row.get("ICCID", ""),
                "ecgi": row.get("ECGI", ""),
                "pci": row.get("PCI", ""),
                "rsrp": row.get("RSRP", ""),
                "rsrq": row.get("RSRQ", ""),
                "snr": row.get("SNR", ""),
                "rssi": row.get("RSSI", ""),
                "model": row.get("Model", ""),
                "manufacturer": row.get("Manufacturer", ""),
                "firmware": row.get("Firmware", ""),
                "imei": row.get("IMEI", ""),
                "serial": row.get("Serial", ""),
                "conn_dev_count": row.get("ConnDevCount", ""),
                "conn_dev_names": row.get("ConnDevNames", ""),
            }
        except (ValueError, KeyError):
            return None

    def reload_logs(self, tail_lines: int = MAX_CACHE_LINES):
        """Reload logs from file."""
        if not LOG_FILE.exists():
            return

        self.cache.clear()

        with open(LOG_FILE, 'r') as f:
            reader = csv.DictReader(f, delimiter='\t')
            self.headers = reader.fieldnames or []

            # Read all lines, keep last N
            all_rows = list(reader)
            for row in all_rows[-tail_lines:]:
                parsed = self._parse_line(row)
                if parsed:
                    self.cache.append(parsed)

        self.last_read_time = datetime.now()

    def get_current_status(self) -> Dict:
        """Get the most recent status entry."""
        self.reload_logs()

        if not self.cache:
            raise HTTPException(status_code=404, detail="No log data available")

        return self.cache[-1]

    def get_recent(self, count: int = 100) -> List[Dict]:
        """Get recent log entries."""
        self.reload_logs()
        return list(self.cache)[-count:]

    def detect_changes(self) -> Dict:
        """Detect changes in key values (IP, carrier, APN, ICCID)."""
        if len(self.cache) < 2:
            return {"changes": []}

        changes = []
        recent = list(self.cache)[-100:]

        watch_fields = ["wan_source", "active_interface", "public_ip", "carrier", "apn", "iccid", "device_ipv4"]

        for i in range(1, len(recent)):
            prev = recent[i - 1]
            curr = recent[i]

            for field in watch_fields:
                prev_val = prev.get(field, "")
                curr_val = curr.get(field, "")

                if prev_val != curr_val and curr_val:
                    changes.append({
                        "timestamp": curr["timestamp"],
                        "field": field,
                        "old_value": prev_val,
                        "new_value": curr_val,
                    })

        return {"changes": changes[-20:]}

    def detect_anomalies(self, rsrp_threshold: int = 10, latency_threshold: int = 50) -> Dict:
        """Detect signal and latency anomalies."""
        if len(self.cache) < 10:
            return {"anomalies": []}

        anomalies = []
        recent = list(self.cache)[-100:]

        baseline_data = recent[:len(recent)//2]

        rsrp_values = []
        for entry in baseline_data:
            rsrp_str = entry.get("rsrp", "")
            if rsrp_str:
                try:
                    rsrp_val = int(str(rsrp_str).split()[0])
                    rsrp_values.append(rsrp_val)
                except (ValueError, IndexError):
                    pass

        avg_rsrp = sum(rsrp_values) / len(rsrp_values) if rsrp_values else None

        latency_values = [e["latency_ms"] for e in baseline_data if e.get("latency_ms")]
        avg_latency = sum(latency_values) / len(latency_values) if latency_values else None

        check_data = recent[len(recent)//2:]

        for entry in check_data:
            if avg_rsrp:
                rsrp_str = entry.get("rsrp", "")
                if rsrp_str:
                    try:
                        rsrp_val = int(str(rsrp_str).split()[0])
                        if rsrp_val < (avg_rsrp - rsrp_threshold):
                            anomalies.append({
                                "timestamp": entry["timestamp"],
                                "type": "rsrp_drop",
                                "message": f"RSRP dropped to {rsrp_val} dBm (avg: {avg_rsrp:.1f} dBm)",
                                "severity": "warning" if rsrp_val > -100 else "critical"
                            })
                    except (ValueError, IndexError):
                        pass

            if avg_latency and entry.get("latency_ms"):
                latency = entry["latency_ms"]
                if latency > (avg_latency + latency_threshold):
                    anomalies.append({
                        "timestamp": entry["timestamp"],
                        "type": "latency_spike",
                        "message": f"Latency spiked to {latency} ms (avg: {avg_latency:.1f} ms)",
                        "severity": "warning" if latency < 500 else "critical"
                    })

            if not entry.get("success"):
                anomalies.append({
                    "timestamp": entry["timestamp"],
                    "type": "ping_failure",
                    "message": f"Ping to {entry.get('dest_ip')} failed",
                    "severity": "critical"
                })

        return {"anomalies": anomalies[-20:]}


# Initialize parser
parser = LogParser()


@app.get("/")
async def root():
    """Redirect to dashboard."""
    return FileResponse(str(TEMPLATE_DIR / "dashboard.html"))


@app.get("/api/status")
async def get_status():
    """Get current device status."""
    return parser.get_current_status()


@app.get("/api/recent")
async def get_recent(count: int = 100):
    """Get recent log entries."""
    if count > MAX_CACHE_LINES:
        count = MAX_CACHE_LINES
    return {"entries": parser.get_recent(count)}


@app.get("/api/changes")
async def get_changes():
    """Detect changes in IP, carrier, APN, ICCID."""
    return parser.detect_changes()


@app.get("/api/anomalies")
async def get_anomalies(rsrp_threshold: int = 10, latency_threshold: int = 50):
    """Detect signal and latency anomalies."""
    return parser.detect_anomalies(rsrp_threshold, latency_threshold)


@app.get("/api/stats")
async def get_stats():
    """Get statistical summary."""
    recent = parser.get_recent(100)

    if not recent:
        raise HTTPException(status_code=404, detail="No data available")

    latencies = [e["latency_ms"] for e in recent if e.get("latency_ms")]
    successes = [e["success"] for e in recent]

    rsrp_values = []
    for e in recent:
        rsrp_str = e.get("rsrp", "")
        if rsrp_str:
            try:
                rsrp_values.append(int(str(rsrp_str).split()[0]))
            except (ValueError, IndexError):
                pass

    return {
        "total_samples": len(recent),
        "success_rate": (sum(successes) / len(successes) * 100) if successes else 0,
        "latency": {
            "min": min(latencies) if latencies else 0,
            "max": max(latencies) if latencies else 0,
            "avg": sum(latencies) / len(latencies) if latencies else 0,
        },
        "rsrp": {
            "min": min(rsrp_values) if rsrp_values else 0,
            "max": max(rsrp_values) if rsrp_values else 0,
            "avg": sum(rsrp_values) / len(rsrp_values) if rsrp_values else 0,
        },
        "current_carrier": recent[-1].get("carrier", ""),
        "current_technology": recent[-1].get("technology", ""),
        "current_band": recent[-1].get("band", ""),
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "device_type": _config.get("device_type", "fx3110"),
        "log_file_exists": LOG_FILE.exists(),
        "cached_entries": len(parser.cache),
        "last_read": parser.last_read_time.isoformat() if parser.last_read_time else None,
    }


# --- SIM Operations ---

def _get_sim_collector():
    """Lazily create a collector for SIM operations."""
    device_type = _config.get("device_type", "fx3110")
    dev_cfg = get_device_config(_config)

    if device_type == "fx4200":
        from collectors.inseego_fx4200 import InseegoFX4200Collector
        return InseegoFX4200Collector(
            base_url=dev_cfg.get("base_url", "https://192.168.1.1"),
            password=dev_cfg.get("password", ""),
            verify_ssl=dev_cfg.get("verify_ssl", False),
            session_refresh=dev_cfg.get("session_refresh", 500),
        )
    elif device_type == "rutm50":
        return _create_rutm50_ssh_helper(dev_cfg)
    return None


def _create_rutm50_ssh_helper(dev_cfg: dict):
    """Create a simple SSH helper for RUTM50 SIM operations."""
    ssh_cfg = dev_cfg.get("ssh", {})

    class RUTM50SIMHelper:
        def __init__(self, ssh_cfg):
            self.host = ssh_cfg.get("host", "")
            self.user = ssh_cfg.get("user", "root")
            self.port = str(ssh_cfg.get("port", 22))
            self.password = ssh_cfg.get("password")
            self.key = ssh_cfg.get("key")
            self.strict = ssh_cfg.get("strict_host_key", "accept-new")
            self.timeout = float(ssh_cfg.get("timeout", 5))

        def _ssh_exec(self, command: str) -> str:
            if not self.host:
                raise RuntimeError("RUTM50 SSH host not configured")

            cmd = [
                "ssh", "-p", self.port,
                "-o", f"StrictHostKeyChecking={self.strict}",
                "-o", f"ConnectTimeout={int(self.timeout)}",
            ]
            if self.key:
                cmd.extend(["-i", self.key, "-o", "BatchMode=yes"])
            cmd.append(f"{self.user}@{self.host}")
            cmd.append(command)

            if self.password and not self.key:
                cmd = ["sshpass", "-p", self.password] + cmd

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout + 2)
            if result.returncode != 0:
                raise RuntimeError(f"SSH failed: {result.stderr.strip()}")
            return result.stdout.strip()

    return RUTM50SIMHelper(ssh_cfg)


_sim_collector = None


def _get_cached_sim_collector():
    global _sim_collector
    if _sim_collector is None:
        _sim_collector = _get_sim_collector()
    return _sim_collector


@app.get("/api/sim/current")
async def get_current_sim():
    """Get current active SIM info."""
    device_type = _config.get("device_type", "fx3110")
    collector = _get_cached_sim_collector()

    if collector is None:
        raise HTTPException(status_code=400, detail="Device does not support SIM operations")

    if device_type == "fx4200":
        try:
            collector.refresh_data()
            slots = collector.get_sim_slots_detail()
            active_imsi = collector.get_active_sim_imsi()
            return {
                "device_type": "fx4200",
                "active_imsi": active_imsi,
                "slots": slots,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    elif device_type == "rutm50":
        try:
            slot = collector._ssh_exec("gsmctl -T")
            return {"device_type": "rutm50", "current_slot": int(slot.strip())}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    raise HTTPException(status_code=400, detail="SIM operations not supported for this device")


@app.get("/api/sim/slots")
async def get_sim_slots():
    """Get all SIM slot details (FX4200)."""
    device_type = _config.get("device_type", "fx3110")
    collector = _get_cached_sim_collector()

    if device_type != "fx4200" or collector is None:
        raise HTTPException(status_code=400, detail="SIM slots endpoint only available for FX4200")

    try:
        collector.refresh_data()
        return {"slots": collector.get_sim_slots_detail()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sim/switch")
async def switch_sim(target_iccid: Optional[str] = None):
    """Switch to another SIM."""
    device_type = _config.get("device_type", "fx3110")
    collector = _get_cached_sim_collector()

    if collector is None:
        raise HTTPException(status_code=400, detail="Device does not support SIM switching")

    if device_type == "fx4200":
        try:
            if target_iccid:
                result = collector.switch_sim_by_iccid(target_iccid)
                return {"success": True, "switched_to_iccid": target_iccid, "result": result}
            else:
                # Auto-switch: find the inactive SIM and switch to it
                collector.refresh_data()
                slots = collector.get_sim_slots_detail()
                active_imsi = collector.get_active_sim_imsi()

                target_slot = None
                for slot in slots:
                    if slot.get("imsi") != active_imsi and slot.get("card_state") == 2:
                        target_slot = slot
                        break

                if not target_slot:
                    raise HTTPException(status_code=400, detail="No alternative SIM available")

                result = collector.switch_sim_by_imsi(target_slot["imsi"])
                return {
                    "success": True,
                    "switched_from": active_imsi,
                    "switched_to": target_slot.get("imsi"),
                    "switched_to_carrier": target_slot.get("oper_name", ""),
                    "result": result,
                }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    elif device_type == "rutm50":
        try:
            current_slot_str = collector._ssh_exec("gsmctl -T")
            current_slot = int(current_slot_str.strip())

            switch_response = collector._ssh_exec("gsmctl -Y")
            if switch_response.strip() != "OK":
                raise HTTPException(status_code=500, detail=f"SIM switch failed: {switch_response}")

            import time
            time.sleep(2)

            new_slot_str = collector._ssh_exec("gsmctl -T")
            new_slot = int(new_slot_str.strip())

            return {
                "success": True,
                "previous_slot": current_slot,
                "current_slot": new_slot,
                "message": f"Switched from SIM {current_slot} to SIM {new_slot}"
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    raise HTTPException(status_code=400, detail="SIM switching not supported for this device")


@app.on_event("startup")
async def startup_event():
    """Load initial data on startup."""
    parser.reload_logs()
