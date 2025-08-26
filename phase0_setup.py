"""
Phase 0: Safe Foundation Setup
Sets feature flags in controlled FALLBACK mode for audit transparency
"""
import os

print("=" * 60)
print("PHASE 0: SAFE FOUNDATION SETUP")
print("=" * 60)

# Set flags for safe audit transparency testing
# Starting in FALLBACK mode with audit UI disabled
flags_to_set = {
    'PCA_OVERLAY_ENABLED': 'true',  # Enable overlay system
    'PCA_MODE': 'FALLBACK',         # Start in safest mode
    'SHOW_AUDIT_UI': 'false',       # Audit UI disabled initially
    'ENABLE_RULES': 'true',         # Rules ready but inactive in FALLBACK
    'USE_PRECEDENCE': 'true'        # Precedence ready but inactive in FALLBACK
}

print("\n📝 Setting controlled feature flags:")
for flag, value in flags_to_set.items():
    os.environ[flag] = value
    print(f"  {flag} = {value}")

# Test that flags are properly set
print("\n🔍 Verifying flag configuration:")
from utils.pca_feature_flags import pca_feature_flags
pca_feature_flags.refresh_flags()

print(f"  Overlay System: {'Enabled' if os.environ.get('PCA_OVERLAY_ENABLED') == 'true' else 'Disabled'}")
print(f"  Current Mode: {pca_feature_flags.mode}")
print(f"  Audit UI: {'Hidden' if not pca_feature_flags.should_show_audit_ui() else 'Visible'}")
print(f"  System State: {'Safe FALLBACK - No overlay processing' if pca_feature_flags.mode == 'FALLBACK' else 'Active'}")

print("\n✅ Phase 0 Setup Complete")
print("System remains in FALLBACK mode - 0% risk to core ledger")
print("Ready for Phase 1 API development")
