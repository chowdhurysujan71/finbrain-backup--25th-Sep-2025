"""
Unified Feature Flags System - Phase 7 Consolidation
Consolidates fragmented flag systems into a single, coherent API
"""

import os
import logging
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger("finbrain.unified_flags")

class PCAMode(Enum):
    """PCA Operating Modes"""
    FALLBACK = "FALLBACK"  # Default - PCA disabled, legacy path only
    SHADOW = "SHADOW"      # Log CC snapshots only, no overlay writes
    DRYRUN = "DRYRUN"      # Write RAW only, show "would apply" to testers
    ON = "ON"              # Full PCA with overlay writes

class UnifiedFlags:
    """
    PHASE 7: Unified Feature Flag System
    Consolidates utils/feature_flags.py, utils/gap_fix_flags.py, 
    utils/pca_flags.py, and utils/pca_feature_flags.py
    """
    
    def __init__(self):
        """Initialize unified flags with safe defaults and comprehensive logging"""
        
        # === CORE SYSTEM FLAGS ===
        self.ai_enabled = self._get_flag('AI_ENABLED', True)
        self.ai_provider = os.environ.get('AI_PROVIDER', 'gemini')
        
        # === PCA SYSTEM FLAGS ===
        self.pca_mode = self._get_pca_mode()
        self.pca_tau_high = float(os.environ.get('PCA_TAU_HIGH', '0.85'))
        self.pca_tau_low = float(os.environ.get('PCA_TAU_LOW', '0.55'))
        self.pca_global_kill = self._get_flag('PCA_KILL_SWITCH', False)
        
        # === FEATURE FLAGS ===
        # Always-on features (from utils/feature_flags.py)
        self.smart_nlp_enabled = True  # Always on for production
        self.smart_tone_enabled = True  # Always on for production  
        self.smart_corrections_enabled = True  # Always on for production
        
        # Configurable features (from utils/gap_fix_flags.py)
        self.enable_clarifiers = self._get_flag('ENABLE_CLARIFIERS', False)
        self.multi_expense_enabled = self._get_flag('FEATURE_MULTI_EXPENSE', True)
        self.web_clarifier_ui = self._get_flag('FEATURE_WEB_CLARIFIER_UI', True)
        self.category_normalization = self._get_flag('FEATURE_CATEGORY_NORMALIZATION', True)
        
        # === OVERLAY SYSTEM FLAGS ===
        self.overlay_enabled = self._get_flag('PCA_OVERLAY_ENABLED', True)
        self.show_audit_ui = self._get_flag('SHOW_AUDIT_UI', True)
        self.enable_rules = self._get_flag('ENABLE_RULES', False)
        self.use_precedence = self._get_flag('USE_PRECEDENCE', False)
        
        # === SAFETY FLAGS ===
        self.strict_validation = self._get_flag('STRICT_VALIDATION', True)
        self.fail_fast_mode = self._get_flag('FAIL_FAST_MODE', False)
        
        # Validate PCA thresholds
        if self.pca_tau_high <= self.pca_tau_low:
            logger.warning(f"Invalid PCA thresholds: tau_high({self.pca_tau_high}) <= tau_low({self.pca_tau_low})")
            self.pca_tau_high = 0.85
            self.pca_tau_low = 0.55
            
        # PHASE 7: Comprehensive boot logging
        self._log_unified_flags()
    
    def _get_flag(self, env_var: str, default: bool) -> bool:
        """Get boolean flag with safe default"""
        try:
            value = os.environ.get(env_var, str(default)).lower()
            return value in ('true', '1', 'yes', 'on')
        except Exception:
            logger.warning(f"Failed to parse {env_var}, using default: {default}")
            return default
    
    def _get_pca_mode(self) -> PCAMode:
        """Get PCA mode from environment with validation"""
        try:
            mode_str = os.environ.get('PCA_MODE', 'ON').upper()
            return PCAMode(mode_str)
        except ValueError:
            logger.warning(f"Invalid PCA_MODE, defaulting to ON")
            return PCAMode.ON
    
    def _log_unified_flags(self):
        """PHASE 7: Boot logging for unified flag system"""
        
        # Group flags by category for readable logging
        core_flags = {
            'ai_enabled': self.ai_enabled,
            'ai_provider': self.ai_provider,
        }
        
        pca_flags = {
            'mode': self.pca_mode.value,
            'tau_high': self.pca_tau_high,
            'tau_low': self.pca_tau_low,
            'global_kill': self.pca_global_kill,
        }
        
        feature_flags = {
            'smart_nlp': self.smart_nlp_enabled,
            'smart_tone': self.smart_tone_enabled,
            'corrections': self.smart_corrections_enabled,
            'clarifiers': self.enable_clarifiers,
            'multi_expense': self.multi_expense_enabled,
            'web_clarifier': self.web_clarifier_ui,
            'category_norm': self.category_normalization,
        }
        
        overlay_flags = {
            'overlay_enabled': self.overlay_enabled,
            'audit_ui': self.show_audit_ui,
            'rules': self.enable_rules,
            'precedence': self.use_precedence,
        }
        
        # Log each category
        logger.info(f"[UNIFIED FLAGS] Core: {core_flags}")
        logger.info(f"[UNIFIED FLAGS] PCA: {pca_flags}")  
        logger.info(f"[UNIFIED FLAGS] Features: {feature_flags}")
        logger.info(f"[UNIFIED FLAGS] Overlay: {overlay_flags}")
        
        # Summary count
        total_enabled = sum([
            self.ai_enabled, self.smart_nlp_enabled, self.smart_tone_enabled,
            self.smart_corrections_enabled, self.multi_expense_enabled,
            self.web_clarifier_ui, self.category_normalization, self.overlay_enabled
        ])
        
        logger.info(f"[UNIFIED FLAGS] Initialization complete: {total_enabled}/8 core features enabled, mode={self.pca_mode.value}")
    
    # === COMPATIBILITY METHODS FOR EXISTING CODE ===
    
    def is_smart_nlp_enabled(self, psid_hash: Optional[str] = None) -> bool:
        """Compatibility method for utils/feature_flags.py"""
        return self.smart_nlp_enabled
    
    def is_smart_tone_enabled(self, psid_hash: Optional[str] = None) -> bool:
        """Compatibility method for utils/feature_flags.py"""
        return self.smart_tone_enabled
    
    def is_smart_corrections_enabled(self, psid_hash: Optional[str] = None) -> bool:
        """Compatibility method for utils/feature_flags.py"""
        return self.smart_corrections_enabled
    
    def should_enable_web_clarifier_ui(self) -> bool:
        """Compatibility method for utils/pca_flags.py"""
        return self.web_clarifier_ui
    
    def should_log_snapshots(self) -> bool:
        """Compatibility method for PCA snapshot logging"""
        return self.pca_mode in [PCAMode.SHADOW, PCAMode.DRYRUN, PCAMode.ON]
    
    def is_overlay_active(self) -> bool:
        """Compatibility method for utils/pca_feature_flags.py"""
        return self.overlay_enabled and self.pca_mode == PCAMode.ON

# Global singleton instance
unified_flags = UnifiedFlags()

# === CONVENIENCE FUNCTIONS FOR BACKWARD COMPATIBILITY ===

def is_smart_nlp_enabled(psid_hash: Optional[str] = None) -> bool:
    """Global convenience function - maintains API compatibility"""
    return unified_flags.is_smart_nlp_enabled(psid_hash)

def is_smart_tone_enabled(psid_hash: Optional[str] = None) -> bool:
    """Global convenience function - maintains API compatibility"""
    return unified_flags.is_smart_tone_enabled(psid_hash)

def is_smart_corrections_enabled(psid_hash: Optional[str] = None) -> bool:
    """Global convenience function - maintains API compatibility"""
    return unified_flags.is_smart_corrections_enabled(psid_hash)

def feature_enabled(*args, **kwargs) -> bool:
    """Global convenience function - always returns True for backward compatibility"""
    return True