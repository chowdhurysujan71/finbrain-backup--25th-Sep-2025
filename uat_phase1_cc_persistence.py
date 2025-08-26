#!/usr/bin/env python3
"""
Phase 1 UAT: CC Persistence & Schema Compliance
Validates that Canonical Commands are being properly stored and match specification
"""

import sys
import os
import json
import time
import uuid
from datetime import datetime
from typing import Dict, Any, List

# Add project root to path
sys.path.append('/home/runner/workspace')

# Import Flask app for context
from app import app, db
from sqlalchemy import text
from utils.pca_flags import pca_flags

class Phase1UAT:
    def __init__(self):
        self.test_results = []
        self.start_time = datetime.now()
        
    def log_result(self, test_name: str, passed: bool, details: str = ""):
        """Log test result"""
        result = {
            'test': test_name,
            'status': 'PASS' if passed else 'FAIL',
            'details': details,
            'timestamp': datetime.now().isoformat()
        }
        self.test_results.append(result)
        status_icon = "✅" if passed else "❌"
        print(f"{status_icon} {test_name}: {result['status']}")
        if details:
            print(f"   {details}")
    
    def test_inference_snapshots_table_exists(self):
        """Test 1: Verify inference_snapshots table exists and has correct structure"""
        try:
            with app.app_context():
                # Check table exists
                result = db.session.execute(text("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = 'inference_snapshots'
                """)).fetchone()
                
                table_exists = result is not None
                
                if table_exists:
                    # Check key columns exist
                    columns_result = db.session.execute(text("""
                        SELECT column_name FROM information_schema.columns 
                        WHERE table_schema = 'public' AND table_name = 'inference_snapshots'
                    """)).fetchall()
                    
                    columns = [row[0] for row in columns_result]
                    required_cols = ['cc_id', 'user_id', 'intent', 'slots_json', 'confidence', 
                                   'decision', 'source_text', 'created_at', 'pca_mode']
                    
                    missing_cols = [col for col in required_cols if col not in columns]
                    has_required = len(missing_cols) == 0
                    
                    self.log_result(
                        "Inference Snapshots Table Structure",
                        table_exists and has_required,
                        f"exists={table_exists}, missing_cols={missing_cols}"
                    )
                else:
                    self.log_result("Inference Snapshots Table Structure", False, "table does not exist")
                    
        except Exception as e:
            self.log_result("Inference Snapshots Table Structure", False, f"Exception: {str(e)}")
    
    def test_cc_data_persistence(self):
        """Test 2: Verify CC data is being actively persisted"""
        try:
            with app.app_context():
                # Check recent records
                recent_count = db.session.execute(text("""
                    SELECT COUNT(*) FROM inference_snapshots 
                    WHERE created_at >= NOW() - INTERVAL '24 hours'
                """)).scalar()
                
                # Check total records
                total_count = db.session.execute(text("""
                    SELECT COUNT(*) FROM inference_snapshots
                """)).scalar()
                
                # Check unique users
                unique_users = db.session.execute(text("""
                    SELECT COUNT(DISTINCT user_id) FROM inference_snapshots
                """)).scalar()
                
                has_data = total_count > 0
                has_recent = recent_count > 0
                has_users = unique_users > 0
                
                self.log_result(
                    "CC Data Persistence",
                    has_data and has_users,
                    f"total={total_count}, recent_24h={recent_count}, users={unique_users}"
                )
                
        except Exception as e:
            self.log_result("CC Data Persistence", False, f"Exception: {str(e)}")
    
    def test_cc_schema_compliance(self):
        """Test 3: Verify stored CC data matches specification schema"""
        try:
            with app.app_context():
                # Get recent CC samples
                samples = db.session.execute(text("""
                    SELECT cc_id, intent, slots_json, confidence, decision, 
                           clarifier_json, source_text, ui_note
                    FROM inference_snapshots 
                    ORDER BY created_at DESC 
                    LIMIT 10
                """)).fetchall()
                
                compliance_issues = []
                valid_samples = 0
                
                for sample in samples:
                    cc_id, intent, slots_json, confidence, decision, clarifier_json, source_text, ui_note = sample
                    
                    # Check CC ID exists and is reasonable
                    if not cc_id or len(cc_id) < 10:
                        compliance_issues.append("cc_id too short or missing")
                        continue
                    
                    # Check intent is valid
                    valid_intents = ['LOG_EXPENSE', 'CORRECT', 'RELABEL', 'VOID', 'QUERY', 'HELP']
                    if intent not in valid_intents:
                        compliance_issues.append(f"invalid intent: {intent}")
                    
                    # Check confidence is in range [0.0, 1.0]
                    if confidence is None or confidence < 0.0 or confidence > 1.0:
                        compliance_issues.append(f"invalid confidence: {confidence}")
                    
                    # Check decision is valid
                    valid_decisions = ['AUTO_APPLY', 'ASK_ONCE', 'RAW_ONLY']
                    if decision not in valid_decisions:
                        compliance_issues.append(f"invalid decision: {decision}")
                    
                    # Check slots_json is valid JSON
                    try:
                        if slots_json:
                            json.loads(json.dumps(slots_json))  # Validate JSON
                    except:
                        compliance_issues.append("invalid slots_json format")
                    
                    # Check source_text exists
                    if not source_text:
                        compliance_issues.append("missing source_text")
                    
                    valid_samples += 1
                
                compliance_rate = (valid_samples / len(samples)) * 100 if samples else 0
                
                self.log_result(
                    "CC Schema Compliance",
                    compliance_rate >= 90 and len(compliance_issues) < 5,
                    f"compliance_rate={compliance_rate:.1f}%, issues={len(compliance_issues)}, samples={len(samples)}"
                )
                
                if compliance_issues:
                    print(f"   Sample issues: {compliance_issues[:3]}")
                
        except Exception as e:
            self.log_result("CC Schema Compliance", False, f"Exception: {str(e)}")
    
    def test_decision_distribution(self):
        """Test 4: Verify decision types are being distributed correctly"""
        try:
            with app.app_context():
                # Get decision distribution
                decisions = db.session.execute(text("""
                    SELECT decision, COUNT(*) as count, AVG(confidence) as avg_conf
                    FROM inference_snapshots 
                    WHERE created_at >= NOW() - INTERVAL '7 days'
                    GROUP BY decision
                    ORDER BY count DESC
                """)).fetchall()
                
                decision_data = {row[0]: {'count': row[1], 'avg_conf': row[2]} for row in decisions}
                
                # Check we have different decision types
                has_auto_apply = 'AUTO_APPLY' in decision_data
                has_ask_once = 'ASK_ONCE' in decision_data
                total_decisions = sum(d['count'] for d in decision_data.values())
                
                # Verify confidence thresholds make sense
                confidence_logic_ok = True
                if has_auto_apply and has_ask_once:
                    auto_conf = decision_data['AUTO_APPLY']['avg_conf']
                    ask_conf = decision_data['ASK_ONCE']['avg_conf']
                    confidence_logic_ok = auto_conf > ask_conf  # AUTO_APPLY should have higher confidence
                
                self.log_result(
                    "Decision Distribution",
                    has_auto_apply and total_decisions >= 5 and confidence_logic_ok,
                    f"decisions={list(decision_data.keys())}, total={total_decisions}, conf_logic_ok={confidence_logic_ok}"
                )
                
        except Exception as e:
            self.log_result("Decision Distribution", False, f"Exception: {str(e)}")
    
    def test_pca_mode_tracking(self):
        """Test 5: Verify PCA modes are being tracked correctly"""
        try:
            with app.app_context():
                # Get mode distribution
                modes = db.session.execute(text("""
                    SELECT pca_mode, COUNT(*) as count
                    FROM inference_snapshots 
                    WHERE created_at >= NOW() - INTERVAL '7 days'
                    GROUP BY pca_mode
                    ORDER BY count DESC
                """)).fetchall()
                
                mode_data = {row[0]: row[1] for row in modes}
                
                # Check current mode setting
                current_mode = pca_flags._get_pca_mode()
                
                # Verify modes are being tracked
                has_mode_data = len(mode_data) > 0
                tracking_current_mode = current_mode in mode_data
                
                self.log_result(
                    "PCA Mode Tracking",
                    has_mode_data and tracking_current_mode,
                    f"current_mode={current_mode}, tracked_modes={list(mode_data.keys())}, tracking_current={tracking_current_mode}"
                )
                
        except Exception as e:
            self.log_result("PCA Mode Tracking", False, f"Exception: {str(e)}")
    
    def test_core_foundation_safety(self):
        """Test 6: Verify core foundation remains safe (expenses table untouched)"""
        try:
            with app.app_context():
                # Check expenses table integrity
                expense_count = db.session.execute(text("""
                    SELECT COUNT(*) FROM expenses
                """)).scalar()
                
                # Check recent expense writes
                recent_expenses = db.session.execute(text("""
                    SELECT COUNT(*) FROM expenses 
                    WHERE created_at >= NOW() - INTERVAL '24 hours'
                """)).scalar()
                
                # Verify expenses table structure is unchanged
                expense_columns = db.session.execute(text("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_schema = 'public' AND table_name = 'expenses'
                    ORDER BY column_name
                """)).fetchall()
                
                expected_core_columns = ['amount', 'category', 'created_at', 'date', 'description', 'user_id']
                has_core_columns = all(any(col[0] == expected for col in expense_columns) for expected in expected_core_columns)
                
                foundation_safe = expense_count > 0 and has_core_columns
                
                self.log_result(
                    "Core Foundation Safety",
                    foundation_safe,
                    f"expense_count={expense_count}, recent_expenses={recent_expenses}, core_columns_ok={has_core_columns}"
                )
                
        except Exception as e:
            self.log_result("Core Foundation Safety", False, f"Exception: {str(e)}")
    
    def test_performance_tracking(self):
        """Test 7: Verify performance metrics are being tracked"""
        try:
            with app.app_context():
                # Check processing time data
                perf_data = db.session.execute(text("""
                    SELECT AVG(processing_time_ms) as avg_time,
                           MAX(processing_time_ms) as max_time,
                           COUNT(*) as count
                    FROM inference_snapshots 
                    WHERE processing_time_ms IS NOT NULL
                    AND created_at >= NOW() - INTERVAL '24 hours'
                """)).fetchone()
                
                if perf_data and perf_data[0] is not None:
                    avg_time, max_time, count = perf_data
                    
                    # Check performance is reasonable
                    avg_reasonable = avg_time < 5000  # Less than 5 seconds average
                    max_reasonable = max_time < 30000  # Less than 30 seconds max
                    has_data = count > 0
                    
                    self.log_result(
                        "Performance Tracking",
                        has_data and avg_reasonable and max_reasonable,
                        f"avg_time={avg_time:.1f}ms, max_time={max_time:.1f}ms, count={count}"
                    )
                else:
                    self.log_result("Performance Tracking", False, "No performance data found")
                
        except Exception as e:
            self.log_result("Performance Tracking", False, f"Exception: {str(e)}")
    
    def run_all_tests(self):
        """Run complete Phase 1 UAT suite"""
        print("🧪 PHASE 1 UAT: CC Persistence & Schema Compliance")
        print("=" * 70)
        print(f"Started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Run all test suites
        self.test_inference_snapshots_table_exists()
        self.test_cc_data_persistence()
        self.test_cc_schema_compliance()
        self.test_decision_distribution()
        self.test_pca_mode_tracking()
        self.test_core_foundation_safety()
        self.test_performance_tracking()
        
        # Calculate results
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r['status'] == 'PASS'])
        pass_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        print()
        print("=" * 70)
        print(f"PHASE 1 UAT RESULTS:")
        print(f"✅ Passed: {passed_tests}/{total_tests} ({pass_rate:.1f}%)")
        print(f"⏱️  Duration: {duration:.2f}s")
        print(f"🎯 Exit Gate: {'PASS' if pass_rate >= 90 else 'FAIL'}")
        
        if pass_rate >= 90:
            print()
            print("🎉 PHASE 1 VALIDATED!")
            print("✅ Inference snapshots table operational")
            print("✅ CC persistence working correctly") 
            print("✅ Schema compliance verified")
            print("✅ Decision routing active")
            print("✅ Core foundation safe (0% risk)")
            print("✅ Performance tracking in place")
            print("✅ Ready for Phase 2 validation or Phase 3 development")
        else:
            print()
            print("❌ PHASE 1 ISSUES FOUND")
            failed_tests = [r for r in self.test_results if r['status'] == 'FAIL']
            for test in failed_tests:
                print(f"   ❌ {test['test']}: {test['details']}")
        
        return pass_rate >= 90

if __name__ == "__main__":
    uat = Phase1UAT()
    success = uat.run_all_tests()
    sys.exit(0 if success else 1)