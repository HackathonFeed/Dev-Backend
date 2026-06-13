#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFRA_DIR="${ROOT_DIR}/infra"
ENV_FILE="${ROOT_DIR}/.env"
REGION="${AWS_REGION:-us-east-1}"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

echo "==> Checking prerequisites"
require_cmd docker
require_cmd npm
require_cmd npx

if ! command -v aws >/dev/null 2>&1; then
  echo "AWS CLI is not installed."
  echo "Install: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
  echo "Then run: aws configure"
  exit 1
fi

if ! aws sts get-caller-identity >/dev/null 2>&1; then
  echo "AWS credentials are not configured. Run: aws configure" >&2
  exit 1
fi

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
export CDK_DEFAULT_ACCOUNT="${ACCOUNT_ID}"
export CDK_DEFAULT_REGION="${REGION}"

echo "==> Installing CDK dependencies"
cd "${INFRA_DIR}"
npm install

echo "==> Bootstrapping CDK (safe to re-run)"
npx cdk bootstrap "aws://${ACCOUNT_ID}/${REGION}"

CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:3000,http://localhost:5173}"
echo "==> Deploying stack (CORS_ORIGINS=${CORS_ORIGINS})"
npx cdk deploy --require-approval never -c corsOrigins="${CORS_ORIGINS}"

SECRET_ARN="$(aws cloudformation describe-stacks \
  --stack-name HackathonFeedApi \
  --query "Stacks[0].Outputs[?OutputKey=='AppSecretArn'].OutputValue" \
  --output text \
  --region "${REGION}")"

if [[ -f "${ENV_FILE}" ]]; then
  echo "==> Updating Secrets Manager from ${ENV_FILE}"
  bash "${ROOT_DIR}/scripts/setup-aws-secrets.sh" "${SECRET_ARN}"
else
  echo "==> No .env found. Update secret manually:"
  echo "    ${SECRET_ARN}"
fi

LB_URL="$(aws cloudformation describe-stacks \
  --stack-name HackathonFeedApi \
  --query "Stacks[0].Outputs[?OutputKey=='LoadBalancerUrl'].OutputValue" \
  --output text \
  --region "${REGION}")"

echo
echo "Deployment complete."
echo "API URL: ${LB_URL}"
echo "Health:  ${LB_URL}/health"
echo "Docs:    ${LB_URL}/docs"
