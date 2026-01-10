# Changelog

All notable changes to the FX3110 Monitor project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

- **v2.0.0** (2026-01-10) - Real-time dashboard, WAN source tracking, anomaly detection, Docker deployment
- **v1.0.0** (Initial) - Basic monitoring with TSV logging

---

## Upgrade Notes

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
