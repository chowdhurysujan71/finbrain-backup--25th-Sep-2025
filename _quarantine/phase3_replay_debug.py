#!/usr/bin/env python3
"""
Phase 3: Replay & Debug Implementation
Implements CC replay functionality with audit trails
"""

import sys
import os
import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from flask import Blueprint, request, jsonify, abort

# Add project root to path
sys.path.append('/home/runner/workspace')

from app import app, db
from sqlalchemy import text
from utils.pca_flags import pca_flags

# Blueprint for replay endpoints
replay_bp = Blueprint('replay', __name__, url_prefix='/api/replay')

class CCReplayEngine:
    """Canonical Command Replay Engine for debugging and audit"""
    
    def __init__(self):
        self.replay_enabled = os.environ.get('ENABLE_REPLAY', 'false').lower() == 'true'
        
    def get_cc_by_id(self, cc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve CC by ID from inference_snapshots"""
        try:
            with app.app_context():
                result = db.session.execute(text("""
                    SELECT cc_id, user_id, intent, slots_json, confidence, decision,
                           clarifier_json, model_version, processing_time_ms, 
                           source_text, ui_note, created_at, pca_mode, applied, error_message
                    FROM inference_snapshots 
                    WHERE cc_id = :cc_id
                """), {'cc_id': cc_id}).fetchone()
                
                if not result:
                    return None
                
                return {
                    'cc_id': result[0],
                    'user_id': result[1], 
                    'intent': result[2],
                    'slots': result[3],
                    'confidence': result[4],
                    'decision': result[5],
                    'clarifier': result[6],
                    'model_version': result[7],
                    'processing_time_ms': result[8],
                    'source_text': result[9],
                    'ui_note': result[10],
                    'created_at': result[11].isoformat() if result[11] else None,
                    'pca_mode': result[12],
                    'applied': result[13],
                    'error_message': result[14]
                }
                
        except Exception as e:
            print(f"Error retrieving CC {cc_id}: {str(e)}")
            return None
    
    def replay_cc_decision(self, cc_data: Dict[str, Any]) -> Dict[str, Any]:
        """Replay a CC through current decision logic"""
        try:
            # Extract key fields
            confidence = cc_data['confidence']
            intent = cc_data['intent'] 
            tau_high, tau_low = pca_flags.get_decision_thresholds()
            
            # Replay decision logic
            if confidence >= tau_high:
                new_decision = "AUTO_APPLY"
                clarifier_needed = False
            elif confidence >= tau_low:
                new_decision = "ASK_ONCE" 
                clarifier_needed = True
            else:
                new_decision = "RAW_ONLY"
                clarifier_needed = False
            
            # Generate replay result
            replay_result = {
                'original_decision': cc_data['decision'],
                'replayed_decision': new_decision,
                'decision_changed': cc_data['decision'] != new_decision,
                'confidence': confidence,
                'thresholds': {'tau_high': tau_high, 'tau_low': tau_low},
                'clarifier_needed': clarifier_needed,
                'replay_timestamp': datetime.now().isoformat(),
                'current_pca_mode': pca_flags.mode.value
            }
            
            return replay_result
            
        except Exception as e:
            return {
                'error': str(e),
                'replay_timestamp': datetime.now().isoformat()
            }
    
    def get_user_cc_history(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get CC history for a user"""
        try:
            with app.app_context():
                results = db.session.execute(text("""
                    SELECT cc_id, intent, confidence, decision, created_at, 
                           LEFT(source_text, 100) as source_preview,
                           applied, error_message
                    FROM inference_snapshots 
                    WHERE user_id = :user_id
                    ORDER BY created_at DESC
                    LIMIT :limit
                """), {'user_id': user_id, 'limit': limit}).fetchall()
                
                return [{
                    'cc_id': row[0],
                    'intent': row[1], 
                    'confidence': row[2],
                    'decision': row[3],
                    'created_at': row[4].isoformat() if row[4] else None,
                    'source_preview': row[5],
                    'applied': row[6],
                    'error_message': row[7]
                } for row in results]
                
        except Exception as e:
            print(f"Error retrieving user history for {user_id}: {str(e)}")
            return []

# Initialize replay engine
replay_engine = CCReplayEngine()

def register_replay_routes(app):
    """Register replay routes if enabled"""
    if replay_engine.replay_enabled:
        app.register_blueprint(replay_bp)
        print("✅ Replay API registered at /api/replay/* (enabled)")
    else:
        print("🔒 Replay API disabled (ENABLE_REPLAY=false)")
    return replay_engine.replay_enabled

@replay_bp.route('/<cc_id>', methods=['GET'])
def replay_cc(cc_id: str):
    """Replay a specific CC and return decision analysis"""
    if not replay_engine.replay_enabled:
        abort(403, "Replay functionality is disabled")
    
    # Validate cc_id format
    if not cc_id or len(cc_id) < 10:
        abort(400, "Invalid CC ID format")
    
    # Get original CC
    cc_data = replay_engine.get_cc_by_id(cc_id)
    if not cc_data:
        abort(404, "CC not found")
    
    # Replay decision logic
    replay_result = replay_engine.replay_cc_decision(cc_data)
    
    return jsonify({
        'cc_id': cc_id,
        'original_cc': cc_data,
        'replay_analysis': replay_result,
        'debug_info': {
            'replay_enabled': replay_engine.replay_enabled,
            'server_time': datetime.now().isoformat()
        }
    })

@replay_bp.route('/user/<user_id>/history', methods=['GET'])  
def get_user_history(user_id: str):
    """Get CC history for a user"""
    if not replay_engine.replay_enabled:
        abort(403, "Replay functionality is disabled")
    
    limit = min(int(request.args.get('limit', 50)), 200)  # Max 200 records
    
    history = replay_engine.get_user_cc_history(user_id, limit)
    
    return jsonify({
        'user_id': user_id,
        'history': history,
        'count': len(history),
        'limit': limit
    })

@replay_bp.route('/batch', methods=['POST'])
def replay_batch():
    """Replay multiple CCs for batch analysis"""
    if not replay_engine.replay_enabled:
        abort(403, "Replay functionality is disabled")
    
    data = request.get_json()
    if not data or 'cc_ids' not in data:
        abort(400, "cc_ids array required")
    
    cc_ids = data['cc_ids'][:50]  # Limit to 50 CCs per batch
    
    results = []
    for cc_id in cc_ids:
        cc_data = replay_engine.get_cc_by_id(cc_id)
        if cc_data:
            replay_result = replay_engine.replay_cc_decision(cc_data)
            results.append({
                'cc_id': cc_id,
                'replay_analysis': replay_result
            })
        else:
            results.append({
                'cc_id': cc_id,
                'error': 'CC not found'
            })
    
    return jsonify({
        'batch_results': results,
        'processed': len(results),
        'requested': len(cc_ids)
    })

def register_replay_routes(app):
    """Register replay routes with the Flask app"""
    if replay_engine.replay_enabled:
        app.register_blueprint(replay_bp)
        print(f"✅ Replay API registered at /api/replay/* (enabled)")
    else:
        print(f"🔒 Replay API disabled (ENABLE_REPLAY=false)")

if __name__ == "__main__":
    # CLI tool for replay functionality
    import argparse
    
    parser = argparse.ArgumentParser(description='CC Replay CLI Tool')
    parser.add_argument('--cc-id', help='Replay specific CC ID')
    parser.add_argument('--user-id', help='Get history for user ID')
    parser.add_argument('--limit', type=int, default=10, help='Limit for history query')
    parser.add_argument('--batch-file', help='JSON file with CC IDs for batch replay')
    
    args = parser.parse_args()
    
    if args.cc_id:
        cc_data = replay_engine.get_cc_by_id(args.cc_id)
        if cc_data:
            replay_result = replay_engine.replay_cc_decision(cc_data)
            print(json.dumps({
                'cc_id': args.cc_id,
                'original_cc': cc_data,
                'replay_analysis': replay_result
            }, indent=2))
        else:
            print(f"CC {args.cc_id} not found")
            sys.exit(1)
    
    elif args.user_id:
        history = replay_engine.get_user_cc_history(args.user_id, args.limit)
        print(json.dumps({
            'user_id': args.user_id, 
            'history': history,
            'count': len(history)
        }, indent=2))
    
    elif args.batch_file:
        try:
            with open(args.batch_file, 'r') as f:
                batch_data = json.load(f)
            
            cc_ids = batch_data.get('cc_ids', [])
            results = []
            
            for cc_id in cc_ids:
                cc_data = replay_engine.get_cc_by_id(cc_id)
                if cc_data:
                    replay_result = replay_engine.replay_cc_decision(cc_data)
                    results.append({
                        'cc_id': cc_id,
                        'replay_analysis': replay_result
                    })
            
            print(json.dumps({
                'batch_results': results,
                'processed': len(results)
            }, indent=2))
            
        except Exception as e:
            print(f"Error processing batch file: {e}")
            sys.exit(1)
    
    else:
        parser.print_help()