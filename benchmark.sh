#!/bin/bash

###############################################################################
# Sentinel Benchmark Script for Evaluators
# Run performance tests and generate benchmark reports
###############################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
WEBHOOK_URL="${WEBHOOK_URL:-http://localhost:8000/webhooks/alert}"
API_URL="${API_URL:-http://localhost:8001}"
TARGET_APP_URL="${TARGET_APP_URL:-http://localhost:5000}"

# Benchmark variables
RESULTS_FILE="benchmark_results_$(date +%s).json"
INCIDENTS=()
TIMES=()

###############################################################################
# Helper Functions
###############################################################################

print_header() {
    echo -e "\n${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  $1${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}!${NC} $1"
}

print_info() {
    echo -e "${BLUE}→${NC} $1"
}

check_services() {
    print_info "Checking system services..."
    
    # Check webhook ingress
    if ! curl -s -f http://localhost:8000/health > /dev/null 2>&1; then
        print_error "Webhook Ingress not responding"
        return 1
    fi
    print_success "Webhook Ingress (8000)"
    
    # Check dashboard API
    if ! curl -s -f http://localhost:8001/health > /dev/null 2>&1; then
        print_error "Dashboard API not responding"
        return 1
    fi
    print_success "Dashboard API (8001)"
    
    # Check target app
    if ! curl -s -f http://localhost:5000/health > /dev/null 2>&1; then
        print_warning "Target App (5000) - may not be critical"
    else
        print_success "Target App (5000)"
    fi
    
    # Check Redis
    if ! docker exec sentinel-redis-1 redis-cli ping > /dev/null 2>&1; then
        print_error "Redis not responding"
        return 1
    fi
    print_success "Redis (6379)"
    
    # Check PostgreSQL
    if ! docker exec sentinel-postgres-1 pg_isready -U sentinel > /dev/null 2>&1; then
        print_error "PostgreSQL not responding"
        return 1
    fi
    print_success "PostgreSQL (5432)"
    
    return 0
}

trigger_incident() {
    local incident_num=$1
    local incident_id="BENCH-$(date +%s%N)-$incident_num"
    
    print_info "Triggering incident $incident_num..."
    
    local response=$(curl -s -X POST "$WEBHOOK_URL" \
        -H "Content-Type: application/json" \
        -d "{
            \"source\": \"datadog\",
            \"message\": \"Benchmark test incident #$incident_num - High error rate detected\",
            \"severity\": \"P1\",
            \"service\": \"target-app\",
            \"environment\": \"production\",
            \"benchmark_id\": \"$incident_id\"
        }")
    
    echo "$incident_id"
}

wait_for_incident_completion() {
    local incident_id=$1
    local max_wait=120
    local elapsed=0
    local interval=2
    
    print_info "Waiting for incident $incident_id to complete (max ${max_wait}s)..."
    
    while [ $elapsed -lt $max_wait ]; do
        local incident=$(curl -s "$API_URL/api/incidents?limit=1" | grep -o "$incident_id" || true)
        
        if [ -n "$incident" ]; then
            local status=$(curl -s "$API_URL/api/incidents" | grep -o '"status":"[^"]*"' | head -1 | cut -d'"' -f4)
            
            if [ "$status" = "resolved" ]; then
                print_success "Incident completed!"
                return 0
            fi
        fi
        
        sleep $interval
        elapsed=$((elapsed + interval))
        echo -ne "\r  ⏳ Waiting... ${elapsed}s"
    done
    
    print_warning "Incident timeout after ${max_wait}s"
    return 1
}

run_single_incident_test() {
    print_header "Single Incident Test"
    
    local start_time=$(date +%s%N)
    
    # Generate normal traffic
    print_info "Generating normal traffic..."
    for i in {1..10}; do
        curl -s -X POST "$TARGET_APP_URL/checkout" \
            -H "Content-Type: application/json" \
            -d '{"coupon_code": "SAVE10"}' > /dev/null 2>&1 || true
        sleep 0.1
    done
    
    # Trigger failure
    print_info "Triggering failure scenario..."
    curl -s -X POST "$TARGET_APP_URL/checkout" \
        -H "Content-Type: application/json" \
        -d '{"coupon_code": "BUGGY"}' > /dev/null 2>&1 || true
    
    sleep 0.5
    
    # Fire alert
    incident_id=$(trigger_incident 1)
    wait_for_incident_completion "$incident_id"
    
    local end_time=$(date +%s%N)
    local duration_ms=$(( (end_time - start_time) / 1000000 ))
    local duration_s=$(echo "scale=2; $duration_ms / 1000" | bc)
    
    print_success "Test completed in ${duration_s}s"
    TIMES+=("$duration_s")
}

run_multi_incident_test() {
    local num_incidents=$1
    print_header "Multiple Incident Test ($num_incidents incidents)"
    
    local start_time=$(date +%s%N)
    
    # Trigger multiple incidents in parallel
    print_info "Triggering $num_incidents incidents..."
    for i in $(seq 1 $num_incidents); do
        trigger_incident $i > /dev/null &
        sleep 0.5
    done
    wait
    
    print_success "All incidents triggered"
    
    # Wait for all to complete
    print_info "Waiting for all incidents to complete..."
    sleep 30
    
    local end_time=$(date +%s%N)
    local duration_ms=$(( (end_time - start_time) / 1000000 ))
    local duration_s=$(echo "scale=2; $duration_ms / 1000" | bc)
    
    print_success "Test completed in ${duration_s}s"
    TIMES+=("$duration_s")
}

run_load_test() {
    print_header "Load Test (10 sequential incidents)"
    
    local start_time=$(date +%s%N)
    
    for i in $(seq 1 10); do
        print_info "[$i/10] Triggering incident..."
        trigger_incident $i > /dev/null
        sleep 2
    done
    
    local end_time=$(date +%s%N)
    local duration_ms=$(( (end_time - start_time) / 1000000 ))
    local duration_s=$(echo "scale=2; $duration_ms / 1000" | bc)
    
    print_success "Load test completed in ${duration_s}s"
    TIMES+=("$duration_s")
}

calculate_stats() {
    local total=0
    local count=${#TIMES[@]}
    
    if [ $count -eq 0 ]; then
        return
    fi
    
    for time in "${TIMES[@]}"; do
        total=$(echo "$total + $time" | bc)
    done
    
    local avg=$(echo "scale=2; $total / $count" | bc)
    local min=${TIMES[0]}
    local max=${TIMES[0]}
    
    for time in "${TIMES[@]}"; do
        if (( $(echo "$time < $min" | bc -l) )); then
            min=$time
        fi
        if (( $(echo "$time > $max" | bc -l) )); then
            max=$time
        fi
    done
    
    print_header "Benchmark Results"
    echo -e "Total Runs:       ${BLUE}$count${NC}"
    echo -e "Average Time:     ${GREEN}${avg}s${NC}"
    echo -e "Minimum Time:     ${GREEN}${min}s${NC}"
    echo -e "Maximum Time:     ${GREEN}${max}s${NC}"
    echo -e "Total Time:       ${GREEN}${total}s${NC}"
    
    # Save to JSON
    cat > "$RESULTS_FILE" <<EOF
{
  "benchmark_date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "test_count": $count,
  "average_time_seconds": $avg,
  "min_time_seconds": $min,
  "max_time_seconds": $max,
  "total_time_seconds": $total,
  "individual_times": [$(IFS=, ; echo "${TIMES[*]}")]
}
EOF
    
    print_success "Results saved to $RESULTS_FILE"
}

show_usage() {
    cat <<EOF
${BLUE}Sentinel Benchmark Script${NC}

Usage: ./benchmark.sh [OPTIONS]

Options:
    -h, --help              Show this help message
    -c, --check             Check system services and exit
    -s, --single            Run single incident test (default)
    -m, --multi NUM         Run test with NUM concurrent incidents
    -l, --load              Run load test with 10 sequential incidents
    -f, --full              Run all tests (single, multi, load)

Examples:
    ./benchmark.sh -c                # Check services
    ./benchmark.sh -s                # Run single incident test
    ./benchmark.sh -m 5              # Run test with 5 concurrent incidents
    ./benchmark.sh -l                # Run load test
    ./benchmark.sh -f                # Run all tests

EOF
}

###############################################################################
# Main Script
###############################################################################

main() {
    if [ $# -eq 0 ]; then
        show_usage
        exit 0
    fi
    
    print_header "Sentinel Benchmark Suite"
    echo -e "Webhook URL: ${BLUE}$WEBHOOK_URL${NC}"
    echo -e "API URL:     ${BLUE}$API_URL${NC}"
    echo -e "Target App:  ${BLUE}$TARGET_APP_URL${NC}\n"
    
    # Check services first
    if ! check_services; then
        print_error "System services not ready. Please start Sentinel with: docker compose up -d"
        exit 1
    fi
    
    print_success "All services operational\n"
    
    # Parse arguments
    case "$1" in
        -h|--help)
            show_usage
            exit 0
            ;;
        -c|--check)
            print_success "System check passed"
            exit 0
            ;;
        -s|--single)
            run_single_incident_test
            ;;
        -m|--multi)
            if [ -z "$2" ]; then
                print_error "Multi-incident test requires a number"
                exit 1
            fi
            run_multi_incident_test "$2"
            ;;
        -l|--load)
            run_load_test
            ;;
        -f|--full)
            run_single_incident_test
            sleep 5
            run_multi_incident_test 5
            sleep 5
            run_load_test
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
    
    calculate_stats
    
    print_header "Benchmark Complete"
    echo -e "Results file: ${BLUE}$RESULTS_FILE${NC}"
    echo -e "\nNext steps:"
    echo -e "  - View results: ${BLUE}cat $RESULTS_FILE${NC}"
    echo -e "  - View incidents: ${BLUE}curl http://localhost:8001/api/incidents${NC}"
    echo -e "  - Dashboard: ${BLUE}http://localhost:9000/dashboard.html${NC}\n"
}

main "$@"
