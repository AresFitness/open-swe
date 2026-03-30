#!/usr/bin/env bash
# setup-sandbox.sh — Prepare the sandbox environment for building both repos.
#
# Run this after repos are cloned into the sandbox. It:
#   1. Sets up iOS secrets (secrets.xcconfig from AWS Secrets Manager)
#   2. Sets up Asensei SSH key for private Swift packages
#   3. Installs iOS Tuist dependencies + generates Xcode project
#   4. Installs backend Node.js dependencies
#   5. Points iOS at the dev environment
#
# Prerequisites on the Mac:
#   - AWS CLI configured with access to amp_ios_secrets and amp_ios_asensei_ssh
#   - Xcode installed with command line tools
#   - Homebrew packages: tuist, swiftgen, swiftlint
#   - Node.js 22+, pnpm 10+
#
# Usage:
#   SANDBOX_DIR=/tmp/amp-swe-sandbox ./scripts/setup-sandbox.sh

set -euo pipefail

SANDBOX_DIR="${SANDBOX_DIR:-/tmp/amp-swe-sandbox}"
IOS_DIR="${SANDBOX_DIR}/amp-ios"
BACKEND_DIR="${SANDBOX_DIR}/RedefinedFitness"
AWS_REGION="us-east-1"

echo "=== AMP SWE Agent — Sandbox Setup ==="
echo "Sandbox: ${SANDBOX_DIR}"
echo ""

# ── Step 1: iOS Secrets ─────────────────────────────────────────────

setup_ios_secrets() {
    if [ ! -d "$IOS_DIR" ]; then
        echo "⚠️  iOS repo not found at ${IOS_DIR}, skipping iOS setup"
        return 0
    fi

    echo "📦 Step 1: Setting up iOS secrets..."

    # Fetch secrets from AWS Secrets Manager
    local secrets
    secrets=$(aws secretsmanager get-secret-value \
        --secret-id amp_ios_secrets \
        --region "${AWS_REGION}" \
        --query 'SecretString' \
        --output text 2>/dev/null) || {
        echo "⚠️  Failed to fetch iOS secrets from AWS. Trying fallback..."
        # Fallback: create a minimal secrets.xcconfig so Makefile doesn't fail
        touch "${IOS_DIR}/Configuration/secrets.xcconfig"
        echo "  Created empty secrets.xcconfig (builds may fail without real secrets)"
        return 0
    }

    # Write secrets.xcconfig
    mkdir -p "${IOS_DIR}/Configuration"
    echo "${secrets}" > "${IOS_DIR}/Configuration/secrets.xcconfig"
    echo "  ✅ secrets.xcconfig written ($(echo "${secrets}" | wc -l | tr -d ' ') keys)"

    # Generate Configuration.plist from secrets
    if [ -f "${IOS_DIR}/ci_scripts/convert_secrets.sh" ]; then
        (cd "${IOS_DIR}" && sh ci_scripts/convert_secrets.sh 2>/dev/null) || true
        echo "  ✅ Configuration.plist generated"
    fi
}

# ── Step 2: Asensei SSH Key ─────────────────────────────────────────

setup_asensei_ssh() {
    if [ ! -d "$IOS_DIR" ]; then
        return 0
    fi

    echo "🔑 Step 2: Setting up Asensei SSH key..."

    # Check if already configured
    if [ -f ~/.ssh/id_asensei ]; then
        echo "  ✅ SSH key already exists at ~/.ssh/id_asensei"
        return 0
    fi

    local ssh_key
    ssh_key=$(aws secretsmanager get-secret-value \
        --secret-id amp_ios_asensei_ssh \
        --region "${AWS_REGION}" \
        --query 'SecretString' \
        --output text 2>/dev/null) || {
        echo "  ⚠️  Failed to fetch SSH key from AWS, skipping"
        return 0
    }

    mkdir -p ~/.ssh
    echo "${ssh_key}" > ~/.ssh/id_asensei
    chmod 600 ~/.ssh/id_asensei

    # Add SSH config if not present
    if ! grep -q "Host asensei" ~/.ssh/config 2>/dev/null; then
        cat >> ~/.ssh/config <<'SSHEOF'

Host asensei
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_asensei
    IdentitiesOnly yes
    StrictHostKeyChecking no
SSHEOF
    fi

    # Configure git URL rewriting for Asensei packages
    git config --global url."ssh://git@asensei/asensei".insteadOf "git@github.com:asensei" 2>/dev/null || true

    echo "  ✅ SSH key configured"
}

# ── Step 3: iOS Project Setup ───────────────────────────────────────

setup_ios_project() {
    if [ ! -d "$IOS_DIR" ]; then
        return 0
    fi

    echo "🔧 Step 3: Setting up iOS project..."

    cd "${IOS_DIR}"

    # Install Tuist dependencies (this downloads SPM packages)
    echo "  Installing Tuist dependencies..."
    if command -v tuist &>/dev/null; then
        tuist install 2>&1 | tail -3 || {
            echo "  ⚠️  tuist install failed, continuing..."
        }
    else
        echo "  ⚠️  tuist not found, skipping"
        return 0
    fi

    # Set dev environment (generates amplifyconfiguration.json + awsconfiguration.json)
    echo "  Setting dev environment..."
    AMP_ENV=dev make env 2>&1 | tail -3 || {
        echo "  ⚠️  make env failed, continuing..."
    }

    # Generate Xcode project
    echo "  Generating Xcode project..."
    make project 2>&1 | tail -5 || {
        echo "  ⚠️  make project failed, continuing..."
    }

    echo "  ✅ iOS project ready"
}

# ── Step 4: Backend Setup ───────────────────────────────────────────

setup_backend() {
    if [ ! -d "$BACKEND_DIR" ]; then
        echo "⚠️  Backend repo not found at ${BACKEND_DIR}, skipping"
        return 0
    fi

    echo "📦 Step 4: Setting up backend..."

    cd "${BACKEND_DIR}"

    # Install pnpm dependencies
    echo "  Installing pnpm dependencies..."
    pnpm install --frozen-lockfile 2>&1 | tail -5 || {
        echo "  Retrying without --frozen-lockfile..."
        pnpm install 2>&1 | tail -5 || {
            echo "  ⚠️  pnpm install failed"
            return 0
        }
    }

    echo "  ✅ Backend dependencies installed"
}

# ── Step 5: Verify ──────────────────────────────────────────────────

verify_setup() {
    echo ""
    echo "=== Verification ==="

    if [ -d "$BACKEND_DIR" ]; then
        if [ -d "${BACKEND_DIR}/node_modules" ]; then
            echo "  ✅ Backend: node_modules exists"
        else
            echo "  ❌ Backend: node_modules missing"
        fi
    fi

    if [ -d "$IOS_DIR" ]; then
        if [ -f "${IOS_DIR}/Configuration/secrets.xcconfig" ]; then
            local count
            count=$(wc -l < "${IOS_DIR}/Configuration/secrets.xcconfig" | tr -d ' ')
            echo "  ✅ iOS: secrets.xcconfig (${count} lines)"
        else
            echo "  ❌ iOS: secrets.xcconfig missing"
        fi

        if [ -f "${IOS_DIR}/Amp.xcworkspace/contents.xcworkspacedata" ]; then
            echo "  ✅ iOS: Xcode workspace generated"
        else
            echo "  ⚠️  iOS: Xcode workspace not found (may need make project)"
        fi

        if [ -f "${IOS_DIR}/Modules/AmpConfiguration/Sources/amplifyconfiguration.json" ]; then
            echo "  ✅ iOS: Amplify configuration present"
        else
            echo "  ⚠️  iOS: Amplify configuration missing (run make dev)"
        fi
    fi

    echo ""
    echo "=== Setup Complete ==="
}

# ── Run ─────────────────────────────────────────────────────────────

setup_ios_secrets
setup_asensei_ssh
setup_ios_project
setup_backend
verify_setup
