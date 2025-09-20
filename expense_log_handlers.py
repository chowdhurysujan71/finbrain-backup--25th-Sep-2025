"""
EXPENSE_LOG and CLARIFY_EXPENSE intent handlers
Implements PoR v1.1 expense logging and clarification flows
"""

import logging
import time
from typing import Dict, Any

logger = logging.getLogger("finbrain.expense_log_handlers")

def handle_expense_log_intent(user_id: str, text: str, signals: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle EXPENSE_LOG intent - money + first-person past-tense verb detected
    
    Args:
        user_id: User identifier (PSID hash)
        text: Original message text
        signals: Extracted routing signals
        
    Returns:
        Response dictionary with expense logging confirmation
    """
    try:
        # Extract expense details using existing parsers
        from parsers.expense import parse_amount_currency_category
        from utils.ai_adapter_v2 import production_ai_adapter
        
        # Parse expense using existing system
        parsed_expense = parse_amount_currency_category(text)
        
        if parsed_expense and parsed_expense.get('amount', 0) > 0:
            # Store expense using CANONICAL SINGLE WRITER (spec compliance)
            try:
                import backend_assistant as ba
                from datetime import datetime
                import uuid
                
                # Generate proper metadata for unified function
                source_message_id = f"chat_expense_{int(time.time() * 1000000)}"
                
                expense_record = ba.add_expense(
                    user_id=user_id,
                    amount_minor=int(parsed_expense['amount'] * 100),  # Convert to minor units
                    currency='BDT',
                    category=parsed_expense.get('category', 'General'),
                    description=parsed_expense.get('description', text[:50]),
                    source='chat',  # Intent handler is chat-based
                    message_id=source_message_id
                )
            except Exception as db_error:
                logger.error(f"Unified expense creation failed: {db_error}")
                # Return error for proper handling
                return {
                    "intent": "EXPENSE_LOG",
                    "success": False,
                    "response": "Unable to log expense. Please try again.",
                    "error": str(db_error)
                }
            
            if expense_record:
                # Generate confirmation response
                amount = parsed_expense['amount']
                category = parsed_expense.get('category', 'General')
                
                # Use Bengali numerals for Bengali users  
                is_bengali = any(char in text for char in 'আইউএওঅকখগঘচছজঝটঠডঢতথদধনপফবভমযরলশষসহ')
                if is_bengali:
                    ai_response = f"✅ লগ করা হলো: ৳{amount:.0f} {category}র জন্য"
                else:
                    ai_response = f"✅ Logged: ৳{amount:.0f} for {category}"
                
                return {
                    "intent": "EXPENSE_LOG",
                    "success": True,
                    "response": ai_response,
                    "expense_id": expense_record.get('expense_id'),
                    "amount": parsed_expense['amount'],
                    "category": parsed_expense.get('category')
                }
        
        # Fallback if parsing failed
        return {
            "intent": "EXPENSE_LOG",
            "success": False,
            "response": "I couldn't parse the expense details. Can you try again with amount and description?",
            "error": "parsing_failed"
        }
        
    except Exception as e:
        logger.error(f"EXPENSE_LOG handler error: {e}")
        return {
            "intent": "EXPENSE_LOG",
            "success": False,
            "response": "Sorry, I couldn't log that expense right now. Please try again.",
            "error": str(e)
        }

def handle_clarify_expense_intent(user_id: str, text: str, signals: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle CLARIFY_EXPENSE intent - money detected but no first-person verb
    
    Args:
        user_id: User identifier
        text: Original message text
        signals: Extracted routing signals
        
    Returns:
        Response dictionary with clarification options
    """
    try:
        # Extract money amount for clarification
        from utils.bn_digits import to_en_digits
        from nlp.money_patterns import extract_money_mentions
        
        # Normalize and extract money mentions
        normalized_text = to_en_digits(text)
        money_mentions = extract_money_mentions(normalized_text)
        
        if money_mentions:
            money_amount = money_mentions[0]  # Use first money mention
            
            # Detect if user is likely Bengali speaker based on text
            is_bengali = any(char in text for char in 'আইউএওঅকখগঘচছজঝটঠডঢতথদধনপফবভমযরলশষসহ')
            
            if is_bengali:
                # Bengali clarification template
                clarify_text = f"Tea হিসেবে ৳{money_amount.replace('৳', '').strip()} আজ লগ করতে চান?"
                options = ["হ্যাঁ, লগ করুন", "না", "বরং সারাংশ দেখান"]
            else:
                # English clarification template
                clarify_text = f"Log ৳{money_amount.replace('৳', '').strip()} for Tea today?"
                options = ["Yes, log it", "No", "Show summary instead"]
            
            return {
                "intent": "CLARIFY_EXPENSE",
                "success": True,
                "response": clarify_text,
                "options": options,
                "money_amount": money_amount,
                "original_text": text,
                "language": "bengali" if is_bengali else "english"
            }
        
        # Fallback if no money found (shouldn't happen)
        return {
            "intent": "CLARIFY_EXPENSE", 
            "success": False,
            "response": "I noticed you mentioned an amount but I'm not sure what you want to do. Can you clarify?",
            "error": "no_money_extracted"
        }
        
    except Exception as e:
        logger.error(f"CLARIFY_EXPENSE handler error: {e}")
        return {
            "intent": "CLARIFY_EXPENSE",
            "success": False,
            "response": "I'm not sure what you'd like to do. Can you try again?",
            "error": str(e)
        }

def handle_clarification_response(user_id: str, response_text: str, original_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle user response to clarification prompt
    
    Args:
        user_id: User identifier
        response_text: User's response to clarification
        original_context: Original clarification context
        
    Returns:
        Response dictionary with appropriate action
    """
    try:
        response_lower = response_text.lower().strip()
        
        # Check for "Yes, log it" responses
        if any(phrase in response_lower for phrase in ['yes', 'হ্যাঁ', 'log', 'লগ করুন']):
            # Convert to EXPENSE_LOG format and handle
            money_amount = original_context.get('money_amount', '50')
            synthetic_expense_text = f"expense {money_amount} taka"
            
            # Create signals for expense logging
            signals = {"has_money": True, "has_first_person_spent_verb": True}
            
            return handle_expense_log_intent(user_id, synthetic_expense_text, signals)
        
        # Check for "Show summary" responses  
        elif any(phrase in response_lower for phrase in ['summary', 'সারাংশ', 'analysis']):
            # Route to analysis with route correction tracking
            from handlers.summary import handle_summary
            
            result = handle_summary(user_id)
            return {
                "intent": "CLARIFY_RESPONSE",
                "success": True,
                "response": result.get('text', 'Here is your spending summary'),
                "action": "analysis_requested"
            }
        
        # Handle "No" responses
        else:
            return {
                "intent": "CLARIFY_RESPONSE",
                "success": True,
                "response": "No problem! Let me know if you need anything else.",
                "action": "dismissed"
            }
            
    except Exception as e:
        logger.error(f"Clarification response handler error: {e}")
        return {
            "intent": "CLARIFY_RESPONSE",
            "success": False,
            "response": "I didn't understand your response. Can you try again?",
            "error": str(e)
        }