#!/usr/bin/env python3
"""
FinBrain Diagnostic CLI - Health monitoring script for development
"""
import sys
from datetime import datetime

import requests


def check_health_endpoint():
    """Check the /health endpoint"""
    try:
        response = requests.get("http://localhost:5000/health", timeout=5)
        if response.status_code == 200:
            health_data = response.json()
            return {"status": "healthy", "data": health_data}
        else:
            return {"status": "unhealthy", "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"status": "unreachable", "error": str(e)}

def check_database():
    """Check database connectivity"""
    try:
        sys.path.append('/home/runner/workspace')
        from app import app, db
        
        with app.app_context():
            # Simple query to test connectivity
            result = db.session.execute(db.text("SELECT 1")).scalar()
            
            # Check table counts
            from models import Expense, User
            user_count = User.query.count()
            expense_count = Expense.query.count()
            
            return {
                "status": "connected",
                "query_test": result == 1,
                "user_count": user_count,
                "expense_count": expense_count
            }
    except Exception as e:
        return {"status": "error", "error": str(e)}

def check_ai_status():
    """Check AI adapter status"""
    try:
        sys.path.append('/home/runner/workspace')
        from utils.ai_adapter_v2 import ProductionAIAdapter
        
        adapter = ProductionAIAdapter()
        return {
            "status": "loaded",
            "provider": getattr(adapter, 'provider', 'unknown'),
            "enabled": getattr(adapter, 'enabled', False)
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

def check_critical_modules():
    """Check for missing critical modules"""
    critical_modules = [
        'utils.production_router',
        'utils.intent_router',
        'utils.ai_adapter_v2',
        'utils.identity',
        'models'
    ]
    
    results = {}
    for module in critical_modules:
        try:
            __import__(module)
            results[module] = "available"
        except ImportError as e:
            results[module] = f"missing: {e}"
        except Exception as e:
            results[module] = f"error: {e}"
    
    return results

def main():
    print("=== FINBRAIN DIAGNOSTIC SUMMARY ===")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()
    
    # Health check
    print("1. Health Endpoint:")
    health = check_health_endpoint()
    if health['status'] == 'healthy':
        print("   ✓ Healthy")
        if 'facebook_token_status' in health.get('data', {}):
            print(f"   ✓ Facebook Token: {health['data']['facebook_token_status']}")
    else:
        print(f"   ✗ {health['status']}: {health.get('error', 'Unknown')}")
    print()
    
    # Database check
    print("2. Database:")
    db_status = check_database()
    if db_status['status'] == 'connected':
        print("   ✓ Connected")
        print(f"   ✓ Users: {db_status['user_count']}")
        print(f"   ✓ Expenses: {db_status['expense_count']}")
    else:
        print(f"   ✗ {db_status['status']}: {db_status.get('error', 'Unknown')}")
    print()
    
    # AI status
    print("3. AI Adapter:")
    ai_status = check_ai_status()
    if ai_status['status'] == 'loaded':
        print("   ✓ Loaded")
        print(f"   ✓ Provider: {ai_status['provider']}")
        print(f"   ✓ Enabled: {ai_status['enabled']}")
    else:
        print(f"   ✗ {ai_status['status']}: {ai_status.get('error', 'Unknown')}")
    print()
    
    # Module check
    print("4. Critical Modules:")
    modules = check_critical_modules()
    for module, status in modules.items():
        if status == "available":
            print(f"   ✓ {module}")
        else:
            print(f"   ✗ {module}: {status}")
    print()
    
    # Overall assessment
    issues = []
    if health['status'] != 'healthy':
        issues.append("Health endpoint failing")
    if db_status['status'] != 'connected':
        issues.append("Database connectivity")
    if ai_status['status'] != 'loaded':
        issues.append("AI adapter not loading")
    if any('missing' in status for status in modules.values()):
        issues.append("Missing critical modules")
    
    if issues:
        print(f"⚠️  ISSUES DETECTED: {', '.join(issues)}")
        return 1
    else:
        print("✅ ALL SYSTEMS OPERATIONAL")
        return 0

if __name__ == "__main__":
    sys.exit(main())