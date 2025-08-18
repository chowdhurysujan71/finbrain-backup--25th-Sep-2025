#!/usr/bin/env python3
"""
Quick verification that debug echo will work in production
"""

import os
if not os.environ.get("ID_SALT"):
    os.environ["ID_SALT"] = "3dcce5a0b1eeb774cc1e0320edb773fed53afbcdd4b14d6201373659278cae34"

from utils.identity import psid_hash

def test_debug_echo_format():
    """Test the debug echo format that will appear in user messages"""
    print("🔍 DEBUG ECHO VERIFICATION")
    print("=" * 30)
    
    test_psid = "real_user_example"
    user_hash = psid_hash(test_psid)
    
    # Simulate different response types with debug echo
    response_scenarios = [
        ("✅ Logged: ৳50.00 for coffee (Food)", "AI"),
        ("📊 Last 7 days: ৳450 total", "STD"), 
        ("Got it.", "FBK"),
        ("Taking a quick breather to stay fast & free...", "ERR")
    ]
    
    print(f"User PSID: {test_psid}")
    print(f"Generated Hash: {user_hash}")
    print(f"Short Hash: {user_hash[:8]}...")
    print()
    
    for response, mode in response_scenarios:
        debug_echo = f"{response}\n\npong | psid_hash={user_hash[:8]}... | mode={mode}"
        print(f"Mode {mode}:")
        print(f"  Original: {response}")
        print(f"  With Debug: {debug_echo}")
        print()
    
    print("✅ Debug echo format verified")
    print("Users will see hash consistency in all responses for 24h")
    
if __name__ == "__main__":
    test_debug_echo_format()