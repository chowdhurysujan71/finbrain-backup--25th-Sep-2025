#!/usr/bin/env python3
"""
update_changelog.py - Auto-generate CHANGELOG entries for Alembic migrations

This script automatically creates CHANGELOG entries when new migrations are added.
It extracts migration metadata and formats it for consistent documentation.

Usage:
    python scripts/update_changelog.py [--revision <revision_id>] [--dry-run]

Examples:
    python scripts/update_changelog.py                    # Process all migrations
    python scripts/update_changelog.py --revision cf6afe03b206  # Process specific revision  
    python scripts/update_changelog.py --dry-run          # Preview changes without writing
"""

import os
import sys
import argparse
import re
import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import subprocess
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MigrationInfo:
    """Container for migration metadata"""
    def __init__(self, revision_id: str, filename: str, down_revision: Optional[str] = None, 
                 create_date: Optional[str] = None, summary: Optional[str] = None, author: Optional[str] = None):
        self.revision_id = revision_id
        self.filename = filename
        self.down_revision = down_revision
        self.create_date = create_date
        self.summary = summary or self._extract_summary_from_filename(filename)
        self.author = author or self._get_git_author()
        
    def _extract_summary_from_filename(self, filename: str) -> str:
        """Extract human-readable summary from migration filename"""
        # Remove revision prefix and .py suffix
        name_part = re.sub(r'^[a-f0-9]+_', '', filename)
        name_part = re.sub(r'\.py$', '', name_part)
        
        # Convert underscores to spaces and title case
        summary = name_part.replace('_', ' ').title()
        
        # Handle common patterns
        summary = re.sub(r'\bAddIndex\b', 'Add Index', summary)
        summary = re.sub(r'\bCreateTable\b', 'Create Table', summary)
        summary = re.sub(r'\bAlterColumn\b', 'Alter Column', summary)
        summary = re.sub(r'\bDropTable\b', 'Drop Table', summary)
        
        return summary
    
    def _get_git_author(self) -> str:
        """Get author from git commit if available"""
        try:
            result = subprocess.run(
                ['git', 'log', '-1', '--pretty=format:%an', '--', f'alembic/versions/{self.filename}'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
            pass
        
        # Fallback to git config
        try:
            result = subprocess.run(
                ['git', 'config', 'user.name'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
            pass
            
        return "Unknown"

class ChangelogManager:
    """Manages CHANGELOG.md file operations"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.changelog_path = project_root / "CHANGELOG.md"
        self.migrations_dir = project_root / "alembic" / "versions"
        
    def initialize_changelog(self):
        """Create initial CHANGELOG.md if it doesn't exist"""
        if not self.changelog_path.exists():
            logger.info("Creating initial CHANGELOG.md")
            initial_content = self._get_initial_changelog_content()
            self.changelog_path.write_text(initial_content)
            
    def _get_initial_changelog_content(self) -> str:
        """Generate initial CHANGELOG.md content"""
        return """# Migration Changelog

All notable database schema changes will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Alembic Migration Versioning](https://alembic.sqlalchemy.org/).

## Format
Each migration entry includes:
- **Revision ID**: Alembic revision identifier
- **Summary**: Human-readable description of changes
- **Author**: Migration author from git history
- **Date**: Migration creation date
- **Type**: Category of changes (Schema, Data, Index, etc.)

---

"""
    
    def parse_migration_file(self, filepath: Path) -> Optional[MigrationInfo]:
        """Parse migration file to extract metadata"""
        try:
            content = filepath.read_text()
            
            # Extract revision info
            revision_match = re.search(r"revision:\s*str\s*=\s*['\"]([^'\"]+)['\"]", content)
            down_revision_match = re.search(r"down_revision:\s*[^=]*=\s*['\"]([^'\"]*)['\"]", content)
            
            # Extract creation date from docstring or comments
            create_date_match = re.search(r"Create Date:\s*([^\n]+)", content)
            
            # Extract summary from docstring
            summary_match = re.search(r'"""([^"]+)', content)
            
            if not revision_match:
                logger.warning(f"Could not extract revision from {filepath.name}")
                return None
                
            revision_id = revision_match.group(1)
            down_revision = down_revision_match.group(1) if down_revision_match else None
            create_date = create_date_match.group(1).strip() if create_date_match else None
            summary = summary_match.group(1).strip() if summary_match else None
            
            return MigrationInfo(
                revision_id=revision_id,
                filename=filepath.name,
                down_revision=down_revision,
                create_date=create_date,
                summary=summary,
                author=None  # Will be set by constructor
            )
            
        except Exception as e:
            logger.error(f"Error parsing migration file {filepath}: {e}")
            return None
    
    def get_existing_entries(self) -> List[str]:
        """Get list of revision IDs already in CHANGELOG"""
        if not self.changelog_path.exists():
            return []
            
        content = self.changelog_path.read_text()
        # Find all revision IDs in format ### Revision: abc123
        revision_pattern = r"###\s+Revision:\s+([a-f0-9]+)"
        return re.findall(revision_pattern, content)
    
    def format_migration_entry(self, migration: MigrationInfo) -> str:
        """Format migration info as CHANGELOG entry"""
        date = migration.create_date or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Determine migration type based on summary and content
        migration_type = self._determine_migration_type(migration)
        
        entry = f"""
### Revision: {migration.revision_id}
- **Summary**: {migration.summary}
- **Author**: {migration.author}
- **Date**: {date}
- **Type**: {migration_type}
- **Previous**: {migration.down_revision or 'None'}
- **File**: `{migration.filename}`

"""
        return entry
    
    def _determine_migration_type(self, migration: MigrationInfo) -> str:
        """Determine migration category based on content"""
        summary_lower = migration.summary.lower()
        
        if any(word in summary_lower for word in ['index', 'concurrent']):
            return "Index Operations"
        elif any(word in summary_lower for word in ['create', 'add table']):
            return "Schema Addition"
        elif any(word in summary_lower for word in ['alter', 'modify', 'change']):
            return "Schema Modification"
        elif any(word in summary_lower for word in ['data', 'migration', 'populate']):
            return "Data Migration"
        elif any(word in summary_lower for word in ['drop', 'remove', 'delete']):
            return "Schema Removal"
        elif any(word in summary_lower for word in ['baseline', 'initial']):
            return "Baseline"
        else:
            return "General"
    
    def add_migration_entry(self, migration: MigrationInfo) -> bool:
        """Add new migration entry to CHANGELOG"""
        existing_entries = self.get_existing_entries()
        
        if migration.revision_id in existing_entries:
            logger.info(f"Migration {migration.revision_id} already in CHANGELOG")
            return False
            
        # Read current content
        content = self.changelog_path.read_text()
        
        # Find insertion point (after the header but before existing entries)
        header_end = content.find("---\n")
        if header_end == -1:
            # No header separator found, append to end
            new_content = content + self.format_migration_entry(migration)
        else:
            # Insert after header
            insert_point = header_end + 4  # After "---\n"
            new_content = (
                content[:insert_point] + 
                self.format_migration_entry(migration) + 
                content[insert_point:]
            )
        
        self.changelog_path.write_text(new_content)
        logger.info(f"Added migration {migration.revision_id} to CHANGELOG")
        return True
    
    def process_migrations(self, specific_revision: Optional[str] = None) -> List[str]:
        """Process all migrations or a specific revision"""
        if not self.migrations_dir.exists():
            logger.error(f"Migrations directory not found: {self.migrations_dir}")
            return []
            
        migration_files = list(self.migrations_dir.glob("*.py"))
        if not migration_files:
            logger.warning("No migration files found")
            return []
            
        processed = []
        
        for migration_file in sorted(migration_files):
            # Skip __pycache__ and non-migration files
            if migration_file.name.startswith('__'):
                continue
                
            migration_info = self.parse_migration_file(migration_file)
            if not migration_info:
                continue
                
            # Filter by specific revision if requested
            if specific_revision and migration_info.revision_id != specific_revision:
                continue
                
            if self.add_migration_entry(migration_info):
                processed.append(migration_info.revision_id)
                
        return processed

def main():
    parser = argparse.ArgumentParser(description="Auto-generate CHANGELOG entries for migrations")
    parser.add_argument("--revision", help="Process specific revision only")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Find project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # Verify we're in the right place
    if not (project_root / "alembic").exists():
        logger.error("Could not find alembic directory. Are you in the project root?")
        sys.exit(1)
    
    logger.info("Starting CHANGELOG update process...")
    logger.info(f"Project root: {project_root}")
    
    changelog_manager = ChangelogManager(project_root)
    
    if args.dry_run:
        logger.info("DRY RUN MODE - No files will be modified")
        
    if not args.dry_run:
        changelog_manager.initialize_changelog()
    
    processed = changelog_manager.process_migrations(args.revision)
    
    if processed:
        logger.info(f"Processed {len(processed)} migrations: {', '.join(processed)}")
    else:
        logger.info("No new migrations to process")
    
    logger.info("CHANGELOG update process completed")

if __name__ == "__main__":
    main()