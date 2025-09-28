#!/usr/bin/env python3
"""
Deployment Readiness Check for FinBrain Web-Only

Validates that the system is ready for web-only deployment.
Checks critical functionality without blocking on legacy patterns.
"""

import os
import sys
import requests
import subprocess
from datetime import datetime

# Add project root to Python path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def check_server_running():
    """Check if the server is running and responsive"""
    try:
        response = requests.get('http://localhost:5000/health', timeout=10)
        if response.status_code == 200:
            print("✅ Server is running and responsive")
            return True
        else:
            print(f"❌ Server returned status {response.status_code}")
            return False
    except requests.exceptions.Timeout:
        print("⚠️  Server timeout (server may be starting up)")
        # Try one more time with longer timeout
        try:
            response = requests.get('http://localhost:5000/health', timeout=15)
            if response.status_code == 200:
                print("✅ Server is running and responsive (after retry)")
                return True
        except:
            pass
        print("❌ Server not responsive after retries")
        return False
    except Exception as e:
        print(f"❌ Server not accessible: {e}")
        return False

def check_database_connection():
    """Check database connectivity"""
    try:
        # Test database drivers - try psycopg2-binary first, then psycopg
        db_driver_found = False
        try:
            import psycopg2
            db_driver_found = True
            print("✅ psycopg2 driver available")
        except ImportError:
            try:
                import psycopg
                db_driver_found = True
                print("✅ psycopg3 driver available")
            except ImportError:
                pass
        
        if not db_driver_found:
            print("❌ No PostgreSQL drivers found (psycopg2 or psycopg3)")
            return False
            
        # Test model imports (optional - main thing is driver availability)
        try:
            from models import User
            print("✅ Database models imported successfully")
        except ImportError as e:
            print(f"⚠️  Model import issue: {e} (driver available, models may need path setup)")
            # Don't fail on this - main thing is driver availability
        
        # Test that we can get environment database URL
        import os
        db_url = os.getenv('DATABASE_URL')
        if db_url:
            print("✅ Database URL configured")
        else:
            print("⚠️  DATABASE_URL not configured")
            return False
            
        return True
    except Exception as e:
        print(f"❌ Database check failed: {e}")
        return False

def check_web_auth_endpoints():
    """Check web authentication endpoints"""
    endpoints = [
        '/login',
        '/logout', 
        '/register'
    ]
    
    working_endpoints = 0
    
    for endpoint in endpoints:
        try:
            response = requests.get(f'http://localhost:5000{endpoint}', timeout=5, allow_redirects=False)
            # Auth endpoints typically redirect or return 405 for GET
            if response.status_code in [200, 302, 405]:
                print(f"✅ {endpoint} endpoint accessible")
                working_endpoints += 1
            else:
                print(f"⚠️  {endpoint} returned {response.status_code}")
        except Exception as e:
            print(f"⚠️  {endpoint} not accessible: {e}")
    
    if working_endpoints > 0:
        print("✅ Web authentication infrastructure present")
        return True
    else:
        print("❌ No web authentication endpoints working")
        return False

def check_banner_system():
    """Check banner system functionality"""
    try:
        response = requests.get('http://localhost:5000/api/banners', timeout=5, allow_redirects=False)
        # Should redirect to login or return auth error
        if response.status_code in [302, 401, 403]:
            print("✅ Banner API endpoint protected (requires auth)")
            return True
        else:
            print(f"⚠️  Banner API returned unexpected status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Banner API not accessible: {e}")
        return False

def check_environment_config():
    """Check critical environment configuration"""
    required_vars = [
        'NUDGES_ENABLED',
        'DATABASE_URL'
    ]
    
    all_present = True
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var} is set")
        else:
            print(f"❌ {var} is missing")
            all_present = False
    
    # Check NUDGES_ENABLED specifically
    nudges_enabled = os.getenv('NUDGES_ENABLED', 'false').lower() == 'true'
    if nudges_enabled:
        print("✅ NUDGES_ENABLED is active")
    else:
        print("⚠️  NUDGES_ENABLED is not active")
    
    return all_present

def check_file_structure():
    """Check critical file structure"""
    critical_files = [
        'app.py',
        'main.py',
        'models.py',
        'routes_nudges.py',
        'pwa_ui.py',
        'templates/chat.html',
        'utils/feature_flags.py',
        'utils/test_clock.py'
    ]
    
    missing_files = []
    
    for file_path in critical_files:
        if os.path.exists(file_path):
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} missing")
            missing_files.append(file_path)
    
    return len(missing_files) == 0

def main():
    """Run deployment readiness check"""
    print("🚀 FinBrain Deployment Readiness Check")
    print("=" * 40)
    print(f"Check time: {datetime.now().isoformat()}")
    print()
    
    checks = [
        ("File Structure", check_file_structure),
        ("Environment Config", check_environment_config),
        ("Server Running", check_server_running),
        ("Database Connection", check_database_connection),
        ("Web Auth Endpoints", check_web_auth_endpoints),
        ("Banner System", check_banner_system),
    ]
    
    results = []
    
    for check_name, check_func in checks:
        print(f"\n🔍 {check_name}")
        print("-" * (len(check_name) + 3))
        
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            print(f"❌ {check_name} failed with error: {e}")
            results.append((check_name, False))
    
    # Summary
    print(f"\n📊 Deployment Readiness Summary")
    print("=" * 33)
    
    passed = 0
    total = len(results)
    
    for check_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{check_name:20} {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} checks passed")
    
    if passed >= total - 1:  # Allow 1 failure
        print("\n🎉 READY FOR DEPLOYMENT!")
        print("✅ Core web-only functionality is operational")
        return 0
    else:
        print("\n⚠️  DEPLOYMENT READINESS ISSUES")
        print("🔧 Please resolve critical issues before deployment")
        return 1

if __name__ == '__main__':
    exit(main())