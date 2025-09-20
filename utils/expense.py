"""Core expense parsing and processing logic"""
import re
import logging
from datetime import datetime
from utils.categories import categorize_expense
from utils.db import save_expense

logger = logging.getLogger(__name__)

def parse_amount(message):
    """Extract numeric amount from expense message using regex"""
    try:
        # Remove currency symbols and extract numbers
        cleaned_message = re.sub(r'[৳$€£¥₹]', '', message)
        
        # Find all numbers (including decimals)
        amounts = re.findall(r'\d+\.?\d*', cleaned_message)
        
        if amounts:
            # Take the first number found
            amount = float(amounts[0])
            return amount if amount > 0 else None
        
        return None
        
    except (ValueError, TypeError) as e:
        logger.error(f"Error parsing amount from '{message}': {str(e)}")
        return None

def extract_description(message, amount):
    """Extract description by removing amount and cleaning text"""
    try:
        if not amount:
            return message.strip()
        
        # Remove the amount from the message
        amount_str = str(int(amount)) if amount.is_integer() else str(amount)
        description = re.sub(rf'\b{re.escape(amount_str)}\b', '', message, 1)
        
        # Remove currency symbols
        description = re.sub(r'[৳$€£¥₹]', '', description)
        
        # Clean up extra spaces
        description = ' '.join(description.split())
        
        return description.strip() or 'Expense'
        
    except Exception as e:
        logger.error(f"Error extracting description: {str(e)}")
        return 'Expense'

def process_expense_message(user_identifier, message, platform, unique_id):
    """Process expense message and save to database"""
    try:
        # Parse amount from message
        amount = parse_amount(message)
        
        if not amount:
            return {
                'success': False,
                'message': 'No amount found in message. Please include a number like "Coffee 150" or "৳200 lunch"'
            }
        
        # Extract description
        description = extract_description(message, amount)
        
        # Categorize expense
        category = categorize_expense(description + ' ' + message)
        
        # Save to database using CANONICAL SINGLE WRITER (spec compliance)
        import backend_assistant as ba
        result = ba.add_expense(
            user_id=user_identifier,
            amount_minor=int(amount * 100),  # Convert to minor units
            currency='BDT',
            category=category,
            description=description,
            source='form',  # This appears to be form-based input
            message_id=unique_id
        )
        
        if result['success']:
            # Format response message
            category_emoji = get_category_emoji(category)
            response_message = f"✅ Logged: {description} {amount} {category_emoji} Total: ৳{result['monthly_total']:.2f}"
            
            return {
                'success': True,
                'message': response_message,
                'amount': amount,
                'category': category,
                'monthly_total': result['monthly_total']
            }
        else:
            return {
                'success': False,
                'message': 'Error saving expense. Please try again.'
            }
            
    except Exception as e:
        logger.error(f"Error processing expense message: {str(e)}")
        return {
            'success': False,
            'message': 'Error processing expense. Please try again.'
        }

def get_category_emoji(category):
    """Get emoji for expense category"""
    emojis = {
        'Food': '🍔',
        'Transport': '🚗',
        'Shopping': '🛍️',
        'Groceries': '🛒',
        'Utilities': '💡',
        'Entertainment': '🎬',
        'Health': '🏥',
        'Education': '📚',
        'Personal Care': '💅',
        'Misc': '💼'
    }
    return emojis.get(category, '💼')

def format_expense_summary(summary):
    """Format monthly summary for display"""
    try:
        total = summary['total_amount']
        count = summary['expense_count']
        month = summary['month']
        
        message = f"📊 {month} Summary:\n"
        message += f"💰 Total: ৳{total:.2f}\n"
        message += f"📝 Expenses: {count}\n"
        
        if summary['categories']:
            message += "\n📋 Categories:\n"
            for category, amount in summary['categories'].items():
                emoji = get_category_emoji(category)
                percentage = (amount / total * 100) if total > 0 else 0
                message += f"{emoji} {category}: ৳{amount:.2f} ({percentage:.1f}%)\n"
        
        return message.strip()
        
    except Exception as e:
        logger.error(f"Error formatting expense summary: {str(e)}")
        return "Error generating summary"
