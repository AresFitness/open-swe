#!/usr/bin/env bash
# run.sh — Entry point for the launchd service.
# Loads .env, activates venv, and starts the LangGraph server.

set -euo pipefail

AGENT_DIR="/Users/agent/amp-swe-agent"
cd "${AGENT_DIR}"

# Load environment variables from .env
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Activate the virtual environment
export PATH="${AGENT_DIR}/.venv/bin:${PATH}"

# Ensure sandbox directory exists
mkdir -p "${LOCAL_SANDBOX_ROOT_DIR:-/tmp/amp-swe-sandbox}"

# Start the LangGraph server (serves both API and dashboard)
exec langgraph dev --no-browser --host 0.0.0.0 --port 2024
