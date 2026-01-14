# Modular Collector Architecture

## Overview

The FX3110 Monitor has been refactored to support multiple cellular device types through a modular collector architecture. This design separates device-specific data collection logic from the monitoring core, making it easy to add support for new devices.

## Architecture

### Core Components

```
FX3110_Monitor/
├── collectors/              # Modular collector modules
│   ├── __init__.py         # Public API exports
│   ├── base.py             # Abstract base classes
│   ├── inseego.py          # Inseego FX-series collector
│   ├── teltonika.py        # Teltonika RUT-series collector
│   └── rpi_network.py      # RPi network utilities collector
├── monitor.py              # Main entry point with factory pattern
├── api/                    # Dashboard and API service
│   ├── main.py            # FastAPI application
│   └── templates/         # Dashboard HTML
└── FX3110_Monitor.py       # Legacy monolithic script (deprecated)
```

### Design Patterns

1. **Abstract Base Classes** - Define common interfaces
2. **Factory Pattern** - Select collector based on DEVICE_TYPE env var
3. **Separation of Concerns** - Device collectors vs network utilities
4. **Dependency Injection** - Configuration via environment variables

## Collector Interface

### CellularCollector (Abstract Base Class)

All cellular device collectors must implement:

```python
class CellularCollector(ABC):
    @abstractmethod
    def get_signal_metrics(self) -> Dict:
        """Returns: rsrp, rsrq, snr, rssi"""
        pass

    @abstractmethod
    def get_network_info(self) -> Dict:
        """Returns: carrier, technology, band, bandwidth"""
        pass

    @abstractmethod
    def get_connection_status(self) -> Dict:
        """Returns: wan_status, wan_source, device_ipv4"""
        pass

    @abstractmethod
    def get_sim_info(self) -> Dict:
        """Returns: apn, iccid, sim_status"""
        pass

    @abstractmethod
    def get_device_info(self) -> Dict:
        """Returns: model, manufacturer, firmware, imei, serial"""
        pass

    def get_all(self) -> Dict:
        """Combines all methods into single dict"""
        pass
```

### NetworkCollector (Abstract Base Class)

Network utility collectors must implement:

```python
class NetworkCollector(ABC):
    @abstractmethod
    def ping(self, dest: str, interface: Optional[str] = None) -> Dict:
        """Returns: success, latency_ms, source_ip"""
        pass

    @abstractmethod
    def get_active_interface(self, dest: str = "8.8.8.8") -> str:
        """Returns interface name that routes to destination"""
        pass

    @abstractmethod
    def get_public_ip(self) -> str:
        """Returns public IP address"""
        pass
```

## Implemented Collectors

### 1. InseegoCollector

**Supports:** FX3110, FX2000, MiFi series

**Data Source:** HTTP scraping of web interface

**Key Methods:**
- `_fetch_text(url)` - GET request for HTML
- `_fetch_json(url)` - GET request for JSON endpoints
- `_extract_by_id(html, element_id)` - Parse HTML by element ID

**Configuration:**
```bash
DEVICE_TYPE=inseego
DEVICE_BASE=http://192.168.1.1
```

### 2. TeltonikaCollector

**Supports:** RUTM50, RUTX series

**Data Source:** SSH + gsmctl + ubus commands

**Key Features:**
- Signal metrics from `gsmctl -E` JSON (fixed bug: reads from cache.rsrp_value)
- WAN status via `mwan3 status` (failover-aware) or `ubus` (fallback)
- Carrier info from `gsmctl -o`, `-t`, `-b`
- APN from `uci get network.mob1s1a1.apn`
- ICCID from `gsmctl -J`

**Configuration:**
```bash
DEVICE_TYPE=rutm50
RUTM50_SSH_HOST=192.168.3.1
RUTM50_SSH_USER=root
RUTM50_SSH_PASSWORD=your_password
RUTM50_CELL_IFACE=mob1s1a1
```

**SSH Authentication:**
- Supports password (via sshpass) or SSH key
- Automatically disables BatchMode for password auth
- StrictHostKeyChecking configurable

### 3. RPiNetworkCollector

**Supports:** Raspberry Pi network utilities

**Key Methods:**
- `ping()` - Execute ping with optional interface binding
- `get_active_interface()` - Detect routing interface via `ip route get`
- `get_public_ip()` - Query public IP from ipify.org with fallback

## Factory Pattern

The `build_cellular_collector()` function in `monitor.py` instantiates the correct collector based on `DEVICE_TYPE` environment variable:

```python
def build_cellular_collector():
    if DEVICE_TYPE == "rutm50":
        return TeltonikaCollector(
            ssh_host=os.getenv("RUTM50_SSH_HOST"),
            ssh_password=os.getenv("RUTM50_SSH_PASSWORD"),
            # ...config...
        )
    else:  # Default to Inseego
        return InseegoCollector(
            base_url=os.getenv("DEVICE_BASE", "http://192.168.1.1")
        )
```

## Main Loop (monitor.py)

```python
cellular = build_cellular_collector()
network = RPiNetworkCollector()

while True:
    # Collect cellular metrics
    signal = safe_get(cellular.get_signal_metrics, {})
    net_info = safe_get(cellular.get_network_info, {})
    conn = safe_get(cellular.get_connection_status, {})
    sim = safe_get(cellular.get_sim_info, {})
    device = safe_get(cellular.get_device_info, {})

    # Collect network metrics
    ping_result = safe_get(lambda: network.ping("8.8.8.8"), {})
    public_ip = safe_get(network.get_public_ip, "")

    # Output TSV row
    print(f"{timestamp}\t{signal['rsrp']}\t{net_info['carrier']}\t...")

    time.sleep(MAIN_LOOP_INTERVAL)
```

## Dashboard Integration

The API service in `api/main.py` reads TSV logs and serves data via FastAPI:

- **Dynamic Title**: Dashboard displays device model (e.g., "RUTM50 Monitor Dashboard")
- **Real-time Updates**: JavaScript polls `/api/status` endpoint
- **Device Info**: Model, manufacturer from TSV columns

## Bug Fixes

### Critical Signal Metrics Bug (RUTM50)

**Issue:** RSRP, RSRQ, SNR showing incorrect values

**Root Cause:** Original code read from wrong JSON fields in `gsmctl -E` output:
```python
# WRONG - reads cell_info fields
rsrp = cell_info[0].get("tac")  # TAC value 5382, not RSRP!
rsrq = cell_info[0].get("pcid")  # PCID value 493, not RSRQ!
```

**Fix:** Read from `cache` object instead:
```python
# CORRECT - reads cached signal values
data = json.loads(gsmctl_output)
cache = data.get("cache", {})
rsrp = cache.get("rsrp_value")  # -93 dBm
rsrq = cache.get("rsrq_value")  # -7 dB
snr = cache.get("sinr_value")   # 12 dB
rssi = cache.get("rssi_value")  # -65 dBm
```

**Location:** `collectors/teltonika.py:87-105`

## Adding New Devices

To add support for a new device type:

1. **Create collector module** in `collectors/new_device.py`
2. **Inherit from `CellularCollector`** base class
3. **Implement all abstract methods** (get_signal_metrics, etc.)
4. **Add factory logic** in `monitor.py` build_cellular_collector()
5. **Update .env.example** with new config variables
6. **Test** with actual hardware

Example template:

```python
from .base import CellularCollector

class NewDeviceCollector(CellularCollector):
    def __init__(self, config):
        self.config = config

    def get_signal_metrics(self) -> Dict:
        # Query device API/CLI
        return {"rsrp": ..., "rsrq": ..., "snr": ..., "rssi": ...}

    # ... implement other methods ...
```

## Configuration

### Environment Variables

**Common:**
- `DEVICE_TYPE` - "inseego" or "rutm50"
- `MAIN_LOOP_INTERVAL` - Seconds between readings (default: 10)

**Inseego-specific:**
- `DEVICE_BASE` - Base URL (default: http://192.168.1.1)

**Teltonika-specific:**
- `RUTM50_SSH_HOST` - SSH hostname/IP
- `RUTM50_SSH_USER` - SSH username (default: root)
- `RUTM50_SSH_PASSWORD` - SSH password
- `RUTM50_SSH_KEY` - Path to SSH private key (alternative to password)
- `RUTM50_CELL_IFACE` - Cellular interface name (default: mob1s1a1)

**Network:**
- `BIND_INTERFACE` - Force ping through specific interface (optional)

### Example .env

```bash
# Device selection
DEVICE_TYPE=rutm50

# Teltonika RUTM50 configuration
RUTM50_SSH_HOST=192.168.3.1
RUTM50_SSH_PASSWORD=smartSIM12#
RUTM50_CELL_IFACE=mob1s1a1

# Monitoring interval
MAIN_LOOP_INTERVAL=10
```

## Testing

### Unit Testing (Future)

Collectors are designed to be easily testable:

```python
# Mock SSH responses
def test_teltonika_signal_metrics():
    collector = TeltonikaCollector(...)
    with patch.object(collector, '_ssh_exec') as mock_ssh:
        mock_ssh.return_value = '{"cache": {"rsrp_value": -93}}'
        result = collector.get_signal_metrics()
        assert result["rsrp"] == -93
```

### Integration Testing

Test with actual hardware:

```bash
# Terminal 1: Monitor logs
docker-compose up -d && docker-compose logs -f fx3110-monitor

# Terminal 2: Watch TSV output
tail -f logs/fx3110_log.tsv

# Verify:
# - Signal metrics appear correctly
# - WAN source shows Cellular when on cellular
# - Failover detected when switching
```

## Migration from Legacy

The monolithic `FX3110_Monitor.py` is kept for backward compatibility but is deprecated. To migrate:

1. **Update Dockerfile** CMD to run `monitor.py` instead
2. **Update docker-compose.yml** command override
3. **Configure DEVICE_TYPE** in .env
4. **Test** thoroughly before removing FX3110_Monitor.py

## Future Enhancements

- [ ] Add Cradlepoint collector
- [ ] Add Peplink collector
- [ ] Add Sierra Wireless collector
- [ ] Unit test suite with pytest
- [ ] Collector plugin system (dynamic loading)
- [ ] Metrics caching to reduce API calls
- [ ] Health check endpoints for each collector
- [ ] Async collectors (asyncio) for better performance
