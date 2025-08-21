# GLOBAL DATABASE WRITE PATH AUDIT

**Audit Date:** 2025-08-21  
**Scope:** All database write operations across the FinBrain repository  
**Focus:** Identifying bypass paths that skip canonical helpers and required field validation

## TABLES IDENTIFIED

1. **expenses** - Main expense logging table  
2. **users** - User profile and tracking table  
3. **monthly_summaries** - Monthly analytics aggregation table  
4. **rate_limits** - Rate limiting tracking table  

## WRITE PATH ANALYSIS

### EXPENSES TABLE

| File | Line | Function | Helper Used | Required Fields Set | Risk |
|------|------|----------|-------------|-------------------|------|
| utils/db.py | 68 | save_expense() | ✅ CANONICAL | ✅ month, date, time set | LOW |
| handlers/logger.py | 31 | handle_log() | ❌ BYPASS | ✅ FIXED (month guard added) | LOW |
| archive/test_conversational_ai.py | 66 | setup_test_user() | ❌ BYPASS | ✅ month field set | MEDIUM |
| archive/background_processor_corrupted.py | 272 | _process_job_safe() | ❌ BYPASS | ⚠️ UNKNOWN | HIGH |

**Canonical Helper:** `utils/db.py:save_expense()` - Properly sets all required fields  
**Active Bypasses:** 1 production path (handlers/), multiple test/archive paths  

### USERS TABLE

| File | Line | Function | Helper Used | Required Fields Set | Risk |
|------|------|----------|-------------|-------------------|------|
| utils/db.py | 24 | get_or_create_user() | ✅ CANONICAL | ✅ user_id_hash, platform set | LOW |
| archive/background_processor_corrupted.py | 259 | _process_job_safe() | ❌ BYPASS | ⚠️ UNKNOWN | HIGH |
| archive/test_conversational_ai.py | 43 | setup_test_user() | ❌ BYPASS | ✅ user_id_hash set | MEDIUM |

**Canonical Helper:** `utils/db.py:get_or_create_user()` - Properly validates and sets required fields  
**Active Bypasses:** 1 production path (archived corrupted processor), multiple test paths  

### MONTHLY_SUMMARIES TABLE

| File | Line | Function | Helper Used | Required Fields Set | Risk |
|------|------|----------|-------------|-------------------|------|
| utils/db.py | 97 | save_expense() | ✅ CANONICAL | ✅ user_id_hash, month set | LOW |

**Canonical Helper:** Within `utils/db.py:save_expense()` - Proper field validation  
**Active Bypasses:** 0 found  

### RATE_LIMITS TABLE

| File | Line | Function | Helper Used | Required Fields Set | Risk |
|------|------|----------|-------------|-------------------|------|
| utils/rate_limiter.py | 30 | check_rate_limit() | ✅ CANONICAL | ✅ user_id_hash, platform set | LOW |

**Canonical Helper:** `utils/rate_limiter.py:check_rate_limit()` - Proper field validation and creation  
**Active Bypasses:** 0 found  

## RAW SQL OPERATIONS

| File | Line | Operation | Table | Status | Risk |
|------|------|-----------|-------|--------|------|
| archive/migrate_identity.py | 210 | UPDATE users | users | ARCHIVED | LOW |
| archive/migrate_identity.py | 190 | DELETE FROM expenses | expenses | ARCHIVED | LOW |
| archive/migrate_identity.py | 227 | DELETE FROM users | users | ARCHIVED | LOW |
| scripts/check_db_indexes.py | 50 | CREATE INDEX | expenses | MAINTENANCE | LOW |
| scripts/check_db_indexes.py | 57 | CREATE INDEX | users | MAINTENANCE | LOW |

## CRITICAL FINDINGS

### ✅ RESOLVED ISSUES
1. **handlers/logger.py (Line 31):** Fixed missing month field validation for Expense creation

### ⚠️ HIGH RISK ACTIVE BYPASSES
1. **archive/background_processor_corrupted.py:** Contains direct User and Expense creation bypassing canonical helpers

### 🔍 MEDIUM RISK BYPASSES
1. **Test files:** Multiple test files bypass canonical helpers but have proper field validation
2. **Archive paths:** Several archived files contain bypasses that may be referenced

## SECURITY RECOMMENDATIONS

1. **Immediate:** Audit `archive/background_processor_corrupted.py` for active usage
2. **High Priority:** Establish linting rules to prevent direct model constructors outside utils/db.py
3. **Long Term:** Implement model-level validation to catch missing required fields at runtime

## CALL GRAPH ANALYSIS

**Primary Entry Points:**
1. Webhook → production_router → handlers → DB
2. Webhook → production_router → utils/expense → utils/db (CANONICAL)
3. Background processor → Direct DB (BYPASS RISK)

**Safe Path:** Webhook → Router → utils/expense.process_expense_message() → utils/db.save_expense()  
**Risk Path:** Any handler or processor directly instantiating models

## RISK ASSESSMENT BY TABLE

- **expenses:** LOW RISK (canonical helper dominant, critical bypass fixed)
- **users:** MEDIUM RISK (canonical helper present, some bypasses in archived code)  
- **monthly_summaries:** LOW RISK (only canonical path found)
- **rate_limits:** LOW RISK (canonical helper found, no bypasses detected)

**Overall Risk Level:** LOW-MEDIUM (due to archived bypass paths only)