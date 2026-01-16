#!/bin/sh
# Teltonika RUTM50 Data Collector Script
# Runs locally on the router, outputs all metrics as JSON
# Reduces SSH sessions from ~20 to 1 per collection cycle

# Escape special characters for JSON string values
json_escape() {
    printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g; s/	/\\t/g' | tr '\n' ' '
}

# Start JSON output
echo "{"

# === Signal Quality Metrics ===
echo "\"signal_quality\": \"$(json_escape "$(gsmctl -q 2>/dev/null)")\","
echo "\"operator\": \"$(json_escape "$(gsmctl -o 2>/dev/null)")\","
echo "\"technology\": \"$(json_escape "$(gsmctl -t 2>/dev/null)")\","
echo "\"band\": \"$(json_escape "$(gsmctl -b 2>/dev/null)")\","

# === Connection State ===
echo "\"conn_state\": \"$(json_escape "$(gsmctl -j 2>/dev/null)")\","
echo "\"ps_state\": \"$(json_escape "$(gsmctl -P 2>/dev/null)")\","
echo "\"net_state\": \"$(json_escape "$(gsmctl -g 2>/dev/null)")\","

# === Cell Information ===
echo "\"cell_id\": \"$(json_escape "$(gsmctl -C 2>/dev/null)")\","
echo "\"operator_num\": \"$(json_escape "$(gsmctl -f 2>/dev/null)")\","
echo "\"network_info\": \"$(json_escape "$(gsmctl -F 2>/dev/null)")\","
echo "\"serving_info\": \"$(json_escape "$(gsmctl -K 2>/dev/null)")\","
echo "\"neighbour_info\": \"$(json_escape "$(gsmctl -I 2>/dev/null)")\","

# === SIM and Device Info ===
echo "\"volte\": \"$(json_escape "$(gsmctl -v 2>/dev/null)")\","
echo "\"active_sim\": \"$(json_escape "$(gsmctl -L 2>/dev/null)")\","
echo "\"iccid\": \"$(json_escape "$(gsmctl -J 2>/dev/null)")\","
echo "\"sim_status\": \"$(json_escape "$(gsmctl -z 2>/dev/null)")\","

# === Modem Info (comprehensive JSON from gsmctl) ===
MODEM_INFO=$(gsmctl --info 2>/dev/null || gsmctl -E 2>/dev/null || echo '{}')
echo "\"modem_info\": $MODEM_INFO,"

# === Interface Status (already JSON from ubus) ===
WAN_STATUS=$(ubus call network.interface.wan status 2>/dev/null || echo '{}')
echo "\"wan_status\": $WAN_STATUS,"

LAN_STATUS=$(ubus call network.interface.lan status 2>/dev/null || echo '{}')
echo "\"lan_status\": $LAN_STATUS,"

# Cellular interfaces - try both SIM slots
CELL1_STATUS=$(ubus call network.interface.mob1s1a1 status 2>/dev/null || echo '{}')
echo "\"cell1_status\": $CELL1_STATUS,"

CELL2_STATUS=$(ubus call network.interface.mob1s2a1 status 2>/dev/null || echo '{}')
echo "\"cell2_status\": $CELL2_STATUS,"

# === APN Configuration ===
APN1=$(uci get network.mob1s1a1.apn 2>/dev/null || echo "")
echo "\"apn_sim1\": \"$(json_escape "$APN1")\","

APN2=$(uci get network.mob1s2a1.apn 2>/dev/null || echo "")
echo "\"apn_sim2\": \"$(json_escape "$APN2")\","

# === MWAN3 Status (multi-WAN failover) ===
MWAN3=$(mwan3 status 2>/dev/null | head -50 || echo "")
echo "\"mwan3_status\": \"$(json_escape "$MWAN3")\","

# === Timestamp ===
echo "\"collected_at\": \"$(date -Iseconds 2>/dev/null || date)\""

echo "}"
