#!/bin/bash
# Deploy teltonika_collector.sh to Teltonika router
# Usage: ./deploy_collector.sh <host> [user] [key_file]
# Or with password: SSHPASS=password ./deploy_collector.sh <host> [user]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COLLECTOR_SCRIPT="$SCRIPT_DIR/teltonika_collector.sh"
REMOTE_PATH="/tmp/teltonika_collector.sh"

HOST="${1:?Usage: $0 <host> [user] [key_file]}"
USER="${2:-root}"
KEY="$3"

echo "Deploying collector script to $USER@$HOST..."

if [ -n "$KEY" ]; then
    # Key-based auth
    scp -i "$KEY" -o StrictHostKeyChecking=accept-new "$COLLECTOR_SCRIPT" "$USER@$HOST:$REMOTE_PATH"
    ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$USER@$HOST" "chmod +x $REMOTE_PATH"
elif [ -n "$SSHPASS" ]; then
    # Password-based auth via sshpass
    sshpass -e scp -o StrictHostKeyChecking=accept-new "$COLLECTOR_SCRIPT" "$USER@$HOST:$REMOTE_PATH"
    sshpass -e ssh -o StrictHostKeyChecking=accept-new "$USER@$HOST" "chmod +x $REMOTE_PATH"
else
    # Interactive password prompt
    scp -o StrictHostKeyChecking=accept-new "$COLLECTOR_SCRIPT" "$USER@$HOST:$REMOTE_PATH"
    ssh -o StrictHostKeyChecking=accept-new "$USER@$HOST" "chmod +x $REMOTE_PATH"
fi

echo "Collector script deployed to $REMOTE_PATH"
echo ""
echo "Test with: ssh $USER@$HOST '$REMOTE_PATH'"
