"""
PCA Feature Flags Management
Controls overlay system activation layers
"""

import os
import logging

logger = logging.getLogger("finbrain.pca_flags")

class PCAFeatureFlags:
    """
    Multi-layered feature control for safe deployment
    Master flag > Mode > Granular flags
    """
    
    def __init__(self):
        self.refresh_flags()
        
    def refresh_flags(self):
        """Refresh flags from environment"""
        # Master kill switch
        self.overlay_enabled = os.environ.get('PCA_OVERLAY_ENABLED', 'false').lower() == 'true'
        
        # PCA Mode
        self.mode = os.environ.get('PCA_MODE', 'FALLBACK').upper()
        
        # Granular feature flags
        self.show_audit_ui = os.environ.get('SHOW_AUDIT_UI', 'false').lower() == 'true'
        self.enable_rules = os.environ.get('ENABLE_RULES', 'false').lower() == 'true'
        self.use_precedence = os.environ.get('USE_PRECEDENCE', 'false').lower() == 'true'
        
        logger.info(f"PCA Feature Flags: overlay={self.overlay_enabled}, mode={self.mode}, "
                   f"audit_ui={self.show_audit_ui}, rules={self.enable_rules}, precedence={self.use_precedence}")
    
    def is_overlay_active(self) -> bool:
        """Check if overlay system should be active"""
        return self.overlay_enabled and self.mode == 'ON'
    
    def is_shadow_mode(self) -> bool:
        """Check if in shadow mode (logging only)"""
        return self.mode == 'SHADOW'
    
    def is_dryrun_mode(self) -> bool:
        """Check if in dryrun mode (raw writes only)"""
        return self.mode == 'DRYRUN'
    
    def should_show_audit_ui(self) -> bool:
        """Check if audit UI should be visible"""
        return self.is_overlay_active() and self.show_audit_ui
    
    def should_enable_rules(self) -> bool:
        """Check if rule management should be enabled"""
        return self.is_overlay_active() and self.enable_rules
    
    def should_use_precedence(self) -> bool:
        """Check if precedence engine should be used"""
        return self.is_overlay_active() and self.use_precedence
    
    def get_status(self) -> dict:
        """Get current flag status for monitoring"""
        return {
            'master_flag': self.overlay_enabled,
            'mode': self.mode,
            'overlay_active': self.is_overlay_active(),
            'features': {
                'audit_ui': self.should_show_audit_ui(),
                'rules': self.should_enable_rules(),
                'precedence': self.should_use_precedence()
            }
        }

# Global instance
pca_feature_flags = PCAFeatureFlags()