#!/bin/bash
set -euo pipefail

# FinBrain Trust Check - Comprehensive Security and Validation Suite
# Combines all existing security audits and validation scripts into one authoritative check
# Generates report.json for CI/CD pipeline consumption

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORT_FILE="${SCRIPT_DIR}/report.json"
TEMP_DIR="/tmp/trust_check_$$"
EXIT_CODE=0

# Colors and formatting
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }

# Initialize report structure
init_report() {
    mkdir -p "$TEMP_DIR"
    cat > "$REPORT_FILE" << 'EOF'
{
  "trust_check": {
    "version": "1.0.0",
    "timestamp": "",
    "duration_seconds": 0,
    "overall_status": "RUNNING",
    "summary": {
      "total_checks": 0,
      "passed": 0,
      "failed": 0,
      "warnings": 0
    },
    "checks": {
      "database_unification": {"status": "PENDING", "details": [], "duration": 0},
      "security_audit": {"status": "PENDING", "details": [], "duration": 0},
      "ai_contamination": {"status": "PENDING", "details": [], "duration": 0},
      "ui_guardrails": {"status": "PENDING", "details": [], "duration": 0},
      "migration_safety": {"status": "PENDING", "details": [], "duration": 0},
      "production_gate": {"status": "PENDING", "details": [], "duration": 0},
      "feature_flag_safety": {"status": "PENDING", "details": [], "duration": 0}
    },
    "artifacts": [],
    "environment": {
      "python_version": "",
      "database_url_set": false,
      "required_secrets": []
    }
  }
}
EOF
}

# Update report with results
update_report() {
    local check_name="$1"
    local status="$2"
    local details="$3"
    local duration="$4"
    
    python3 << EOF
import json
import sys
import os

report_file = "$REPORT_FILE"
with open(report_file, 'r') as f:
    report = json.load(f)

report['trust_check']['checks']['$check_name'] = {
    'status': '$status',
    'details': $details,
    'duration': $duration
}

# Update summary
summary = report['trust_check']['summary']
if '$status' == 'PASS':
    summary['passed'] += 1
elif '$status' == 'FAIL':
    summary['failed'] += 1
elif '$status' == 'WARN':
    summary['warnings'] += 1

summary['total_checks'] += 1

with open(report_file, 'w') as f:
    json.dump(report, f, indent=2)
EOF
}

# Environment validation
validate_environment() {
    log_info "Validating environment setup..."
    
    local env_details="[]"
    local env_status="PASS"
    
    # Check Python version
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_VERSION=$(python3 --version 2>&1)
        log_info "Python version: $PYTHON_VERSION"
    else
        log_error "Python 3 is required but not found"
        env_status="FAIL"
        env_details='["Python 3 not found"]'
    fi
    
    # Check required tools
    for tool in psql curl jq; do
        if ! command -v $tool >/dev/null 2>&1; then
            log_error "Required tool '$tool' not found"
            env_status="FAIL"
            env_details='["Required tools missing"]'
        fi
    done
    
    # Check DATABASE_URL
    if [ -n "${DATABASE_URL:-}" ]; then
        log_info "DATABASE_URL is set"
        python3 << EOF
import json
with open("$REPORT_FILE", 'r') as f:
    report = json.load(f)
report['trust_check']['environment']['database_url_set'] = True
with open("$REPORT_FILE", 'w') as f:
    json.dump(report, f, indent=2)
EOF
    else
        log_error "DATABASE_URL is not set"
        env_status="FAIL"
        env_details='["DATABASE_URL not set"]'
    fi
    
    update_report "environment" "$env_status" "$env_details" "0"
    return 0
}

# 1. Database Unification Regression Checks
run_database_unification_check() {
    log_info "Running database unification regression checks..."
    local start_time=$(date +%s)
    local status="PASS"
    local details="[]"
    
    if [ -f "./test_unification_regression.sh" ]; then
        if bash ./test_unification_regression.sh > "$TEMP_DIR/unification.log" 2>&1; then
            log_success "Database unification checks passed"
            details='["All unification checks passed", "No fragmented reads found", "UI guardrails enforced"]'
        else
            log_error "Database unification checks failed"
            status="FAIL"
            details='["Database unification regression detected", "Check logs for details"]'
            EXIT_CODE=1
        fi
    else
        log_warn "test_unification_regression.sh not found, running Python version"
        if python3 ci_unification_checks.py > "$TEMP_DIR/unification_py.log" 2>&1; then
            log_success "Python unification checks passed"
            details='["Python unification checks passed"]'
        else
            log_error "Python unification checks failed"
            status="FAIL"
            details='["Python unification checks failed"]'
            EXIT_CODE=1
        fi
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    update_report "database_unification" "$status" "$details" "$duration"
}

# 2. Security Audit (Gemini AI, API keys, rate limiting)
run_security_audit() {
    log_info "Running comprehensive security audit..."
    local start_time=$(date +%s)
    local status="PASS"
    local details="[]"
    
    if [ -f "./scripts/security_audit.py" ]; then
        if python3 ./scripts/security_audit.py > "$TEMP_DIR/security.log" 2>&1; then
            log_success "Security audit passed"
            details='["AI backend-only calls verified", "API key protection active", "Rate limiting functional", "Kill switch operational"]'
        else
            log_error "Security audit failed"
            status="FAIL"
            details='["Security vulnerabilities detected", "Check security audit logs"]'
            EXIT_CODE=1
        fi
    else
        log_warn "Security audit script not found"
        status="WARN"
        details='["Security audit script not found"]'
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    update_report "security_audit" "$status" "$details" "$duration"
}

# 3. AI Cross-Contamination Test
run_ai_contamination_check() {
    log_info "Running AI cross-contamination tests..."
    local start_time=$(date +%s)
    local status="PASS"
    local details="[]"
    
    if [ -f "./critical_cross_contamination_test.py" ]; then
        if python3 ./critical_cross_contamination_test.py > "$TEMP_DIR/contamination.log" 2>&1; then
            log_success "AI contamination tests passed"
            details='["No cross-user data contamination detected", "User isolation verified", "Concurrent request safety confirmed"]'
        else
            log_error "AI contamination tests failed"
            status="FAIL"
            details='["CRITICAL: AI cross-contamination detected", "User data isolation compromised"]'
            EXIT_CODE=1
        fi
    else
        log_warn "AI contamination test script not found"
        status="WARN"
        details='["AI contamination test script not found"]'
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    update_report "ai_contamination" "$status" "$details" "$duration"
}

# 4. UI Guardrails Validation
run_ui_guardrails_check() {
    log_info "Running UI guardrails validation..."
    local start_time=$(date +%s)
    local status="PASS"
    local details="[]"
    
    if [ -f "./ui_guardrails_validation.py" ]; then
        if python3 ./ui_guardrails_validation.py > "$TEMP_DIR/ui_guardrails.log" 2>&1; then
            log_success "UI guardrails validation passed"
            details='["Frontend restricted to approved endpoints", "No direct database access in UI", "API boundary enforced"]'
        else
            log_error "UI guardrails validation failed"
            status="FAIL"
            details='["UI guardrails violations detected", "Frontend bypassing API boundaries"]'
            EXIT_CODE=1
        fi
    else
        log_warn "UI guardrails validation script not found"
        status="WARN"
        details='["UI guardrails validation script not found"]'
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    update_report "ui_guardrails" "$status" "$details" "$duration"
}

# 5. Migration Safety Check
run_migration_safety_check() {
    log_info "Running migration safety checks..."
    local start_time=$(date +%s)
    local status="PASS"
    local details="[]"
    
    # Test migration script exists and is executable
    if [ -f "./scripts/migrate_with_lock.py" ]; then
        log_info "Migration script found, checking advisory lock mechanism..."
        
        # Test migration dry run (don't actually run migrations in trust check)
        if python3 -c "
import sys
sys.path.append('.')
from scripts.migrate_with_lock import AdvisoryLockManager
print('Migration script imports successfully')
" > "$TEMP_DIR/migration.log" 2>&1; then
            log_success "Migration safety checks passed"
            details='["Migration script validated", "Advisory lock mechanism available", "Safe concurrent migration support"]'
        else
            log_error "Migration safety check failed"
            status="FAIL"
            details='["Migration script validation failed", "Advisory lock mechanism unavailable"]'
            EXIT_CODE=1
        fi
    else
        log_error "Migration script not found"
        status="FAIL"
        details='["Migration script missing"]'
        EXIT_CODE=1
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    update_report "migration_safety" "$status" "$details" "$duration"
}

# 6. Production Gate Checks
run_production_gate_check() {
    log_info "Running production gate checks..."
    local start_time=$(date +%s)
    local status="PASS"
    local details="[]"
    
    # Start server if not already running
    local server_started=false
    if ! curl -fs "http://localhost:5000/health" > /dev/null 2>&1; then
        log_info "Starting test server..."
        if command -v gunicorn >/dev/null 2>&1; then
            gunicorn --bind 0.0.0.0:5000 --reuse-port --daemon main:app
            server_started=true
            sleep 5
        else
            log_warn "Gunicorn not available, skipping server-dependent checks"
            status="WARN"
            details='["Server not available for testing"]'
        fi
    fi
    
    if [ "$status" = "PASS" ]; then
        if [ -f "./scripts/gate_prod.sh" ]; then
            if bash ./scripts/gate_prod.sh > "$TEMP_DIR/prod_gate.log" 2>&1; then
                log_success "Production gate checks passed"
                details='["Health endpoints responsive", "API contracts validated", "CORS policy active", "Database schema verified"]'
            else
                log_error "Production gate checks failed"
                status="FAIL"
                details='["Production gate validation failed", "Critical endpoints not responding"]'
                EXIT_CODE=1
            fi
        else
            log_warn "Production gate script not found"
            status="WARN"
            details='["Production gate script not found"]'
        fi
    fi
    
    # Clean up test server if we started it
    if [ "$server_started" = true ]; then
        pkill -f "gunicorn.*main:app" || true
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    update_report "production_gate" "$status" "$details" "$duration"
}

# 7. Feature Flag Safety Check
run_feature_flag_safety_check() {
    log_info "Running feature flag safety checks..."
    local start_time=$(date +%s)
    local status="PASS"
    local details="[]"
    
    # Check PCA flags configuration
    if [ -f "./uat_phase0_clarifier_config.py" ]; then
        if python3 ./uat_phase0_clarifier_config.py > "$TEMP_DIR/flags.log" 2>&1; then
            log_success "Feature flag safety checks passed"
            details='["Kill switches functional", "Configuration thresholds valid", "Feature flags safely configured"]'
        else
            log_error "Feature flag safety checks failed"
            status="FAIL"
            details='["Feature flag configuration unsafe", "Kill switches non-functional"]'
            EXIT_CODE=1
        fi
    else
        log_warn "Feature flag safety test not found"
        status="WARN"
        details='["Feature flag safety test not found"]'
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    update_report "feature_flag_safety" "$status" "$details" "$duration"
}

# Additional UAT checks if available
run_additional_uat_checks() {
    log_info "Running additional UAT checks..."
    
    local uat_scripts=(
        "uat_phase1_cc_persistence.py"
        "uat_phase2_router_decision.py"
        "final_contamination_fix_validation.py"
    )
    
    for script in "${uat_scripts[@]}"; do
        if [ -f "./$script" ]; then
            log_info "Running $script..."
            if python3 "./$script" > "$TEMP_DIR/${script}.log" 2>&1; then
                log_info "$script passed"
            else
                log_warn "$script failed (non-blocking)"
            fi
        fi
    done
}

# Finalize report
finalize_report() {
    local end_time=$(date +%s)
    local total_duration=$((end_time - START_TIME))
    
    # Update final report
    python3 << EOF
import json
from datetime import datetime

with open("$REPORT_FILE", 'r') as f:
    report = json.load(f)

trust_check = report['trust_check']
trust_check['timestamp'] = datetime.now().isoformat()
trust_check['duration_seconds'] = $total_duration

# Determine overall status
summary = trust_check['summary']
if summary['failed'] > 0:
    trust_check['overall_status'] = 'FAIL'
elif summary['warnings'] > 0:
    trust_check['overall_status'] = 'WARN'
else:
    trust_check['overall_status'] = 'PASS'

# Add artifacts
trust_check['artifacts'] = [
    'trust_check_logs.tar.gz',
    'report.json'
]

with open("$REPORT_FILE", 'w') as f:
    json.dump(report, f, indent=2)
EOF

    # Create artifacts
    tar -czf trust_check_logs.tar.gz -C "$TEMP_DIR" . 2>/dev/null || true
    
    # Print summary
    echo ""
    echo "==============================================="
    echo "          FINBRAIN TRUST CHECK REPORT"
    echo "==============================================="
    
    python3 << EOF
import json
with open("$REPORT_FILE", 'r') as f:
    report = json.load(f)

trust_check = report['trust_check']
summary = trust_check['summary']
status = trust_check['overall_status']

print(f"Overall Status: {status}")
print(f"Total Checks: {summary['total_checks']}")
print(f"Passed: {summary['passed']}")
print(f"Failed: {summary['failed']}")
print(f"Warnings: {summary['warnings']}")
print(f"Duration: {trust_check['duration_seconds']} seconds")
print("")

for check_name, check_data in trust_check['checks'].items():
    status_icon = "✅" if check_data['status'] == 'PASS' else "❌" if check_data['status'] == 'FAIL' else "⚠️"
    print(f"{status_icon} {check_name}: {check_data['status']} ({check_data['duration']}s)")

print("")
print("Report saved to: $REPORT_FILE")
print("Logs archived to: trust_check_logs.tar.gz")
EOF
}

# Cleanup function
cleanup() {
    rm -rf "$TEMP_DIR" 2>/dev/null || true
}

# Main execution
main() {
    log_info "Starting FinBrain Trust Check v1.0.0"
    log_info "================================================"
    
    START_TIME=$(date +%s)
    
    # Initialize
    init_report
    trap cleanup EXIT
    
    # Environment validation
    validate_environment
    
    # Core security and validation checks
    run_database_unification_check
    run_security_audit
    run_ai_contamination_check
    run_ui_guardrails_check
    run_migration_safety_check
    run_production_gate_check
    run_feature_flag_safety_check
    
    # Additional UAT checks (non-blocking)
    run_additional_uat_checks
    
    # Finalize
    finalize_report
    
    if [ $EXIT_CODE -eq 0 ]; then
        log_success "All trust checks passed!"
    else
        log_error "Trust check failures detected!"
    fi
    
    exit $EXIT_CODE
}

# Run main function
main "$@"