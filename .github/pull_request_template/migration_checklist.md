# Migration Safety Checklist

## Migration Requirements
This PR contains database migration changes that require safety validation.

### ✅ Migration Downgrade Requirements
- [ ] **Downgrade Path**: Migration includes a tested `downgrade()` function that safely reverses all changes
- [ ] **Data Safety**: Downgrade preserves all existing data without loss or corruption
- [ ] **Rollback Testing**: Migration has been tested in both upgrade → downgrade → upgrade cycle
- [ ] **Dependencies**: All migration dependencies are properly handled in downgrade sequence

### ✅ Irreversible Migration Requirements (if applicable)
- [ ] **Explicit Marking**: Migration is clearly marked as irreversible with `raise NotImplementedError("Irreversible migration")`
- [ ] **Manual Recovery Plan**: RECOVERY.md document created with detailed manual rollback steps
- [ ] **Data Backup Plan**: Manual backup and restore procedures documented
- [ ] **Risk Assessment**: Business impact of irreversibility documented and approved

### ✅ Change Documentation
- [ ] **CHANGELOG Entry**: Auto-generated or manual CHANGELOG entry includes revision ID, summary, author, and date
- [ ] **Migration Summary**: Clear description of schema changes and business rationale
- [ ] **Breaking Changes**: Any breaking changes are clearly documented

### ✅ Testing Requirements
- [ ] **Staging Verification**: Migration tested on staging environment with production-like data
- [ ] **Performance Impact**: Migration performance measured and acceptable for production scale
- [ ] **Advisory Lock**: Migration uses advisory lock coordination for multi-instance deployments
- [ ] **Concurrent Safety**: If creating indexes, uses CREATE INDEX CONCURRENTLY patterns

### ✅ Production Readiness
- [ ] **Zero Downtime**: Migration designed for zero-downtime deployment
- [ ] **Rollback Strategy**: Clear rollback plan documented for production deployment
- [ ] **Monitor Plan**: Post-deployment monitoring strategy defined

## Migration Type
Select the type of migration:
- [ ] **Schema Addition** (new tables, columns, indexes)
- [ ] **Schema Modification** (alter columns, constraints)
- [ ] **Data Migration** (data transformation, cleanup)
- [ ] **Index Operations** (concurrent index creation/removal)
- [ ] **Irreversible Change** (data deletion, schema removal)

## Reviewer Checklist
- [ ] **Downgrade Verified**: Reviewer has validated the downgrade path or approved irreversible designation
- [ ] **Documentation Review**: CHANGELOG and RECOVERY.md (if applicable) are complete and accurate
- [ ] **Safety Approval**: Migration safety measures meet production requirements

---

**Migration Safety Contract**: Every migration must either provide a safe downgrade path OR include comprehensive manual recovery documentation. No exceptions.