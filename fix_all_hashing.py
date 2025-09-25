#!/usr/bin/env python3
"""
One-shot script to fix all remaining hash function calls
"""
import os
import re


def update_file_hashing(file_path, patterns_to_fix):
    """Update a file to use ensure_hashed instead of legacy hash functions"""
    try:
        with open(file_path) as f:
            content = f.read()
        
        original_content = content
        
        # Add ensure_hashed import if not present
        if 'ensure_hashed' not in content and any(pattern in content for pattern, _ in patterns_to_fix):
            # Find the import section and add the import
            if 'from utils.crypto import' in content:
                content = content.replace(
                    'from utils.crypto import',
                    'from utils.crypto import ensure_hashed,'
                )
            else:
                # Add new import after existing imports
                import_lines = []
                other_lines = []
                for line in content.split('\n'):
                    if line.strip().startswith('import ') or line.strip().startswith('from '):
                        import_lines.append(line)
                    else:
                        other_lines.append(line)
                
                if import_lines:
                    import_lines.append('from utils.crypto import ensure_hashed')
                    content = '\n'.join(import_lines + other_lines)
        
        # Apply pattern replacements
        for old_pattern, new_pattern in patterns_to_fix:
            content = re.sub(old_pattern, new_pattern, content, flags=re.MULTILINE)
        
        # Write back if changed
        if content != original_content:
            with open(file_path, 'w') as f:
                f.write(content)
            print(f"Updated: {file_path}")
            return True
        else:
            print(f"No changes needed: {file_path}")
            return False
    
    except Exception as e:
        print(f"Error updating {file_path}: {e}")
        return False

def main():
    """Fix all hash function calls"""
    
    # Files and patterns to fix
    files_to_fix = {
        'utils/policy_guard.py': [
            (r'hash_psid\(psid\)', 'ensure_hashed(psid)'),
        ],
        'utils/mvp_router.py': [
            (r'hash_psid\(psid\)', 'ensure_hashed(psid)'),
        ],
        'utils/ai_adapter.py': [
            (r'hash_psid\(psid\)', 'ensure_hashed(psid)'),
        ],
        'utils/rate_limiter.py': [
            (r'hash_user_id\(user_identifier\)', 'ensure_hashed(user_identifier)'),
        ],
        'utils/report_generator.py': [
            (r'hash_user_id\(user_identifier\)', 'ensure_hashed(user_identifier)'),
        ],
        'utils/db.py': [
            (r'hash_user_id\(user_identifier\)', 'ensure_hashed(user_identifier)'),
        ],
    }
    
    print("Fixing hash function calls across the codebase...")
    
    for file_path, patterns in files_to_fix.items():
        if os.path.exists(file_path):
            update_file_hashing(file_path, patterns)
        else:
            print(f"File not found: {file_path}")
    
    print("\nDone! All hash function calls should now use ensure_hashed()")

if __name__ == "__main__":
    main()