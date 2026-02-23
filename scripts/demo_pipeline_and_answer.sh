#!/usr/bin/env bash
# Demo: Run pipeline for tenant A + url, then call /answer with sample query.
# Requires: Postgres running, API running (uvicorn), DATABASE_URL set.
#
# Usage: ./scripts/demo_pipeline_and_answer.sh [URL] [TENANT] [QUERY]

set -e

URL="${1:-https://example.com}"
TENANT="${2:-A}"
QUERY="${3:-What is this page about?}"
API_BASE="${API_BASE:-http://localhost:8000}"

echo "1. Running pipeline for tenant=$TENANT url=$URL"
python -m apps.api.services.pipeline --tenant "$TENANT" --url "$URL"

echo ""
echo "2. Calling POST /answer with query='$QUERY'"
curl -s -X POST "$API_BASE/answer" \
  -H "Authorization: Bearer tenant:$TENANT" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"$QUERY\"}" | python -m json.tool
