"""
PCA (Precision Capture & Audit) Feature Flags
Zero-risk implementation with kill switches and gradual rollout
"""

import os
import logging
from enum import Enum
from typing import Optional, Dict, Any
import hashlib
import uuid
from datetime import datetime

logger = logging.getLogger("finbrain.pca_flags")

class PCAMode(Enum):
    """PCA Operating Modes"""
    FALLBACK = "FALLBACK"  # Default - PCA disabled, legacy path only
    SHADOW = "SHADOW"      # Log CC snapshots only, no overlay writes
    DRYRUN = "DRYRUN"      # Write RAW only, show "would apply" to testers
    ON = "ON"              # Full PCA with overlay writes

class PCAFlags:
    """PCA Feature Flag Manager with Kill Switches"""
    
    def __init__(self):
        """Initialize PCA flags with safe defaults"""
        self.mode = self._get_pca_mode()
        self.tau_high = float(os.environ.get('PCA_TAU_HIGH', '0.85'))
        self.tau_low = float(os.environ.get('PCA_TAU_LOW', '0.55'))
        self.slo_budget_ms = int(os.environ.get('PCA_SLO_BUDGET_MS', '600'))
        self.canary_users = self._get_canary_users()
        self.global_kill_switch = os.environ.get('PCA_KILL_SWITCH', 'false').lower() == 'true'
        self.enable_clarifiers = os.environ.get('ENABLE_CLARIFIERS', 'false').lower() == 'true'
        
        # Validate thresholds
        if self.tau_high <= self.tau_low:
            logger.warning(f"Invalid thresholds: tau_high({self.tau_high}) <= tau_low({self.tau_low}), "
                         f"adjusting to safe defaults")
            self.tau_high = 0.85
            self.tau_low = 0.55
        
        # Log configuration at startup
        logger.info(f"PCA Flags initialized: mode={self.mode.value}, "
                   f"tau_high={self.tau_high}, tau_low={self.tau_low}, "
                   f"slo_budget_ms={self.slo_budget_ms}, "
                   f"global_kill={self.global_kill_switch}, "
                   f"clarifiers={self.enable_clarifiers}")
    
    def _get_pca_mode(self) -> PCAMode:
        """Get PCA mode from environment with validation"""
        mode_str = os.environ.get('PCA_MODE', 'FALLBACK').upper()
        try:
            return PCAMode(mode_str)
        except ValueError:
            logger.warning(f"Invalid PCA_MODE '{mode_str}', defaulting to FALLBACK")
            return PCAMode.FALLBACK
    
    def _get_canary_users(self) -> set:
        """Get canary user set from environment"""
        canary_str = os.environ.get('PCA_CANARY_USERS', '')
        if not canary_str:
            return set()
        return set(user.strip() for user in canary_str.split(',') if user.strip())
    
    def is_pca_enabled_for_user(self, user_id_hash: str) -> bool:
        """
        Check if PCA is enabled for a specific user
        
        Args:
            user_id_hash: SHA-256 hashed user identifier
            
        Returns:
            True if PCA should process this user's messages
        """
        # Global kill switch overrides everything
        if self.global_kill_switch:
            return False
        
        # FALLBACK mode - PCA disabled for everyone
        if self.mode == PCAMode.FALLBACK:
            return False
        
        # SHADOW mode - enabled for canary users only (if we had canary capability)
        if self.mode == PCAMode.SHADOW:
            return user_id_hash in self.canary_users if self.canary_users else True
            
        # DRYRUN mode - PHASE 3: enabled for ALL users (no canary logic)
        if self.mode == PCAMode.DRYRUN:
            return True  # Full population processing
        
        # ON mode - enabled for canary users only (for now) 
        if self.mode == PCAMode.ON:
            return user_id_hash in self.canary_users
        
        return False
    
    def get_decision_thresholds(self) -> tuple:
        """Get confidence thresholds for decision making"""
        return self.tau_high, self.tau_low
    
    def should_write_overlays(self) -> bool:
        """Check if overlay tables should be written to"""
        return self.mode == PCAMode.ON and not self.global_kill_switch
    
    def should_write_raw_only(self) -> bool:
        """Check if only RAW should be written (DRYRUN mode)"""
        return self.mode == PCAMode.DRYRUN and not self.global_kill_switch
    
    def should_log_snapshots(self) -> bool:
        """Check if CC snapshots should be logged"""
        return self.mode in [PCAMode.SHADOW, PCAMode.DRYRUN, PCAMode.ON] and not self.global_kill_switch
    
    def should_enable_clarifiers(self) -> bool:
        """Check if clarifier UI should be active"""
        return (self.enable_clarifiers and 
                self.mode in [PCAMode.DRYRUN, PCAMode.ON] and 
                not self.global_kill_switch)
    
    def get_clarifier_thresholds(self) -> tuple:
        """Get clarifier decision thresholds for confidence scoring"""
        return self.tau_high, self.tau_low
    
    def get_status(self) -> Dict[str, Any]:
        """Get current PCA status for monitoring"""
        return {
            'mode': self.mode.value,
            'global_kill_switch': self.global_kill_switch,
            'tau_high': self.tau_high,
            'tau_low': self.tau_low,
            'slo_budget_ms': self.slo_budget_ms,
            'canary_user_count': len(self.canary_users),
            'overlays_enabled': self.should_write_overlays(),
            'snapshots_enabled': self.should_log_snapshots(),
            'clarifiers_enabled': self.should_enable_clarifiers(),
            'enable_clarifiers_flag': self.enable_clarifiers,
            'version': 'pca-v1.1-clarifiers'
        }

# Global instance
pca_flags = PCAFlags()

def generate_cc_id(user_id: str, message_id: str, timestamp: datetime, text: str) -> str:
    """
    Generate deterministic Canonical Command ID for idempotency
    
    Args:
        user_id: User identifier (already hashed)
        message_id: Facebook message ID
        timestamp: Message timestamp
        text: Message text
        
    Returns:
        Deterministic CC ID for deduplication
    """
    # Create stable hash from inputs
    hash_input = f"{user_id}:{message_id}:{timestamp.isoformat()}:{text}"
    hash_digest = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
    
    # Format as UUID-like string for readability
    return f"cc_{hash_digest[:8]}_{hash_digest[8:12]}_{hash_digest[12:16]}"

def get_schema_hash() -> str:
    """Get stable hash of CC schema keys for validation"""
    schema_keys = [
        'schema_version', 'cc_id', 'schema_hash', 'user_id', 'intent', 'slots',
        'confidence', 'decision', 'clarifier', 'source_text', 'model_version', 'ui_note'
    ]
    key_string = ':'.join(sorted(schema_keys))
    return hashlib.sha1(key_string.encode()).hexdigest()[:8]

def is_kill_switch_active() -> bool:
    """Check if global PCA kill switch is active"""
    return pca_flags.global_kill_switch

def force_fallback_mode() -> bool:
    """Check if system should use fallback mode"""
    return pca_flags.mode == PCAMode.FALLBACK or pca_flags.global_kill_switch