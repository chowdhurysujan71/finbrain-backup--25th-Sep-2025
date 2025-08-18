#!/usr/bin/env python3
"""
Runtime import probe to detect circular dependencies and broken imports
"""
import sys
import traceback

def test_import(module_path, expected_symbols=None):
    """Test if a module can be imported and has expected symbols"""
    try:
        module = __import__(module_path, fromlist=[''])
        
        if expected_symbols:
            for symbol in expected_symbols:
                if not hasattr(module, symbol):
                    print(f"❌ {module_path}: Missing symbol '{symbol}'")
                    return False
                else:
                    print(f"✅ {module_path}: Has symbol '{symbol}'")
        else:
            print(f"✅ {module_path}: Import successful")
        return True
    except ImportError as e:
        print(f"❌ {module_path}: ImportError - {e}")
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"❌ {module_path}: {type(e).__name__} - {e}")
        traceback.print_exc()
        return False

print("=== IMPORT PROBE STARTING ===\n")

# Test critical modules
modules_to_test = [
    ("utils.user_manager", ["resolve_user_id"]),
    ("utils.user_manager", ["user_manager"]),  # This should fail
    ("utils.user_manager", ["UserManager"]),   # This should fail
    ("utils.background_processor", None),
    ("utils.production_router", None),
    ("utils.dispatcher", None),
    ("utils.intent_router", ["detect_intent"]),
    ("utils.webhook_processor", None),
    ("handlers.summary", ["handle_summary"]),
    ("handlers.insight", ["handle_insight"]),
    ("handlers.logger", ["handle_log"]),
    ("services.summaries", ["build_user_summary", "format_summary_text"]),
]

failed = []
for module, symbols in modules_to_test:
    if not test_import(module, symbols):
        failed.append(module)
    print()

print("=== SUMMARY ===")
if failed:
    print(f"❌ {len(failed)} modules failed:")
    for module in failed:
        print(f"  - {module}")
else:
    print("✅ All modules imported successfully")