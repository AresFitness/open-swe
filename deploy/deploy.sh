#!/usr/bin/env bash
# deploy.sh — Pull latest code, rebuild, and restart the service.
#
# Run on the Mac Mini to deploy updates:
#   bash deploy/deploy.sh
#
# Or triggered by CI (GitHub Actions) via SSH.

set -euo pipefail

REPO_DIR="/Users/agent/amp-swe-agent"
SERVICE="system/com.amp.swe-agent"

echo "=== Deploying AMP SWE Agent ==="
cd "${REPO_DIR}"

# Pull latest
echo "Pulling latest..."
git pull --ff-only origin main
git submodule update --remote --merge

# Update Python deps
echo "Updating Python dependencies..."
uv sync --python 3.12

# Pull secrets from AWS
echo "Pulling .env from AWS..."
bash deploy/pull-env.sh

# Rebuild dashboard
echo "Building dashboard..."
cd dashboard
npm ci --silent
npm run build
cd ..

# Restart service
echo "Restarting service..."
sudo launchctl kickstart -k "${SERVICE}" 2>/dev/null || {
    echo "Service not running, bootstrapping..."
    sudo launchctl bootstrap system /Library/LaunchDaemons/com.amp.swe-agent.plist
}

# Wait for health
echo "Waiting for health check..."
for i in $(seq 1 10); do
    sleep 3
    if curl -s http://localhost:2024/health | grep -q "healthy"; then
        echo "✅ Deployed and healthy"
        exit 0
    fi
done

echo "⚠️  Service started but health check not responding"
echo "Check logs: tail -f /var/log/swe-agent.log"
exit 1
