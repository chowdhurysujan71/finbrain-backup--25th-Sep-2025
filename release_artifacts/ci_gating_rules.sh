#!/bin/bash
# CI Pipeline Gating Rules
# Block builds that violate A1 critical rules

echo "=== A1 LINT GATING CHECK ==="

# Critical blockers (must be zero to pass)
F821_COUNT=$(ruff check . --select F821 --exclude=_quarantine --output-format=concise 2>/dev/null | grep -c ":" || echo "0")
E722_COUNT=$(ruff check . --select E722 --exclude=_quarantine --output-format=concise 2>/dev/null | grep -c ":" || echo "0")
E999_COUNT=$(ruff check . --select E999 --exclude=_quarantine --output-format=concise 2>/dev/null | grep -c ":" || echo "0")
B_COUNT=$(ruff check . --select B --exclude=_quarantine --output-format=concise 2>/dev/null | grep -c ":" || echo "0")
S_COUNT=$(ruff check . --select S --exclude=_quarantine --output-format=concise 2>/dev/null | grep -c ":" || echo "0")

echo "Critical violations: F821=$F821_COUNT, E722=$E722_COUNT, E999=$E999_COUNT, B=$B_COUNT, S=$S_COUNT"

# Gate check
TOTAL_CRITICAL=$((F821_COUNT + E722_COUNT + E999_COUNT + B_COUNT + S_COUNT))

if [ $TOTAL_CRITICAL -gt 0 ]; then
    echo "❌ BUILD BLOCKED: $TOTAL_CRITICAL critical violations found"
    echo "Fix these violations before deployment:"
    ruff check . --select F821,E722,E999,B,S --exclude=_quarantine
    exit 1
fi

echo "✅ A1 GATE PASSED: Zero critical violations"

# Ratcheting on diffs (warn but don't block)
echo "=== DIFF RATCHETING CHECK ==="
if command -v git >/dev/null 2>&1; then
    DIFF_VIOLATIONS=$(git diff HEAD~1 --name-only | xargs ruff check --select E,W --exclude=_quarantine 2>/dev/null | wc -l || echo "0")
    if [ $DIFF_VIOLATIONS -gt 0 ]; then
        echo "⚠️ WARNING: $DIFF_VIOLATIONS style violations in diff (not blocking)"
    else
        echo "✅ DIFF CLEAN: No new style violations"
    fi
fi

