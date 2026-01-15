#!/bin/bash
# Disable selective routing for RUTM50 monitoring
# Removes the specific route to RUTM50, allowing all traffic to use default route

set -e

RUTM50_NETWORK="192.168.8.0/24"
ETH_INTERFACE="eth0"

echo "🔧 Disabling selective routing for RUTM50..."

# Check if the route exists
if ip route show | grep -q "$RUTM50_NETWORK"; then
    # Get the full route details
    ROUTE_DETAILS=$(ip route show | grep "$RUTM50_NETWORK" | head -1)

    # Remove the route
    sudo ip route del $RUTM50_NETWORK 2>/dev/null || true
    echo "✅ Removed route: $ROUTE_DETAILS"
else
    echo "ℹ️  No specific route to $RUTM50_NETWORK found"
fi

echo ""
echo "📋 Current routing table:"
ip route show | head -5

echo ""
echo "✅ Selective routing disabled!"
echo ""
echo "   All traffic now uses the default route (including RUTM50)"
echo ""
echo "💡 To re-enable: ./scripts/enable-rutm50-routing.sh"
