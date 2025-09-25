#!/bin/bash
set -e

# CI Static Checks - Evidence-Driven Release Assurance
# Generates artifacts for type checking and linting with zero-error enforcement

echo "🔍 Starting CI Static Checks - Evidence Generation"
echo "=================================================="

# Create artifacts directory
mkdir -p artifacts/static

# Log Python version
echo "📋 Python Version Check"
python --version | tee artifacts/static/python_version.txt

# Log dependency versions
echo -e "\n📦 Dependency Versions"
pip show mypy ruff 2>/dev/null | sed -n '1,20p' | tee artifacts/static/dependency_versions.txt || echo "Dependencies not installed"

# Install dev dependencies if missing
echo -e "\n📥 Installing dev dependencies..."
pip install mypy ruff pytest pytest-cov --quiet

# Run mypy with strict checking (excluding quarantined paths)
echo -e "\n🔎 Running MyPy Type Checking (strict mode, production paths only)"
echo "Command: mypy --version && mypy . --strict --ignore-missing-imports --exclude='(_quarantine|_attic)'"
mypy --version | tee artifacts/static/mypy_version.txt
# Capture mypy output and check content for errors (excluding quarantined/attic paths)
set +e
mypy . --strict --ignore-missing-imports --exclude='(_quarantine|_attic|migrations)' 2>&1 | tee artifacts/static/mypy_results.txt
MYPY_EXIT=$?
set -e
# Parse output to detect any errors (regardless of exit code) - handle both singular/plural
if grep -E -q "Found [0-9]+ errors?" artifacts/static/mypy_results.txt; then
    ERROR_COUNT=$(grep -E "Found [0-9]+ errors?" artifacts/static/mypy_results.txt | sed 's/Found \([0-9]*\) error.*/\1/')
    echo "DEBUG: MYPY_EXIT=$MYPY_EXIT, but found $ERROR_COUNT errors in output"
    echo "❌ MyPy: FAIL ($ERROR_COUNT type errors found in production code)"
    MYPY_REAL_STATUS=1
else
    echo "DEBUG: MYPY_EXIT=$MYPY_EXIT, no errors found in output"
    echo "✅ MyPy: PASS (0 errors in production code)"
    MYPY_REAL_STATUS=0
fi

# Run ruff linting with output parsing for true error detection
echo -e "\n🧹 Running Ruff Linting"
echo "Command: ruff --version && ruff check ."
ruff --version | tee artifacts/static/ruff_version.txt
# Capture ruff output and check content for errors (ignore exit code)
set +e
ruff check . 2>&1 | tee artifacts/static/ruff_results.txt
RUFF_EXIT=$?
set -e
# Parse output to detect any errors (regardless of exit code)
if grep -q "Found [0-9]* errors" artifacts/static/ruff_results.txt; then
    ERROR_COUNT=$(grep "Found [0-9]* errors" artifacts/static/ruff_results.txt | sed 's/Found \([0-9]*\) errors.*/\1/')
    echo "DEBUG: RUFF_EXIT=$RUFF_EXIT, but found $ERROR_COUNT errors in output"
    echo "❌ Ruff: FAIL ($ERROR_COUNT lint errors found)"
    RUFF_REAL_STATUS=1
else
    echo "DEBUG: RUFF_EXIT=$RUFF_EXIT, no errors found in output"  
    echo "✅ Ruff: PASS (0 lint errors)"
    RUFF_REAL_STATUS=0
fi

# Generate summary report
echo -e "\n📊 CI Static Checks Summary" | tee artifacts/static/summary.txt
echo "=============================" | tee -a artifacts/static/summary.txt
echo "MyPy Status: $([ $MYPY_REAL_STATUS -eq 0 ] && echo "PASS" || echo "FAIL")" | tee -a artifacts/static/summary.txt
echo "Ruff Status: $([ $RUFF_REAL_STATUS -eq 0 ] && echo "PASS" || echo "FAIL")" | tee -a artifacts/static/summary.txt
echo "Overall: $([ $MYPY_REAL_STATUS -eq 0 ] && [ $RUFF_REAL_STATUS -eq 0 ] && echo "PASS ✅" || echo "FAIL ❌")" | tee -a artifacts/static/summary.txt

# Exit with failure if any check failed (enforces build gates)
OVERALL_EXIT=$((MYPY_REAL_STATUS + RUFF_REAL_STATUS))
if [ $OVERALL_EXIT -eq 0 ]; then
    echo -e "\n🎉 All static checks passed! Build can proceed."
else
    echo -e "\n🚫 Static checks failed! Build must be blocked."
fi

echo -e "\n📁 Artifacts generated in artifacts/static/"
ls -la artifacts/static/

exit $OVERALL_EXIT