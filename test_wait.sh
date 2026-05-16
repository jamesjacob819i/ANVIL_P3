API_URL="http://localhost:8001"
incident_id="BENCH-1234"
status=$(curl -s "$API_URL/api/incidents" | grep -o '"status":"[^"]*"' | head -1 | cut -d'"' -f4)
echo $status
incident=$(curl -s "$API_URL/api/incidents?limit=1" | grep -o "$incident_id" || true)
echo $incident
