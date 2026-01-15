#!/bin/bash
# Enable selective routing for RUTM50 monitoring
# This routes RUTM50 traffic (192.168.8.0/24) through eth0 while keeping
# general internet traffic on the default route.

set -e

RUTM50_NETWORK="192.168.8.0/24"
RUTM50_HOST="192.168.8.1"
ETH_INTERFACE="eth0"

echo "🔧 Enabling selective routing for RUTM50..."
echo "   RUTM50 Network: $RUTM50_NETWORK"
echo "   Interface: $ETH_INTERFACE"

# Check if eth0 has an IP address
if ! ip addr show $ETH_INTERFACE | grep -q "inet "; then
    echo "❌ Error: $ETH_INTERFACE has no IP address. Is it connected?"
    exit 1
fi

# Get the gateway for eth0 (if any)
ETH_GATEWAY=$(ip route show dev $ETH_INTERFACE | grep default | awk '{print $3}' | head -1)

if [ -z "$ETH_GATEWAY" ]; then
    echo "⚠️  Warning: No default gateway found on $ETH_INTERFACE"
    echo "   Will route directly to RUTM50 network without gateway"

    # Add direct route to RUTM50 network
    if ! ip route show | grep -q "$RUTM50_NETWORK dev $ETH_INTERFACE"; then
        sudo ip route add $RUTM50_NETWORK dev $ETH_INTERFACE scope link
        echo "✅ Added direct route to $RUTM50_NETWORK via $ETH_INTERFACE"
    else
        echo "ℹ️  Route to $RUTM50_NETWORK already exists"
    fi
else
    # Add route to RUTM50 network via eth0 gateway
    if ! ip route show | grep -q "$RUTM50_NETWORK via $ETH_GATEWAY"; then
        sudo ip route add $RUTM50_NETWORK via $ETH_GATEWAY dev $ETH_INTERFACE
        echo "✅ Added route to $RUTM50_NETWORK via $ETH_GATEWAY"
    else
        echo "ℹ️  Route to $RUTM50_NETWORK already exists"
    fi
fi

# Verify the route
echo ""
echo "📋 Current routing table:"
ip route show | grep -E "default|$RUTM50_NETWORK"

echo ""
echo "✅ Selective routing enabled!"
echo ""
echo "   General internet traffic → Default route (ChromeOS network)"
echo "   RUTM50 traffic ($RUTM50_NETWORK) → $ETH_INTERFACE"
echo ""
echo "💡 To test: ping $RUTM50_HOST"
echo "💡 To disable: ./scripts/disable-rutm50-routing.sh"
