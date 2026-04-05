#!/usr/bin/env bash
# push-env.sh — Push the local .env file to AWS Secrets Manager.
#
# Usage:
#   bash deploy/push-env.sh
#
# Use this after editing .env locally to sync to AWS.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${REPO_DIR}/.env"
SECRET_NAME="amp_swe_agent_env"
AWS_REGION="us-east-1"

if [ ! -f "${ENV_FILE}" ]; then
    echo "❌ .env not found at ${ENV_FILE}"
    exit 1
fi

echo "Pushing .env to AWS Secrets Manager (${SECRET_NAME})..."

aws secretsmanager update-secret \
    --secret-id "${SECRET_NAME}" \
    --secret-string "$(cat "${ENV_FILE}")" \
    --region "${AWS_REGION}" > /dev/null

echo "✅ Secret updated"
