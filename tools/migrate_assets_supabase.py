#!/usr/bin/env python3
"""
Migration helper to upload local files to Supabase Storage
Usage: python tools/migrate_assets_supabase.py --src ./local_uploads --user-id <uid>
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict

import requests


class SupabaseMigrator:
    """Helper class for migrating files to Supabase Storage"""
    
    def __init__(self):
        self.url = os.environ.get("SUPABASE_URL")
        self.service_key = os.environ.get("SUPABASE_SERVICE_KEY")
        self.bucket = os.environ.get("SUPABASE_BUCKET", "user-assets")
        
        if not self.url or not self.service_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables required")
            
        self.base_url = f"{self.url}/storage/v1"
        self.headers = {
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json"
        }
    
    def upload_file(self, local_path: Path, remote_path: str) -> dict[str, Any]:
        """
        Upload a single file to Supabase Storage
        
        Args:
            local_path: Path to local file
            remote_path: Target path in Supabase bucket (e.g., "user123/document.pdf")
            
        Returns:
            Dict with upload status and metadata
        """
        start_time = time.time()
        
        try:
            # Get file info
            file_size = local_path.stat().st_size
            content_type = self._get_content_type(local_path.suffix)
            
            # Upload directly using service key
            upload_url = f"{self.base_url}/object/{self.bucket}/{remote_path}"
            
            with open(local_path, 'rb') as file_data:
                upload_headers = {
                    "Authorization": f"Bearer {self.service_key}",
                    "Content-Type": content_type,
                    "x-upsert": "true"  # Allow overwrite
                }
                
                response = requests.post(
                    upload_url,
                    data=file_data,
                    headers=upload_headers,
                    timeout=30
                )
                response.raise_for_status()
            
            elapsed_ms = (time.time() - start_time) * 1000
            
            return {
                "status": "success",
                "local_path": str(local_path),
                "remote_path": remote_path,
                "size_bytes": file_size,
                "content_type": content_type,
                "upload_time_ms": round(elapsed_ms, 2),
                "timestamp": int(time.time())
            }
            
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            
            return {
                "status": "error",
                "local_path": str(local_path),
                "remote_path": remote_path,
                "error": str(e),
                "upload_time_ms": round(elapsed_ms, 2),
                "timestamp": int(time.time())
            }
    
    def _get_content_type(self, file_extension: str) -> str:
        """Map file extension to content type"""
        content_type_map = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg', 
            '.png': 'image/png',
            '.pdf': 'application/pdf',
            '.txt': 'text/plain',
            '.json': 'application/json',
            '.md': 'text/plain',
            '.csv': 'text/csv'
        }
        return content_type_map.get(file_extension.lower(), 'application/octet-stream')
    
    def migrate_directory(self, src_dir: Path, user_id: str) -> dict[str, Any]:
        """
        Migrate entire directory to Supabase Storage
        
        Args:
            src_dir: Source directory path
            user_id: User ID for path prefix
            
        Returns:
            Dict with migration summary
        """
        if not src_dir.exists() or not src_dir.is_dir():
            raise ValueError(f"Source directory does not exist: {src_dir}")
        
        results = []
        success_count = 0
        error_count = 0
        total_bytes = 0
        
        # Walk directory recursively
        for file_path in src_dir.rglob("*"):
            if file_path.is_file():
                # Calculate relative path and create remote path
                relative_path = file_path.relative_to(src_dir)
                remote_path = f"{user_id}/{relative_path}"
                
                # Upload file
                result = self.upload_file(file_path, remote_path)
                results.append(result)
                
                # Track statistics
                if result["status"] == "success":
                    success_count += 1
                    total_bytes += result["size_bytes"]
                else:
                    error_count += 1
                
                # Log result
                print(json.dumps(result))
        
        return {
            "migration_summary": {
                "total_files": len(results),
                "successful": success_count,
                "failed": error_count,
                "total_bytes_uploaded": total_bytes,
                "user_id": user_id,
                "source_directory": str(src_dir)
            },
            "detailed_results": results
        }


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="Migrate local files to Supabase Storage")
    parser.add_argument("--src", required=True, help="Source directory path")
    parser.add_argument("--user-id", required=True, help="User ID for path prefix")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be uploaded without actually uploading")
    
    args = parser.parse_args()
    
    try:
        # Validate environment
        migrator = SupabaseMigrator()
        src_path = Path(args.src)
        
        if args.dry_run:
            print(f"DRY RUN: Would migrate files from {src_path} to Supabase bucket '{migrator.bucket}' with user prefix '{args.user_id}'")
            
            for file_path in src_path.rglob("*"):
                if file_path.is_file():
                    relative_path = file_path.relative_to(src_path)
                    remote_path = f"{args.user_id}/{relative_path}"
                    file_size = file_path.stat().st_size
                    
                    print(json.dumps({
                        "action": "would_upload",
                        "local_path": str(file_path),
                        "remote_path": remote_path,
                        "size_bytes": file_size
                    }))
            
            return
        
        # Perform actual migration
        print(f"Starting migration from {src_path} to Supabase bucket '{migrator.bucket}'")
        print(f"User ID prefix: {args.user_id}")
        print("=" * 50)
        
        summary = migrator.migrate_directory(src_path, args.user_id)
        
        print("=" * 50)
        print("Migration Summary:")
        print(json.dumps(summary["migration_summary"], indent=2))
        
        # Exit with error code if any uploads failed
        if summary["migration_summary"]["failed"] > 0:
            sys.exit(1)
            
    except Exception as e:
        print(json.dumps({
            "status": "error",
            "message": str(e),
            "timestamp": int(time.time())
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()