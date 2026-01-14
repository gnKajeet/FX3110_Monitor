# FX3110 Monitor - Current Status

**Last Updated:** 2026-01-13
**Branch:** refactor/modular-collectors
**Version:** 3.0.0 (unreleased)

## Project Summary

The FX3110 Monitor is a lightweight cellular modem monitoring system that supports multiple device types through a modular architecture. Currently deployed on Raspberry Pi at 192.168.86.38, monitoring a Teltonika RUTM50 cellular router.

## Current Deployment

### Hardware Configuration
- **Platform:** Raspberry Pi (user: inseego@192.168.86.38)
- **Router:** Teltonika RUTM50 (192.168.3.1)
- **Modem:** Quectel RG520N-NA (internal to RUTM50)
- **Network:** Dual-interface setup
  - Ethernet: Connected to RUTM50 at 192.168.3.x
  - WiFi: Connected to home network at 192.168.86.38

### Active Services
- **fx3110-monitor** - Data collection container
  - Runs monitor.py with TeltonikaCollector
  - Logs to ~/FX3110_Monitor/logs/fx3110_log.tsv
  - 10-second collection interval
- **fx3110-api** - Dashboard and API container
  - FastAPI service on port 8080
  - Dashboard: http://192.168.86.38:8080/
  - Real-time updates every 5 seconds

### Current Metrics Being Collected
- Signal Metrics: RSRP, RSRQ, SNR, RSSI (from gsmctl -E cache)
- Network Info: Carrier (AT&T), Technology (LTE), Band (LTE_B2)
- WAN Status: Connected via Ethernet (detected via mwan3)
- Connection: Device IP 192.168.86.43, Public IP 151.200.36.142
- SIM Info: APN (sentinelent01.com.attz), ICCID, status
- Device Info: Model (RUTM50), Manufacturer (Teltonika/Quectel), Firmware, IMEI, Serial
- Network Tests: Ping to 8.8.8.8 with latency tracking

## Architecture Overview

### Modular Collector System
The system uses a **factory pattern** with abstract base classes to support multiple device types:

```
monitor.py
    ↓
build_cellular_collector() [Factory]
    ↓
TeltonikaCollector (current) OR InseegoCollector
    ↓
Abstract Methods:
  - get_signal_metrics()
  - get_network_info()
  - get_connection_status()
  - get_sim_info()
  - get_device_info()
```

### Implemented Collectors

#### 1. TeltonikaCollector (Active)
**Location:** collectors/teltonika.py
**Supports:** RUTM50, RUTX series
**Method:** SSH + gsmctl + ubus + mwan3

**Key Features:**
- Signal metrics from `gsmctl -E` JSON (reads from cache object)
- WAN source via `mwan3 status` (checks active 100% policy)
- Carrier info from `gsmctl -o`, `-t`, `-b`
- APN from `uci get network.mob1s1a1.apn`
- ICCID from `gsmctl -J`
- Failover-aware WAN detection

**Configuration:**
```bash
DEVICE_TYPE=rutm50
RUTM50_SSH_HOST=192.168.3.1
RUTM50_SSH_PASSWORD=smartSIM12#
RUTM50_CELL_IFACE=mob1s1a1
```

#### 2. InseegoCollector
**Location:** collectors/inseego.py
**Supports:** FX3110, FX2000, MiFi series
**Method:** HTTP scraping of web interface

**Key Features:**
- HTML element ID extraction for metrics
- JSON endpoint parsing for device info
- Web interface at http://192.168.1.1

**Configuration:**
```bash
DEVICE_TYPE=inseego
DEVICE_BASE=http://192.168.1.1
```

#### 3. RPiNetworkCollector
**Location:** collectors/rpi_network.py
**Supports:** Network utilities (ping, routing, public IP)

**Key Features:**
- Ping with optional interface binding
- Route detection via `ip route get`
- Public IP lookup from multiple services

### Dashboard Features
**URL:** http://192.168.86.38:8080/

- **Dynamic Title:** Shows device model (e.g., "RUTM50 Monitor Dashboard")
- **Real-time Updates:** Auto-refresh every 5 seconds
- **Status Cards:**
  - WAN Source (Cellular/Ethernet) with color coding
  - Connection status with latency stats
  - Signal strength with RSRP visualization
  - Carrier and network info
  - SIM card details
- **Historical Data:**
  - Recent log entries
  - Configuration changes detection
  - Signal/latency anomaly alerts
- **Dark Mode:** Optimized for 24/7 monitoring

## Recent Changes (Refactoring Branch)

### Major Refactoring (refactor/modular-collectors branch)

#### 1. Modular Architecture Implementation
- Created abstract base classes (CellularCollector, NetworkCollector)
- Separated device-specific logic into collector modules
- Implemented factory pattern in monitor.py
- Deprecated monolithic FX3110_Monitor.py

#### 2. Critical Bug Fixes

**Signal Metrics Bug (RUTM50):**
- **Issue:** RSRP showing TAC (5382), RSRQ showing PCID (493)
- **Cause:** Reading from cell_info fields instead of cache object
- **Fix:** Updated to read from cache.rsrp_value, cache.rsrq_value, cache.sinr_value
- **Location:** collectors/teltonika.py:87-105

**WAN Source Detection Bug:**
- **Issue:** Showing "Cellular" when actually on Ethernet
- **Cause:** Checking interface online status instead of active routing policy
- **Fix:** Parse mwan3 output for interface with 100% policy allocation
- **Location:** collectors/teltonika.py:133-145

**Model Name Issue:**
- **Issue:** Dashboard showing "RG520N-NA" (modem) instead of "RUTM50" (router)
- **Fix:** Updated get_device_info() to return router model as primary
- **Location:** collectors/teltonika.py:240-267

#### 3. Container Improvements
- Fixed log file permissions (user: 1000:1000)
- Updated docker-compose.yml with command override using tee
- Proper stdout/file logging for docker logs and TSV output

#### 4. Documentation
- Created MODULAR_ARCHITECTURE.md (comprehensive architecture guide)
- Updated .clinerules with collector details and bug fix info
- Documented mwan3 integration and testing strategy

## Known Issues

### Resolved
- ✅ Signal metrics showing incorrect values (fixed)
- ✅ WAN source not detecting failover properly (fixed)
- ✅ Dashboard showing modem model instead of router model (fixed)
- ✅ Container permission errors writing logs (fixed)

### Active
- None currently

## Testing Status

### Verified Functionality
- ✅ Signal metrics displaying correctly (RSRP: -92 dBm, RSRQ: -6 dB, SNR: 15 dB)
- ✅ WAN source detection working (Ethernet when wan=100%, Cellular when mob1s1a1=100%)
- ✅ Model name showing "RUTM50" in dashboard
- ✅ APN collection working (sentinelent01.com.attz)
- ✅ Carrier detection working (AT&T)
- ✅ Public IP tracking working (151.200.36.142 via ethernet)
- ✅ Dashboard title dynamic updates
- ✅ Container logging to both docker logs and TSV file

### Pending Tests
- Actual failover event (disconnect ethernet, verify cellular takeover detection)
- Inseego device support (no hardware available currently)
- Load testing (long-term stability)

## Configuration Files

### Current .env Configuration
```bash
# Device selection
DEVICE_TYPE=rutm50

# Teltonika RUTM50
RUTM50_SSH_HOST=192.168.3.1
RUTM50_SSH_USER=root
RUTM50_SSH_PASSWORD=smartSIM12#
RUTM50_CELL_IFACE=mob1s1a1

# Monitoring
MAIN_LOOP_INTERVAL=10
DEST=8.8.8.8
```

### Docker Compose Services
```yaml
services:
  fx3110-monitor:
    build: .
    container_name: fx3110-monitor
    user: "1000:1000"
    network_mode: host
    command: sh -c "python monitor.py | tee /logs/fx3110_log.tsv"
    volumes:
      - ./logs:/logs
    cap_add:
      - NET_RAW
      - NET_ADMIN

  fx3110-api:
    build: ./api
    container_name: fx3110-api
    ports:
      - "8080:8080"
    volumes:
      - ./logs:/logs:ro
    depends_on:
      - fx3110-monitor
```

## Data Flow

```
RUTM50 (192.168.3.1)
    ↓ SSH
TeltonikaCollector
    ↓ gsmctl -E, mwan3 status, ubus
Signal Metrics, WAN Status, Network Info
    ↓
monitor.py (main loop)
    ↓ TSV format
logs/fx3110_log.tsv
    ↓ read-only mount
FastAPI Service (api/main.py)
    ↓ JSON endpoints
Dashboard (templates/dashboard.html)
    ↓ JavaScript fetch
Browser (http://192.168.86.38:8080/)
```

## API Endpoints

### Status
- `GET /` - Dashboard web interface
- `GET /api/status` - Current status snapshot
- `GET /api/health` - Health check

### Data
- `GET /api/recent?count=100` - Recent log entries
- `GET /api/stats` - Statistical summary (min/max/avg)
- `GET /api/changes` - Configuration change detection
- `GET /api/anomalies` - Signal and latency anomaly detection

## File Structure

```
FX3110_Monitor/
├── collectors/              # Modular collector system
│   ├── __init__.py
│   ├── base.py             # Abstract base classes
│   ├── inseego.py          # Inseego FX3110/FX2000 collector
│   ├── teltonika.py        # Teltonika RUTM50/RUTX collector
│   └── rpi_network.py      # Network utilities
├── api/                     # Dashboard and API service
│   ├── main.py             # FastAPI application
│   ├── Dockerfile
│   ├── requirements.txt
│   └── templates/
│       └── dashboard.html
├── docs/                    # Documentation
│   ├── ARCHITECTURE.md     # System design
│   ├── MODULAR_ARCHITECTURE.md  # Collector architecture
│   ├── DEPLOYMENT.md       # Deployment guide
│   ├── CHANGELOG.md        # Version history
│   └── CURRENT_STATUS.md   # This file
├── logs/                    # TSV log output
│   └── fx3110_log.tsv
├── monitor.py              # Main entry point (NEW)
├── FX3110_Monitor.py       # Legacy script (DEPRECATED)
├── docker-compose.yml      # Multi-service orchestration
├── Dockerfile              # Monitor container
├── requirements.txt
├── .env                    # Configuration (not committed)
├── .env.example            # Configuration template
├── .clinerules             # Project context for Claude Code
└── README.md
```

## Git Status

### Repository
- **GitHub:** https://github.com/gnKajeet/FX3110_Monitor
- **Current Branch:** refactor/modular-collectors
- **Status:** Ready to merge to main after final testing

### Recent Commits
1. `1fb6bcf` - Fix mwan3 WAN source detection to check active policy percentage
2. `9f6aebe` - Add modular architecture documentation and fix model name
3. `dcdb9bb` - Fix permissions, improve WAN detection, and add dynamic dashboard title
4. `40b8484` - Fix Dockerfile inline comment syntax
5. `193e22f` - Refactor to modular collectors architecture

## Next Steps

### Immediate (Before Merge)
1. Monitor for 24-48 hours to ensure stability
2. Test actual failover scenario (disconnect ethernet)
3. Verify cellular takeover detection with public IP change
4. Review all documentation for accuracy

### Short Term (Post-Merge)
1. Merge refactor/modular-collectors to main
2. Tag release as v3.0.0
3. Update production deployment
4. Archive legacy FX3110_Monitor.py

### Medium Term
1. Add unit tests for collectors
2. Add Cradlepoint collector (if hardware available)
3. Add Peplink collector (if hardware available)
4. Implement async collectors for better performance

### Long Term
1. InfluxDB integration for time-series storage
2. Grafana dashboards for historical analysis
3. Alerting system (email/SMS)
4. Bandwidth usage tracking
5. Cost monitoring for cellular data

## Support & Contact

- **Developer:** Working with Claude Code
- **Deployment:** Raspberry Pi at 192.168.86.38
- **Dashboard:** http://192.168.86.38:8080/
- **Issues:** https://github.com/gnKajeet/FX3110_Monitor/issues

---

**Document Status:** Living document, updated with major milestones
**Maintenance:** Update this file when major changes are deployed
**Related Docs:** See CHANGELOG.md for version history, MODULAR_ARCHITECTURE.md for technical details
