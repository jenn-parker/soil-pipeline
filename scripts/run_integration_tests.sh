#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  echo "Missing .env. Copy .env.sample to .env and configure the LocalStack auth token first." >&2
  exit 1
fi

# Load the same local settings used by Docker Compose, then use the published
# host ports because pytest runs outside the Compose network.
set -a
# shellcheck disable=SC1091
source .env
set +a

export DATABASE_URL="${INTEGRATION_DATABASE_URL:-postgresql+asyncpg://earth_user:earth_password@localhost:5432/soil_db}"
export AWS_ENDPOINT_URL_S3="${INTEGRATION_AWS_ENDPOINT_URL_S3:-http://localhost:4566}"
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-test}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-test}"
export S3_BATCH_BUCKET="${S3_BATCH_BUCKET:-soil-pipeline-batches}"

alembic upgrade head
RUN_INTEGRATION_TESTS=1 python -m pytest tests/integration -q "$@"
