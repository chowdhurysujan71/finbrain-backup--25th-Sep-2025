#!/usr/bin/env python3
"""
Comprehensive validation of all database field fixes
"""
import sys
from app import app, db
from models import User, Expense
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def validate_fixes():
    """Validate all the fixes are properly applied"""
    
    with app.app_context():
        errors = []
        warnings = []
        
        print("=" * 60)
        print("DATABASE FIELD VALIDATION REPORT")
        print("=" * 60)
        
        # 1. Check User model has correct field
        print("\n1. User Model Check:")
        if hasattr(User, 'user_id_hash'):
            print("   ✅ User model has user_id_hash field")
        else:
            errors.append("User model missing user_id_hash field")
            print("   ❌ User model missing user_id_hash field")
        
        # 2. Check Expense model has user_id field
        print("\n2. Expense Model Check:")
        if hasattr(Expense, 'user_id'):
            print("   ✅ Expense model has user_id field")
        else:
            errors.append("Expense model missing user_id field")
            print("   ❌ Expense model missing user_id field")
            
        # 3. Check imports are standardized
        print("\n3. Import Standardization Check:")
        try:
            from utils.user_manager import resolve_user_id
            print("   ✅ resolve_user_id imports correctly")
        except ImportError as e:
            errors.append(f"Cannot import resolve_user_id: {e}")
            print(f"   ❌ Cannot import resolve_user_id: {e}")
        
        try:
            from utils.security import ensure_hashed
            print("   ✅ ensure_hashed imports correctly from utils.security")
        except ImportError as e:
            warnings.append(f"Cannot import ensure_hashed from utils.security: {e}")
            print(f"   ⚠️ Cannot import ensure_hashed from utils.security: {e}")
            
        # 4. Check database indexes
        print("\n4. Database Index Check:")
        result = db.session.execute(text("""
            SELECT indexname 
            FROM pg_indexes
            WHERE tablename = 'expenses'
            AND indexname LIKE '%user_id%'
        """))
        
        expense_indexes = [row[0] for row in result]
        if expense_indexes:
            print(f"   ✅ Expense table has user_id indexes: {', '.join(expense_indexes)}")
        else:
            warnings.append("No user_id index found on expenses table")
            print("   ⚠️ No user_id index found on expenses table")
            
        result = db.session.execute(text("""
            SELECT indexname
            FROM pg_indexes  
            WHERE tablename = 'users'
            AND indexname LIKE '%user_id_hash%'
        """))
        
        user_indexes = [row[0] for row in result]
        if user_indexes:
            print(f"   ✅ User table has user_id_hash indexes: {', '.join(user_indexes)}")
        else:
            warnings.append("No user_id_hash index found on users table")
            print("   ⚠️ No user_id_hash index found on users table")
            
        # 5. Test routing functionality
        print("\n5. Production Router Check:")
        try:
            from utils.production_router import ProductionRouter
            router = ProductionRouter()
            
            # Check that router has the guard assertion
            import inspect
            source = inspect.getsource(router._handle_ai_expense_logging)
            if 'assert hasattr(User, "user_id_hash")' in source:
                print("   ✅ Router has regression guard for User.user_id_hash")
            else:
                warnings.append("Router missing regression guard assertion")
                print("   ⚠️ Router missing regression guard assertion")
                
        except Exception as e:
            errors.append(f"Cannot validate production router: {e}")
            print(f"   ❌ Cannot validate production router: {e}")
            
        # 6. Check for stray filter_by(user_id=...) on User model
        print("\n6. Query Pattern Check:")
        import os
        import re
        
        suspicious_files = []
        for root, dirs, files in os.walk('utils'):
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    with open(filepath, 'r') as f:
                        content = f.read()
                        # Look for User queries with user_id instead of user_id_hash
                        if re.search(r'User.*filter_by\(user_id=', content):
                            suspicious_files.append(filepath)
        
        if suspicious_files:
            warnings.append(f"Found User queries using user_id: {suspicious_files}")
            print(f"   ⚠️ Found User queries using user_id in: {', '.join(suspicious_files)}")
        else:
            print("   ✅ No User queries using incorrect field name")
            
        # Summary
        print("\n" + "=" * 60)
        print("VALIDATION SUMMARY")
        print("=" * 60)
        
        if errors:
            print(f"\n❌ CRITICAL ERRORS ({len(errors)}):")
            for error in errors:
                print(f"   - {error}")
                
        if warnings:
            print(f"\n⚠️ WARNINGS ({len(warnings)}):")
            for warning in warnings:
                print(f"   - {warning}")
                
        if not errors and not warnings:
            print("\n✅ ALL VALIDATIONS PASSED!")
            print("The system is properly configured with:")
            print("  • User model uses user_id_hash field")
            print("  • Expense model uses user_id field")
            print("  • Imports are standardized to utils.user_manager")
            print("  • Database indexes are in place")
            print("  • No stray incorrect queries found")
            
        return len(errors) == 0

if __name__ == "__main__":
    success = validate_fixes()
    sys.exit(0 if success else 1)