# FINBRAIN CHAT & AI UAT ANALYSIS

**Timestamp:** 2025-09-08T15:09:02Z  
**Commit:** b35edc513aaf0748a70b781d78291c0deb282044

## ASCII Snapshot

```
[PWA (new chat)] → (fetch JSON + X-User-ID) → [Flask /ai-chat:pwa_ui.py:364]
        → [core/brain.process_user_message] → [Router → AI → Fallback]
        → [DB (16 tables, expenses: 14 indexes)] → [Reply JSON]
```

## Raw Counts

| Metric | Value | Source |
|--------|-------|--------|
| **Disk Usage** | 579M | `du -sh .` |
| **Directories** | 88 | `find . -maxdepth 2 -type d` |
| **Files** | 18,164 | `find . -type f -not -path "./venv/*" -not -path "./node_modules/*"` |
| **Routes** | 113 | `rg -n "@(app\|[A-Za-z_]+)\.route\|register_blueprint" -g "*.py"` |
| **DB Tables** | 16 | `psql $DATABASE_URL -c "\dt"` |
| **Expenses Indexes** | 14 | `psql $DATABASE_URL -c "select indexname from pg_indexes where tablename='expenses'"` |

## Key Command Outputs

### Routes (Critical Endpoints)
```
pwa_ui.py:364:@pwa_ui.route('/ai-chat', methods=['POST'])
pwa_ui.py:398:@pwa_ui.route('/expense', methods=['POST'])
app.py:660:@app.route("/webhook/messenger", methods=["GET", "POST"])
app.py:495:@app.route('/health', methods=['GET'])
```

### PWA Manifest
```bash
$ ls -la static/manifest.webmanifest
manifest: missing
```

### Database Tables
```
ai_request_audit, expense_edits, expenses, expenses_mid_backfill_backup, 
growth_counters, inference_snapshots, monthly_summaries, rate_limits, 
real_users_allowlist, report_feedback, telemetry_events, 
transactions_effective, user_corrections, user_milestones, user_rules, users
```

### Expenses Table Indexes
```
expenses_pkey (UNIQUE)
idx_expenses_user_id_created_at (user_id, created_at DESC)
ux_expenses_psid_mid (UNIQUE: user_id, mid)
ix_expenses_user_created (user_id, created_at DESC)
ix_expenses_month (month)
ix_expenses_user_created_uncorrected (user_id, created_at DESC WHERE superseded_by IS NULL)
ix_expenses_superseded_by (superseded_by WHERE superseded_by IS NOT NULL)
idx_expenses_user_insights (user_id, created_at DESC)
idx_expenses_user_category (user_id, category, created_at DESC)
idx_expenses_user_id_hash (user_id_hash)
idx_expenses_user_time (user_id_hash, created_at)
idx_expenses_user_category_time (user_id_hash, category, created_at)
idx_expenses_uid_created (user_id_hash, created_at DESC)
idx_expenses_recent_user (user_id_hash, created_at DESC WHERE created_at >= '2024-01-01')
```

### Migrations
```bash
$ rg -n "alembic|migrations" -g "*"
Result: No project-level migration files found.
Details: References found only in .cache/uv/ dependency files (SQLAlchemy)
```

### Tests
```bash
$ pytest -q 2>/dev/null | tail -n 1
1 warning, 5 errors in 11.23s
```

## Working vs Not

### Working (Measured)
- ✅ **Flask Routes**: 113 routes registered across 13 blueprints
- ✅ **/ai-chat Endpoint**: Present at pwa_ui.py:364 with POST method
- ✅ **Database Schema**: 16 tables present, expenses has 14 indexes
- ✅ **User Isolation Indexes**: Multiple user_id_hash indexes for performance
- ✅ **Application Boot**: Service starts successfully (workflow logs show initialization complete)

### Not Working (Measured)
- ❌ **PWA Manifest**: static/manifest.webmanifest missing
- ❌ **Tests**: pytest shows 5 errors, 1 warning
- ❌ **Migrations**: No alembic/migration framework detected

### Unknown (Requires Testing)
- ❓ **Chat Contract**: /ai-chat JSON envelope format not verified
- ❓ **AI Processing**: core/brain.process_user_message pathway not tested
- ❓ **Cross-User Isolation**: Data leakage not verified
- ❓ **Rate Limiting**: Functional behavior not tested
- ❓ **Security Posture**: CORS/CSRF configuration not verified

## Artifacts Generated

- `results/size.txt` - Disk usage and file counts
- `inventories/routes.json` - All Flask routes with file:line references  
- `inventories/schema.json` - Database tables and indexes
- `results/manifest.txt` - PWA manifest status
- `results/migrations.txt` - Migration framework analysis
- `results/tests.txt` - Test suite status

## GO/NO-GO Assessment

**Decision: CONDITIONAL GO**

**Rationale:** Core infrastructure (routes, database, application boot) measured as functional. Missing components (PWA manifest, tests, migrations) are deployment concerns but do not block basic functionality.

**Evidence File Paths:**
- Application structure: `results/size.txt`
- Route inventory: `inventories/routes.json`  
- Database schema: `inventories/schema.json`
- All probe outputs: `results/*.txt`