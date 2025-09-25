#!/bin/bash
# Nightly A1-A5 Artifact Generation
# Run this via cron: 0 2 * * * /path/to/nightly_artifacts.sh

set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE_DIR="release_artifacts/nightly"

mkdir -p "$ARCHIVE_DIR"

echo "=== NIGHTLY ARTIFACT GENERATION $TIMESTAMP ==="

# A1: CI/lint statistics
echo "Generating A1..."
ruff check . --select F821,E722 --exclude=_quarantine --statistics > "$ARCHIVE_DIR/A1_$TIMESTAMP.txt" 2>&1

# A2: Core flows test
echo "Generating A2..."
{
    echo "=== Health Flow ==="
    curl -s -w 'Status: %{http_code}, Time: %{time_total}s' http://localhost:5000/health -o /dev/null || echo "FAILED"
    echo ""
    echo "=== Main Route ==="
    curl -s -w 'Status: %{http_code}, Time: %{time_total}s' http://localhost:5000/ -o /dev/null || echo "FAILED"
    echo ""
    echo "=== Backend API ==="
    curl -s -w 'Status: %{http_code}, Time: %{time_total}s' http://localhost:5000/api/backend/version -o /dev/null || echo "FAILED"
    echo ""
} > "$ARCHIVE_DIR/A2_$TIMESTAMP.txt"

# A3: Router logs (last 100 requests)
echo "Generating A3..."
tail -100 /var/log/finbrain.log 2>/dev/null | grep -E 'request_id|→' > "$ARCHIVE_DIR/A3_$TIMESTAMP.txt" || echo "No logs found" > "$ARCHIVE_DIR/A3_$TIMESTAMP.txt"

# A4: Code audit
echo "Generating A4..."
{
    echo "=== Forbidden Pattern Scan ==="
    grep -r "save_expense\|upsert_expense_idempotent" handlers/ routes/ models.py app.py main.py 2>/dev/null | wc -l || echo "0"
    echo "forbidden patterns found"
} > "$ARCHIVE_DIR/A4_$TIMESTAMP.txt"

# A5: Cache headers
echo "Generating A5..."
{
    echo "=== Main Route Cache ==="
    curl -s -I http://localhost:5000/ | grep -i cache || echo "No cache headers"
    echo "=== API Route Cache ==="
    curl -s -I http://localhost:5000/api/backend/version | grep -i cache || echo "No cache headers"
} > "$ARCHIVE_DIR/A5_$TIMESTAMP.txt"

# Generate summary
{
    echo "**Nightly Build Report $TIMESTAMP**"
    echo ""
    echo "**A1 (Lint):** $(head -1 "$ARCHIVE_DIR/A1_$TIMESTAMP.txt" | grep -o '[0-9]* error' || echo '0 errors')"
    echo "**A2 (Flows):** $(grep -c 'Status: 200' "$ARCHIVE_DIR/A2_$TIMESTAMP.txt" || echo '0')/4 operational"
    echo "**A3 (Router):** $(wc -l < "$ARCHIVE_DIR/A3_$TIMESTAMP.txt") request mappings found"
    echo "**A4 (Audit):** $(head -1 "$ARCHIVE_DIR/A4_$TIMESTAMP.txt" | cut -d' ' -f1) forbidden patterns"
    echo "**A5 (Cache):** $(grep -c 'no-store' "$ARCHIVE_DIR/A5_$TIMESTAMP.txt" || echo '0') routes with no-store"
} > "$ARCHIVE_DIR/SUMMARY_$TIMESTAMP.md"

# Cleanup old artifacts (keep last 30 days)
find "$ARCHIVE_DIR" -name "*.txt" -mtime +30 -delete 2>/dev/null || true
find "$ARCHIVE_DIR" -name "*.md" -mtime +30 -delete 2>/dev/null || true

echo "✅ Nightly artifacts generated: $ARCHIVE_DIR/"
echo "Summary: $ARCHIVE_DIR/SUMMARY_$TIMESTAMP.md"
