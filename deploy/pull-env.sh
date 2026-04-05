#!/usr/bin/env bash
# pull-env.sh — Pull the .env file from AWS Secrets Manager.
#
# Usage:
#   bash deploy/pull-env.sh
#
# Requires AWS CLI configured with access to amp_swe_agent_env secret.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${REPO_DIR}/.env"
SECRET_NAME="amp_swe_agent_env"
AWS_REGION="us-east-1"

echo "Pulling .env from AWS Secrets Manager (${SECRET_NAME})..."

aws secretsmanager get-secret-value \
    --secret-id "${SECRET_NAME}" \
    --region "${AWS_REGION}" \
    --query 'SecretString' \
    --output text > "${ENV_FILE}"

chmod 600 "${ENV_FILE}"

KEY_COUNT=$(grep -c "=" "${ENV_FILE}" 2>/dev/null || echo 0)
echo "✅ .env written (${KEY_COUNT} lines) at ${ENV_FILE}"
