# Network Isolation for RUTM50 Monitoring

## The Problem

When monitoring a RUTM50 router on a Chromebook, switching SIM slots causes the cellular modem to disconnect briefly (2-10 seconds), which interrupts your internet connection if the Chromebook is using the RUTM50 for internet access.

## Solutions

### Option 1: Use ChromeOS WiFi for Internet (Recommended)

**Configure your Chromebook to use WiFi for internet access instead of the RUTM50:**

1. **Connect ChromeOS to WiFi:**
   - Click the system tray (bottom-right)
   - Select a WiFi network and connect
   - Make sure WiFi stays connected

2. **Connect to RUTM50 via Ethernet:**
   - Plug ethernet cable from RUTM50 LAN port to Chromebook
   - The RUTM50 connection will be available for monitoring

3. **ChromeOS Network Priority:**
   - ChromeOS automatically prefers WiFi over Ethernet for internet
   - Ethernet connection will be used for local traffic (like 192.168.8.0/24)
   - SIM switching on RUTM50 won't affect your WiFi internet

**Result:** Your internet stays up when switching SIM slots, only RUTM50 SSH connection is briefly interrupted.

### Option 2: Routing Scripts (Linux Container Only)

If you need to fine-tune routing within the Linux container, use these scripts:

```bash
# Enable selective routing (only RUTM50 traffic through eth0)
./scripts/enable-rutm50-routing.sh

# Disable selective routing (all traffic through default route)
./scripts/disable-rutm50-routing.sh
```

**What this does:**
- Adds a specific route for 192.168.8.0/24 (RUTM50 network)
- General internet traffic uses the default ChromeOS route
- **Note:** This only affects routing within the Linux container, not ChromeOS itself

**Limitations:**
- If ChromeOS is using the RUTM50 for internet, you'll still experience disconnects during SIM switching
- The Linux container shares the ChromeOS network stack

### Option 3: Dual Network Setup (Advanced)

For completely isolated monitoring without internet disruption:

1. **RUTM50 Connection:** Use USB-to-Ethernet adapter plugged into Chromebook
   - Set to static IP or use DHCP from RUTM50
   - Used exclusively for monitoring

2. **Internet Connection:** Use built-in WiFi or built-in Ethernet
   - Normal internet access
   - Completely separate from RUTM50

3. **Update Environment:**
   ```bash
   # In .env, set the interface for monitoring
   BIND_INTERFACE=eth1  # or whichever interface is the USB adapter
   ```

**Result:** RUTM50 SIM switching never affects your internet.

## How to Check Your Setup

### Check if ChromeOS is using RUTM50 for internet:

1. Open Chrome browser (outside Linux container)
2. Visit: `https://whatismyipaddress.com/`
3. Check if the IP matches your RUTM50's public IP

If yes, you're routing through RUTM50 and will lose internet during SIM switches. Solution: Connect ChromeOS to WiFi.

### Check Linux container routing:

```bash
# View routing table
ip route show

# Test internet connectivity
curl -I https://google.com

# Test RUTM50 connectivity
ping -c 3 192.168.8.1
```

## Recommendations

**For Chromebook Users:**
1. ✅ Connect ChromeOS to WiFi for internet
2. ✅ Connect to RUTM50 via ethernet for monitoring
3. ✅ Use the dashboard SIM switch button when internet is stable
4. ℹ️  SIM switches will briefly interrupt RUTM50 monitoring (2-10 seconds) but not your WiFi internet

**For Raspberry Pi Users:**
1. ✅ Use WiFi (wlan0) for internet and SSH access
2. ✅ Use Ethernet (eth0) for RUTM50 monitoring
3. ✅ Set `BIND_INTERFACE=eth0` in `.env`
4. ℹ️  SIM switches won't affect WiFi internet

## Testing SIM Switch Isolation

1. Open two terminal windows

2. **Terminal 1** - Monitor internet connectivity:
   ```bash
   # This should stay responsive during SIM switch
   while true; do
     date
     curl -s -m 2 https://google.com -o /dev/null && echo "✅ Internet OK" || echo "❌ Internet DOWN"
     sleep 1
   done
   ```

3. **Terminal 2** - Monitor RUTM50 connectivity:
   ```bash
   # This will show disconnect during SIM switch
   while true; do
     date
     ping -c 1 -W 1 192.168.8.1 > /dev/null && echo "✅ RUTM50 OK" || echo "❌ RUTM50 DOWN"
     sleep 1
   done
   ```

4. Use the dashboard to switch SIM slots

**Expected Result:**
- Terminal 1 (Internet): Should stay "✅ Internet OK" throughout
- Terminal 2 (RUTM50): Will show "❌ RUTM50 DOWN" for 2-10 seconds during switch, then recover

If Terminal 1 shows downtime, your Chromebook is routing internet through the RUTM50. Fix this by connecting to WiFi in ChromeOS.
