#!/bin/bash
# Open SSH tunnel to FX4200 via Raspberry Pi (Tailscale)
# Usage: ./scripts/fx4200_tunnel.sh [local_port] [pi_host] [pi_user]
#
# Then set base_url: https://localhost:<local_port> in config.yaml

LOCAL_PORT=${1:-8443}
PI_HOST=${2:-100.68.232.116}
PI_USER=${3:-smartsim}
REMOTE_TARGET="192.168.1.1:443"

echo "Opening tunnel: localhost:${LOCAL_PORT} -> ${REMOTE_TARGET} via ${PI_USER}@${PI_HOST}"
echo "Press Ctrl+C to close"
exec ssh -N -L "${LOCAL_PORT}:${REMOTE_TARGET}" "${PI_USER}@${PI_HOST}"
