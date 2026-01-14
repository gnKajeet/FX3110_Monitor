# RUTM50 Storage and Flash Memory Recommendations

## Hardware Specifications

### Storage Components

**Flash Storage:**
- **16MB NOR Flash** (serial) - Used for firmware and bootloader
- **256MB NAND Flash** (serial) - User storage and overlay filesystem
- **80MB Overlay Available** - Writable userspace for configurations, packages, and data

**RAM:**
- **256MB DDR3 RAM**
- **100MB Available** for userspace applications

### Processing
- **CPU:** MediaTek MT7621A dual-core @ 880 MHz
- **OS:** RutOS (OpenWrt-based)

## Flash Memory Endurance

### Write/Erase Cycle Limits

| Flash Type | Cycles per Block | Typical Use |
|------------|------------------|-------------|
| NOR Flash | ~100,000 cycles | Firmware/bootloader |
| NAND Flash (SLC) | ~100,000 cycles | High-endurance storage |
| NAND Flash (MLC) | ~1,000-10,000 cycles | Standard storage |

### Wear Leveling

The RUTM50 uses **JFFS2** (Journalling Flash File System v2) or **UBIFS** on the overlay partition, providing:
- Automatic wear leveling (distributes writes across blocks)
- Garbage collection
- Bad block management
- Error Correction Code (ECC) for NAND flash

## Flash Wear Analysis

### Write Frequency Impact

Assuming 80MB overlay with NAND flash at 10,000 cycles:
- Total write capacity: 80MB × 10,000 = 800GB before failure

**Safe write patterns:**
- 1 write/hour: 91+ years lifespan ✓
- 10 writes/hour: 9+ years lifespan ✓
- 1 write/minute: 1.5 years lifespan ⚠
- 10 writes/minute: 2 months lifespan ✗
- 1 write/second: Immediate concern ✗

### Write Frequency Guidelines

| Pattern | Target Location | Assessment |
|---------|----------------|------------|
| < 1/hour | Flash (/overlay) | Excellent - No concerns |
| 1-10/hour | Flash (/overlay) | Very Safe |
| 1/minute | Flash (/overlay) | Safe with monitoring |
| 10/minute | Flash (/overlay) | Monitor closely |
| 1/second or more | RAM (/tmp) | Required |
| Continuous | RAM or USB | Required |

## Storage Location Recommendations

### Volatile Storage - /tmp (RAM-based)

**Use for:**
- High-frequency data collection (every few seconds)
- Real-time status snapshots
- Event streams and continuous logs
- SQLite databases with frequent inserts
- Any data updated more than once per minute

**Benefits:**
- Unlimited write cycles
- Faster read/write performance
- Zero flash wear

**Drawbacks:**
- Lost on reboot
- Limited to ~100MB available space

### Persistent Storage - /overlay (Flash-based)

**Use for:**
- Configuration changes (occasional)
- Periodic summaries (hourly/daily aggregates)
- Batch-written data
- Historical statistics
- Application state that must survive reboots

**Safe patterns:**
- Configuration updates: As needed
- Hourly summaries: 24 writes/day = 9,000/year = 10+ year lifespan
- Daily archives: 365 writes/year = 27+ year lifespan

**Avoid:**
- Continuous logging
- Per-event database inserts
- Frequent status updates
- Real-time metrics

### USB Storage (Optional)

**Use for:**
- Unlimited write scenarios
- Long-term data archiving
- Continuous logging without flash concerns
- Large datasets exceeding overlay capacity

**Requirements:**
- USB mass storage device attached
- Storage Memory Expansion configured in RutOS
- Mount point at /mnt/usb or similar

## Data Storage Solutions for Cellular Monitoring

### SQLite Database

**Installation:**
```
opkg update
opkg install sqlite3-cli libsqlite3
```

**Characteristics:**
- Requires ~750KB storage
- Self-contained, serverless
- ACID-compliant transactions
- Ideal for structured data

**Location strategy:**
- `/tmp/` - High-frequency updates (RAM)
- `/overlay/` - Periodic summaries (Flash)
- `/mnt/usb/` - Long-term archives (USB)

### ubus (Micro Bus) - IPC

**Native OpenWrt inter-process communication:**
- JSON-based data exchange
- Real-time method calls and event publishing
- No persistent storage (memory-based)
- Ideal for service-to-service communication

**Use cases:**
- Service discovery and registration
- Real-time status queries
- Event notifications between processes
- Lightweight data sharing

### JSON File Storage

**Simple file-based approach:**
- Fast read/write operations
- Easy parsing and manipulation
- Suitable for configuration and state snapshots
- Location determines persistence (RAM vs Flash)

### Named Pipes (FIFO)

**For real-time data streaming:**
- Zero storage overhead
- Blocking/non-blocking operation modes
- Point-to-point communication
- Lost if not consumed immediately

## Recommended Architecture Patterns

### High-Frequency Collection with Batch Persistence

**Pattern:**
1. Collect data frequently (10-60 seconds) → Store in RAM (`/tmp/`)
2. Aggregate periodically (hourly) → Write summary to Flash (`/overlay/`)
3. Archive long-term (daily) → Copy to USB (`/mnt/usb/`) if available

**Benefits:**
- Minimizes flash writes
- Preserves important historical data
- Balances performance and durability

### RAM Buffer with Periodic Flush

**Pattern:**
1. Use SQLite in `/tmp/` for active data collection
2. Every hour, calculate aggregates (averages, min/max, counts)
3. Insert aggregated results into persistent database in `/overlay/`
4. Clear RAM buffer to reclaim space

**Write frequency:** 24 flash writes/day = Safe for 10+ years

### Dual Database Strategy

**Current data (volatile):**
- Location: `/tmp/cellular_current.db`
- Updates: Every 10-60 seconds
- Retention: Current session only

**Historical data (persistent):**
- Location: `/overlay/cellular_history.db`
- Updates: Hourly aggregates
- Retention: Weeks to months

**Long-term archive (optional):**
- Location: `/mnt/usb/archive_YYYYMMDD.db`
- Updates: Daily exports
- Retention: Years

## Monitoring Flash Health

### Check Overlay Usage
```
df -h /overlay
```

### Monitor UBI/UBIFS (if applicable)
```
cat /sys/class/ubi/ubi0/bad_peb_count
cat /sys/class/ubi/ubi0/wear_leveling
```

### Check Mount Information
```
grep 'ubifs' /proc/mounts
mount | grep overlay
```

## Key Takeaways

1. **NOR Flash (16MB)** - Extremely durable, not a practical concern
2. **NAND Flash (256MB)** - Limited cycles but adequate with proper write patterns
3. **RAM (100MB usable)** - Primary location for high-frequency data collection
4. **Write Batching** - Accumulate in RAM, aggregate, then periodically flush to flash
5. **USB Expansion** - Consider for continuous logging without flash wear concerns

## Best Practices

- Monitor overlay storage capacity regularly
- Implement write batching for all frequent updates
- Use RAM for real-time data, flash for summaries
- Consider USB storage for unlimited write scenarios
- Log aggregated metrics rather than individual events
- Rotate and archive historical data periodically
- Test flash write patterns in development before deployment

## References

- [Teltonika Networks RUTM50 Product Page](https://www.teltonika-networks.com/products/routers/rutm50)
- [RUTM50 System - Teltonika Networks Wiki](https://wiki.teltonika-networks.com/view/RUTM50_System)
- [Flash Memory - OpenWrt Wiki](https://oldwiki.archive.openwrt.org/doc/techref/flash)
- [Flash Memory Lifespan - OpenWrt Forum](https://forum.openwrt.org/t/flash-memory-lifespan/71299)
- [UCI Command Usage - Teltonika Networks](https://wiki.teltonika-networks.com/view/UCI_command_usage)
- [UBUS Inter-Process Messaging](https://niranjanvram.github.io/guides/docs/openwrt/core-components/ubus/)

---

*Document created: 2026-01-14*
*Target device: Teltonika RUTM50 5G Cellular Router*
*OS: RutOS (OpenWrt-based)*
