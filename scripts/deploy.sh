#!/usr/bin/env bash
set -Eeuo pipefail

: "${IMAGE_URI:?IMAGE_URI is required}"

AWS_REGION="${AWS_REGION:-us-east-1}"
APP_DIR="/opt/fastapi-example"

cd "$APP_DIR"

# 1. Read configuration from Parameter Store
get_parameter() {
  aws ssm get-parameter \
    --region "$AWS_REGION" \
    --name "/fastapi/prod/$1" \
    --with-decryption \
    --query 'Parameter.Value' \
    --output text
}

POSTGRES_USER=$(get_parameter POSTGRES_USER)
POSTGRES_DB=$(get_parameter POSTGRES_DB)
POSTGRES_PASSWORD=$(get_parameter POSTGRES_PASSWORD)

export POSTGRES_USER POSTGRES_DB POSTGRES_PASSWORD

# 2. Build the database connection URL
# URL-encode credentials to support special characters
DATABASE_URL=$(python3 -c '
import os
from urllib.parse import quote

user = quote(os.environ["POSTGRES_USER"], safe="")
password = quote(os.environ["POSTGRES_PASSWORD"], safe="")
database = quote(os.environ["POSTGRES_DB"], safe="")

print(f"postgresql://{user}:{password}@db:5432/{database}")
')

export DATABASE_URL

for var in IMAGE_URI POSTGRES_USER POSTGRES_DB POSTGRES_PASSWORD DATABASE_URL; do
  if [[ -z "${!var:-}" ]]; then
    echo "ERROR: Missing required variable: $var" >&2
    exit 1
  fi
done
# 3. Authenticate to ECR using the EC2 IAM role
REGISTRY="${IMAGE_URI%%/*}"

aws ecr get-login-password \
  --region "$AWS_REGION" |
  docker login \
    --username AWS \
    --password-stdin "$REGISTRY"

# 4. Download the requested FastAPI image
docker compose -f compose.prod.yaml pull api

# 5. Create/update services and verify health
docker compose -f compose.prod.yaml \
  up -d --wait --wait-timeout 180

# 6. Validate FastAPI
curl --fail --silent --show-error \
  http://127.0.0.1:8000/health

# 7. Show running services
docker compose -f compose.prod.yaml ps

printf '\nDeployment completed: %s\n' "$IMAGE_URI"