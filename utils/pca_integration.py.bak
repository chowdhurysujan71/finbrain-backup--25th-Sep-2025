"""
PCA Integration Layer
Phase 2: Shadow Mode Integration with Webhook Pipeline
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
import time

logger = logging.getLogger("finbrain.pca_integration")

def integrate_pca_with_webhook(user_id: str, message_text: str, message_id: str, 
                              timestamp: datetime) -> Tuple[bool, Dict[str, Any]]:
    """
    Integrate PCA processing with webhook message handling
    
    Args:
        user_id: Hashed user identifier
        message_text: User's message text
        message_id: Facebook message ID
        timestamp: Message timestamp
        
    Returns:
        Tuple of (should_continue_legacy_flow, pca_result)
    """
    try:
        from utils.pca_flags import pca_flags, PCAMode
        from utils.pca_processor import process_message_with_pca
        from utils.structured import log_structured_event
        
        # Early exit if PCA disabled globally
        if pca_flags.global_kill_switch or pca_flags.mode == PCAMode.FALLBACK:
            return True, {'pca_processed': False, 'mode': 'FALLBACK'}
        
        # Skip canary user logic - process all users in DRYRUN mode
        # Note: Canary logic removed due to lack of gated releases
        
        # Process message through PCA system
        start_time = time.time()
        pca_result = process_message_with_pca(user_id, message_text, message_id, timestamp)
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # Add processing metrics
        pca_result['processing_time_ms'] = processing_time_ms
        pca_result['timestamp'] = timestamp.isoformat()
        
        # Log structured telemetry
        log_structured_event('PCA_MESSAGE_PROCESSED', {
            'user_id': user_id[:12] + '...',  # Partial for privacy
            'mode': pca_result.get('mode', 'unknown'),
            'processed': pca_result.get('pca_processed', False),
            'processing_time_ms': processing_time_ms,
            'cc_logged': pca_result.get('cc_logged', False),
            'intent': pca_result.get('intent', 'none'),
            'confidence': pca_result.get('confidence', 0.0)
        })
        
        # Determine if legacy flow should continue
        should_continue = pca_result.get('fallback_to_legacy', True)
        
        logger.info(f"PCA integration: user={user_id[:8]}... mode={pca_result.get('mode')} "
                   f"processed={pca_result.get('pca_processed')} time={processing_time_ms}ms")
        
        return should_continue, pca_result
        
    except Exception as e:
        logger.error(f"PCA integration failed for user {user_id[:8]}...: {e}")
        
        # Log error event
        try:
            from utils.structured import log_structured_event
            log_structured_event('PCA_INTEGRATION_ERROR', {
                'user_id': user_id[:12] + '...',
                'error': str(e)[:200],
                'message_length': len(message_text)
            })
        except:
            pass
        
        # Always fallback to legacy on errors
        return True, {'pca_processed': False, 'error': str(e)}

def get_pca_deployment_status() -> Dict[str, Any]:
    """
    Get PCA deployment status (simplified from canary system)
    
    Returns:
        Dictionary with deployment configuration
    """
    from utils.pca_flags import pca_flags
    
    return {
        'deployment_model': 'full_population',  # No gated releases available
        'pca_mode': pca_flags.mode.value,
        'global_kill_switch': pca_flags.global_kill_switch,
        'coverage': '100%' if pca_flags.mode.value != 'FALLBACK' else '0%',
        'ready_for_dryrun': pca_flags.mode.value in ['DRYRUN', 'ON'],
        'setup_timestamp': datetime.utcnow().isoformat()
    }

def get_pca_telemetry_summary() -> Dict[str, Any]:
    """
    Get PCA processing telemetry summary for monitoring
    
    Returns:
        Dictionary with processing statistics
    """
    try:
        from app import db
        from models_pca import InferenceSnapshot
        from datetime import timedelta
        
        # Get processing stats for last 24 hours
        yesterday = datetime.utcnow() - timedelta(days=1)
        
        # Query recent snapshots
        recent_snapshots = db.session.query(InferenceSnapshot).filter(
            InferenceSnapshot.created_at >= yesterday
        ).all()
        
        if not recent_snapshots:
            return {
                'period': 'last_24h',
                'total_processed': 0,
                'cc_logged': 0,
                'intents': {},
                'avg_confidence': 0.0,
                'modes': {},
                'timestamp': datetime.utcnow().isoformat()
            }
        
        # Calculate metrics
        total_count = len(recent_snapshots)
        intents = {}
        modes = {}
        total_confidence = 0.0
        
        for snapshot in recent_snapshots:
            # Count intents
            intent = snapshot.intent
            intents[intent] = intents.get(intent, 0) + 1
            
            # Count modes
            mode = snapshot.pca_mode
            modes[mode] = modes.get(mode, 0) + 1
            
            # Sum confidence
            total_confidence += snapshot.confidence
        
        avg_confidence = total_confidence / total_count if total_count > 0 else 0.0
        
        return {
            'period': 'last_24h',
            'total_processed': total_count,
            'cc_logged': total_count,  # All snapshots are logged CCs
            'intents': intents,
            'avg_confidence': round(avg_confidence, 3),
            'modes': modes,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get PCA telemetry: {e}")
        return {
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }

def enable_shadow_mode_for_user(user_id_hash: str) -> Dict[str, Any]:
    """
    Enable SHADOW mode for a specific user by adding to canary list
    
    Args:
        user_id_hash: SHA-256 hashed user identifier
        
    Returns:
        Result dictionary with status
    """
    try:
        import os
        from utils.pca_flags import pca_flags
        
        # Get current canary users
        current_canary = os.environ.get('PCA_CANARY_USERS', '')
        canary_set = set(u.strip() for u in current_canary.split(',') if u.strip())
        
        # Add new user
        canary_set.add(user_id_hash)
        
        # Update environment (note: this only affects current process)
        new_canary_str = ','.join(sorted(canary_set))
        os.environ['PCA_CANARY_USERS'] = new_canary_str
        
        # Refresh PCA flags to pick up new canary list
        pca_flags.__init__()
        
        logger.info(f"User {user_id_hash[:8]}... enabled for PCA SHADOW mode")
        
        return {
            'success': True,
            'user_hash': user_id_hash[:8] + '...',
            'total_canary_users': len(canary_set),
            'mode': 'SHADOW',
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to enable SHADOW mode for user {user_id_hash[:8]}...: {e}")
        return {
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }