"""
Phase 2 Integration Test Suite for PCA Overlay System
Tests end-to-end integration before 100% live deployment
"""

import json
import os
from datetime import datetime
from unittest.mock import MagicMock, patch

# Set test environment
os.environ['PCA_OVERLAY_ENABLED'] = 'true'
os.environ['PCA_MODE'] = 'SHADOW'  # Start with SHADOW for safety
os.environ['SHOW_AUDIT_UI'] = 'true'
os.environ['ENABLE_RULES'] = 'true'
os.environ['USE_PRECEDENCE'] = 'true'

from app import app
from routes.pca_api import pca_api
from routes.pca_ui import pca_ui
from utils.canonical_command import CanonicalCommand, CCSlots
from utils.multi_item_parser import multi_item_parser
from utils.pca_feature_flags import pca_feature_flags
from utils.precedence_engine import precedence_engine


class TestPhase2Integration:
    """Phase 2: End-to-End Integration Testing"""
    
    def setup_method(self):
        """Setup for each test"""
        self.app = app
        self.client = app.test_client()
        
        # Register blueprints if not already registered
        if 'pca_api' not in app.blueprints:
            app.register_blueprint(pca_api)
        if 'pca_ui' not in app.blueprints:
            app.register_blueprint(pca_ui)
        
        pca_feature_flags.refresh_flags()
        precedence_engine.clear_cache()
        
    def teardown_method(self):
        """Cleanup after each test"""
        precedence_engine.clear_cache()
        
    # A. API Integration Tests
    def test_a1_api_rule_creation(self):
        """A1: API rule creation works end-to-end"""
        rule_data = {
            'rule_name': 'Test Coffee Rule',
            'merchant_pattern': 'starbucks',
            'category': 'coffee',
            'scope': 'future_only'
        }
        
        response = self.client.post('/api/rules/create',
                                  data=json.dumps(rule_data),
                                  content_type='application/json')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] == True
        assert 'rule_id' in data
        assert 'preview_count' in data
        
        print("✅ A1: API rule creation works end-to-end")
        
    def test_a2_api_correction_creation(self):
        """A2: API correction creation works end-to-end"""
        correction_data = {
            'tx_id': 'test_tx_123',
            'category': 'entertainment',
            'reason': 'Test correction'
        }
        
        response = self.client.post('/api/corrections/create',
                                  data=json.dumps(correction_data),
                                  content_type='application/json')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] == True
        assert 'correction_id' in data
        
        print("✅ A2: API correction creation works end-to-end")
        
    def test_a3_api_effective_transaction(self):
        """A3: API effective transaction retrieval works"""
        response = self.client.get('/api/transactions/test_tx_123/effective')
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'tx_id' in data
        assert 'original' in data
        assert 'effective' in data
        assert 'source' in data
        
        print("✅ A3: API effective transaction retrieval works")
        
    # B. UI Integration Tests
    def test_b1_rule_manager_page(self):
        """B1: Rule manager page loads correctly"""
        response = self.client.get('/rules')
        
        assert response.status_code == 200
        assert b'Automatic Categorization Rules' in response.data
        assert b'Create New Rule' in response.data
        
        print("✅ B1: Rule manager page loads correctly")
        
    def test_b2_transaction_audit_page(self):
        """B2: Transaction audit page loads correctly"""
        response = self.client.get('/transactions/test_tx_123/audit')
        
        assert response.status_code == 200
        assert b'Transaction Audit' in response.data
        assert b'Original vs Effective' in response.data
        
        print("✅ B2: Transaction audit page loads correctly")
        
    def test_b3_pca_dashboard_page(self):
        """B3: PCA dashboard page loads correctly"""
        response = self.client.get('/dashboard/pca')
        
        assert response.status_code == 200
        assert b'PCA Overlay System Dashboard' in response.data
        assert b'System Status' in response.data
        
        print("✅ B3: PCA dashboard page loads correctly")
        
    # C. Message Flow Integration Tests
    def test_c1_single_item_message_flow(self):
        """C1: Single item message processes correctly"""
        # Create CC for single expense
        cc = CanonicalCommand(
            cc_id="test_cc_single",
            user_id="test_user",
            intent="LOG_EXPENSE",
            confidence=0.9,
            decision="AUTO_APPLY",
            source_text="lunch 100"
        )
        cc.slots = CCSlots(
            amount=100,
            category="food",
            merchant_text="lunch"
        )
        
        # Verify CC structure
        assert cc.schema_version == "pca-v1.1"
        assert cc.schema_hash == "pca-v1.1-cc-keys"
        
        # Test precedence resolution
        result = precedence_engine.get_effective_view(
            user_id="test_user",
            tx_id="test_tx_single",
            raw_expense={
                'amount': 100,
                'category': 'food',
                'merchant_text': 'lunch'
            }
        )
        
        assert result.source == 'raw'  # No overlays yet
        assert result.amount == 100
        assert result.category == 'food'
        
        print("✅ C1: Single item message processes correctly")
        
    def test_c2_multi_item_message_flow(self):
        """C2: Multi-item message splits and processes correctly"""
        text = "lunch 100, coffee 50, taxi 75"
        
        # Test detection
        assert multi_item_parser.detect_multi_item(text) == True
        
        # Test parsing
        items = multi_item_parser.parse_items(text)
        assert len(items) == 3
        assert items[0]['amount'] == 100
        assert items[0]['category'] == 'food'
        
        # Test CC splitting
        base_cc = CanonicalCommand(
            cc_id="test_cc_multi",
            user_id="test_user",
            intent="LOG_EXPENSE",
            confidence=0.85,
            decision="AUTO_APPLY",
            source_text=text
        )
        base_cc.slots = CCSlots(currency="BDT")
        
        commands = multi_item_parser.split_into_commands(base_cc, items)
        assert len(commands) == 3
        assert commands[0].cc_id == "test_cc_multi_item_0"
        assert commands[1].cc_id == "test_cc_multi_item_1"
        assert commands[2].cc_id == "test_cc_multi_item_2"
        
        print("✅ C2: Multi-item message splits and processes correctly")
        
    # D. Shadow Mode Testing
    def test_d1_shadow_mode_behavior(self):
        """D1: Shadow mode logs but doesn't write overlays"""
        os.environ['PCA_MODE'] = 'SHADOW'
        pca_feature_flags.refresh_flags()
        
        assert pca_feature_flags.is_shadow_mode() == True
        assert pca_feature_flags.is_overlay_active() == False
        
        # API should still work but not write to DB
        rule_data = {
            'rule_name': 'Shadow Test Rule',
            'merchant_pattern': 'test',
            'category': 'test',
            'scope': 'future_only'
        }
        
        response = self.client.post('/api/rules/create',
                                  data=json.dumps(rule_data),
                                  content_type='application/json')
        
        # Should fail gracefully in shadow mode
        assert response.status_code == 503  # Service unavailable
        
        print("✅ D1: Shadow mode logs but doesn't write overlays")
        
    def test_d2_dryrun_mode_behavior(self):
        """D2: Dryrun mode writes raw only"""
        os.environ['PCA_MODE'] = 'DRYRUN'
        pca_feature_flags.refresh_flags()
        
        assert pca_feature_flags.is_dryrun_mode() == True
        assert pca_feature_flags.is_overlay_active() == False
        
        # Should not create overlays
        response = self.client.post('/api/rules/create',
                                  data=json.dumps({'category': 'test', 'merchant_pattern': 'test'}),
                                  content_type='application/json')
        
        assert response.status_code == 503
        
        print("✅ D2: Dryrun mode writes raw only")
        
    def test_d3_on_mode_behavior(self):
        """D3: ON mode allows full overlay operations"""
        os.environ['PCA_MODE'] = 'ON'
        pca_feature_flags.refresh_flags()
        
        assert pca_feature_flags.is_overlay_active() == True
        assert pca_feature_flags.should_enable_rules() == True
        assert pca_feature_flags.should_show_audit_ui() == True
        
        print("✅ D3: ON mode allows full overlay operations")
        
    # E. Database Integration Tests
    def test_e1_precedence_with_mock_data(self):
        """E1: Precedence engine works with mock database data"""
        with patch('utils.precedence_engine.db') as mock_db:
            # Mock correction
            mock_correction = MagicMock()
            mock_correction.fields_json = {'category': 'entertainment'}
            mock_correction.id = 1
            mock_correction.created_at = datetime.now()
            
            mock_db.session.query.return_value.filter_by.return_value.order_by.return_value.first.return_value = mock_correction
            
            result = precedence_engine.get_effective_view(
                user_id="test_user",
                tx_id="test_tx",
                raw_expense={'amount': 100, 'category': 'food'}
            )
            
            assert result.source == 'correction'
            assert result.category == 'entertainment'
            
        print("✅ E1: Precedence engine works with mock database data")
        
    # F. Error Handling Tests
    def test_f1_api_error_handling(self):
        """F1: API handles errors gracefully"""
        # Test invalid rule creation
        response = self.client.post('/api/rules/create',
                                  data=json.dumps({}),  # Missing required fields
                                  content_type='application/json')
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        
        print("✅ F1: API handles errors gracefully")
        
    def test_f2_ui_error_handling(self):
        """F2: UI handles missing data gracefully"""
        # Test non-existent transaction audit
        response = self.client.get('/transactions/nonexistent/audit')
        
        # Should redirect with flash message (or handle gracefully)
        assert response.status_code in [200, 302]  # Either render or redirect
        
        print("✅ F2: UI handles missing data gracefully")
        
    # G. Performance Integration Tests
    def test_g1_concurrent_precedence_requests(self):
        """G1: Precedence engine handles concurrent requests"""
        import threading
        
        results = []
        
        def make_request():
            result = precedence_engine.get_effective_view(
                user_id="test_user",
                tx_id="concurrent_test",
                raw_expense={'amount': 100, 'category': 'food'}
            )
            results.append(result)
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # All results should be consistent
        assert len(results) == 5
        for result in results:
            assert result.amount == 100
            assert result.category == 'food'
        
        print("✅ G1: Precedence engine handles concurrent requests")

def run_phase2_integration():
    """Run Phase 2 Integration tests"""
    print("\n" + "="*60)
    print("PHASE 2 UAT: End-to-End Integration")
    print("="*60)
    
    test_suite = TestPhase2Integration()
    
    # Run all tests
    test_methods = [
        test_suite.test_a1_api_rule_creation,
        test_suite.test_a2_api_correction_creation,
        test_suite.test_a3_api_effective_transaction,
        test_suite.test_b1_rule_manager_page,
        test_suite.test_b2_transaction_audit_page,
        test_suite.test_b3_pca_dashboard_page,
        test_suite.test_c1_single_item_message_flow,
        test_suite.test_c2_multi_item_message_flow,
        test_suite.test_d1_shadow_mode_behavior,
        test_suite.test_d2_dryrun_mode_behavior,
        test_suite.test_d3_on_mode_behavior,
        test_suite.test_e1_precedence_with_mock_data,
        test_suite.test_f1_api_error_handling,
        test_suite.test_f2_ui_error_handling,
        test_suite.test_g1_concurrent_precedence_requests
    ]
    
    passed = 0
    failed = 0
    
    for test_method in test_methods:
        test_suite.setup_method()
        try:
            test_method()
            passed += 1
        except Exception as e:
            print(f"❌ {test_method.__name__}: {str(e)}")
            failed += 1
        finally:
            test_suite.teardown_method()
    
    print("\n" + "="*60)
    print(f"PHASE 2 UAT RESULTS: {passed} PASSED, {failed} FAILED")
    print("="*60)
    
    return failed == 0

if __name__ == "__main__":
    success = run_phase2_integration()
    exit(0 if success else 1)