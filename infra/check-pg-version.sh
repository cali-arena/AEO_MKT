#!/usr/bin/env sh
# Check Postgres major version in the running db container.
# Run from project root: sh infra/check-pg-version.sh
# Use this to pick the right pgvector image tag (pg15, pg16, pg17, pg18).

set -e
COMPOSE_FILE="${COMPOSE_FILE:-infra/docker-compose.yml}"
ENV_FILE="${ENV_FILE:-.env}"

# Default container name when using compose project "infra"
CONTAINER="${DB_CONTAINER:-infra-db-1}"
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$" 2>/dev/null; then
  CONTAINER="$(docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps -q db 2>/dev/null | xargs -I{} docker inspect -f '{{.Name}}' {} 2>/dev/null | sed 's/^\///')"
  [ -z "$CONTAINER" ] && CONTAINER="infra-db-1"
fi

echo "Checking Postgres version in container: $CONTAINER"
docker exec "$CONTAINER" psql -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-ai_mkt}" -t -c "SHOW server_version;"
echo "Major version (use this for pgvector image tag, e.g. pgvector/pgvector:pg16):"
docker exec "$CONTAINER" psql -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-ai_mkt}" -t -c "SELECT (regexp_match(current_setting('server_version'), '^([0-9]+)'))[1] AS major;"
