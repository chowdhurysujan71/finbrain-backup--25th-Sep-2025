#!/bin/bash

# Idempotent database migration script for FinBrain
# This script can be run multiple times safely

set -e  # Exit on any error

echo "=== FinBrain Database Migration Script ==="
echo "Starting database migration process..."

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "Error: DATABASE_URL environment variable is required"
    exit 1
fi

echo "✓ DATABASE_URL is set"

# Show current migration heads
echo ""
echo "=== Current Migration Heads ==="
alembic show heads

# Show current revision
echo ""
echo "=== Current Database Revision ==="
alembic current

# Apply any pending migrations
echo ""
echo "=== Applying Migrations ==="
alembic upgrade head

echo ""
echo "=== Migration Complete ==="
echo "✓ Database is now up to date with latest migrations"

# Show final state
echo ""
echo "=== Final State ==="
alembic current