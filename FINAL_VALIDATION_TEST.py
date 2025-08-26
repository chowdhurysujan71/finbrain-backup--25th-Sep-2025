#!/usr/bin/env python3
"""
Final CC System Validation - Test all operational phases
"""

import sys
import requests
import json
from datetime import datetime

sys.path.append('/home/runner/workspace')
from app import app, db
from sqlalchemy import text

def test_all_phases():
    """Test all implemented phases with corrected endpoints"""
    print("🎯 FINAL CC SYSTEM VALIDATION")
    print("="*50)
    
    results = {}
    base_url = "http://localhost:5000"
    
    # Phase 1: Get CC data from database
    print("\n📋 Phase 1: CC Persistence Validation")
    try:
        with app.app_context():
            cc_count = db.session.execute(text("SELECT COUNT(*) FROM inference_snapshots")).scalar()
            latest_cc = db.session.execute(text("""
                SELECT cc_id, confidence, decision, intent 
                FROM inference_snapshots 
                ORDER BY created_at DESC LIMIT 1
            """)).fetchone()
            
        results['phase1'] = {
            'status': 'PASS' if cc_count > 0 else 'FAIL',
            'cc_count': cc_count,
            'latest_cc': dict(latest_cc._asdict()) if latest_cc else None
        }
        print(f"✅ CC Count: {cc_count}, Latest: {latest_cc.cc_id if latest_cc else 'None'}")
    except Exception as e:
        results['phase1'] = {'status': 'ERROR', 'error': str(e)}
        print(f"❌ Error: {e}")
    
    # Phase 3: Test Replay API with real CC ID
    print("\n🔄 Phase 3: Replay & Debug Validation")
    if results['phase1']['status'] == 'PASS' and results['phase1']['latest_cc']:
        cc_id = results['phase1']['latest_cc']['cc_id']
        try:
            response = requests.get(f"{base_url}/api/replay/{cc_id}", timeout=5)
            results['phase3'] = {
                'status': 'PASS' if response.status_code == 200 else 'FAIL',
                'status_code': response.status_code,
                'has_replay_data': 'replay_analysis' in response.text if response.status_code == 200 else False
            }
            print(f"✅ Replay API: {response.status_code}, CC: {cc_id}")
        except Exception as e:
            results['phase3'] = {'status': 'ERROR', 'error': str(e)}
            print(f"❌ Replay Error: {e}")
    else:
        results['phase3'] = {'status': 'SKIP', 'reason': 'No CC data available'}
        print("⚠️ Skipped - No CC data")
    
    # Phase 4: Enhanced Monitoring
    print("\n📊 Phase 4: Enhanced Monitoring Validation")
    try:
        health_resp = requests.get(f"{base_url}/api/monitoring/health", timeout=5)
        metrics_resp = requests.get(f"{base_url}/api/monitoring/metrics", timeout=5)
        
        results['phase4'] = {
            'status': 'PASS' if health_resp.status_code == 200 and metrics_resp.status_code == 200 else 'FAIL',
            'health_status': health_resp.status_code,
            'metrics_status': metrics_resp.status_code,
            'system_health': json.loads(health_resp.text).get('overall_health') if health_resp.status_code == 200 else None
        }
        print(f"✅ Health: {health_resp.status_code}, Metrics: {metrics_resp.status_code}")
    except Exception as e:
        results['phase4'] = {'status': 'ERROR', 'error': str(e)}
        print(f"❌ Monitoring Error: {e}")
    
    # Phase 5: Production Blast
    print("\n🚀 Phase 5: Production Blast Validation")
    try:
        prod_resp = requests.get(f"{base_url}/api/production/status", timeout=10)
        results['phase5'] = {
            'status': 'PASS' if prod_resp.status_code == 200 else 'FAIL',
            'status_code': prod_resp.status_code,
            'deployment_ready': json.loads(prod_resp.text).get('deployment_ready') if prod_resp.status_code == 200 else False
        }
        print(f"✅ Production Status: {prod_resp.status_code}")
    except Exception as e:
        results['phase5'] = {'status': 'ERROR', 'error': str(e)}
        print(f"❌ Production Error: {e}")
    
    # Final Summary
    print("\n" + "="*50)
    print("🎯 FINAL VALIDATION SUMMARY")
    print("="*50)
    
    passed_phases = sum(1 for phase in results.values() if phase['status'] == 'PASS')
    total_phases = len(results)
    
    print(f"Phases Passed: {passed_phases}/{total_phases}")
    for phase_name, result in results.items():
        status_icon = "✅" if result['status'] == 'PASS' else "❌" if result['status'] == 'ERROR' else "⚠️"
        print(f"{status_icon} {phase_name.upper()}: {result['status']}")
    
    if passed_phases == total_phases:
        print("\n🎉 ALL PHASES OPERATIONAL - CC SYSTEM COMPLETE!")
        return True
    else:
        print(f"\n⚠️ {total_phases - passed_phases} phases need attention")
        return False

if __name__ == "__main__":
    success = test_all_phases()
    exit(0 if success else 1)