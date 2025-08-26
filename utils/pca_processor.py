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
        logger.warning(f"CC snapshot already exists: {cc_dict.get('cc_id', 'unknown')}")
        try:
            db.session.rollback()
        except:
            pass
        return False
        
    except Exception as e:
        logger.error(f"Failed to log CC snapshot {cc_dict.get('cc_id', 'unknown')}: {e}")
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
        
        # PHASE 3: DRYRUN Mode - Process all users (no canary logic)
        # Note: Removed user-level enablement due to no gated releases
        
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
            # PHASE 3: DRYRUN mode - Enhanced CC generation for all users
            return process_dryrun_mode(user_id, message_text, message_id, cc_id, timestamp, pca_flags)
        
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

def process_dryrun_mode(user_id: str, message_text: str, message_id: str, cc_id: str, 
                       timestamp: datetime, pca_flags) -> Dict[str, Any]:
    """
    PHASE 3: Enhanced DRYRUN mode processing for all users
    
    Features:
    - Enhanced expense detection patterns (Bengali + English)
    - All messages processed (not just expenses)
    - Complete audit trail logging
    - Performance monitoring
    - Zero impact on user experience
    """
    import re
    import time as time_module
    
    processing_start = time_module.time()
    
    try:
        from utils.canonical_command import CanonicalCommand, create_help_cc, create_fallback_cc, CCSlots, CCIntent, CCDecision
        
        # Enhanced expense detection patterns
        expense_patterns = [
            r'৳\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',  # ৳500, ৳1,500.50
            r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:taka|৳|tk|BDT)',  # 500 taka, 1500৳, 200 tk
            r'(?:spent|cost|paid|bought|expense|khoroch|খরচ)\s*৳?\s*(\d+)',  # spent ৳500, খরচ 200
            r'(?:kinlam|kিনলাম|dilam|দিলাম)\s*৳?\s*(\d+)',  # Bengali expense verbs
            r'(\d+)\s*(?:টাকা|taka)',  # 500 টাকা
        ]
        
        # Check for expense patterns
        expense_detected = False
        amount_value = None
        amount_match = None
        
        for pattern in expense_patterns:
            match = re.search(pattern, message_text, re.IGNORECASE)
            if match:
                expense_detected = True
                amount_match = match
                try:
                    # Extract numeric amount
                    amount_text = match.group(1) if match.group(1) else match.group(2) if len(match.groups()) > 1 else match.group(0)
                    amount_value = float(amount_text.replace(',', '').replace('৳', '').strip())
                except (ValueError, AttributeError):
                    amount_value = None
                break
        
        # Generate appropriate CC based on message content
        if expense_detected:
            # Create expense CC with enhanced data
            cc = CanonicalCommand(
                cc_id=cc_id,
                user_id=user_id,
                intent=CCIntent.LOG_EXPENSE.value,
                slots=CCSlots(
                    amount=amount_value,
                    currency='BDT',
                    category='general',  # Could be enhanced with AI categorization
                    merchant_text=message_text[:100],
                    note=f"Auto-detected expense: ৳{amount_value}" if amount_value else "Expense pattern detected"
                ),
                confidence=0.8 if amount_value else 0.6,  # Higher confidence if amount extracted
                decision=CCDecision.AUTO_APPLY.value,
                source_text=message_text,
                model_version='dryrun-enhanced-v1',
                ui_note=f"Detected ৳{amount_value} expense via pattern matching" if amount_value else "Expense detected"
            )
            intent_result = "LOG_EXPENSE"
            confidence_result = cc.confidence
            
        else:
            # Simple intent classification for non-expense messages
            query_keywords = ['help', 'summary', 'total', 'report', 'balance', 'show', 'আমার', 'দেখাও']
            greeting_keywords = ['hello', 'hi', 'hey', 'assalam', 'নমস্কার', 'হাই']
            
            if any(word in message_text.lower() for word in query_keywords):
                cc = create_help_cc(user_id, cc_id, message_text, "Query or help request detected")
                intent_result = "HELP"
                confidence_result = 0.75
                
            elif any(word in message_text.lower() for word in greeting_keywords):
                cc = CanonicalCommand(
                    cc_id=cc_id,
                    user_id=user_id,
                    intent=CCIntent.GREETING.value,
                    slots=CCSlots(),
                    confidence=0.9,
                    decision=CCDecision.RAW_ONLY.value,
                    source_text=message_text,
                    model_version='dryrun-enhanced-v1',
                    ui_note="Greeting detected"
                )
                intent_result = "GREETING"
                confidence_result = 0.9
                
            else:
                # Fallback for unrecognized messages
                cc = create_fallback_cc(user_id, cc_id, message_text, "Unrecognized message type")
                intent_result = "UNKNOWN"
                confidence_result = 0.3
        
        # Calculate processing metrics
        processing_time_ms = int((time_module.time() - processing_start) * 1000)
        
        # Log CC snapshot to audit trail
        cc_dict = cc.to_dict()
        cc_logged = log_cc_snapshot(cc_dict, processing_time_ms=processing_time_ms, applied=False)
        
        # Log structured telemetry for analysis
        try:
            from utils.structured import log_cc_generation_event
            log_cc_generation_event(cc_dict, processing_time_ms, applied=False)
        except Exception as telemetry_error:
            logger.warning(f"Telemetry logging failed: {telemetry_error}")
        
        # Return comprehensive result
        result = {
            'pca_processed': True,
            'cc_logged': cc_logged,
            'cc_id': cc_id,
            'intent': intent_result,
            'confidence': confidence_result,
            'processing_time_ms': processing_time_ms,
            'expense_detected': expense_detected,
            'amount_extracted': amount_value,
            'pattern_matched': expense_detected,
            'mode': 'DRYRUN',
            'model_version': 'dryrun-enhanced-v1',
            'fallback_to_legacy': True  # Always continue to existing flow in DRYRUN
        }
        
        # Performance monitoring
        if processing_time_ms > 100:
            logger.warning(f"DRYRUN processing slow: {processing_time_ms}ms for CC {cc_id}")
        
        logger.debug(f"DRYRUN processed: {intent_result} conf={confidence_result:.2f} time={processing_time_ms}ms")
        
        return result
        
    except Exception as e:
        processing_time_ms = int((time_module.time() - processing_start) * 1000)
        logger.error(f"DRYRUN mode processing failed: {e}")
        
        # Log error CC for debugging
        try:
            error_cc = create_help_cc(user_id, cc_id, message_text, f"DRYRUN processing error: {str(e)}")
            log_cc_snapshot(error_cc.to_dict(), processing_time_ms=processing_time_ms, error_message=str(e))
        except:
            pass
        
        return {
            'pca_processed': True,
            'cc_logged': False,
            'error': str(e),
            'processing_time_ms': processing_time_ms,
            'mode': 'DRYRUN',
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