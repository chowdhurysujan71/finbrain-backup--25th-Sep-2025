#!/bin/bash
set -euo pipefail

# rollback.sh - Safe Alembic migration rollback with advisory lock coordination
# Usage: ./scripts/rollback.sh <target_revision>
# Example: ./scripts/rollback.sh 5b555895a514

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Import shared migration configuration
source_migration_config() {
    # Try to get migration constants from Python config
    if command -v python3 &> /dev/null; then
        local config_output
        config_output=$(cd "$PROJECT_DIR" && python3 -c "
from utils.migration_config import get_migration_lock_id, get_migration_backup_dir, get_safe_database_info
import os
print(f'LOCK_ID={get_migration_lock_id()}')
print(f'BACKUP_DIR={get_migration_backup_dir()}')
if 'DATABASE_URL' in os.environ:
    print(f'SAFE_DB_INFO={get_safe_database_info(os.environ["DATABASE_URL"])}')
else:
    print('SAFE_DB_INFO=database@unknown_host')
" 2>/dev/null || echo "LOCK_ID=919191
BACKUP_DIR=$PROJECT_DIR/migration_backups
SAFE_DB_INFO=database@unknown_host")
        
        eval "$config_output"
    else
        # Fallback if Python not available
        LOCK_ID=919191
        BACKUP_DIR="$PROJECT_DIR/migration_backups"
        SAFE_DB_INFO="database@unknown_host"
    fi
}

# Load configuration
source_migration_config

# Configuration constants
MAX_WAIT_SECONDS=300  # 5 minutes maximum wait for lock

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" >&2
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" >&2
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

print_usage() {
    echo "Usage: $0 <target_revision>"
    echo ""
    echo "Safely rollback Alembic migrations using advisory lock coordination."
    echo ""
    echo "Arguments:"
    echo "  target_revision    The Alembic revision to rollback to (e.g., 5b555895a514 or -1)"
    echo ""
    echo "Examples:"
    echo "  $0 5b555895a514     # Rollback to specific revision"
    echo "  $0 -1               # Rollback one migration"
    echo "  $0 -2               # Rollback two migrations"
    echo "  $0 base             # Rollback all migrations"
    echo ""
    echo "Safety Features:"
    echo "  - Uses PostgreSQL advisory locks to prevent concurrent migrations"
    echo "  - Validates target revision exists before rollback"
    echo "  - Creates migration backup log before rollback"
    echo "  - Verifies database connection and schema after rollback"
    echo ""
}

check_dependencies() {
    log_info "Checking dependencies..."
    
    if ! command -v alembic &> /dev/null; then
        log_error "alembic command not found. Please install Alembic."
        exit 1
    fi
    
    if ! command -v psql &> /dev/null; then
        log_error "psql command not found. Please install PostgreSQL client."
        exit 1
    fi
    
    if [[ -z "${DATABASE_URL:-}" ]]; then
        log_error "DATABASE_URL environment variable not set."
        exit 1
    fi
    
    log_success "All dependencies available"
}

get_current_revision() {
    log_info "Getting current migration revision..."
    local current_rev
    local alembic_output
    
    # Get alembic current output
    alembic_output=$(alembic current --verbose 2>/dev/null || echo "")
    
    if [[ -z "$alembic_output" ]]; then
        log_error "Could not get alembic current output"
        exit 1
    fi
    
    # Try multiple parsing approaches to handle different Alembic output formats
    
    # Format 1: "Current revision: <revision_id>"
    current_rev=$(echo "$alembic_output" | grep -i "current revision" | head -1 | sed -E 's/.*current revision[s]*:?[[:space:]]*([a-f0-9]+).*/\1/i' || echo "")
    
    # Format 2: "Current revision(s): <revision_id>"
    if [[ -z "$current_rev" ]]; then
        current_rev=$(echo "$alembic_output" | grep -i "current revision(s)" | head -1 | sed -E 's/.*current revision\(s\)[s]*:?[[:space:]]*([a-f0-9]+).*/\1/i' || echo "")
    fi
    
    # Format 3: Plain revision ID on its own line
    if [[ -z "$current_rev" ]]; then
        current_rev=$(echo "$alembic_output" | grep -E '^[a-f0-9]{12,40}$' | head -1 || echo "")
    fi
    
    # Format 4: Extract any hex string that looks like a revision
    if [[ -z "$current_rev" ]]; then
        current_rev=$(echo "$alembic_output" | grep -oE '[a-f0-9]{12,40}' | head -1 || echo "")
    fi
    
    # Format 5: Handle "None" case (no migrations applied)
    if [[ -z "$current_rev" ]] && echo "$alembic_output" | grep -iq "none"; then
        current_rev="base"
    fi
    
    if [[ -z "$current_rev" ]]; then
        log_error "Could not parse current migration revision from output:"
        log_error "$alembic_output"
        exit 1
    fi
    
    echo "$current_rev"
}

validate_target_revision() {
    local target_rev="$1"
    log_info "Validating target revision: $target_rev"
    
    # Handle relative revisions (-1, -2, etc.)
    if [[ "$target_rev" =~ ^-[0-9]+$ ]]; then
        log_info "Relative revision detected: $target_rev"
        return 0
    fi
    
    # Handle special revisions
    if [[ "$target_rev" == "base" ]]; then
        log_info "Base revision detected"
        return 0
    fi
    
    # Validate specific revision exists
    if ! alembic history | grep -q "$target_rev"; then
        log_error "Target revision '$target_rev' not found in migration history"
        log_info "Available revisions:"
        alembic history --verbose
        exit 1
    fi
    
    log_success "Target revision validated"
}

acquire_advisory_lock() {
    log_info "Acquiring advisory lock (ID: $LOCK_ID)..."
    
    local lock_acquired=false
    local wait_count=0
    
    while [[ $wait_count -lt $MAX_WAIT_SECONDS ]]; do
        if psql "$DATABASE_URL" -t -c "SELECT pg_try_advisory_lock($LOCK_ID);" | grep -q "t"; then
            lock_acquired=true
            break
        fi
        
        log_warning "Migration lock held by another process, waiting... (${wait_count}s/${MAX_WAIT_SECONDS}s)"
        sleep 1
        ((wait_count++))
    done
    
    if [[ "$lock_acquired" == "false" ]]; then
        log_error "Failed to acquire advisory lock after ${MAX_WAIT_SECONDS} seconds"
        log_error "Another migration process may be running. Please try again later."
        exit 1
    fi
    
    log_success "Advisory lock acquired"
}

release_advisory_lock() {
    log_info "Releasing advisory lock..."
    psql "$DATABASE_URL" -t -c "SELECT pg_advisory_unlock($LOCK_ID);" >/dev/null
    log_success "Advisory lock released"
}

create_backup_log() {
    local current_rev="$1"
    local target_rev="$2"
    
    log_info "Creating migration backup log..."
    mkdir -p "$BACKUP_DIR"
    
    local backup_file="$BACKUP_DIR/rollback_$(date +%Y%m%d_%H%M%S).log"
    
    # SECURITY: Create backup log with only safe, non-sensitive information
    cat > "$backup_file" <<EOF
# Migration Rollback Log
# Generated: $(date)
# Current Revision: $current_rev
# Target Revision: $target_rev
# Database: $SAFE_DB_INFO
# User: $(whoami)
# Host: $(hostname)
# Script Version: $(basename "$0")
# Project: $(basename "$PROJECT_DIR")

## Pre-Rollback State
$(alembic current --verbose 2>/dev/null || echo "Could not get current state")

## Migration History
$(alembic history --verbose 2>/dev/null || echo "Could not get migration history")

## Schema State Before Rollback
EOF
    
    # Add schema dump if possible (without connection string in output)
    if command -v pg_dump &> /dev/null && [[ -n "${DATABASE_URL:-}" ]]; then
        log_info "Adding schema dump to backup log..."
        {
            echo "-- Schema dump generated at $(date)"
            echo "-- Database: $SAFE_DB_INFO"
            pg_dump "$DATABASE_URL" --schema-only 2>/dev/null | grep -v "^-- Dumped from database version" | grep -v "^-- Dumped by pg_dump version"
        } >> "$backup_file" || {
            echo "-- Schema dump failed at $(date)" >> "$backup_file"
        }
    else
        echo "-- Schema dump not available (pg_dump not found or DATABASE_URL not set)" >> "$backup_file"
    fi
    
    log_success "Backup log created: $backup_file"
}

perform_rollback() {
    local target_rev="$1"
    
    log_info "Starting migration rollback to: $target_rev"
    log_warning "This operation will modify the database schema!"
    
    # Show what will be rolled back
    log_info "Rollback plan:"
    alembic downgrade "$target_rev" --sql 2>/dev/null || log_warning "Could not generate rollback SQL preview"
    
    # Perform the actual rollback
    log_info "Executing rollback..."
    if alembic downgrade "$target_rev"; then
        log_success "Migration rollback completed successfully"
    else
        log_error "Migration rollback failed!"
        log_error "Database may be in an inconsistent state"
        log_error "Check the backup log and consider manual recovery"
        exit 1
    fi
}

verify_rollback() {
    log_info "Verifying rollback success..."
    
    # Check database connection
    if ! psql "$DATABASE_URL" -c "SELECT 1;" >/dev/null 2>&1; then
        log_error "Database connection failed after rollback"
        exit 1
    fi
    
    # Check current revision
    local new_rev
    new_rev=$(get_current_revision)
    log_info "Current revision after rollback: $new_rev"
    
    # Verify schema integrity
    if ! psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM information_schema.tables;" >/dev/null 2>&1; then
        log_error "Schema integrity check failed after rollback"
        exit 1
    fi
    
    log_success "Rollback verification completed"
}

cleanup_on_exit() {
    local exit_code=$?
    
    # Always try to release the lock
    if command -v psql &> /dev/null && [[ -n "${DATABASE_URL:-}" ]]; then
        psql "$DATABASE_URL" -t -c "SELECT pg_advisory_unlock($LOCK_ID);" >/dev/null 2>&1 || true
    fi
    
    if [[ $exit_code -ne 0 ]]; then
        log_error "Rollback script failed with exit code: $exit_code"
        log_error "Check the backup logs in: $BACKUP_DIR"
    fi
    
    exit $exit_code
}

main() {
    # Set up cleanup on exit
    trap cleanup_on_exit EXIT
    
    # Check arguments
    if [[ $# -ne 1 ]]; then
        log_error "Invalid number of arguments"
        print_usage
        exit 1
    fi
    
    local target_revision="$1"
    
    # Show help if requested
    if [[ "$target_revision" == "-h" || "$target_revision" == "--help" ]]; then
        print_usage
        exit 0
    fi
    
    log_info "=== FinBrain Migration Rollback Script ==="
    log_info "Target revision: $target_revision"
    log_info "Timestamp: $(date)"
    log_info "Database: $SAFE_DB_INFO"
    
    # Validation and setup
    check_dependencies
    local current_revision
    current_revision=$(get_current_revision)
    log_info "Current revision: $current_revision"
    
    validate_target_revision "$target_revision"
    
    # Safety checks
    if [[ "$current_revision" == "$target_revision" ]]; then
        log_warning "Already at target revision: $target_revision"
        log_info "No rollback needed"
        exit 0
    fi
    
    # Acquire lock and perform rollback
    acquire_advisory_lock
    create_backup_log "$current_revision" "$target_revision"
    perform_rollback "$target_revision"
    verify_rollback
    
    log_success "=== Migration rollback completed successfully ==="
    log_info "Backup logs available in: $BACKUP_DIR"
    log_info "Current revision: $(get_current_revision)"
}

# Run main function with all arguments
main "$@"