#!/bin/sh
# Optimized Teltonika RUTM50 Data Collector Script
# Runs locally on the router, outputs all metrics as JSON
# Reduces commands by using gsmctl --info cache for most data

# Escape special characters for JSON string values
json_escape() {
    printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g; s/	/\\t/g' | tr '\n' ' '
}

# Start JSON output
echo "{"

# === PRIMARY DATA SOURCE: gsmctl --info ===
# This single command contains most of the data we need
MODEM_INFO=$(gsmctl --info 2>/dev/null || gsmctl -E 2>/dev/null || echo '{}')
echo "\"modem_info\": $MODEM_INFO,"

# === SUPPLEMENTARY DATA (not in modem_info cache) ===

# Connection state (not in cache)
echo "\"conn_state\": \"$(json_escape "$(gsmctl -j 2>/dev/null)")\","

# Packet service state (not in cache)
echo "\"ps_state\": \"$(json_escape "$(gsmctl -P 2>/dev/null)")\","

# Neighbour cell info (not in cache - this is important for analysis)
echo "\"neighbour_info\": \"$(json_escape "$(gsmctl -I 2>/dev/null)")\","

# Network info (might be redundant with cache, but keep for compatibility)
echo "\"network_info\": \"$(json_escape "$(gsmctl -F 2>/dev/null)")\","

# Serving info (might be redundant with cache, but keep for compatibility)
echo "\"serving_info\": \"$(json_escape "$(gsmctl -K 2>/dev/null)")\","

# SIM status (pin_state_str in cache might be sufficient, but check)
echo "\"sim_status\": \"$(json_escape "$(gsmctl -z 2>/dev/null)")\","

# === INTERFACE STATUS (ubus - already JSON) ===
WAN_STATUS=$(ubus call network.interface.wan status 2>/dev/null || echo '{}')
echo "\"wan_status\": $WAN_STATUS,"

LAN_STATUS=$(ubus call network.interface.lan status 2>/dev/null || echo '{}')
echo "\"lan_status\": $LAN_STATUS,"

# Cellular interfaces - try both SIM slots
CELL1_STATUS=$(ubus call network.interface.mob1s1a1 status 2>/dev/null || echo '{}')
echo "\"cell1_status\": $CELL1_STATUS,"

CELL2_STATUS=$(ubus call network.interface.mob1s2a1 status 2>/dev/null || echo '{}')
echo "\"cell2_status\": $CELL2_STATUS,"

# === APN CONFIGURATION ===
APN1=$(uci get network.mob1s1a1.apn 2>/dev/null || echo "")
echo "\"apn_sim1\": \"$(json_escape "$APN1")\","

APN2=$(uci get network.mob1s2a1.apn 2>/dev/null || echo "")
echo "\"apn_sim2\": \"$(json_escape "$APN2")\","

# === MWAN3 STATUS (multi-WAN failover) ===
MWAN3=$(mwan3 status 2>/dev/null | head -50 || echo "")
echo "\"mwan3_status\": \"$(json_escape "$MWAN3")\","

# === TIMESTAMP ===
echo "\"collected_at\": \"$(date -Iseconds 2>/dev/null || date)\""

echo "}"
