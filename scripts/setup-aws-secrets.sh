#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
REGION="${AWS_REGION:-us-east-1}"

if [[ $# -lt 1 ]]; then
  SECRET_ARN="$(aws cloudformation describe-stacks \
    --stack-name HackathonFeedApi \
    --query "Stacks[0].Outputs[?OutputKey=='AppSecretArn'].OutputValue" \
    --output text \
    --region "${REGION}" 2>/dev/null || true)"
  if [[ -z "${SECRET_ARN}" || "${SECRET_ARN}" == "None" ]]; then
    echo "Usage: $0 <secret-arn>" >&2
    exit 1
  fi
else
  SECRET_ARN="$1"
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}" >&2
  exit 1
fi

get_env() {
  local key="$1"
  local value
  value="$(grep -E "^${key}=" "${ENV_FILE}" | tail -n1 | cut -d= -f2- || true)"
  printf '%s' "${value}"
}

JWT_SECRET_KEY="$(get_env JWT_SECRET_KEY)"
DATABASE_URL="$(get_env DATABASE_URL)"
SUPABASE_URL="$(get_env SUPABASE_URL)"
SUPABASE_SERVICE_KEY="$(get_env SUPABASE_SERVICE_KEY)"
if [[ -z "${SUPABASE_SERVICE_KEY}" ]]; then
  SUPABASE_SERVICE_KEY="$(get_env SUPABASE_KEY)"
fi
GOOGLE_CLIENT_ID="$(get_env GOOGLE_CLIENT_ID)"
GEMINI_API_KEY="$(get_env GEMINI_API_KEY)"
RAZORPAY_KEY_ID="$(get_env RAZORPAY_KEY_ID)"
RAZORPAY_KEY_SECRET="$(get_env RAZORPAY_KEY_SECRET)"
SMTP_EMAIL="$(get_env SMTP_EMAIL)"
SMTP_PASSWORD="$(get_env SMTP_PASSWORD)"

if [[ -z "${JWT_SECRET_KEY}" || "${JWT_SECRET_KEY}" == *"change-this"* ]]; then
  JWT_SECRET_KEY="$(openssl rand -base64 48)"
fi

export JWT_SECRET_KEY DATABASE_URL SUPABASE_URL SUPABASE_SERVICE_KEY \
  GOOGLE_CLIENT_ID GEMINI_API_KEY RAZORPAY_KEY_ID RAZORPAY_KEY_SECRET \
  SMTP_EMAIL SMTP_PASSWORD

SECRET_JSON="$(python3 - <<'PY'
import json, os
print(json.dumps({
    "JWT_SECRET_KEY": os.environ.get("JWT_SECRET_KEY", ""),
    "DATABASE_URL": os.environ.get("DATABASE_URL", ""),
    "SUPABASE_URL": os.environ.get("SUPABASE_URL", ""),
    "SUPABASE_SERVICE_KEY": os.environ.get("SUPABASE_SERVICE_KEY", ""),
    "GOOGLE_CLIENT_ID": os.environ.get("GOOGLE_CLIENT_ID", ""),
    "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY", ""),
    "RAZORPAY_KEY_ID": os.environ.get("RAZORPAY_KEY_ID", ""),
    "RAZORPAY_KEY_SECRET": os.environ.get("RAZORPAY_KEY_SECRET", ""),
    "SMTP_EMAIL": os.environ.get("SMTP_EMAIL", ""),
    "SMTP_PASSWORD": os.environ.get("SMTP_PASSWORD", ""),
}))
PY
)"

aws secretsmanager put-secret-value \
  --secret-id "${SECRET_ARN}" \
  --secret-string "${SECRET_JSON}" \
  --region "${REGION}"

echo "Updated secret: ${SECRET_ARN}"

CLUSTER="$(aws cloudformation describe-stacks \
  --stack-name HackathonFeedApi \
  --query "Stacks[0].Outputs[?OutputKey=='EcsClusterName'].OutputValue" \
  --output text \
  --region "${REGION}")"
SERVICE="$(aws cloudformation describe-stacks \
  --stack-name HackathonFeedApi \
  --query "Stacks[0].Outputs[?OutputKey=='EcsServiceName'].OutputValue" \
  --output text \
  --region "${REGION}")"

aws ecs update-service \
  --cluster "${CLUSTER}" \
  --service "${SERVICE}" \
  --force-new-deployment \
  --region "${REGION}" >/dev/null

echo "Forced new ECS deployment to pick up secrets."
