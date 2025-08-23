"""
End-to-end coaching flow simulation and demonstration
Shows session state transitions and telemetry events
"""

import os
import sys
import time
import logging
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up logging to capture events
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def run_coaching_demo():
    """Run complete coaching flow demonstration"""
    
    print("🎯 FinBrain Coaching Flow Demo")
    print("=" * 50)
    
    from handlers.coaching import maybe_continue, handle_coaching_response
    from utils.session import get_coaching_session, delete_coaching_session
    from utils.structured import log_structured_event
    
    test_psid = "demo_user_12345678"
    
    # Clean slate
    delete_coaching_session(test_psid)
    
    print("\\n📊 Step 1: User requests summary/insight")
    print("Input: 'insight'")
    
    # Simulate insight request triggering coaching
    coaching_reply = maybe_continue(test_psid, 'insight', {
        'categories': ['transport', 'food'],
        'total_amount': 5500
    })
    
    if coaching_reply:
        print(f"✅ Coaching Started!")
        print(f"Reply: {coaching_reply['text']}")
        print(f"Quick Replies: {[qr['title'] for qr in coaching_reply.get('quick_replies', [])]}")
        
        session = get_coaching_session(test_psid)
        print(f"Session State: {session}")
    else:
        print("❌ No coaching triggered")
        return
    
    print("\\n🚗 Step 2: User selects 'transport' focus area")
    print("Input: 'transport'")
    
    # User selects transport
    reply2 = handle_coaching_response(test_psid, 'transport')
    
    if reply2:
        print(f"✅ Focus Selected!")
        print(f"Reply: {reply2['text']}")
        print(f"Quick Replies: {[qr['title'] for qr in reply2.get('quick_replies', [])]}")
        
        session = get_coaching_session(test_psid)
        print(f"Session State: state={session['state']}, topic={session['topic']}, turns={session['turns']}")
    
    print("\\n⚡ Step 3: User commits to 'off-peak' action")
    print("Input: 'off-peak'")
    
    # User commits to action
    reply3 = handle_coaching_response(test_psid, 'off-peak')
    
    if reply3:
        print(f"✅ Action Committed!")
        print(f"Reply: {reply3['text']}")
        
        session = get_coaching_session(test_psid)
        if session:
            print(f"Session State: state={session['state']}, cooldown_until={session.get('cooldown_until')}")
        else:
            print("Session State: Completed and cleaned up")
    
    print("\\n🔄 Step 4: Try immediate coaching again (should be blocked)")
    print("Input: 'summary'")
    
    # Should be blocked by cooldown
    blocked_reply = maybe_continue(test_psid, 'summary', {'categories': ['food']})
    
    if blocked_reply:
        print("❌ Unexpected: Coaching started despite cooldown")
    else:
        print("✅ Correctly blocked by cooldown/rate limit")
    
    print("\\n📈 Step 5: Rate limit test")
    
    # Test daily counter
    from utils.session import get_daily_coaching_count
    daily_count = get_daily_coaching_count(test_psid)
    print(f"Daily coaching count: {daily_count}")
    
    print("\\n🧪 Step 6: Session state transition test")
    
    # Create manual session to test state handling
    from utils.session import set_coaching_session
    
    test_session = {
        'state': 'await_focus',
        'last_question': 'focus',
        'topic': None,
        'turns': 2,
        'started_at': time.time()
    }
    
    set_coaching_session(test_psid, test_session, 300)
    
    # Test unclear response (should re-ask)
    unclear_reply = handle_coaching_response(test_psid, 'unclear message')
    if unclear_reply:
        print(f"✅ Re-ask on unclear input: {unclear_reply['text'][:50]}...")
    
    # Test turn limit
    test_session['turns'] = 3  # At limit
    set_coaching_session(test_psid, test_session, 300)
    
    limit_reply = handle_coaching_response(test_psid, 'another unclear message')
    if limit_reply:
        print(f"✅ Turn limit handling: {limit_reply['text'][:50]}...")
    
    print("\\n✨ Demo Complete!")
    print("=" * 50)
    
    # Show final state
    final_session = get_coaching_session(test_psid)
    if final_session:
        print(f"Final session: {final_session}")
    else:
        print("Final session: None (cleaned up)")
    
    # Clean up
    delete_coaching_session(test_psid)

def show_sample_payloads():
    """Show example quick-reply payloads"""
    
    print("\\n📱 Sample Quick-Reply Payloads")
    print("=" * 30)
    
    # Q1 Focus payload
    q1_payload = {
        'text': 'Which area do you want to improve first—transport, food or other? 🎯',
        'quick_replies': [
            {'title': 'Transport', 'payload': 'COACH_TRANSPORT'},
            {'title': 'Food', 'payload': 'COACH_FOOD'},
            {'title': 'Other', 'payload': 'COACH_OTHER'},
            {'title': 'Skip', 'payload': 'COACH_SKIP'}
        ]
    }
    
    print("Q1 Focus Selection:")
    print(f"Text: {q1_payload['text']}")
    print("Quick Replies:")
    for qr in q1_payload['quick_replies']:
        print(f"  - {qr['title']} → {qr['payload']}")
    
    # Q2 Commit payload  
    q2_payload = {
        'text': 'Nice choice! Let\\'s try one small step: batch trips or off-peak. Which sounds doable this week? 💪',
        'quick_replies': [
            {'title': 'Batch Trips', 'payload': 'COACH_BATCH_TRIPS'},
            {'title': 'Off-Peak', 'payload': 'COACH_OFF_PEAK'},
            {'title': 'Something Else', 'payload': 'COACH_OTHER'},
            {'title': 'Skip', 'payload': 'COACH_SKIP'}
        ]
    }
    
    print("\\nQ2 Action Commitment:")
    print(f"Text: {q2_payload['text']}")
    print("Quick Replies:")
    for qr in q2_payload['quick_replies']:
        print(f"  - {qr['title']} → {qr['payload']}")

if __name__ == "__main__":
    print("🚀 Starting FinBrain Coaching Flow Demo...")
    
    try:
        run_coaching_demo()
        show_sample_payloads()
        
        print("\\n🎉 Demo completed successfully!")
        
    except Exception as e:
        print(f"\\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()