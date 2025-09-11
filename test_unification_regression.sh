#!/bin/bash
# Simple bash version of unification checks for CI/CD pipelines
# Fails build if database unification is violated

set -e  # Exit on any error

echo "🚀 Database Unification Regression Tests"
echo "========================================"

# Check if required tools are available
command -v psql >/dev/null 2>&1 || { echo "❌ psql required but not installed."; exit 1; }
command -v grep >/dev/null 2>&1 || { echo "❌ grep required but not installed."; exit 1; }

# A) Code pattern checks
echo ""
echo "📁 A) Code Pattern Checks"

echo "🔍 Checking for forbidden inference_snapshots reads..."
if grep -r "FROM inference_snapshots" --include="*.py" handlers/ routes/ pwa_ui.py backend_assistant.py 2>/dev/null; then
    echo "❌ FAIL: Found forbidden inference_snapshots reads in user-facing code"
    exit 1
else
    echo "✅ PASS: No inference_snapshots reads in user-facing code"
fi

echo "🔍 Checking for forbidden monthly_summaries reads..."
if grep -r "FROM monthly_summaries" --include="*.py" handlers/ routes/ pwa_ui.py backend_assistant.py 2>/dev/null; then
    echo "❌ FAIL: Found forbidden monthly_summaries reads in user-facing code"
    exit 1
else
    echo "✅ PASS: No monthly_summaries reads in user-facing code"
fi

# C) UI Guardrail checks
echo ""
echo "🛡️  C) UI Guardrail Checks"

echo "🔍 Checking for direct database access in UI components..."
if grep -r "db\.session\|execute.*text\|\.fetchall\|\.first()" --include="*.py" pwa_ui.py routes/pwa*.py 2>/dev/null; then
    echo "❌ FAIL: Found direct database access in UI components (must use API endpoints only)"
    exit 1
else
    echo "✅ PASS: No direct database access in UI components"
fi

echo "🔍 Checking for prepared statement calls outside backend..."
if grep -r "EXECUTE.*recent_expenses\|EXECUTE.*weekly_totals" --include="*.py" --exclude="backend_assistant.py" --exclude="routes_backend_assistant.py" handlers/ routes/ pwa_ui.py 2>/dev/null; then
    echo "❌ FAIL: Found prepared statement calls outside backend layer"
    exit 1
else
    echo "✅ PASS: Prepared statements only used in backend layer"
fi

# B) Database state checks
echo ""
echo "🗃️  B) Database State Checks"

echo "🔍 Checking for orphan LOG_EXPENSE snapshots..."
ORPHANS=$(psql "$DATABASE_URL" -t -c "
    SELECT COUNT(*) FROM inference_snapshots s
    LEFT JOIN expenses e ON e.mid = s.cc_id
    WHERE e.id IS NULL AND s.intent = 'LOG_EXPENSE'
" | tr -d ' ')

if [ "$ORPHANS" -gt 0 ]; then
    echo "❌ FAIL: Found $ORPHANS orphan LOG_EXPENSE snapshots"
    exit 1
else
    echo "✅ PASS: No orphan LOG_EXPENSE snapshots ($ORPHANS found)"
fi

echo "🔍 Checking for duplicate idempotency keys..."
DUPLICATES=$(psql "$DATABASE_URL" -t -c "
    SELECT COUNT(*) FROM (
      SELECT idempotency_key FROM expenses GROUP BY 1 HAVING COUNT(*)>1
    ) d
" | tr -d ' ')

if [ "$DUPLICATES" -gt 0 ]; then
    echo "❌ FAIL: Found $DUPLICATES duplicate idempotency keys"
    exit 1
else
    echo "✅ PASS: No duplicate idempotency keys ($DUPLICATES found)"
fi

# D) UI Guardrails Check  
echo ""
echo "🔒 D) UI Guardrails - Frontend restricted to approved endpoints"

echo "🔍 Checking UI guardrails compliance..."
if python3 ui_guardrails_validation.py; then
    echo "✅ PASS: UI guardrails enforced - frontend uses only approved endpoints"
else
    echo "❌ FAIL: UI guardrails violated - frontend bypassing approved endpoints"
    exit 1
fi

# E) Permission checks
echo ""
echo "🔒 E) Permission Checks"

echo "🔍 Checking for write permissions on legacy tables..."
WRITE_PERMS=$(psql "$DATABASE_URL" -t -c "
    SELECT COUNT(*) FROM information_schema.role_table_grants
    WHERE grantee = 'neondb_owner' 
    AND table_name IN ('inference_snapshots', 'transactions_effective', 'messages', 'expense_edits', 'ai_request_audit', 'user_corrections')
    AND privilege_type IN ('INSERT','UPDATE','DELETE')
" | tr -d ' ')

if [ "$WRITE_PERMS" -gt 0 ]; then
    echo "❌ FAIL: Found $WRITE_PERMS write permissions on legacy tables"
    exit 1
else
    echo "✅ PASS: No write permissions on legacy tables ($WRITE_PERMS found)"
fi

# F) Verify unified read path
echo "🔍 Verifying expenses table accessibility..."
EXPENSE_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM expenses" | tr -d ' ')

if [ "$EXPENSE_COUNT" -gt 0 ]; then
    echo "✅ PASS: Expenses table accessible with $EXPENSE_COUNT records"
else
    echo "❌ FAIL: Expenses table has no records - unified read path may be broken"
    exit 1
fi

echo ""
echo "🎉 ALL CHECKS PASSED - Database unification intact"
echo "✅ Build can proceed safely"