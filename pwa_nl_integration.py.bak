"""
Natural Language Integration for PWA UI
Integrates the NL expense parser with the existing form-based expense system
"""

import logging
from flask import request, jsonify, render_template, redirect, url_for
from typing import Dict, Any

from utils.nl_expense_parser import parse_nl_expense, ExpenseParseResult
from utils.expense_editor import edit_last_expense, expense_editor
from utils.db import save_expense
from utils.identity import psid_hash
from models import Expense
from app import db

logger = logging.getLogger(__name__)

def handle_nl_expense_entry(text: str, user_id_hash: str) -> Dict[str, Any]:
    """
    Handle natural language expense entry with clarification flow
    
    Args:
        text: User's natural language input
        user_id_hash: User identifier
        
    Returns:
        Dict with parsing results and next steps
    """
    try:
        # Parse with NL parser
        result = parse_nl_expense(text, user_id_hash)
        
        if result.success and not result.needs_clarification:
            # High confidence - save directly
            expense_result = save_expense(
                user_identifier=user_id_hash,
                description=result.description or text,
                amount=result.amount,
                category=result.category,
                platform='pwa',
                original_message=text,
                unique_id=f"nl_{user_id_hash}_{hash(text)}",
                db_session=db
            )
            
            if expense_result.get('success', False):
                # Update NL metadata
                expense_id = expense_result.get('expense_id')
                if expense_id:
                    expense = Expense.query.get(expense_id)
                    if expense:
                        expense.nl_confidence = result.confidence
                        expense.nl_language = result.language
                        expense.needed_clarification = False
                        db.session.commit()
                
                return {
                    "success": True,
                    "action": "saved",
                    "expense": {
                        "id": expense_id,
                        "amount": result.amount,
                        "category": result.category,
                        "description": result.description,
                        "confidence": result.confidence
                    },
                    "message": f"✅ Expense logged: ৳{result.amount} for {result.category}"
                }
            else:
                return {
                    "success": False,
                    "action": "error",
                    "error": expense_result.get('error', 'Failed to save expense')
                }
        
        elif result.needs_clarification:
            # Low confidence - request clarification
            return {
                "success": True,
                "action": "clarify",
                "clarification_type": result.clarification_type,
                "detected_amount": result.amount,
                "detected_description": result.description or text,
                "suggested_categories": result.suggested_categories or [],
                "confidence": result.confidence,
                "message": "Need clarification for accurate logging"
            }
        
        else:
            # Parsing failed
            return {
                "success": False,
                "action": "error",
                "error": result.error_message or "Could not understand the expense"
            }
            
    except Exception as e:
        logger.error(f"NL expense entry error: {e}")
        return {
            "success": False,
            "action": "error", 
            "error": f"Processing failed: {str(e)}"
        }

def handle_clarification_response(
    original_text: str, 
    user_id_hash: str,
    confirmed_amount: float = None,
    confirmed_category: str = None,
    confirmed_description: str = None
) -> Dict[str, Any]:
    """
    Handle user's clarification response and save the expense
    
    Args:
        original_text: Original user input
        user_id_hash: User identifier
        confirmed_amount: User-confirmed amount
        confirmed_category: User-selected category
        confirmed_description: User-confirmed description
        
    Returns:
        Dict with save results
    """
    try:
        # Save the clarified expense
        expense_result = save_expense(
            user_identifier=user_id_hash,
            description=confirmed_description or original_text,
            amount=confirmed_amount,
            category=confirmed_category,
            platform='pwa',
            original_message=original_text,
            unique_id=f"nl_clarified_{user_id_hash}_{hash(original_text)}",
            db_session=db
        )
        
        if expense_result.get('success', False):
            # Update metadata to indicate this needed clarification
            expense_id = expense_result.get('expense_id')
            if expense_id:
                expense = Expense.query.get(expense_id)
                if expense:
                    expense.nl_confidence = 0.9  # High confidence after clarification
                    expense.nl_language = 'clarified'
                    expense.needed_clarification = True
                    db.session.commit()
            
            return {
                "success": True,
                "expense": {
                    "id": expense_id,
                    "amount": confirmed_amount,
                    "category": confirmed_category,
                    "description": confirmed_description
                },
                "message": f"✅ Expense confirmed: ৳{confirmed_amount} for {confirmed_category}"
            }
        else:
            return {
                "success": False,
                "error": expense_result.get('error', 'Failed to save clarified expense')
            }
            
    except Exception as e:
        logger.error(f"Clarification response error: {e}")
        return {
            "success": False,
            "error": f"Saving failed: {str(e)}"
        }

def handle_edit_last_expense_request(
    user_id_hash: str,
    new_amount: float = None,
    new_category: str = None,
    new_description: str = None,
    reason: str = None
) -> Dict[str, Any]:
    """
    Handle "Edit Last Expense" functionality
    
    Args:
        user_id_hash: User identifier
        new_amount: New amount (if changing)
        new_category: New category (if changing)
        new_description: New description (if changing)
        reason: Reason for edit
        
    Returns:
        Dict with edit results
    """
    try:
        result = edit_last_expense(
            user_id_hash=user_id_hash,
            new_amount=new_amount,
            new_category=new_category,
            new_description=new_description,
            reason=reason
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Edit last expense error: {e}")
        return {
            "success": False,
            "error": f"Edit failed: {str(e)}"
        }

def get_expense_edit_history(user_id_hash: str, expense_id: int) -> List[Dict]:
    """Get edit history for an expense"""
    try:
        return expense_editor.get_edit_history(expense_id, user_id_hash)
    except Exception as e:
        logger.error(f"Get edit history error: {e}")
        return []

# Template rendering helpers
def render_clarification_ui(
    original_text: str,
    detected_amount: float = None,
    suggested_categories: List[Dict] = None
) -> str:
    """Render the clarification UI for low-confidence parsing"""
    
    categories = [
        {"id": "food", "name": "🍽️ Food", "icon": "🍽️"},
        {"id": "transport", "name": "🚗 Transport", "icon": "🚗"},
        {"id": "shopping", "name": "🛍️ Shopping", "icon": "🛍️"},
        {"id": "bills", "name": "💡 Bills", "icon": "💡"},
        {"id": "health", "name": "🏥 Health", "icon": "🏥"},
        {"id": "education", "name": "📚 Education", "icon": "📚"},
        {"id": "entertainment", "name": "🎬 Entertainment", "icon": "🎬"},
        {"id": "other", "name": "📝 Other", "icon": "📝"}
    ]
    
    # Prioritize suggested categories
    if suggested_categories:
        suggested_ids = [cat.get('category') for cat in suggested_categories]
        categories.sort(key=lambda x: 0 if x['id'] in suggested_ids else 1)
    
    return render_template('clarification_ui.html', 
                         original_text=original_text,
                         detected_amount=detected_amount,
                         categories=categories,
                         suggested_categories=suggested_categories or [])

def render_edit_last_expense_ui(user_id_hash: str) -> str:
    """Render the edit last expense UI"""
    last_expense = expense_editor.get_last_expense(user_id_hash)
    
    if not last_expense:
        return render_template('no_expenses.html')
    
    return render_template('edit_expense.html',
                         expense=last_expense,
                         categories=[
                             {"id": "food", "name": "🍽️ Food"},
                             {"id": "transport", "name": "🚗 Transport"}, 
                             {"id": "shopping", "name": "🛍️ Shopping"},
                             {"id": "bills", "name": "💡 Bills"},
                             {"id": "health", "name": "🏥 Health"},
                             {"id": "education", "name": "📚 Education"},
                             {"id": "entertainment", "name": "🎬 Entertainment"},
                             {"id": "other", "name": "📝 Other"}
                         ])