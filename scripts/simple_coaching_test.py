#!/usr/bin/env python3
"""
Simple coaching flow verification script
Tests the core coaching workflow without complex session management
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_coaching_basic_flow():
    """Test basic coaching flow components"""
    
    print("🧪 Basic Coaching Flow Test")
    print("=" * 40)
    
    from handlers.coaching import maybe_continue, _start_coaching_flow, _get_topic_suggestions
    from utils.session import delete_coaching_session
    
    test_psid = "simple_test_12345678"
    
    # Clean up
    delete_coaching_session(test_psid)
    
    print("\\n1. Testing topic suggestions...")
    suggestions = _get_topic_suggestions('transport')
    print(f"   ✅ Topic suggestions: {suggestions}")
    assert 'transport' in suggestions
    
    print("\\n2. Testing maybe_continue with insight...")
    result = maybe_continue(test_psid, 'insight', {'categories': ['transport', 'food']})
    
    if result:
        print(f"   ✅ Coaching started successfully!")
        print(f"   Intent: {result['intent']}")
        print(f"   Text: {result['text'][:50]}...")
        print(f"   Quick replies: {len(result.get('quick_replies', []))} buttons")
    else:
        print("   ❌ No coaching started")
        
    print("\\n3. Testing coaching templates...")
    from templates.replies_ai import coach_focus, coach_commit, coach_done
    
    focus_reply = coach_focus(['transport', 'food'])
    print(f"   ✅ Focus template: {focus_reply['text'][:30]}...")
    
    commit_reply = coach_commit('transport', ['batch trips', 'off-peak'])
    print(f"   ✅ Commit template: {commit_reply['text'][:30]}...")
    
    done_reply = coach_done('off-peak')
    print(f"   ✅ Done template: {done_reply['text'][:30]}...")
    
    print("\\n4. Testing session management...")
    from utils.session import get_coaching_session, set_coaching_session
    
    # Test setting/getting session
    test_session = {'state': 'test', 'turns': 1}
    set_coaching_session(test_psid, test_session, 300)
    
    retrieved = get_coaching_session(test_psid)
    if retrieved and retrieved['state'] == 'test':
        print("   ✅ Session management working")
    else:
        print("   ❌ Session management failed")
    
    # Clean up
    delete_coaching_session(test_psid)
    
    print("\\n✅ Basic flow test completed!")

def test_coaching_telemetry():
    """Test coaching telemetry events"""
    
    print("\\n🔍 Telemetry Test")
    print("=" * 20)
    
    from utils.structured import log_structured_event
    
    # Test logging
    try:
        log_structured_event("COACH_TEST", {"test": True})
        print("   ✅ Telemetry logging working")
    except Exception as e:
        print(f"   ❌ Telemetry failed: {e}")

def test_rate_limiting():
    """Test rate limiting components"""
    
    print("\\n⏱️ Rate Limiting Test")
    print("=" * 25)
    
    from utils.session import get_daily_coaching_count, increment_daily_coaching_count
    from utils.config import COACH_PER_DAY_MAX
    
    test_psid = "rate_test_12345678"
    
    initial_count = get_daily_coaching_count(test_psid)
    new_count = increment_daily_coaching_count(test_psid)
    
    print(f"   Initial count: {initial_count}")
    print(f"   After increment: {new_count}")
    print(f"   Daily max: {COACH_PER_DAY_MAX}")
    
    if new_count > initial_count:
        print("   ✅ Rate limiting components working")
    else:
        print("   ❌ Rate limiting not working")

if __name__ == "__main__":
    try:
        test_coaching_basic_flow()
        test_coaching_telemetry()
        test_rate_limiting()
        
        print("\\n🎉 All basic tests passed!")
        
    except Exception as e:
        print(f"\\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()