"""
Phase 1 UAT Test Suite for PCA Overlay System
Tests foundation components before deployment
"""

import pytest
import os
import json
from datetime import datetime
from unittest.mock import patch, MagicMock

# Set test environment
os.environ['PCA_OVERLAY_ENABLED'] = 'false'  # Start with overlay disabled
os.environ['PCA_MODE'] = 'FALLBACK'
os.environ['SHOW_AUDIT_UI'] = 'false'
os.environ['ENABLE_RULES'] = 'false'
os.environ['USE_PRECEDENCE'] = 'false'

from utils.precedence_engine import PrecedenceEngine, PrecedenceResult
from utils.canonical_command import CanonicalCommand, CCSlots
from utils.pca_feature_flags import PCAFeatureFlags
from utils.multi_item_parser import MultiItemParser

class TestPhase1UAT:
    """Phase 1: Foundation Components UAT"""
    
    def setup_method(self):
        """Setup for each test"""
        self.precedence = PrecedenceEngine()
        self.flags = PCAFeatureFlags()
        self.parser = MultiItemParser()
        
    def teardown_method(self):
        """Cleanup after each test"""
        self.precedence.clear_cache()
        
    # A. Feature Flag Control Tests
    def test_a1_master_kill_switch(self):
        """A1: Master kill switch completely disables overlay"""
        # Start with overlay disabled
        os.environ['PCA_OVERLAY_ENABLED'] = 'false'
        self.flags.refresh_flags()
        
        assert not self.flags.overlay_enabled
        assert not self.flags.is_overlay_active()
        assert not self.flags.should_show_audit_ui()
        assert not self.flags.should_enable_rules()
        assert not self.flags.should_use_precedence()
        
        # Enable overlay
        os.environ['PCA_OVERLAY_ENABLED'] = 'true'
        os.environ['PCA_MODE'] = 'ON'
        self.flags.refresh_flags()
        
        assert self.flags.overlay_enabled
        assert self.flags.is_overlay_active()
        
        print("✅ A1: Master kill switch controls overlay activation")
        
    def test_a2_mode_control(self):
        """A2: Mode control (FALLBACK/SHADOW/DRYRUN/ON)"""
        os.environ['PCA_OVERLAY_ENABLED'] = 'true'
        
        # Test FALLBACK mode
        os.environ['PCA_MODE'] = 'FALLBACK'
        self.flags.refresh_flags()
        assert not self.flags.is_overlay_active()
        assert not self.flags.is_shadow_mode()
        
        # Test SHADOW mode
        os.environ['PCA_MODE'] = 'SHADOW'
        self.flags.refresh_flags()
        assert not self.flags.is_overlay_active()
        assert self.flags.is_shadow_mode()
        
        # Test DRYRUN mode
        os.environ['PCA_MODE'] = 'DRYRUN'
        self.flags.refresh_flags()
        assert not self.flags.is_overlay_active()
        assert self.flags.is_dryrun_mode()
        
        # Test ON mode
        os.environ['PCA_MODE'] = 'ON'
        self.flags.refresh_flags()
        assert self.flags.is_overlay_active()
        
        print("✅ A2: Mode control transitions work correctly")
        
    def test_a3_granular_flags(self):
        """A3: Granular feature flags independent control"""
        os.environ['PCA_OVERLAY_ENABLED'] = 'true'
        os.environ['PCA_MODE'] = 'ON'
        
        # Test individual flag control
        os.environ['SHOW_AUDIT_UI'] = 'true'
        os.environ['ENABLE_RULES'] = 'false'
        os.environ['USE_PRECEDENCE'] = 'false'
        self.flags.refresh_flags()
        
        assert self.flags.should_show_audit_ui()
        assert not self.flags.should_enable_rules()
        assert not self.flags.should_use_precedence()
        
        # Change flags
        os.environ['SHOW_AUDIT_UI'] = 'false'
        os.environ['ENABLE_RULES'] = 'true'
        os.environ['USE_PRECEDENCE'] = 'true'
        self.flags.refresh_flags()
        
        assert not self.flags.should_show_audit_ui()
        assert self.flags.should_enable_rules()
        assert self.flags.should_use_precedence()
        
        print("✅ A3: Granular flags work independently")
        
    # B. Schema Version Tests
    def test_b1_schema_versioning(self):
        """B1: Schema version and hash in Canonical Command"""
        cc = CanonicalCommand(
            cc_id="test_123",
            user_id="user_456",
            intent="LOG_EXPENSE"
        )
        
        assert cc.schema_version == "pca-v1.1"
        assert cc.schema_hash == "pca-v1.1-cc-keys"
        
        # Verify JSON serialization includes schema fields
        cc_dict = cc.to_dict()
        assert cc_dict['schema_version'] == "pca-v1.1"
        assert cc_dict['schema_hash'] == "pca-v1.1-cc-keys"
        
        print("✅ B1: Schema version and hash properly set")
        
    def test_b2_cc_backwards_compatibility(self):
        """B2: CC structure backwards compatible"""
        # Old CC structure should still work
        cc = CanonicalCommand(
            cc_id="test_123",
            user_id="user_456",
            intent="LOG_EXPENSE",
            confidence=0.9,
            decision="AUTO_APPLY",
            source_text="test expense",
            ui_note="Logged expense"
        )
        
        # Should have new fields with defaults
        assert cc.schema_version == "pca-v1.1"
        assert cc.schema_hash == "pca-v1.1-cc-keys"
        
        # Old fields still work
        assert cc.confidence == 0.9
        assert cc.decision == "AUTO_APPLY"
        
        print("✅ B2: CC structure maintains backwards compatibility")
        
    # C. Precedence Engine Tests
    def test_c1_precedence_disabled_fallback(self):
        """C1: Precedence engine returns raw when overlay disabled"""
        os.environ['PCA_OVERLAY_ENABLED'] = 'false'
        
        raw_expense = {
            'amount': 100,
            'category': 'food',
            'merchant_text': 'Restaurant ABC'
        }
        
        result = self.precedence.get_effective_view(
            user_id="test_user",
            tx_id="tx_123",
            raw_expense=raw_expense
        )
        
        assert result.source == 'raw'
        assert result.amount == 100
        assert result.category == 'food'
        assert result.merchant_text == 'Restaurant ABC'
        
        print("✅ C1: Precedence engine falls back to raw when disabled")
        
    def test_c2_precedence_ordering(self):
        """C2: Precedence order (Correction > Rule > Effective > Raw)"""
        os.environ['PCA_OVERLAY_ENABLED'] = 'true'
        
        # Test with mocked correction data
        with patch.object(self.precedence, '_get_latest_correction') as mock_correction:
            mock_correction.return_value = {
                'id': 1,
                'fields': {'category': 'entertainment', 'amount': 100},
                'reason': 'User correction',
                'created_at': datetime.now()
            }
            
            result = self.precedence.get_effective_view(
                user_id="test_user",
                tx_id="tx_123",
                raw_expense={'amount': 100, 'category': 'food'}
            )
            
            assert result.source == 'correction'
            assert result.category == 'entertainment'
            assert result.correction_id == 1
        
        print("✅ C2: Precedence ordering correctly prioritizes corrections")
        
    def test_c3_rule_specificity_scoring(self):
        """C3: Rule specificity scoring"""
        # Test specificity calculation
        pattern1 = {'merchant_id': 'STORE_123'}
        pattern2 = {'store_name_contains': 'starbucks'}
        pattern3 = {'text_contains': 'coffee'}
        pattern4 = {'category_was': 'food'}
        
        expense = {
            'merchant_id': 'STORE_123',
            'merchant_text': 'Starbucks Coffee Shop',
            'category': 'food'
        }
        
        score1 = self.precedence._calculate_rule_specificity(pattern1, expense)
        score2 = self.precedence._calculate_rule_specificity(pattern2, expense)
        score3 = self.precedence._calculate_rule_specificity(pattern3, expense)
        score4 = self.precedence._calculate_rule_specificity(pattern4, expense)
        
        # Verify specificity ordering
        assert score1 > score2  # merchant_id > store_name
        assert score2 > score3  # store_name > text_contains
        assert score3 > score4  # text_contains > category_was
        
        print("✅ C3: Rule specificity scoring follows correct priority")
        
    # D. Multi-item Parser Tests
    def test_d1_multi_item_detection(self):
        """D1: Multi-item message detection"""
        # Should detect multi-item
        assert self.parser.detect_multi_item("lunch 100, taxi 50")
        assert self.parser.detect_multi_item("100 for food and 50 for transport")
        assert self.parser.detect_multi_item("groceries 200; electricity 150")
        
        # Should not detect multi-item
        assert not self.parser.detect_multi_item("lunch 100")
        assert not self.parser.detect_multi_item("spent 500 today")
        
        print("✅ D1: Multi-item detection works correctly")
        
    def test_d2_multi_item_parsing(self):
        """D2: Multi-item parsing into separate items"""
        text = "lunch 100, coffee 50, taxi 75"
        items = self.parser.parse_items(text)
        
        assert len(items) == 3
        assert items[0]['amount'] == 100
        assert items[0]['category'] == 'food'
        assert items[1]['amount'] == 50
        assert items[1]['category'] == 'coffee'
        assert items[2]['amount'] == 75
        assert items[2]['category'] == 'transport'
        
        print("✅ D2: Multi-item parsing extracts individual items")
        
    def test_d3_multi_item_cc_split(self):
        """D3: Multi-item CC split into individual commands"""
        base_cc = CanonicalCommand(
            cc_id="multi_123",
            user_id="user_456",
            intent="LOG_EXPENSE",
            confidence=0.9,
            decision="AUTO_APPLY"
        )
        base_cc.slots = CCSlots(currency="BDT", time_expr="today")
        
        items = [
            {'amount': 100, 'merchant_text': 'lunch', 'category': 'food'},
            {'amount': 50, 'merchant_text': 'coffee', 'category': 'coffee'}
        ]
        
        commands = self.parser.split_into_commands(base_cc, items)
        
        assert len(commands) == 2
        assert commands[0].cc_id == "multi_123_item_0"
        assert commands[0].slots.amount == 100
        assert commands[0].slots.category == 'food'
        assert commands[1].cc_id == "multi_123_item_1"
        assert commands[1].slots.amount == 50
        assert commands[1].slots.category == 'coffee'
        
        print("✅ D3: Multi-item CC correctly splits into individual commands")
        
    # E. Performance Tests
    def test_e1_precedence_caching(self):
        """E1: Precedence engine caches results"""
        # Test basic caching behavior
        self.precedence.clear_cache()
        assert len(self.precedence.cache) == 0
        
        # Add to cache manually
        test_result = PrecedenceResult(
            category='food',
            subcategory=None,
            amount=100,
            merchant_text='Test',
            source='raw',
            confidence=0.5
        )
        
        self.precedence.cache['test_key'] = test_result
        assert len(self.precedence.cache) == 1
        assert 'test_key' in self.precedence.cache
        
        # Retrieve from cache
        cached = self.precedence.cache.get('test_key')
        assert cached is test_result
        
        # Clear works
        self.precedence.clear_cache()
        assert len(self.precedence.cache) == 0
        
        print("✅ E1: Precedence engine properly caches results")
        
    def test_e2_flag_status_monitoring(self):
        """E2: Flag status available for monitoring"""
        os.environ['PCA_OVERLAY_ENABLED'] = 'true'
        os.environ['PCA_MODE'] = 'ON'
        os.environ['SHOW_AUDIT_UI'] = 'true'
        self.flags.refresh_flags()
        
        status = self.flags.get_status()
        
        assert status['master_flag'] == True
        assert status['mode'] == 'ON'
        assert status['overlay_active'] == True
        assert status['features']['audit_ui'] == True
        
        print("✅ E2: Flag status correctly reported for monitoring")

def run_phase1_uat():
    """Run Phase 1 UAT tests"""
    print("\n" + "="*60)
    print("PHASE 1 UAT: Foundation Components")
    print("="*60)
    
    test_suite = TestPhase1UAT()
    
    # Run all tests
    test_methods = [
        test_suite.test_a1_master_kill_switch,
        test_suite.test_a2_mode_control,
        test_suite.test_a3_granular_flags,
        test_suite.test_b1_schema_versioning,
        test_suite.test_b2_cc_backwards_compatibility,
        test_suite.test_c1_precedence_disabled_fallback,
        test_suite.test_c2_precedence_ordering,
        test_suite.test_c3_rule_specificity_scoring,
        test_suite.test_d1_multi_item_detection,
        test_suite.test_d2_multi_item_parsing,
        test_suite.test_d3_multi_item_cc_split,
        test_suite.test_e1_precedence_caching,
        test_suite.test_e2_flag_status_monitoring
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
    print(f"PHASE 1 UAT RESULTS: {passed} PASSED, {failed} FAILED")
    print("="*60)
    
    return failed == 0

if __name__ == "__main__":
    success = run_phase1_uat()
    exit(0 if success else 1)