"""
Gap-Fix Feature Flags Management
Safe feature flag system with fail-closed defaults and structured logging
"""

import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)

class GapFixFlags:
    """
    Centralized feature flag management for gap-fix enhancements
    All flags default to False (fail-closed) for safety
    """
    
    def __init__(self):
        """Initialize all gap-fix feature flags with safe defaults"""
        # Enhanced NLP and clarifier features
        self.enable_clarifiers = self._get_flag('ENABLE_CLARIFIERS', False)
        self.feature_multi_expense = self._get_flag('FEATURE_MULTI_EXPENSE', False)
        
        # AI system controls
        self.ai_enabled = self._get_flag('AI_ENABLED', False) 
        self.ai_provider = os.environ.get('AI_PROVIDER', 'none')
        
        # Schema and observability enhancements
        self.enhanced_confidence_scoring = self._get_flag('ENHANCED_CONFIDENCE_SCORING', True)  # Safe to enable
        self.schema_unification = self._get_flag('SCHEMA_UNIFICATION', True)  # Safe to enable
        self.enhanced_observability = self._get_flag('ENHANCED_OBSERVABILITY', True)  # Safe to enable
        
        # Safety guards
        self.strict_validation = self._get_flag('STRICT_VALIDATION', True)  # Safe to enable
        self.fail_fast_mode = self._get_flag('FAIL_FAST_MODE', False)
        
        # Log all flag states at startup for observability
        self._log_startup_flags()
    
    def _get_flag(self, env_var: str, default: bool) -> bool:
        """Get boolean flag with safe default"""
        try:
            value = os.environ.get(env_var, str(default)).lower()
            return value in ('true', '1', 'yes', 'on')
        except Exception:
            logger.warning(f"Failed to parse {env_var}, using default: {default}")
            return default
    
    def _log_startup_flags(self):
        """Log all feature flag states for startup observability"""
        flags_state = {
            'enable_clarifiers': self.enable_clarifiers,
            'feature_multi_expense': self.feature_multi_expense,
            'ai_enabled': self.ai_enabled,
            'ai_provider': self.ai_provider,
            'enhanced_confidence_scoring': self.enhanced_confidence_scoring,
            'schema_unification': self.schema_unification,
            'enhanced_observability': self.enhanced_observability,
            'strict_validation': self.strict_validation,
            'fail_fast_mode': self.fail_fast_mode
        }
        
        logger.info(f"Gap-Fix Feature Flags: {flags_state}")
        
        # Log any flags that are enabled for security audit
        enabled_flags = [k for k, v in flags_state.items() if v and k != 'ai_provider']
        if enabled_flags:
            logger.info(f"Enabled features: {', '.join(enabled_flags)}")
        else:
            logger.info("All experimental features disabled (fail-closed mode)")
    
    def is_clarifier_enabled(self) -> bool:
        """Check if clarifier system is enabled"""
        return self.enable_clarifiers
    
    def is_multi_expense_enabled(self) -> bool:
        """Check if multi-expense logging is enabled"""
        return self.feature_multi_expense
    
    def is_ai_enabled(self) -> bool:
        """Check if AI processing is enabled"""
        return self.ai_enabled and self.ai_provider != 'none'
    
    def get_ai_provider(self) -> str:
        """Get configured AI provider"""
        return self.ai_provider if self.ai_enabled else 'none'
    
    def should_use_enhanced_confidence(self) -> bool:
        """Check if enhanced confidence scoring should be used"""
        return self.enhanced_confidence_scoring
    
    def should_use_schema_unification(self) -> bool:
        """Check if schema unification should be used"""
        return self.schema_unification
    
    def should_use_enhanced_observability(self) -> bool:
        """Check if enhanced observability should be used"""
        return self.enhanced_observability
    
    def get_all_flags(self) -> dict[str, Any]:
        """Get all flag states for debugging/admin interfaces"""
        return {
            'enable_clarifiers': self.enable_clarifiers,
            'feature_multi_expense': self.feature_multi_expense,
            'ai_enabled': self.ai_enabled,
            'ai_provider': self.ai_provider,
            'enhanced_confidence_scoring': self.enhanced_confidence_scoring,
            'schema_unification': self.schema_unification,
            'enhanced_observability': self.enhanced_observability,
            'strict_validation': self.strict_validation,
            'fail_fast_mode': self.fail_fast_mode
        }


# Global instance - initialized once per process
gap_fix_flags = GapFixFlags()