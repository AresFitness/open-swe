#!/usr/bin/env bash
# setup-sandbox.sh — Run each repo's own .swe/setup.sh in the sandbox.
#
# Each repo owns its setup logic. This script just discovers and runs them.
# Cross-repo orchestration (E2E testing, schema sync) lives here.
#
# Usage:
#   SANDBOX_DIR=/tmp/amp-swe-sandbox ./scripts/setup-sandbox.sh

set -euo pipefail

SANDBOX_DIR="${SANDBOX_DIR:-/tmp/amp-swe-sandbox}"

echo "=== AMP SWE Agent — Sandbox Setup ==="
echo "Sandbox: ${SANDBOX_DIR}"
echo ""

# ── Run each repo's .swe/setup.sh ──────────────────────────────────

failed=0
for repo_dir in "${SANDBOX_DIR}"/*/; do
    repo_name=$(basename "${repo_dir}")
    setup_script="${repo_dir}.swe/setup.sh"

    if [ -f "${setup_script}" ]; then
        echo "━━━ ${repo_name} ━━━"
        if bash "${setup_script}"; then
            echo ""
        else
            echo "  ⚠️  ${repo_name} setup failed (exit $?), continuing..."
            echo ""
            failed=$((failed + 1))
        fi
    else
        echo "━━━ ${repo_name}: no .swe/setup.sh, skipping ━━━"
        echo ""
    fi
done

# ── Summary ─────────────────────────────────────────────────────────

echo "=== Setup Complete ==="
if [ ${failed} -gt 0 ]; then
    echo "⚠️  ${failed} repo(s) had setup issues"
else
    echo "✅ All repos set up successfully"
fi
