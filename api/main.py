import os
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
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="FX3110 Monitor API", version="1.0.0")

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
        self.last_values = {}  # Track last known values for change detection

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
        except (ValueError, KeyError) as e:
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
        # Always reload to get latest data
        self.reload_logs()

        if not self.cache:
            raise HTTPException(status_code=404, detail="No log data available")

        return self.cache[-1]

    def get_recent(self, count: int = 100) -> List[Dict]:
        """Get recent log entries."""
        # Always reload to get latest data
        self.reload_logs()

        return list(self.cache)[-count:]

    def detect_changes(self) -> Dict:
        """Detect changes in key values (IP, carrier, APN, ICCID)."""
        if len(self.cache) < 2:
            return {"changes": []}

        changes = []
        recent = list(self.cache)[-100:]  # Check last 100 entries

        # Track fields to monitor for changes
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

        return {"changes": changes[-20:]}  # Return last 20 changes

    def detect_anomalies(self, rsrp_threshold: int = 10, latency_threshold: int = 50) -> Dict:
        """Detect signal and latency anomalies."""
        if len(self.cache) < 10:
            return {"anomalies": []}

        anomalies = []
        recent = list(self.cache)[-100:]

        # Calculate baseline averages from first 50% of recent data
        baseline_data = recent[:len(recent)//2]

        # Calculate average RSRP (convert "-90 dBm" to -90)
        rsrp_values = []
        for entry in baseline_data:
            rsrp_str = entry.get("rsrp", "")
            if rsrp_str:
                try:
                    rsrp_val = int(rsrp_str.split()[0])
                    rsrp_values.append(rsrp_val)
                except (ValueError, IndexError):
                    pass

        avg_rsrp = sum(rsrp_values) / len(rsrp_values) if rsrp_values else None

        # Calculate average latency
        latency_values = [e["latency_ms"] for e in baseline_data if e.get("latency_ms")]
        avg_latency = sum(latency_values) / len(latency_values) if latency_values else None

        # Check recent entries for anomalies
        check_data = recent[len(recent)//2:]

        for entry in check_data:
            # RSRP anomaly detection
            if avg_rsrp:
                rsrp_str = entry.get("rsrp", "")
                if rsrp_str:
                    try:
                        rsrp_val = int(rsrp_str.split()[0])
                        if rsrp_val < (avg_rsrp - rsrp_threshold):
                            anomalies.append({
                                "timestamp": entry["timestamp"],
                                "type": "rsrp_drop",
                                "message": f"RSRP dropped to {rsrp_val} dBm (avg: {avg_rsrp:.1f} dBm)",
                                "severity": "warning" if rsrp_val > -100 else "critical"
                            })
                    except (ValueError, IndexError):
                        pass

            # Latency anomaly detection
            if avg_latency and entry.get("latency_ms"):
                latency = entry["latency_ms"]
                if latency > (avg_latency + latency_threshold):
                    anomalies.append({
                        "timestamp": entry["timestamp"],
                        "type": "latency_spike",
                        "message": f"Latency spiked to {latency} ms (avg: {avg_latency:.1f} ms)",
                        "severity": "warning" if latency < 500 else "critical"
                    })

            # Connection failure
            if not entry.get("success"):
                anomalies.append({
                    "timestamp": entry["timestamp"],
                    "type": "ping_failure",
                    "message": f"Ping to {entry.get('dest_ip')} failed",
                    "severity": "critical"
                })

        return {"anomalies": anomalies[-20:]}  # Return last 20 anomalies


# Initialize parser
parser = LogParser()


@app.get("/")
async def root():
    """Redirect to dashboard."""
    return FileResponse(str(TEMPLATE_DIR / "dashboard.html"))


@app.get("/api/status")
async def get_status():
    """Get current FX3110 status."""
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

    # Calculate statistics
    latencies = [e["latency_ms"] for e in recent if e.get("latency_ms")]
    successes = [e["success"] for e in recent]

    rsrp_values = []
    for e in recent:
        rsrp_str = e.get("rsrp", "")
        if rsrp_str:
            try:
                rsrp_values.append(int(rsrp_str.split()[0]))
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
        "log_file_exists": LOG_FILE.exists(),
        "cached_entries": len(parser.cache),
        "last_read": parser.last_read_time.isoformat() if parser.last_read_time else None,
    }


def _ssh_exec(command: str) -> str:
    """Execute SSH command on RUTM50 device."""
    ssh_host = os.getenv("RUTM50_SSH_HOST", "")
    ssh_user = os.getenv("RUTM50_SSH_USER", "root")
    ssh_port = os.getenv("RUTM50_SSH_PORT", "22")
    ssh_password = os.getenv("RUTM50_SSH_PASSWORD")
    ssh_key = os.getenv("RUTM50_SSH_KEY")
    ssh_strict = os.getenv("RUTM50_SSH_STRICT", "accept-new")
    ssh_timeout = float(os.getenv("RUTM50_SSH_TIMEOUT", "5"))

    if not ssh_host:
        raise HTTPException(status_code=500, detail="RUTM50_SSH_HOST not configured")

    # Build SSH command
    cmd = [
        "ssh",
        "-p", ssh_port,
        "-o", f"StrictHostKeyChecking={ssh_strict}",
        "-o", f"ConnectTimeout={int(ssh_timeout)}",
    ]

    if ssh_key:
        cmd.extend(["-i", ssh_key, "-o", "BatchMode=yes"])

    cmd.append(f"{ssh_user}@{ssh_host}")
    cmd.append(command)

    if ssh_password and not ssh_key:
        # Check for sshpass
        if subprocess.run(["which", "sshpass"], capture_output=True).returncode != 0:
            raise HTTPException(status_code=500, detail="sshpass is required for password-based SSH")
        cmd = ["sshpass", "-p", ssh_password] + cmd

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=ssh_timeout + 2
        )
        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"SSH command failed: {result.stderr.strip() or 'Unknown error'}"
            )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="SSH command timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SSH error: {str(e)}")


@app.get("/api/sim/current")
async def get_current_sim():
    """Get current active SIM slot (RUTM50 only)."""
    device_type = os.getenv("DEVICE_TYPE", "fx3110").strip().lower()

    if device_type != "rutm50":
        raise HTTPException(status_code=400, detail="SIM switching only supported for RUTM50")

    try:
        slot = _ssh_exec("gsmctl -T")
        return {"current_slot": int(slot.strip()), "device_type": "rutm50"}
    except ValueError:
        raise HTTPException(status_code=500, detail=f"Invalid SIM slot response: {slot}")


@app.post("/api/sim/switch")
async def switch_sim():
    """Switch to the other SIM slot (RUTM50 only)."""
    device_type = os.getenv("DEVICE_TYPE", "fx3110").strip().lower()

    if device_type != "rutm50":
        raise HTTPException(status_code=400, detail="SIM switching only supported for RUTM50")

    try:
        # Get current slot
        current_slot_str = _ssh_exec("gsmctl -T")
        current_slot = int(current_slot_str.strip())

        # Switch to the other slot
        switch_response = _ssh_exec("gsmctl -Y")

        # Validate the response
        if switch_response.strip() != "OK":
            raise HTTPException(
                status_code=500,
                detail=f"SIM switch command failed with response: {switch_response}"
            )

        # Wait a moment for the switch to complete
        import time
        time.sleep(2)

        # Verify new slot
        new_slot_str = _ssh_exec("gsmctl -T")
        new_slot = int(new_slot_str.strip())

        return {
            "success": True,
            "previous_slot": current_slot,
            "current_slot": new_slot,
            "message": f"Switched from SIM {current_slot} to SIM {new_slot}"
        }
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Invalid SIM slot response: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SIM switch failed: {str(e)}")


@app.on_event("startup")
async def startup_event():
    """Load initial data on startup."""
    parser.reload_logs()
