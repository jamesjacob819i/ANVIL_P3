#!/usr/bin/env bash
set -euo pipefail

echo "=== Resetting Sentinel Demo ==="

echo "1. Stopping all containers..."
docker compose -f ../docker-compose.yml down

echo "2. Removing volumes..."
docker volume rm sentinel_postgres_data 2>/dev/null || true

echo "3. Restarting fresh..."
docker compose -f ../docker-compose.yml up -d --build

echo ""
echo "=== Reset complete! Run ./seed_incident.sh to trigger a demo incident. ==="
