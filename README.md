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

## Chromebook Linux (no Docker)

This uses the Linux container terminal on ChromeOS and runs both the monitor and the API directly.

### Initial Setup

```bash
cd ~/FX3110_Monitor
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r api/requirements.txt

# Install sshpass for RUTM50 password-based SSH (if using RUTM50)
sudo apt-get update && sudo apt-get install -y sshpass

cp .env.example .env
nano .env  # Set BIND_INTERFACE (e.g., eth0 or usb0) and DEVICE_TYPE
```

### Important: Environment Variable Handling

The monitor uses `python-dotenv` to load configuration from `.env`, but **shell environment variables take precedence** over the `.env` file. This can cause issues if you have old RUTM50_* or other config variables set in your shell.

**To avoid configuration conflicts:**

1. **Clear any existing environment variables before running:**
   ```bash
   # Clear all RUTM50 variables
   unset $(env | grep '^RUTM50_' | cut -d= -f1)

   # Or start with a clean shell
   bash --norc --noprofile
   source .venv/bin/activate
   ```

2. **For RUTM50 SSH authentication, choose ONE method:**
   - **Password-based** (recommended for quick setup): Comment out `RUTM50_SSH_KEY` in `.env`
   - **Key-based**: Set `RUTM50_SSH_KEY` path and comment out `RUTM50_SSH_PASSWORD`

3. **Verify your configuration is loaded correctly:**
   ```bash
   python3 -c "
   import os
   from dotenv import load_dotenv
   load_dotenv()
   print(f'DEVICE_TYPE={os.getenv(\"DEVICE_TYPE\")}')
   print(f'RUTM50_SSH_HOST={os.getenv(\"RUTM50_SSH_HOST\")}')
   print(f'RUTM50_SSH_KEY={os.getenv(\"RUTM50_SSH_KEY\")}')
   "
   ```

### Running the Monitor

```bash
mkdir -p logs
python3 monitor.py | tee logs/fx3110_log.tsv
```

In a second terminal (same venv), start the dashboard API and bind to all interfaces:

```bash
source .venv/bin/activate
uvicorn api.main:app --host 0.0.0.0 --port 8080
```

Open the dashboard:
- From inside the Linux container: `http://localhost:8080/`
- From ChromeOS browser: `http://penguin.linux.test:8080/`

If you need access from another device, keep `--host 0.0.0.0` and open port 8080 in your firewall.

### Non-Docker equivalents of Docker settings

These map the `docker-compose.yml` settings to the manual setup:

- `network_mode: host` → run directly on the host so `ping -I <iface>` can bind to the modem interface.
- `cap_add: NET_RAW/NET_ADMIN` → if `ping -I <iface>` fails with permission errors, run the monitor with `sudo` or grant ping caps:
  - `sudo setcap cap_net_raw,cap_net_admin=eip $(which ping)`
- `./logs:/logs` → use `logs/fx3110_log.tsv` locally (the API defaults to `logs/` when `/logs` doesn't exist).
- `env_file: .env` → run from the repo so `monitor.py` loads `.env` via `python-dotenv`.
- `ports: 8080:8080` → run `uvicorn api.main:app --host 0.0.0.0 --port 8080`.

If you don't need interface binding, you can set `BIND_INTERFACE=` in `.env` to disable `-I` on ping.

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

## Troubleshooting

### Dashboard shows blank cellular data fields

**Symptoms**: Dashboard loads but shows empty values for RSRP, Carrier, Tech, Band, etc.

**Common causes and fixes:**

1. **Missing `sshpass` (RUTM50 only)**
   ```bash
   sudo apt-get install -y sshpass
   ```

2. **Environment variable conflicts** - Shell variables override `.env` file
   ```bash
   # Check what's actually loaded
   python3 -c "
   import os
   from dotenv import load_dotenv
   load_dotenv()
   print('HOST:', os.getenv('RUTM50_SSH_HOST'))
   print('KEY:', os.getenv('RUTM50_SSH_KEY'))
   print('PASS:', os.getenv('RUTM50_SSH_PASSWORD'))
   "

   # Clear old variables and restart
   unset $(env | grep '^RUTM50_' | cut -d= -f1)
   python3 monitor.py
   ```

3. **SSH key path pointing to non-existent file**
   - Comment out `RUTM50_SSH_KEY` in `.env` if using password auth
   - OR create the SSH key and copy to the router

4. **Wrong IP address or SSH credentials**
   ```bash
   # Test SSH connection manually
   sshpass -p "your_password" ssh -o StrictHostKeyChecking=accept-new root@192.168.8.1 "gsmctl -q"
   ```

5. **Monitor not restarted after `.env` changes**
   - Always kill and restart the monitor after editing `.env`
   ```bash
   pkill -f "python3 monitor.py"
   python3 monitor.py | tee logs/fx3110_log.tsv
   ```

### Verify data collection is working

```bash
# Check recent log entries
tail -2 logs/fx3110_log.tsv

# Should show populated fields like:
# Timestamp  SourceIP  ...  WanStatus  SimStatus  Tech  Band  Carrier  RSRP  RSRQ  ...
# 2026-01-14 18:40:53  ...  Connected  Inserted   LTE   B66   AT&T     -93   -12   ...
```

## Requirements

- **Hardware**: Raspberry Pi 4+ (or any Linux system with dual network interfaces)
- **Software**:
  - Docker and docker-compose (for Docker deployment), OR
  - Python 3.8+ for manual deployment
  - `sshpass` package (for RUTM50 password-based SSH)
- **Network**:
  - FX3110: Access to management UI (default: http://192.168.1.1)
  - RUTM50: SSH access to the router (password or key-based)

## License

MIT (or specify your license)

## Contributing

Issues and pull requests welcome!
