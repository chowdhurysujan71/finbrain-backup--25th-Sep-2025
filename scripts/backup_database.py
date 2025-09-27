#!/usr/bin/env python3
"""
Simple PostgreSQL backup script for finbrain
Creates a pg_dump backup file with timestamp
"""

import os
import subprocess
import sys
from datetime import datetime, timezone


def create_backup():
    """Create a database backup using pg_dump"""
    
    # Get database URL from environment
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not found")
        return False
    
    # Create backup filename with timestamp
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    backup_filename = f"finbrain_backup_{timestamp}.sql"
    backup_path = os.path.join("backups", backup_filename)
    
    # Create backups directory if it doesn't exist
    os.makedirs("backups", exist_ok=True)
    
    try:
        print(f"Creating database backup: {backup_filename}")
        
        # Parse database URL for secure connection
        from urllib.parse import urlparse
        parsed = urlparse(database_url)
        
        # Set environment variables for pg_dump (more secure than CLI args)
        env = os.environ.copy()
        env['PGHOST'] = parsed.hostname
        env['PGPORT'] = str(parsed.port or 5432)
        env['PGUSER'] = parsed.username
        env['PGPASSWORD'] = parsed.password
        env['PGDATABASE'] = parsed.path.lstrip('/')
        
        # Run pg_dump command without database URL in args
        cmd = [
            'pg_dump',
            '--file', backup_path,
            '--verbose',
            '--clean',
            '--if-exists',
            '--no-owner',
            '--no-privileges',
            '--compress=9'  # Add compression
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        
        if result.returncode == 0:
            print(f"✅ Backup completed successfully: {backup_path}")
            
            # Show backup file size
            file_size = os.path.getsize(backup_path)
            print(f"   Backup size: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
            
            return True
        else:
            print(f"❌ Backup failed with return code: {result.returncode}")
            print(f"Error output: {result.stderr}")
            return False
            
    except FileNotFoundError:
        print("❌ ERROR: pg_dump command not found")
        print("   Install PostgreSQL client tools or run this script in an environment with pg_dump")
        return False
    except Exception as e:
        print(f"❌ ERROR: Backup failed: {str(e)}")
        return False


def list_backups():
    """List all available backup files"""
    backup_dir = "backups"
    
    if not os.path.exists(backup_dir):
        print("No backups directory found")
        return
    
    backup_files = [f for f in os.listdir(backup_dir) if f.endswith('.sql')]
    
    if not backup_files:
        print("No backup files found")
        return
    
    print(f"Available backups ({len(backup_files)} files):")
    backup_files.sort(reverse=True)  # Latest first
    
    for backup_file in backup_files:
        backup_path = os.path.join(backup_dir, backup_file)
        file_size = os.path.getsize(backup_path)
        mtime = datetime.fromtimestamp(os.path.getmtime(backup_path))
        print(f"  {backup_file} ({file_size:,} bytes, {mtime.strftime('%Y-%m-%d %H:%M:%S')})")


def main():
    """Main backup script entry point"""
    
    if len(sys.argv) > 1 and sys.argv[1] == 'list':
        list_backups()
        return
    
    print("🛡️  FinBrain Database Backup Tool")
    print("=" * 40)
    
    # Check if DATABASE_URL is available
    if not os.environ.get('DATABASE_URL'):
        print("❌ DATABASE_URL environment variable not found")
        print("   Make sure you're running this in the Replit environment")
        sys.exit(1)
    
    # Create backup
    success = create_backup()
    
    if success:
        print("\n✅ Backup completed successfully!")
        print("\n📋 Usage:")
        print("   python scripts/backup_database.py        # Create new backup")
        print("   python scripts/backup_database.py list   # List all backups")
    else:
        print("\n❌ Backup failed!")
        sys.exit(1)


if __name__ == '__main__':
    main()