# FX3110 Monitor - System Architecture

## Overview

This system monitors an Inseego FX3110 cellular modem connected to a Raspberry Pi via ethernet, while providing SSH access and remote data transmission via WiFi.

## Network Topology

```
┌─────────────────────────────────────────────┐
│         Raspberry Pi (Docker Host)          │
│                                             │
│  ┌──────────────────────────────────────┐  │
│  │  eth0 (192.168.1.x)                  │  │
│  │  ↓                                    │  │
│  │  FX3110 Monitor Container             │  │
│  │  - Pings via eth0                     │  │
│  │  - Scrapes FX3110 status              │  │
│  │  - Logs to /logs/fx3110_log.tsv       │  │
│  └──────────────────────────────────────┘  │
│                                             │
│  ┌──────────────────────────────────────┐  │
│  │  wlan0 (Home Network)                 │  │
│  │  ↑                                    │  │
│  │  SSH Access + Future API Service      │  │
│  └──────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
         │                      │
         ├─eth0─────────┐       └─wlan0─────────┐
         │              │                        │
    ┌────────────┐  ┌────────────────┐    ┌──────────┐
    │  FX3110    │  │  Your Router   │    │ Internet │
    │ Cellular   │  │  (Home WiFi)   │    │  (via    │
    │  Modem     │  │                │    │  Modem)  │
    └────────────┘  └────────────────┘    └──────────┘
   192.168.1.1
```

## Current Implementation (Phase 1)

### Components

1. **FX3110 Monitor Service** (Docker container)
   - Runs continuously, logging to TSV file
   - All FX3110 traffic forced through eth0 interface
   - Captures:
     - Ping latency to 8.8.8.8
     - WAN/SIM status
     - Cellular metrics (RSRP, RSRQ, SNR, Band, etc.)
     - Connected device count and names
     - Public IP address

2. **Data Storage**
   - Tab-separated value (TSV) log file
   - Location: `./logs/fx3110_log.tsv`
   - Rotates on restart (consider adding log rotation)

### Network Configuration

**Interface Binding:**
- Set `BIND_INTERFACE=eth0` in `.env` file
- Container runs with `network_mode: host` for direct interface access
- Requires `CAP_NET_RAW` and `CAP_NET_ADMIN` capabilities

**Routing:**
- FX3110 traffic → eth0 (192.168.1.0/24)
- SSH + future API → wlan0 (home network)
- Public IP checks → wlan0 (outbound internet)

## Future Implementation (Phase 2)

### Planned Components

1. **REST API Service**
   - Read and parse TSV logs
   - Expose current status via HTTP endpoints
   - Provide historical data queries
   - Technologies: FastAPI or Flask

2. **Time-Series Database** (Optional)
   - Store metrics in InfluxDB for better querying
   - Parse TSV and insert into database
   - Enable longer-term trend analysis

3. **Visualization Dashboard** (Optional)
   - Grafana for real-time monitoring
   - View signal strength trends
   - Alert on connectivity issues

### API Design (Draft)

**Endpoints:**

```
GET /api/v1/status
  → Current FX3110 status snapshot

GET /api/v1/metrics/signal?start=<timestamp>&end=<timestamp>
  → Signal strength metrics over time (RSRP, RSRQ, SNR)

GET /api/v1/metrics/latency?start=<timestamp>&end=<timestamp>
  → Ping latency over time

GET /api/v1/devices
  → Currently connected devices

GET /api/v1/health
  → Service health check
```

**Data Format:** JSON

```json
{
  "timestamp": "2026-01-10T09:52:30.123Z",
  "ping": {
    "destination": "8.8.8.8",
    "success": true,
    "latency_ms": 14
  },
  "wan": {
    "status": "Connected",
    "technology": "5G",
    "band": "n71",
    "bandwidth": "20MHz"
  },
  "signal": {
    "rsrp": "-85 dBm",
    "rsrq": "-12 dB",
    "snr": "15 dB"
  },
  "devices": {
    "count": 3,
    "names": ["iPhone", "Laptop", "Tablet"]
  }
}
```

## Deployment Instructions

### Initial Setup

1. **On Raspberry Pi:**
   ```bash
   # Install Docker
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   sudo usermod -aG docker $USER

   # Clone repository
   git clone git@github.com:gnKajeet/FX3110_Monitor.git
   cd FX3110_Monitor

   # Configure
   cp .env.example .env
   nano .env  # Set BIND_INTERFACE=eth0
   ```

2. **Start Services:**
   ```bash
   docker compose up -d
   ```

3. **View Logs:**
   ```bash
   # Live monitoring
   tail -f logs/fx3110_log.tsv

   # Container logs
   docker compose logs -f fx3110-monitor
   ```

4. **Stop Services:**
   ```bash
   docker compose down
   ```

### Network Configuration on Raspberry Pi

Ensure proper routing for dual-interface setup:

```bash
# Check default route (should be via wlan0 for internet)
ip route show default

# If needed, set specific route for FX3110 subnet
sudo ip route add 192.168.1.0/24 dev eth0

# Make persistent by adding to /etc/network/interfaces or using NetworkManager
```

## Security Considerations

1. **Container Security:**
   - Runs as non-root user (UID 1000)
   - Minimal capabilities (NET_RAW, NET_ADMIN only)
   - Read-only access for API service to logs

2. **Network Security:**
   - FX3110 on isolated ethernet subnet
   - No direct internet access from FX3110 subnet
   - API service only exposed on wlan0

3. **SSH Access:**
   - Use SSH keys, disable password auth
   - Consider fail2ban for brute force protection
   - Keep Raspberry Pi OS updated

## Monitoring and Maintenance

1. **Log Rotation:**
   - TODO: Add logrotate configuration
   - Recommended: Keep 7 days of detailed logs
   - Archive older data or summarize to database

2. **Health Checks:**
   - Monitor container status: `docker compose ps`
   - Check log file growth: `ls -lh logs/`
   - Verify disk space: `df -h`

3. **Updates:**
   - Pull latest code: `git pull`
   - Rebuild containers: `docker compose build`
   - Restart services: `docker compose up -d`

## Future Enhancements

- [ ] Environment variable support for all configuration
- [ ] Log rotation and archival
- [ ] REST API service implementation
- [ ] Database integration (InfluxDB)
- [ ] Grafana dashboard templates
- [ ] Alerting on connectivity issues
- [ ] SMS/email notifications via cellular modem
- [ ] Backup cellular connection failover detection
- [ ] Bandwidth usage tracking
- [ ] Cost monitoring for cellular data
