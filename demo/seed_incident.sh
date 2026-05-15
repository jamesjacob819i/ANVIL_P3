#!/usr/bin/env bash
set -euo pipefail

echo "=== Sentinel Demo: Seeding Incident ==="

SENTINEL_REPO="${SENTINEL_REPO:-jamesjacobi/sentinel-demo}"
WEBHOOK_URL="${WEBHOOK_URL:-http://localhost:8000/webhooks/alert}"
TARGET_APP_URL="${TARGET_APP_URL:-http://localhost:5001}"

echo "1. Generating traffic to target app..."
for i in $(seq 1 20); do
  curl -s -X POST "$TARGET_APP_URL/checkout" \
    -H "Content-Type: application/json" \
    -d '{"coupon_code": "SAVE10"}' > /dev/null 2>&1 || true
done

echo "2. Triggering a failure..."
curl -s -X POST "$TARGET_APP_URL/checkout" \
  -H "Content-Type: application/json" \
  -d '{"coupon_code": "BUGGY"}' > /dev/null 2>&1 || true

echo "3. Firing alert webhook to Sentinel..."
curl -s -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "datadog",
    "message": "High error rate detected on /checkout endpoint - 25% error rate in last 5 minutes",
    "severity": "P1",
    "service": "target-app",
    "environment": "production"
  }'

echo ""
echo "=== Incident seeded! Check the dashboard at http://localhost:8001 ==="
