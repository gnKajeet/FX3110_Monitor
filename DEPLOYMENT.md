# Raspberry Pi Deployment Guide

## Prerequisites

- Raspberry Pi 4 (or newer) running Raspberry Pi OS
- Ethernet connection to FX3110 modem
- WiFi connection to your home/office network
- SSH access enabled

## Quick Start

### 1. Install Docker on Raspberry Pi

```bash
# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group (avoid sudo for docker commands)
sudo usermod -aG docker $USER

# Install docker-compose
sudo apt-get install -y docker-compose

# Log out and back in for group changes to take effect
exit
```

### 2. Clone and Configure

```bash
# Clone the repository
cd ~
git clone git@github.com:gnKajeet/FX3110_Monitor.git
cd FX3110_Monitor

# Create configuration from example
cp .env.example .env

# Edit configuration (set BIND_INTERFACE=eth0)
nano .env
```

**Important:** Set `BIND_INTERFACE=eth0` in the `.env` file to ensure all FX3110 traffic goes through ethernet.

### 3. Verify Network Configuration

```bash
# Check interfaces
ip addr show

# You should see:
# - eth0 with IP like 192.168.1.x (connected to FX3110)
# - wlan0 with IP on your home network

# Test connectivity to FX3110
ping -c 3 -I eth0 192.168.1.1

# Test internet via WiFi
ping -c 3 8.8.8.8
```

### 4. Start the Monitor

```bash
# Build and start containers
docker compose up -d

# Verify container is running
docker compose ps

# Watch logs in real-time
docker compose logs -f fx3110-monitor
```

### 5. Access Logs

```bash
# View TSV log file
tail -f logs/fx3110_log.tsv

# Or import into Excel/LibreOffice for analysis
# File is tab-separated with headers
```

## Network Routing Configuration

### Automatic (Recommended)

Modern Raspberry Pi OS should automatically route correctly:
- Default route → wlan0 (internet access)
- 192.168.1.0/24 → eth0 (FX3110 subnet)

### Manual Configuration (if needed)

If the Pi tries to route internet traffic through the FX3110:

```bash
# Check current routes
ip route show

# Set default route via WiFi (replace with your WiFi gateway)
sudo ip route del default
sudo ip route add default via <WIFI_GATEWAY_IP> dev wlan0

# Add specific route for FX3110 subnet
sudo ip route add 192.168.1.0/24 dev eth0

# Make persistent (option 1: dhcpcd)
sudo nano /etc/dhcpcd.conf
# Add:
# interface eth0
# static ip_address=192.168.1.100/24
# nogateway

# Make persistent (option 2: NetworkManager)
# Use nmcli or nmtui to configure
```

## Systemd Auto-Start (Optional)

To start the Docker containers on boot:

```bash
# Enable Docker service
sudo systemctl enable docker

# Docker Compose containers should auto-restart with "restart: unless-stopped"
```

## Monitoring and Maintenance

### View Status

```bash
# Container status
docker compose ps

# Recent logs
docker compose logs --tail=50 fx3110-monitor

# Live log stream
docker compose logs -f fx3110-monitor

# System resources
docker stats fx3110-monitor
```

### Restart Service

```bash
# Restart containers
docker compose restart

# Or rebuild and restart
docker compose down
docker compose up -d --build
```

### Update to Latest Version

```bash
cd ~/FX3110_Monitor
git pull
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Disk Space Management

The TSV log file will grow continuously. Set up log rotation:

```bash
# Create logrotate configuration
sudo nano /etc/logrotate.d/fx3110-monitor

# Add:
/home/pi/FX3110_Monitor/logs/*.tsv {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 pi pi
    postrotate
        docker compose -f /home/pi/FX3110_Monitor/docker-compose.yml restart fx3110-monitor
    endscript
}
```

## Troubleshooting

### Container Won't Start

```bash
# Check container logs
docker compose logs fx3110-monitor

# Check Docker service
sudo systemctl status docker

# Rebuild from scratch
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Ping Fails (Permission Denied)

This usually means the container doesn't have the required capabilities:

```bash
# Verify capabilities in docker-compose.yml:
# cap_add:
#   - NET_RAW
#   - NET_ADMIN

# Restart container
docker compose down
docker compose up -d
```

### Can't Reach FX3110 Web Interface

```bash
# Test from host
ping -c 3 -I eth0 192.168.1.1
curl -I http://192.168.1.1

# Check if eth0 has correct IP
ip addr show eth0

# Should be in 192.168.1.0/24 range
# If not, check DHCP or set static IP
```

### Network Interface Not Found

If you see "BIND_INTERFACE eth0 not found":

```bash
# List all interfaces
ip link show

# On some Raspberry Pi models, ethernet might be named differently:
# - enxXXXXXX (USB ethernet adapters)
# - end0 (some newer models)

# Update .env file with correct interface name
nano .env
```

### WiFi SSH Access Lost

If you lose SSH access via WiFi after starting the monitor:

```bash
# Connect via ethernet temporarily or use keyboard/monitor
# Check routing table
ip route show

# Should see default route via wlan0
# If not, add it back:
sudo ip route add default via <WIFI_GATEWAY> dev wlan0
```

## Security Hardening

### SSH Configuration

```bash
# Disable password authentication (use SSH keys only)
sudo nano /etc/ssh/sshd_config
# Set: PasswordAuthentication no

# Restart SSH
sudo systemctl restart ssh
```

### Firewall (UFW)

```bash
# Install UFW
sudo apt-get install -y ufw

# Allow SSH
sudo ufw allow 22/tcp

# Allow future API port (when implemented)
sudo ufw allow 8080/tcp

# Enable firewall
sudo ufw enable
```

### Keep System Updated

```bash
# Weekly updates (manual)
sudo apt-get update
sudo apt-get upgrade -y

# Or set up unattended-upgrades
sudo apt-get install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

## Performance Tuning

### Reduce SD Card Writes

Frequent writes can wear out SD cards. Consider:

1. **Use USB storage for logs:**
   ```bash
   # Mount USB drive
   sudo mkdir -p /mnt/usb
   sudo mount /dev/sda1 /mnt/usb

   # Update docker-compose.yml volume:
   # - /mnt/usb/fx3110-logs:/logs
   ```

2. **Write to tmpfs (RAM) and sync periodically:**
   ```bash
   # Add to docker-compose.yml:
   # tmpfs:
   #   - /logs:size=100M
   ```

### Resource Limits

If running multiple services, limit container resources:

```yaml
# Add to docker-compose.yml service definition:
deploy:
  resources:
    limits:
      cpus: '0.5'
      memory: 256M
```

## Next Steps

Once the monitoring service is stable:

1. Review logs to understand FX3110 behavior
2. Identify signal strength patterns
3. Plan API service implementation
4. Set up remote data export (when WiFi connectivity permits)

See [ARCHITECTURE.md](ARCHITECTURE.md) for future development roadmap.
