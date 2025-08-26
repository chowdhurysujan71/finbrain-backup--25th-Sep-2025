"""
PCA (Precision Capture & Audit) Message Processor
Phase 1: CC Snapshot Logging and Basic Processing
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger("finbrain.pca_processor")

def log_cc_snapshot(cc_dict: Dict[str, Any], processing_time_ms: Optional[int] = None, 
                   applied: bool = False, error_message: Optional[str] = None) -> bool:
    """
    Log Canonical Command snapshot to inference_snapshots table
    
    Args:
        cc_dict: Complete CC dictionary from CanonicalCommand.to_dict()
        processing_time_ms: Time taken to process this CC
        applied: Whether this CC was actually applied to create transactions
        error_message: Any error that occurred during processing
        
    Returns:
        True if logged successfully, False otherwise
    """
    try:
        from app import db
        from models_pca import InferenceSnapshot
        from utils.pca_flags import pca_flags
        
        # Extract CC components
        cc_id = cc_dict.get('cc_id', '')
        user_id = cc_dict.get('user_id', '')
        intent = cc_dict.get('intent', '')
        slots = cc_dict.get('slots', {})
        confidence = cc_dict.get('confidence', 0.0)
        decision = cc_dict.get('decision', '')
        clarifier = cc_dict.get('clarifier', {})
        model_version = cc_dict.get('model_version', 'unknown')
        source_text = cc_dict.get('source_text', '')
        ui_note = cc_dict.get('ui_note', '')
        
        # Create snapshot record
        snapshot = InferenceSnapshot()
        snapshot.cc_id = cc_id
        snapshot.user_id = user_id
        snapshot.intent = intent
        snapshot.slots_json = slots
        snapshot.confidence = confidence
        snapshot.decision = decision
        snapshot.clarifier_json = clarifier if clarifier and clarifier.get('type') != 'none' else None
        snapshot.model_version = model_version
        snapshot.processing_time_ms = processing_time_ms
        snapshot.source_text = source_text
        snapshot.ui_note = ui_note
        snapshot.pca_mode = pca_flags.mode.value
        snapshot.applied = applied
        snapshot.error_message = error_message
        
        # Insert into database
        db.session.add(snapshot)
        db.session.commit()
        
        logger.debug(f"CC snapshot logged: {cc_id} intent={intent} conf={confidence:.2f} applied={applied}")
        return True
        
    except IntegrityError as e:
        logger.warning(f"CC snapshot already exists: {cc_id}")
        try:
            db.session.rollback()
        except:
            pass
        return False
        
    except Exception as e:
        logger.error(f"Failed to log CC snapshot {cc_id}: {e}")
        try:
            db.session.rollback()
        except:
            pass
        return False

def process_message_with_pca(user_id: str, message_text: str, message_id: str, timestamp: datetime) -> Dict[str, Any]:
    """
    Process message through PCA system based on current mode
    
    Args:
        user_id: Hashed user identifier  
        message_text: User's message text
        message_id: Facebook message ID
        timestamp: Message timestamp
        
    Returns:
        Dictionary containing processing results and metadata
    """
    try:
        from utils.pca_flags import pca_flags, generate_cc_id, PCAMode
        from utils.canonical_command import CanonicalCommand, create_help_cc, create_fallback_cc
        from utils.production_router import production_router
        
        # Check if PCA should process this user
        if not pca_flags.is_pca_enabled_for_user(user_id):
            return {
                'pca_processed': False,
                'reason': 'user_not_enabled',
                'mode': pca_flags.mode.value,
                'fallback_to_legacy': True
            }
        
        # Generate deterministic CC ID
        cc_id = generate_cc_id(user_id, message_id, timestamp, message_text)
        
        # Process based on PCA mode
        processing_start = datetime.utcnow()
        
        if pca_flags.mode == PCAMode.FALLBACK:
            # FALLBACK mode - no PCA processing
            return {
                'pca_processed': False,
                'reason': 'fallback_mode',
                'mode': 'FALLBACK',
                'fallback_to_legacy': True
            }
            
        elif pca_flags.mode == PCAMode.SHADOW:
            # SHADOW mode - log CC snapshots only, don't affect flow
            try:
                # Create a simple expense detection fallback for SHADOW mode
                # Look for money patterns in the message
                import re
                money_pattern = r'(?:৳|BDT|taka)?\s*(\d+(?:\.\d{2})?)'
                money_matches = re.findall(money_pattern, message_text, re.IGNORECASE)
                
                if money_matches:
                    # Money event detected - create LOG_EXPENSE CC
                    from utils.canonical_command import CCSlots, CCIntent, CCDecision
                    
                    amount = float(money_matches[0])
                    slots = CCSlots(
                        amount=amount,
                        currency='BDT',
                        category='general',
                        merchant_text='',
                        note=message_text[:100]
                    )
                    
                    cc = CanonicalCommand(
                        cc_id=cc_id,
                        user_id=user_id,
                        intent=CCIntent.LOG_EXPENSE.value,
                        slots=slots,
                        confidence=0.6,  # Low confidence for regex detection
                        decision=CCDecision.RAW_ONLY.value,
                        source_text=message_text,
                        model_version='shadow-regex-v1',
                        ui_note=f"Detected ৳{amount} expense"
                    )
                else:
                    # No money detected - create HELP CC
                    cc = create_help_cc(user_id, cc_id, message_text, "No expense amount detected")
                
                # Log CC snapshot
                processing_time = int((datetime.utcnow() - processing_start).total_seconds() * 1000)
                log_cc_snapshot(cc.to_dict(), processing_time, applied=False)
                
                return {
                    'pca_processed': True,
                    'mode': 'SHADOW',
                    'cc_logged': True,
                    'cc_id': cc_id,
                    'intent': cc.intent,
                    'confidence': cc.confidence,
                    'fallback_to_legacy': True  # Still use legacy path for actual processing
                }
                
            except Exception as e:
                logger.error(f"SHADOW mode processing failed: {e}")
                # Log error CC
                error_cc = create_help_cc(user_id, cc_id, message_text, "Processing error occurred")
                log_cc_snapshot(error_cc.to_dict(), error_message=str(e))
                
                return {
                    'pca_processed': True,
                    'mode': 'SHADOW',
                    'error': str(e),
                    'fallback_to_legacy': True
                }
        
        elif pca_flags.mode == PCAMode.DRYRUN:
            # DRYRUN mode - not implemented yet
            return {
                'pca_processed': False,
                'reason': 'dryrun_not_implemented',
                'mode': 'DRYRUN',
                'fallback_to_legacy': True
            }
        
        elif pca_flags.mode == PCAMode.ON:
            # ON mode - not implemented yet
            return {
                'pca_processed': False,
                'reason': 'on_mode_not_implemented',
                'mode': 'ON',
                'fallback_to_legacy': True
            }
        
        else:
            # Unknown mode - fallback
            return {
                'pca_processed': False,
                'reason': 'unknown_mode',
                'mode': str(pca_flags.mode),
                'fallback_to_legacy': True
            }
            
    except Exception as e:
        logger.error(f"PCA processing failed for user {user_id[:8]}...: {e}")
        return {
            'pca_processed': False,
            'error': str(e),
            'fallback_to_legacy': True
        }

def get_pca_health_status() -> Dict[str, Any]:
    """Get health status of PCA overlay tables and processing"""
    try:
        from app import db
        from models_pca import TransactionEffective, UserCorrection, UserRule, InferenceSnapshot
        
        # Check table accessibility and basic counts
        tx_count = db.session.query(TransactionEffective).count()
        corr_count = db.session.query(UserCorrection).count()  
        rule_count = db.session.query(UserRule).count()
        snapshot_count = db.session.query(InferenceSnapshot).count()
        
        # Get recent activity (last 24 hours)
        from datetime import timedelta
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_snapshots = db.session.query(InferenceSnapshot).filter(
            InferenceSnapshot.created_at >= yesterday
        ).count()
        
        return {
            'healthy': True,
            'tables': {
                'transactions_effective': tx_count,
                'user_corrections': corr_count,
                'user_rules': rule_count,
                'inference_snapshots': snapshot_count
            },
            'recent_activity': {
                'snapshots_24h': recent_snapshots
            },
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {
            'healthy': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }