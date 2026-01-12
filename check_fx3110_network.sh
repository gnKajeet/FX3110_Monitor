#!/bin/bash
# Script to check FX3110 network status and update configuration

echo "=== FX3110 Network Status Check ==="
echo

# Check current eth0 IP
echo "Current eth0 IP configuration:"
ip addr show eth0 | grep "inet "

echo
echo "Current routing:"
ip route | grep default

echo
echo "Testing connectivity to known FX3110 addresses:"

# Test common FX3110 gateway IPs
for ip in 192.168.1.1 192.168.9.1 10.232.50.169; do
    echo -n "  $ip ... "
    if ping -c 1 -W 2 $ip &> /dev/null; then
        echo "REACHABLE"
        FX3110_IP=$ip
    else
        echo "unreachable"
    fi
done

echo

if [ ! -z "$FX3110_IP" ]; then
    echo "✓ FX3110 found at: $FX3110_IP"
    echo
    echo "To update docker-compose.yml, run:"
    echo "  cd ~/FX3110_Monitor"
    echo "  # Edit docker-compose.yml and change DEVICE_BASE to http://$FX3110_IP"
    echo "  docker-compose down && docker-compose up -d"
else
    echo "✗ FX3110 not reachable on any known address"
    echo
    echo "The FX3110 may still be reconfiguring. Wait a moment and try again."
fi
