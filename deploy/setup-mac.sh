#!/usr/bin/env bash
# setup-mac.sh — One-time setup for a fresh Mac Mini deployment.
#
# Run as root or with sudo:
#   sudo bash deploy/setup-mac.sh
#
# This script:
# 1. Creates the 'agent' user (if not exists)
# 2. Installs system dependencies (Homebrew, Xcode CLI, etc.)
# 3. Clones the repo
# 4. Sets up Python + Node.js
# 5. Builds the dashboard
# 6. Installs the launchd service
# 7. Installs Cloudflare Tunnel

set -euo pipefail

AGENT_USER="agent"
AGENT_HOME="/Users/${AGENT_USER}"
REPO_URL="git@github.com:AresFitness/open-swe.git"
REPO_DIR="${AGENT_HOME}/amp-swe-agent"

echo "=== AMP SWE Agent — Mac Mini Setup ==="
echo ""

# ── 1. Create agent user ────────────────────────────────────────────

if ! id -u "${AGENT_USER}" &>/dev/null; then
    echo "Creating user '${AGENT_USER}'..."
    sysadminctl -addUser "${AGENT_USER}" -fullName "SWE Agent" -shell /bin/zsh -home "${AGENT_HOME}"
    echo "  Created ${AGENT_USER}"
else
    echo "  User '${AGENT_USER}' already exists"
fi

# ── 2. System dependencies ──────────────────────────────────────────

echo ""
echo "Installing system dependencies..."

# Xcode command line tools
if ! xcode-select -p &>/dev/null; then
    xcode-select --install
    echo "  ⚠️  Xcode CLI tools installing — re-run this script after installation completes"
    exit 1
fi
echo "  ✅ Xcode CLI tools"

# Homebrew (as agent user)
if ! su - "${AGENT_USER}" -c "which brew" &>/dev/null; then
    su - "${AGENT_USER}" -c 'NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
fi
echo "  ✅ Homebrew"

# Core tools
su - "${AGENT_USER}" -c "brew install python@3.12 node pnpm git gh tuist swiftlint cloudflared"
echo "  ✅ Core tools installed"

# uv (Python package manager)
su - "${AGENT_USER}" -c "curl -LsSf https://astral.sh/uv/install.sh | sh"
echo "  ✅ uv"

# Maestro
su - "${AGENT_USER}" -c 'curl -fsSL "https://get.maestro.mobile.dev" | bash'
echo "  ✅ Maestro"

# ── 3. Clone repo ──────────────────────────────────────────────────

echo ""
if [ ! -d "${REPO_DIR}" ]; then
    echo "Cloning repo..."
    su - "${AGENT_USER}" -c "git clone ${REPO_URL} ${REPO_DIR}"
    su - "${AGENT_USER}" -c "cd ${REPO_DIR} && git submodule update --init --recursive"
else
    echo "Repo already exists, pulling latest..."
    su - "${AGENT_USER}" -c "cd ${REPO_DIR} && git pull --ff-only && git submodule update --remote"
fi
echo "  ✅ Repo at ${REPO_DIR}"

# ── 4. Python + dependencies ───────────────────────────────────────

echo ""
echo "Installing Python dependencies..."
su - "${AGENT_USER}" -c "cd ${REPO_DIR} && uv sync --python 3.12 --all-extras"
echo "  ✅ Python dependencies"

# ── 5. Build dashboard ─────────────────────────────────────────────

echo ""
echo "Building dashboard..."
su - "${AGENT_USER}" -c "cd ${REPO_DIR}/dashboard && npm ci && npm run build"
echo "  ✅ Dashboard built"

# ── 6. Environment file ────────────────────────────────────────────

echo ""
echo "Pulling .env from AWS Secrets Manager..."
su - "${AGENT_USER}" -c "cd ${REPO_DIR} && bash deploy/pull-env.sh" || {
    echo "  ⚠️  Failed to pull .env from AWS. Create it manually:"
    echo "     cp ${REPO_DIR}/.env.example ${REPO_DIR}/.env && vim ${REPO_DIR}/.env"
}

# ── 7. Install launchd service ──────────────────────────────────────

echo ""
echo "Installing launchd service..."
chmod +x "${REPO_DIR}/deploy/run.sh"
cp "${REPO_DIR}/deploy/com.amp.swe-agent.plist" /Library/LaunchDaemons/
launchctl bootstrap system /Library/LaunchDaemons/com.amp.swe-agent.plist 2>/dev/null || true
echo "  ✅ Service installed (com.amp.swe-agent)"

# ── 8. Create iOS simulator ────────────────────────────────────────

echo ""
echo "Creating iOS simulator..."
su - "${AGENT_USER}" -c "xcrun simctl create 'iPhone 16 Pro' 'iPhone 16 Pro' 2>/dev/null || echo 'Already exists'"
echo "  ✅ Simulator"

# ── 9. Cloudflare Tunnel ───────────────────────────────────────────

echo ""
echo "=== Cloudflare Tunnel Setup ==="
echo ""
echo "To expose the agent to the internet:"
echo ""
echo "  1. Authenticate cloudflared:"
echo "     su - ${AGENT_USER} -c 'cloudflared tunnel login'"
echo ""
echo "  2. Create a tunnel:"
echo "     su - ${AGENT_USER} -c 'cloudflared tunnel create amp-swe-agent'"
echo ""
echo "  3. Configure DNS (in Cloudflare dashboard):"
echo "     swe.ampfit.com → CNAME → <tunnel-id>.cfargotunnel.com"
echo ""
echo "  4. Create tunnel config:"
echo "     cat > ${AGENT_HOME}/.cloudflared/config.yml << EOF"
echo "     tunnel: <tunnel-id>"
echo "     credentials-file: ${AGENT_HOME}/.cloudflared/<tunnel-id>.json"
echo "     ingress:"
echo "       - hostname: swe.ampfit.com"
echo "         service: http://localhost:2024"
echo "       - service: http_status:404"
echo "     EOF"
echo ""
echo "  5. Install as service:"
echo "     sudo cloudflared service install"
echo ""

# ── 10. Summary ─────────────────────────────────────────────────────

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Fill in ${REPO_DIR}/.env with API keys and secrets"
echo "  2. Set up Cloudflare Tunnel (instructions above)"
echo "  3. Start the service:"
echo "     sudo launchctl kickstart system/com.amp.swe-agent"
echo "  4. Check health:"
echo "     curl http://localhost:2024/health"
echo "  5. View logs:"
echo "     tail -f /var/log/swe-agent.log"
echo ""
