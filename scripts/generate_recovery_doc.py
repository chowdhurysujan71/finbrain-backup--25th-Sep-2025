#!/usr/bin/env python3
"""
generate_recovery_doc.py - Generate RECOVERY.md for irreversible migrations

This script creates comprehensive recovery documentation for migrations marked
as irreversible, providing manual rollback steps and data recovery procedures.

Usage:
    python scripts/generate_recovery_doc.py <revision_id>
    python scripts/generate_recovery_doc.py --check-all

Examples:
    python scripts/generate_recovery_doc.py cf6afe03b206
    python scripts/generate_recovery_doc.py --check-all
"""

import os
import sys
import argparse
import re
import datetime
from typing import Dict, List, Optional, Tuple, Set
from pathlib import Path
import subprocess
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IrreversibleMigration:
    """Container for irreversible migration info and recovery procedures"""
    
    def __init__(self, revision_id: str, filename: str, summary: str, 
                 create_date: str, down_revision: Optional[str] = None):
        self.revision_id = revision_id
        self.filename = filename
        self.summary = summary
        self.create_date = create_date
        self.down_revision = down_revision
        self.recovery_steps: List[str] = []
        self.backup_requirements: List[str] = []
        self.risk_level = "HIGH"
        self.estimated_recovery_time = "Unknown"
        
    def analyze_migration_risks(self, migration_content: str):
        """Analyze migration content to determine risks and recovery procedures"""
        content_lower = migration_content.lower()
        
        # Detect dangerous operations
        if 'drop table' in content_lower or 'drop column' in content_lower:
            self.risk_level = "CRITICAL"
            self.recovery_steps.append("⚠️  DATA LOSS OPERATION DETECTED")
            self.recovery_steps.append("This migration permanently removes schema or data")
            
        if 'delete from' in content_lower or 'truncate' in content_lower:
            self.risk_level = "CRITICAL" 
            self.recovery_steps.append("⚠️  DATA DELETION OPERATION DETECTED")
            self.recovery_steps.append("This migration permanently removes data records")
            
        # Detect schema changes
        if 'alter table' in content_lower:
            self.recovery_steps.append("Schema modification detected - may require data transformation")
            
        # Detect index operations
        if 'drop index' in content_lower:
            self.recovery_steps.append("Index removal - can be recreated but may impact performance")
            
        # Set backup requirements based on risk
        if self.risk_level == "CRITICAL":
            self.backup_requirements = [
                "Full database backup before migration",
                "Table-level backup for affected tables", 
                "Data export of critical business data",
                "Schema snapshot for rollback reference"
            ]
            self.estimated_recovery_time = "4-8 hours"
        else:
            self.backup_requirements = [
                "Schema backup before migration",
                "Affected table backup recommended"
            ]
            self.estimated_recovery_time = "1-2 hours"

class RecoveryDocumentGenerator:
    """Generates RECOVERY.md documentation for irreversible migrations"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.migrations_dir = project_root / "alembic" / "versions"
        self.recovery_doc_path = project_root / "RECOVERY.md"
        
    def scan_for_irreversible_migrations(self) -> List[IrreversibleMigration]:
        """Scan all migrations for irreversible patterns"""
        irreversible_migrations = []
        
        if not self.migrations_dir.exists():
            logger.error(f"Migrations directory not found: {self.migrations_dir}")
            return []
            
        for migration_file in self.migrations_dir.glob("*.py"):
            if migration_file.name.startswith('__'):
                continue
                
            try:
                content = migration_file.read_text()
                
                # Check for irreversible markers
                if self._is_irreversible_migration(content):
                    migration_info = self._parse_migration_metadata(migration_file, content)
                    if migration_info:
                        migration_info.analyze_migration_risks(content)
                        irreversible_migrations.append(migration_info)
                        
            except Exception as e:
                logger.error(f"Error analyzing {migration_file.name}: {e}")
                
        return irreversible_migrations
    
    def _is_irreversible_migration(self, content: str) -> bool:
        """Check if migration is marked as irreversible"""
        irreversible_patterns = [
            r'raise\s+NotImplementedError.*["\'].*irreversible.*["\']',
            r'# irreversible migration',
            r'# irreversible:',
            r'def downgrade.*:\s*.*raise.*NotImplementedError',
            r'# NO DOWNGRADE AVAILABLE',
            r'# IRREVERSIBLE'
        ]
        
        content_lower = content.lower()
        for pattern in irreversible_patterns:
            if re.search(pattern, content_lower, re.IGNORECASE | re.MULTILINE):
                return True
                
        return False
    
    def _parse_migration_metadata(self, filepath: Path, content: str) -> Optional[IrreversibleMigration]:
        """Parse migration file metadata"""
        try:
            # Extract revision info
            revision_match = re.search(r"revision:\s*str\s*=\s*['\"]([^'\"]+)['\"]", content)
            down_revision_match = re.search(r"down_revision:\s*[^=]*=\s*['\"]([^'\"]*)['\"]", content)
            
            # Extract creation date and summary
            create_date_match = re.search(r"Create Date:\s*([^\n]+)", content)
            summary_match = re.search(r'"""([^"]+)', content)
            
            if not revision_match:
                return None
                
            revision_id = revision_match.group(1)
            down_revision = down_revision_match.group(1) if down_revision_match else None
            create_date = create_date_match.group(1).strip() if create_date_match else "Unknown"
            
            # Extract summary from docstring or filename
            if summary_match:
                summary = summary_match.group(1).strip().split('\n')[0]
            else:
                summary = filepath.stem.split('_', 1)[1] if '_' in filepath.stem else filepath.stem
                
            return IrreversibleMigration(
                revision_id=revision_id,
                filename=filepath.name,
                summary=summary,
                create_date=create_date,
                down_revision=down_revision
            )
            
        except Exception as e:
            logger.error(f"Error parsing migration metadata from {filepath}: {e}")
            return None
    
    def generate_recovery_document(self, irreversible_migrations: List[IrreversibleMigration]) -> str:
        """Generate comprehensive RECOVERY.md content"""
        
        doc_content = f"""# Migration Recovery Documentation

Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This document provides manual recovery procedures for irreversible database migrations.
**CRITICAL**: These migrations cannot be automatically rolled back through Alembic.

## ⚠️ EMERGENCY CONTACTS
- **Database Administrator**: [Contact Info]
- **System Administrator**: [Contact Info]  
- **DevOps Team**: [Contact Info]
- **Emergency Escalation**: [Contact Info]

## 🚨 IMMEDIATE RECOVERY STEPS

If you need to recover from a failed irreversible migration:

1. **STOP ALL APPLICATION INSTANCES** immediately
2. **DO NOT** attempt additional migrations
3. Contact the database administrator
4. Refer to the specific migration recovery plan below
5. Execute backup restoration procedures if necessary

---

"""

        if not irreversible_migrations:
            doc_content += """## ✅ NO IRREVERSIBLE MIGRATIONS

Currently, no irreversible migrations have been detected in this project.
All migrations have proper downgrade paths.

This is the recommended state - maintain reversible migrations whenever possible.

"""
        else:
            doc_content += f"""## 📋 IRREVERSIBLE MIGRATIONS SUMMARY

**Total Irreversible Migrations**: {len(irreversible_migrations)}

| Revision | Risk Level | Summary | Recovery Time |
|----------|------------|---------|---------------|
"""
            
            for migration in irreversible_migrations:
                doc_content += f"| `{migration.revision_id}` | {migration.risk_level} | {migration.summary} | {migration.estimated_recovery_time} |\n"
                
            doc_content += "\n---\n\n"
            
            # Detailed recovery procedures for each migration
            for migration in irreversible_migrations:
                doc_content += self._generate_migration_recovery_section(migration)
                
        doc_content += self._generate_general_recovery_procedures()
        
        return doc_content
    
    def _generate_migration_recovery_section(self, migration: IrreversibleMigration) -> str:
        """Generate detailed recovery section for a specific migration"""
        
        section = f"""## 🔧 RECOVERY: {migration.revision_id}

**Migration**: `{migration.filename}`
**Summary**: {migration.summary}
**Risk Level**: {migration.risk_level}
**Created**: {migration.create_date}
**Estimated Recovery Time**: {migration.estimated_recovery_time}

### Pre-Migration Requirements

Before this migration was applied, the following backups should have been created:

"""
        
        for requirement in migration.backup_requirements:
            section += f"- {requirement}\n"
            
        section += f"""

### Recovery Procedures

"""
        
        if migration.recovery_steps:
            for step in migration.recovery_steps:
                section += f"- {step}\n"
        else:
            section += """- No specific recovery steps identified
- Consult with database administrator for custom recovery plan
- Review migration content to understand changes made
"""

        section += f"""

### Manual Rollback Steps

1. **IDENTIFY BACKUP LOCATION**
   ```bash
   # Locate the pre-migration backup
   ls -la /backups/migration_{migration.revision_id}_*
   ```

2. **STOP APPLICATION**
   ```bash
   # Stop all application instances
   systemctl stop finbrain-app
   # Or use your deployment-specific stop command
   ```

3. **ASSESS DATABASE STATE**
   ```bash
   # Connect to database and assess current state
   psql $DATABASE_URL -c "SELECT revision FROM alembic_version;"
   ```

4. **RESTORE FROM BACKUP** (if necessary)
   ```bash
   # Example restoration command - ADJUST FOR YOUR BACKUP STRATEGY
   pg_restore -h localhost -U postgres -d finbrain backup_file.sql
   ```

5. **UPDATE ALEMBIC VERSION**
   ```sql
   -- Reset Alembic to previous revision
   UPDATE alembic_version SET version_num = '{migration.down_revision or "previous_revision"}';
   ```

6. **VERIFY RESTORATION**
   ```bash
   # Test database connectivity and basic queries
   psql $DATABASE_URL -c "SELECT COUNT(*) FROM users LIMIT 1;"
   ```

7. **RESTART APPLICATION**
   ```bash
   # Start application and verify functionality
   systemctl start finbrain-app
   ```

### Verification Checklist

After recovery, verify the following:

- [ ] Database is accessible and responsive
- [ ] Critical tables contain expected data
- [ ] Application starts without errors
- [ ] Basic functionality works (login, core features)
- [ ] Alembic version table shows correct revision
- [ ] No data corruption detected

### Data Integrity Checks

```sql
-- Verify critical table record counts
SELECT 'users' as table_name, COUNT(*) as record_count FROM users
UNION ALL
SELECT 'expenses', COUNT(*) FROM expenses  
UNION ALL
SELECT 'monthly_summaries', COUNT(*) FROM monthly_summaries;

-- Check for any obvious data inconsistencies
-- Add application-specific integrity checks here
```

---

"""
        return section
    
    def _generate_general_recovery_procedures(self) -> str:
        """Generate general recovery procedures section"""
        
        return """## 📚 GENERAL RECOVERY PROCEDURES

### Backup Strategy Requirements

For any future irreversible migrations, ensure the following backups are available:

1. **Full Database Backup**
   ```bash
   pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql
   ```

2. **Schema-Only Backup**
   ```bash
   pg_dump --schema-only $DATABASE_URL > schema_backup_$(date +%Y%m%d_%H%M%S).sql
   ```

3. **Critical Data Export**
   ```bash
   # Export critical business data
   psql $DATABASE_URL -c "\\copy users TO 'users_backup.csv' CSV HEADER"
   psql $DATABASE_URL -c "\\copy expenses TO 'expenses_backup.csv' CSV HEADER"
   ```

### Emergency Contacts & Procedures

1. **Escalation Path**
   - L1: Development Team
   - L2: Database Administrator
   - L3: System Administrator
   - L4: Emergency On-Call

2. **Communication Protocol**
   - Notify all stakeholders immediately
   - Document all recovery actions taken
   - Post-mortem required for all recovery incidents

### Prevention Best Practices

1. **Migration Design**
   - Avoid irreversible migrations when possible
   - Use data migration scripts for complex transformations
   - Test migrations thoroughly on staging environment

2. **Backup Validation**
   - Test backup restoration procedures regularly
   - Verify backup integrity before production deployments
   - Automate backup creation for migration workflows

3. **Rollback Planning**
   - Document rollback procedures before migration
   - Test rollback procedures on staging environment
   - Have emergency contacts readily available

### Tools & Resources

- **Database Administration**: [Links to relevant tools]
- **Monitoring**: [Links to monitoring dashboards]
- **Documentation**: [Links to additional documentation]
- **Support**: [Links to support channels]

---

**Last Updated**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Document Version**: 1.0
**Maintained By**: Database Operations Team

"""

    def write_recovery_document(self, irreversible_migrations: List[IrreversibleMigration]):
        """Write RECOVERY.md file to disk"""
        content = self.generate_recovery_document(irreversible_migrations)
        
        self.recovery_doc_path.write_text(content)
        logger.info(f"RECOVERY.md written to: {self.recovery_doc_path}")
        
        if irreversible_migrations:
            logger.warning(f"Found {len(irreversible_migrations)} irreversible migrations!")
            for migration in irreversible_migrations:
                logger.warning(f"  - {migration.revision_id}: {migration.summary} (Risk: {migration.risk_level})")
        else:
            logger.info("No irreversible migrations found - all migrations have proper downgrade paths")

def main():
    parser = argparse.ArgumentParser(description="Generate RECOVERY.md for irreversible migrations")
    parser.add_argument("revision", nargs="?", help="Specific revision to analyze")
    parser.add_argument("--check-all", action="store_true", help="Check all migrations for irreversible patterns")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if not args.revision and not args.check_all:
        parser.error("Must specify either a revision or --check-all")
    
    # Find project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # Verify we're in the right place
    if not (project_root / "alembic").exists():
        logger.error("Could not find alembic directory. Are you in the project root?")
        sys.exit(1)
    
    logger.info("Starting recovery documentation generation...")
    logger.info(f"Project root: {project_root}")
    
    generator = RecoveryDocumentGenerator(project_root)
    
    if args.check_all:
        irreversible_migrations = generator.scan_for_irreversible_migrations()
        generator.write_recovery_document(irreversible_migrations)
    else:
        # Check specific revision (implementation would go here)
        logger.info(f"Checking specific revision: {args.revision}")
        # This would implement single-revision checking
        
    logger.info("Recovery documentation generation completed")

if __name__ == "__main__":
    main()