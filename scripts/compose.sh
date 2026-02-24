#!/usr/bin/env bash
# Run docker compose with --env-file .env from repo root. Use this on the VM
# so POSTGRES_PASSWORD is set and you don't see the "variable is not set" warning.
# Usage: ./scripts/compose.sh up -d --build
#        ./scripts/compose.sh logs -f api

set -e
cd "$(dirname "$0")/.."
exec docker compose -f infra/docker-compose.yml --env-file .env "$@"
