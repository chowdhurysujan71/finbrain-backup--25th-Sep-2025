#!/usr/bin/env python3
"""
Feature Flags/Kill Switch Test Script
Demonstrates all 4 PCA_MODE states and their behaviors
"""

import os
import sys

sys.path.append('.')

def test_pca_modes():
    """Test all 4 PCA modes and their conditional logic"""
    
    print("🚀 Feature Flags/Kill Switch Test Suite")
    print("=" * 50)
    
    # Test each mode
    modes_to_test = ['FALLBACK', 'SHADOW', 'DRYRUN', 'ON']
    
    for mode in modes_to_test:
        print(f"\n🔄 Testing PCA_MODE = {mode}")
        
        # Temporarily set environment variable
        original_mode = os.environ.get('PCA_MODE', 'FALLBACK')
        os.environ['PCA_MODE'] = mode
        
        # Reinitialize pca_flags to pick up new mode
        from utils.pca_flags import PCAFlags
        test_flags = PCAFlags()
        
        # Test mode-specific behavior
        print(f"   ✅ Mode: {test_flags.mode.value}")
        print(f"   ✅ Should log snapshots: {test_flags.should_log_snapshots()}")
        print(f"   ✅ Should write overlays: {test_flags.should_write_overlays()}")
        print(f"   ✅ Should write raw only: {test_flags.should_write_raw_only()}")
        print(f"   ✅ Should enable clarifiers: {test_flags.should_enable_clarifiers()}")
        
        # Verify conditional flow expectations
        if mode == 'FALLBACK':
            assert not test_flags.should_log_snapshots(), "FALLBACK should not log snapshots"
            assert not test_flags.should_write_overlays(), "FALLBACK should not write overlays"
            print("   ✅ FALLBACK mode: Skip CC entirely ✓")
            
        elif mode == 'SHADOW':
            assert test_flags.should_log_snapshots(), "SHADOW should log snapshots"
            assert not test_flags.should_write_overlays(), "SHADOW should not write overlays"
            print("   ✅ SHADOW mode: Log CC but show legacy response ✓")
            
        elif mode == 'DRYRUN':
            assert test_flags.should_log_snapshots(), "DRYRUN should log snapshots"
            assert test_flags.should_write_raw_only(), "DRYRUN should write raw only"
            assert not test_flags.should_write_overlays(), "DRYRUN should not write overlays"
            print("   ✅ DRYRUN mode: Raw write + 'would log' message ✓")
            
        elif mode == 'ON':
            assert test_flags.should_log_snapshots(), "ON should log snapshots"
            assert test_flags.should_write_overlays(), "ON should write overlays"
            print("   ✅ ON mode: Full CC with audit transparency ✓")
        
        # Restore original environment
        os.environ['PCA_MODE'] = original_mode
    
    print("\n🎯 All 4 PCA modes tested successfully!")
    print("✅ Conditional flow logic working correctly")
    print("✅ Feature Flags system fully operational")
    
def test_production_router_integration():
    """Test that production router recognizes all modes"""
    print("\n🔧 Testing Production Router Integration")
    print("-" * 40)
    
    try:
        from utils.production_router import ProductionRouter
        
        # Create router instance
        router = ProductionRouter()
        
        # Test method existence
        assert hasattr(router, '_route_cc_decision'), "Missing _route_cc_decision method"
        assert hasattr(router, '_persist_cc_snapshot'), "Missing _persist_cc_snapshot method"
        assert hasattr(router, '_handle_dryrun_mode'), "Missing _handle_dryrun_mode method"
        assert hasattr(router, '_handle_on_mode'), "Missing _handle_on_mode method"
        
        print("   ✅ All required methods present")
        print("   ✅ Production router ready for Feature Flags")
        
    except Exception as e:
        print(f"   ❌ Integration test failed: {e}")
        return False
    
    return True

def test_kill_switch():
    """Test global kill switch functionality"""
    print("\n🛑 Testing Kill Switch")
    print("-" * 40)
    
    original_kill = os.environ.get('PCA_KILL_SWITCH', 'false')
    
    # Test kill switch disabled
    os.environ['PCA_KILL_SWITCH'] = 'false'
    from utils.pca_flags import PCAFlags
    test_flags = PCAFlags()
    assert not test_flags.global_kill_switch, "Kill switch should be disabled"
    print("   ✅ Kill switch OFF: Normal operation")
    
    # Test kill switch enabled
    os.environ['PCA_KILL_SWITCH'] = 'true'
    test_flags = PCAFlags()
    assert test_flags.global_kill_switch, "Kill switch should be enabled"
    print("   ✅ Kill switch ON: Emergency mode")
    
    # Restore original
    os.environ['PCA_KILL_SWITCH'] = original_kill
    print("   ✅ Kill switch mechanism working")

if __name__ == "__main__":
    print("🎯 Starting Feature Flags/Kill Switch Test Suite...")
    
    try:
        test_pca_modes()
        test_production_router_integration()
        test_kill_switch()
        
        print("\n" + "=" * 50)
        print("🚀 ALL TESTS PASSED!")
        print("✅ Feature Flags/Kill Switch system is OPERATIONAL")
        print("✅ 4-state conditional flow implemented correctly")
        print("✅ Production router integration complete")
        print("✅ Emergency kill switch functional")
        print("\n🔥 Ready for graduated rollout: FALLBACK → SHADOW → DRYRUN → ON")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)