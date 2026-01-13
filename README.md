FX3110 Monitor
==============

Lightweight status and reachability logger for the Inseego FX3110 or Teltonika RUTM50, designed for Raspberry Pi deployment with Docker.

## What it does

- **Connectivity monitoring**: Pings a target IP and logs success/latency
- **Device status**: Pulls WAN/SIM/RF status from the FX3110 web interface or RUTM50 via SSH commands
- **Signal metrics**: Tracks RSRP, RSRQ, SNR, band, and technology (4G/5G)
- **Connected devices**: Monitors device count and names
- **Public IP logging**: Periodically records public IP address
- **Network isolation**: Forces FX3110 traffic through ethernet while maintaining SSH via WiFi

## Architecture

Designed for Raspberry Pi with dual network interfaces:
- **Ethernet (eth0)**: Connected to FX3110 modem (192.168.1.1)
- **WiFi (wlan0)**: SSH access and future remote data transmission

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system design and future roadmap.

## Quick Start (Raspberry Pi + Docker)

### 1. Install Docker

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

### 2. Clone and Configure

```bash
git clone git@github.com:gnKajeet/FX3110_Monitor.git
cd FX3110_Monitor
cp .env.example .env
nano .env  # Set BIND_INTERFACE=eth0 and DEVICE_TYPE
```

### 3. Start Monitoring

```bash
docker compose up -d
```

### 4. Access Dashboard

Open your browser and navigate to:
```
http://<raspberry-pi-ip>:8080/
```

Or view raw logs:
```bash
tail -f logs/fx3110_log.tsv
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for complete deployment instructions and troubleshooting.

## Manual Usage (without Docker)

```bash
# Linux/macOS
python3 FX3110_Monitor.py > fx3110_log.tsv

# Windows
python FX3110_Monitor.py > fx3110_log.tsv
```

**Configuration**: Edit environment variables in `.env` (or export them):
- `DEVICE_TYPE`: `fx3110` or `rutm50`
- `BIND_INTERFACE`: Network interface for device traffic (e.g., "eth0")
- `DEST`: Ping target (default: 8.8.8.8)
- `DEVICE_BASE`: FX3110 IP address (used for `fx3110`)
- `RUTM50_SSH_HOST`, `RUTM50_SSH_USER`, `RUTM50_SSH_KEY`: SSH access (used for `rutm50`)
- Refresh intervals and display limits

## Output Format

Tab-separated values (TSV) with headers:

```
Timestamp  SourceIP  DestIP  Success  Latency_ms  PublicIP  WanStatus  SimStatus  Tech  Band  ...
```

Import into Excel, pandas, or any TSV-compatible tool for analysis.

## RUTM50 Setup (SSH)

Set `DEVICE_TYPE=rutm50` and configure SSH env vars in `.env`:
- `RUTM50_SSH_HOST`, `RUTM50_SSH_USER`, `RUTM50_SSH_KEY` (or `RUTM50_SSH_PASSWORD` with sshpass)
- Optional command overrides: `RUTM50_CMD_SIGNAL`, `RUTM50_CMD_OPERATOR`, `RUTM50_CMD_TECH`, `RUTM50_CMD_WAN`, `RUTM50_CMD_APN`
- Additional telemetry commands (stored as raw text in the log): `RUTM50_CMD_CONNSTATE`, `RUTM50_CMD_PSSTATE`, `RUTM50_CMD_NETSTATE`, `RUTM50_CMD_CELLID`, `RUTM50_CMD_OPERNUM`, `RUTM50_CMD_NETWORK`, `RUTM50_CMD_SERVING`, `RUTM50_CMD_NEIGHBOUR`, `RUTM50_CMD_VOLTE`, `RUTM50_CMD_BAND`
- Modem info JSON (parsed into fields): `RUTM50_CMD_INFO` (default `gsmctl --info`)

The RUTM50 collector runs SSH commands like `gsmctl -q` and `ubus call network.interface.wan status`.
If your firmware uses different commands, override them via the env vars above.
For Docker, mount your SSH key into the container (see the commented volume in `docker-compose.yml`).

## Web Dashboard

Access the real-time monitoring dashboard at `http://<raspberry-pi-ip>:8080/`

**Features:**
- Real-time status updates (5 second refresh)
- Connection status and latency monitoring
- Signal strength visualization with RSRP meter
- Cellular network information (carrier, technology, band)
- Change detection for IP addresses, carrier, APN, and ICCID
- Anomaly detection for signal drops and latency spikes
- Dark mode optimized for 24/7 monitoring

**API Endpoints:**
- `GET /api/status` - Current modem status
- `GET /api/stats` - Statistical summary
- `GET /api/recent?count=100` - Recent log entries
- `GET /api/changes` - Detected configuration changes
- `GET /api/anomalies?rsrp_threshold=10&latency_threshold=50` - Signal/latency anomalies
- `GET /api/health` - Service health check

## Future Enhancements

- Time-series database integration (InfluxDB)
- Advanced analytics dashboard (Grafana)
- Email/SMS alerting on anomalies
- Cellular data usage tracking
- Historical trend analysis

## Requirements

- **Hardware**: Raspberry Pi 4+ (or any Linux system with dual network interfaces)
- **Software**: Docker and docker-compose (or Python 3.8+ for manual deployment)
- **Network**:
  - FX3110: Access to management UI (default: http://192.168.1.1)
  - RUTM50: SSH access to the router (key-based recommended)

## License

MIT (or specify your license)

## Contributing

Issues and pull requests welcome!
