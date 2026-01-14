# Changelog

All notable changes to the FX3110 Monitor project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [3.0.0] - 2026-01-13

### Added - Modular Architecture Refactoring

#### Multi-Device Support via Collector Modules
- **Abstract Base Classes**: Defined `CellularCollector` and `NetworkCollector` interfaces
  - Standardized methods: get_signal_metrics(), get_network_info(), get_connection_status(), get_sim_info(), get_device_info()
  - Enables easy addition of new device types
- **Factory Pattern**: `build_cellular_collector()` function selects collector based on DEVICE_TYPE env var
- **TeltonikaCollector**: Full support for Teltonika RUTM50/RUTX routers
  - SSH-based data collection via gsmctl, ubus, and mwan3
  - Password authentication (sshpass) or SSH key support
  - Configurable cellular interface name
- **InseegoCollector**: Existing FX3110/FX2000 support refactored into modular design
  - HTTP scraping of web interface
  - HTML element ID extraction
  - JSON endpoint parsing
- **RPiNetworkCollector**: Separated network utilities from device-specific collectors
  - Ping with optional interface binding
  - Route detection
  - Public IP lookup with failover providers
- **New Main Entry Point**: `monitor.py` replaces monolithic FX3110_Monitor.py
  - Clean separation of concerns
  - Simplified main loop
  - Better error handling with safe_get() wrapper

#### Enhanced WAN Source Detection (RUTM50)
- **mwan3 Integration**: Uses `mwan3 status` for failover-aware WAN detection
  - Parses active routing policy (checks for 100% allocation)
  - Correctly identifies Cellular vs Ethernet based on actual traffic routing
  - Falls back to ubus + route checking if mwan3 unavailable
- **Policy-Based Detection**: No longer relies only on interface online status
  - Fixes false positives when both interfaces are online but only one is routing

#### Dynamic Dashboard Improvements
- **Device-Specific Titles**: Dashboard title updates based on device model
  - "RUTM50 Monitor Dashboard" for Teltonika routers
  - "FX3110 Monitor Dashboard" for Inseego modems
  - Manufacturer field shows router/modem combo (e.g., "Teltonika/Quectel")
- **Model Information**: Added model, manufacturer, firmware, IMEI, serial to API responses
  - Displayed in dashboard subtitle: "Real-time Teltonika cellular modem monitoring"
  - All fields parsed from TSV logs

#### Documentation
- **MODULAR_ARCHITECTURE.md**: Comprehensive architecture guide
  - Abstract base classes documentation
  - Factory pattern explanation
  - Collector implementation details
  - Critical bug fixes documented
  - Testing strategy and migration guide
  - Template for adding new device types
- **CURRENT_STATUS.md**: Living document showing project state
  - Current deployment details
  - Active configuration
  - Known issues and testing status
  - Data flow diagrams
  - Next steps roadmap
- **.clinerules**: Updated with modular architecture details
  - Collector system overview
  - Data collection methods for each device
  - Critical bug fix documentation

### Changed

#### Container Architecture
- **User Permissions**: Monitor container now runs as host user (UID 1000:1000)
  - Fixes permission denied errors when writing logs
  - Proper ownership of mounted log directory
- **Logging Strategy**: Changed CMD to use tee for dual output
  - Logs written to both docker logs (stdout) and TSV file
  - Easier debugging with `docker-compose logs -f`
- **Dockerfile Simplification**: Removed inline comments causing build errors
  - Separate comment lines for better compatibility

#### RUTM50 Data Collection
- **Signal Metrics Source**: Now reads from gsmctl -E JSON cache object
  - `cache.rsrp_value`, `cache.rsrq_value`, `cache.sinr_value`, `cache.rssi_value`
  - Previously incorrectly read from cell_info array
- **APN Collection**: Uses correct UCI path `network.mob1s1a1.apn`
  - Previously used incorrect `network.mobile.apn`
- **Model Reporting**: Returns router model (RUTM50) instead of internal modem model (RG520N-NA)
  - More user-friendly and accurate
  - Modem manufacturer included in manufacturer field

### Fixed

#### Critical Signal Metrics Bug (RUTM50)
- **Issue**: RSRP showing TAC (5382), RSRQ showing PCID (493), SNR empty
- **Root Cause**: Parsing wrong fields from `gsmctl -E` JSON output
  - Was reading from `cell_info[0].tac`, `cell_info[0].pcid`
  - Should read from `cache.rsrp_value`, `cache.rsrq_value`
- **Impact**: All signal quality metrics were incorrect for RUTM50 users
- **Fix**: Updated TeltonikaCollector.get_signal_metrics() in collectors/teltonika.py:87-105
- **Verification**: Confirmed RSRP=-92 dBm, RSRQ=-6 dB, SNR=15 dB, RSSI=-65 dBm

#### WAN Source Detection Bug (RUTM50)
- **Issue**: Dashboard showing "Cellular" when public IP indicated Ethernet (151.x range)
- **Root Cause**: Code preferred cellular when both interfaces were online
  - Checked interface status but not active routing policy
  - mwan3 showed "wan (100%)" but code ignored this
- **Impact**: False indication of cellular failover
- **Fix**: Parse mwan3 output for interface with 100% policy allocation
  - Updated collectors/teltonika.py:133-145
  - Uses `re.finditer()` to find all percentages, selects the 100% interface
- **Verification**: Correctly shows "Ethernet" when wan=100%, will show "Cellular" when mob1s1a1=100%

#### Model Name Display
- **Issue**: Dashboard displayed "RG520N-NA Monitor Dashboard" (internal modem model)
- **Expected**: "RUTM50 Monitor Dashboard" (router model)
- **Fix**: Updated TeltonikaCollector.get_device_info() to return router model as primary
  - Model: "RUTM50"
  - Manufacturer: "Teltonika/Quectel" (router/modem)
- **Location**: collectors/teltonika.py:240-267

#### Container Log Permissions
- **Issue**: Container crash-looping with "Permission denied" writing to /logs/fx3110_log.tsv
- **Cause**: Container user (UID 1000) didn't match log directory owner
- **Fix**: Added `user: "1000:1000"` to docker-compose.yml
- **Additional**: Changed logging strategy to use tee command for dual output

### Deprecated

- **FX3110_Monitor.py**: Legacy monolithic script marked as deprecated
  - Kept in repository for backward compatibility
  - monitor.py is now the official entry point
  - Will be removed in v4.0.0

### Security

- **SSH Authentication**: TeltonikaCollector supports both password and key-based auth
  - Automatically disables BatchMode for password auth
  - StrictHostKeyChecking configurable (default: accept-new)
  - sshpass required for password authentication

---

## [2.0.0] - 2026-01-10

### Added - Major Feature Release

#### WAN Source Tracking (Cellular vs Ethernet Failover)
- **FX3110 WAN Source Detection**: Automatically detects whether the FX3110 modem is using its cellular connection or ethernet WAN port
- **Change Detection**: Tracks WAN source transitions (Cellular ↔ Ethernet) alongside IP, Carrier, APN, and ICCID changes
- **Dashboard Display**: Prominent color-coded WAN source indicator at top of dashboard
  - Green = Cellular
  - Orange = Ethernet
  - Red = Unknown
- **Environment Variable Support**: Monitor configuration now reads from environment variables
  - `BIND_INTERFACE` - Network interface binding
  - `DEST` - Ping destination
  - `DEVICE_BASE` - FX3110 device IP

#### Real-Time Web Dashboard
- **FastAPI REST API**: Lightweight API service that parses TSV logs and provides JSON endpoints
- **Auto-Refreshing Dashboard**: Real-time web interface with 5-second refresh interval
- **Dark Mode UI**: Optimized for 24/7 monitoring
- **Status Cards**:
  - FX3110 WAN Source (Cellular/Ethernet)
  - Connection Status
  - Latency with min/avg/max statistics
  - Cellular Info (Carrier, Technology, Band)
  - Signal Strength with RSRP meter visualization
  - SIM Card information
  - Connected devices count

#### Change Detection System
- **Automatic Tracking** of configuration changes:
  - WAN source changes (Cellular ↔ Ethernet)
  - Public IP address changes
  - Device IPv4 address changes
  - Carrier name changes
  - APN configuration changes
  - ICCID changes (SIM card swaps)
- **Historical Display**: Shows last 20 changes with timestamps and old→new values

#### Anomaly Detection
- **Signal Quality Monitoring**:
  - RSRP drops (configurable threshold, default: 10 dBm below average)
  - Latency spikes (configurable threshold, default: 50 ms above average)
  - Ping failures
- **Severity Levels**: Warning and Critical alerts
- **Color-Coded Display**: Visual indicators for anomaly severity

#### API Endpoints
- `GET /` - Dashboard web interface
- `GET /api/status` - Current modem status snapshot
- `GET /api/recent?count=N` - Recent log entries
- `GET /api/stats` - Statistical summary (min/max/avg latency and RSRP)
- `GET /api/changes` - Detected configuration changes
- `GET /api/anomalies?rsrp_threshold=N&latency_threshold=N` - Signal and latency anomalies
- `GET /api/health` - Service health check

#### Docker Deployment
- **Raspberry Pi Optimized**: Complete Docker Compose setup for Raspberry Pi deployment
- **Multi-Service Architecture**:
  - `fx3110-monitor` - Data collection service
  - `fx3110-api` - Dashboard and API service
  - Future-ready templates for InfluxDB and Grafana
- **Network Configuration**:
  - Host networking mode for direct eth0 interface access
  - Proper capabilities (NET_RAW, NET_ADMIN) for ping and interface binding
- **Auto-Restart**: Services configured with `restart: unless-stopped`

### Changed

#### Monitor Script Improvements
- **Linux/Raspberry Pi Compatibility**: Changed ping command from `-n` (Windows) to `-c` (Linux)
- **Cross-Platform Latency Parsing**: Supports both Windows and Linux ping output formats
- **Active Interface Detection**: Added `get_active_interface()` function using `ip route`
- **TSV Output Enhancements**: New columns added:
  - `ActiveInterface` - Network interface used for ping
  - `WanSource` - FX3110's WAN source (Cellular/Ethernet)

#### Configuration Management
- **Environment Variables**: Configuration moved from hardcoded constants to environment variables
- **Docker Compose Integration**: Settings managed via docker-compose.yml
- **Example Configuration**: `.env.example` template provided

### Fixed

- **File Permissions**: Fixed log directory permissions for Docker containers (UID 1000)
- **Ping Interface Binding**: Corrected `-I` flag usage for forcing traffic through specific interface
- **Log Output**: Ensured `PYTHONUNBUFFERED=1` for immediate log writes

### Documentation

- **ARCHITECTURE.md**: Complete system design documentation
  - Network topology diagrams
  - Current implementation details
  - Future API design specifications
  - Security considerations
  - Deployment architecture
- **DEPLOYMENT.md**: Step-by-step Raspberry Pi deployment guide
  - Docker installation instructions
  - Network configuration details
  - Troubleshooting common issues
  - Log rotation setup
  - Security hardening recommendations
- **README.md**: Updated with Docker-first approach
  - Quick start guide
  - Dashboard access instructions
  - API endpoint documentation
  - Feature highlights

## [1.0.0] - Initial Release

### Added

#### Core Monitoring Functionality
- **FX3110 Status Monitoring**: Scrapes WAN/SIM/RF status from FX3110 web interface
- **Ping Monitoring**: Tests connectivity to configurable destination (default: 8.8.8.8)
- **Public IP Tracking**: Periodic public IP checks via multiple providers (ifconfig.me, ipify, AWS)
- **Connected Devices**: Monitors device count and names from FX3110 JSON endpoint
- **TSV Logging**: Tab-separated value output for easy import to Excel/pandas

#### Collected Metrics
- Timestamp
- Source and Destination IP
- Ping success/failure
- Latency (ms)
- Public IP address
- WAN Status
- SIM Status
- Technology (4G LTE, 5G, etc.)
- Band information
- Bandwidth
- Device IPv4 address
- Carrier name
- APN
- ICCID (SIM card identifier)
- ECGI, PCI (cell identifiers)
- RSRP, RSRQ, SNR (signal quality metrics)
- Connected device count and names

#### Configuration Options
- `DEST` - Ping target IP
- `DEVICE_BASE` - FX3110 device IP (default: http://192.168.1.1)
- `PUBLIC_IP_REFRESH_SECONDS` - Public IP check interval (default: 60)
- `STATUS_REFRESH_SECONDS` - Device status refresh interval (default: 5)
- `DEVICES_REFRESH_SECONDS` - Connected devices refresh interval (default: 10)
- `MAX_DEVICE_NAMES` - Maximum device names to log (default: 5)

#### Error Handling
- **Graceful Degradation**: Failed fetches don't blank logs (cached values retained)
- **Safe Call Wrapper**: `safe_call()` function prevents crashes on exceptions
- **Timeout Protection**: All HTTP requests have configurable timeouts

---

## Version History

- **v3.0.0** (2026-01-13) - Modular architecture, multi-device support, RUTM50 integration, critical bug fixes
- **v2.0.0** (2026-01-10) - Real-time dashboard, WAN source tracking, anomaly detection, Docker deployment
- **v1.0.0** (Initial) - Basic monitoring with TSV logging

---

## Upgrade Notes

### Upgrading from v2.0.0 to v3.0.0

**Breaking Changes:**
- Main entry point changed from FX3110_Monitor.py to monitor.py
- New collector modules required (collectors/ directory)
- DEVICE_TYPE environment variable now required
- TSV log format unchanged (backward compatible)

**New Features:**
- Multi-device support (Inseego FX3110 and Teltonika RUTM50)
- Improved WAN source detection using mwan3
- Dynamic dashboard titles based on device model
- Fixed critical signal metrics bug for RUTM50

**Migration Steps:**

1. **Backup existing configuration:**
   ```bash
   cp .env .env.backup
   ```

2. **Pull latest code:**
   ```bash
   git fetch
   git checkout refactor/modular-collectors
   git pull
   ```

3. **Update .env file:**
   ```bash
   # For Teltonika RUTM50 users - ADD these lines:
   DEVICE_TYPE=rutm50
   RUTM50_SSH_HOST=192.168.3.1
   RUTM50_SSH_USER=root
   RUTM50_SSH_PASSWORD=your_password
   RUTM50_CELL_IFACE=mob1s1a1

   # For Inseego FX3110 users - ADD this line:
   DEVICE_TYPE=inseego
   # (DEVICE_BASE should already exist)
   ```

4. **Rebuild and restart:**
   ```bash
   docker-compose down
   docker-compose up -d --build
   ```

5. **Verify operation:**
   ```bash
   # Check logs
   docker-compose logs -f fx3110-monitor

   # Check dashboard
   curl http://localhost:8080/api/status
   ```

**Note:** Existing TSV logs are fully compatible. No data migration needed.

### Upgrading from v1.0.0 to v2.0.0

**Breaking Changes:**
- TSV log format changed (new columns: `ActiveInterface`, `WanSource`)
- Existing logs are compatible but won't have new fields

**Migration Steps:**

1. **Backup existing logs:**
   ```bash
   cp fx3110_log.tsv fx3110_log_v1.tsv.backup
   ```

2. **Pull latest code:**
   ```bash
   git pull origin main
   ```

3. **Deploy with Docker:**
   ```bash
   cp .env.example .env
   # Edit .env and set BIND_INTERFACE=eth0
   docker compose up -d
   ```

4. **Access dashboard:**
   ```
   http://<raspberry-pi-ip>:8080/
   ```

**Note:** Old TSV logs can still be imported but will show empty values for `ActiveInterface` and `WanSource` columns.

---

## Future Roadmap

### Planned Features

- [ ] **Time-Series Database Integration** (InfluxDB)
  - Long-term data storage
  - Advanced querying capabilities
  - Data retention policies

- [ ] **Advanced Dashboard** (Grafana)
  - Historical trend analysis
  - Custom dashboards
  - Export capabilities

- [ ] **Alerting System**
  - Email notifications
  - SMS alerts via FX3110
  - Webhook support
  - Configurable alert rules

- [ ] **Data Usage Tracking**
  - Cellular data consumption monitoring
  - Cost tracking
  - Usage reports

- [ ] **Enhanced Anomaly Detection**
  - Machine learning-based predictions
  - Baseline learning
  - Seasonal pattern recognition
  - Automatic threshold adjustment

- [ ] **API Enhancements**
  - Webhook endpoints for external integrations
  - Historical data export (CSV, JSON)
  - Filtering and search capabilities
  - Real-time WebSocket updates

- [ ] **Multi-Device Support**
  - Monitor multiple FX3110 devices
  - Aggregate dashboards
  - Comparative analysis

---

## Contributing

When adding features to this project:

1. Update this CHANGELOG.md with your changes
2. Follow the format: Added/Changed/Deprecated/Removed/Fixed/Security
3. Include the date and version number
4. Reference commit hashes for major changes
5. Update the README.md if user-facing features change
6. Add documentation to ARCHITECTURE.md for design changes

## Template for New Entries

```markdown
## [Version] - YYYY-MM-DD

### Added
- New feature description

### Changed
- Modification to existing feature

### Deprecated
- Features marked for removal

### Removed
- Features that were removed

### Fixed
- Bug fixes

### Security
- Security improvements
```
