FX3110 Monitor
==============

Lightweight status and reachability logger for the Inseego FX3110.

What it does
------------
- Pings a target IP and logs success/latency.
- Pulls WAN/SIM/RF status fields from the FX3110 local UI.
- Pulls connected device count and names from the FX3110 JSON endpoint.
- Periodically records public IP via external providers.

Requirements
------------
- Python 3.8+
- Network access to the FX3110 management UI (default: http://192.168.1.1)

Usage
-----
Run in a terminal and redirect output to a file:

```bash
python FX3110_Monitor.py > fx3110_log.tsv
```

Notes
-----
- The script uses Windows `ping -n 1`. If running on macOS/Linux, change to `ping -c 1`.
- Adjust constants at the top of `FX3110_Monitor.py` for:
  - `DEST` (ping target)
  - `DEVICE_BASE` (FX3110 UI IP)
  - refresh intervals and max device names
- Output is tab-separated with a header row for easy import into Excel or pandas.
