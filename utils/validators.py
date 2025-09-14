"""
Input Validation System for FinBrain API
Provides comprehensive field validation with detailed error messages
"""

import re
import logging
from typing import Dict, Any, List, Optional, Union
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)

class ValidationResult:
    """Container for validation results"""
    def __init__(self):
        self.errors: Dict[str, str] = {}
        self.is_valid = True
    
    def add_error(self, field: str, message: str):
        """Add validation error for a field"""
        self.errors[field] = message
        self.is_valid = False
    
    def has_errors(self) -> bool:
        """Check if any validation errors exist"""
        return not self.is_valid

class ExpenseValidator:
    """Validator for expense-related data"""
    
    # Valid expense categories (from existing system)
    VALID_CATEGORIES = {
        'food', 'transport', 'shopping', 'entertainment', 'bills', 
        'healthcare', 'education', 'travel', 'other'
    }
    
    @staticmethod
    def validate_amount(amount: Any, field_name: str = "amount") -> Optional[str]:
        """
        Validate expense amount
        
        Args:
            amount: Amount to validate (can be string, int, float)
            field_name: Name of the field for error messages
            
        Returns:
            Error message if invalid, None if valid
        """
        if amount is None or amount == "":
            return "Amount is required"
        
        try:
            # Convert to decimal for precise validation
            if isinstance(amount, str):
                amount = amount.strip()
                if not amount:
                    return "Amount is required"
            
            amount_decimal = Decimal(str(amount))
            
            # Check if positive
            if amount_decimal <= 0:
                return "Amount must be greater than 0"
            
            # Check reasonable bounds (less than 1 million)
            if amount_decimal >= 1000000:
                return "Amount must be less than 1,000,000"
            
            # Check decimal places (max 2)
            if amount_decimal.as_tuple().exponent < -2:
                return "Amount can have at most 2 decimal places"
                
            return None
            
        except (ValueError, InvalidOperation, TypeError):
            return "Amount must be a valid number"
    
    @staticmethod
    def validate_category(category: Any) -> Optional[str]:
        """Validate expense category"""
        if not category or str(category).strip() == "":
            return "Category is required"
        
        category_str = str(category).strip().lower()
        
        if category_str not in ExpenseValidator.VALID_CATEGORIES:
            valid_categories = ", ".join(sorted(ExpenseValidator.VALID_CATEGORIES))
            return f"Category must be one of: {valid_categories}"
        
        return None
    
    @staticmethod
    def validate_description(description: Any, required: bool = False) -> Optional[str]:
        """Validate expense description"""
        if description is None or str(description).strip() == "":
            if required:
                return "Description is required"
            return None
        
        desc_str = str(description).strip()
        
        if len(desc_str) > 500:
            return "Description must be 500 characters or less"
        
        return None
    
    @staticmethod
    def validate_expense_data(data: Dict[str, Any]) -> ValidationResult:
        """Validate complete expense submission"""
        result = ValidationResult()
        
        # Validate amount
        amount_error = ExpenseValidator.validate_amount(data.get('amount'))
        if amount_error:
            result.add_error('amount', amount_error)
        
        # Validate category
        category_error = ExpenseValidator.validate_category(data.get('category'))
        if category_error:
            result.add_error('category', category_error)
        
        # Validate description (optional)
        description_error = ExpenseValidator.validate_description(data.get('description'))
        if description_error:
            result.add_error('description', description_error)
        
        return result

class AuthValidator:
    """Validator for authentication-related data"""
    
    # Email regex pattern (basic but robust)
    EMAIL_PATTERN = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    
    @staticmethod
    def validate_email(email: Any) -> Optional[str]:
        """Validate email address format"""
        if not email or str(email).strip() == "":
            return "Email is required"
        
        email_str = str(email).strip().lower()
        
        if len(email_str) > 320:  # RFC 5321 limit
            return "Email address is too long"
        
        if not AuthValidator.EMAIL_PATTERN.match(email_str):
            return "Please enter a valid email address"
        
        return None
    
    @staticmethod
    def validate_password(password: Any, field_name: str = "password") -> Optional[str]:
        """Validate password strength"""
        if not password:
            return f"{field_name.capitalize()} is required"
        
        password_str = str(password)
        
        # Minimum length
        if len(password_str) < 8:
            return f"{field_name.capitalize()} must be at least 8 characters long"
        
        # Maximum length (prevent DoS)
        if len(password_str) > 128:
            return f"{field_name.capitalize()} must be 128 characters or less"
        
        # Check for at least one letter and one number
        has_letter = any(c.isalpha() for c in password_str)
        has_number = any(c.isdigit() for c in password_str)
        
        if not has_letter:
            return f"{field_name.capitalize()} must contain at least one letter"
        
        if not has_number:
            return f"{field_name.capitalize()} must contain at least one number"
        
        return None
    
    @staticmethod
    def validate_name(name: Any, required: bool = True, field_name: str = "name") -> Optional[str]:
        """Validate person name"""
        if not name or str(name).strip() == "":
            if required:
                return f"{field_name.capitalize()} is required"
            return None
        
        name_str = str(name).strip()
        
        if len(name_str) > 100:
            return f"{field_name.capitalize()} must be 100 characters or less"
        
        # Check for valid characters (letters, spaces, hyphens, apostrophes)
        if not re.match(r"^[a-zA-Z\s\-']+$", name_str):
            return f"{field_name.capitalize()} can only contain letters, spaces, hyphens, and apostrophes"
        
        return None
    
    @staticmethod
    def validate_login_data(data: Dict[str, Any]) -> ValidationResult:
        """Validate login form data"""
        result = ValidationResult()
        
        # Validate email
        email_error = AuthValidator.validate_email(data.get('email'))
        if email_error:
            result.add_error('email', email_error)
        
        # Validate password (basic check for login)
        password = data.get('password')
        if not password:
            result.add_error('password', 'Password is required')
        
        return result
    
    @staticmethod
    def validate_registration_data(data: Dict[str, Any]) -> ValidationResult:
        """Validate registration form data"""
        result = ValidationResult()
        
        # Validate email
        email_error = AuthValidator.validate_email(data.get('email'))
        if email_error:
            result.add_error('email', email_error)
        
        # Validate password with strength requirements
        password_error = AuthValidator.validate_password(data.get('password'))
        if password_error:
            result.add_error('password', password_error)
        
        # Validate name (optional but if provided should be valid)
        name_error = AuthValidator.validate_name(data.get('name'), required=False)
        if name_error:
            result.add_error('name', name_error)
        
        return result

class APIValidator:
    """General API validation utilities"""
    
    @staticmethod
    def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> ValidationResult:
        """Validate that all required fields are present and non-empty"""
        result = ValidationResult()
        
        for field in required_fields:
            value = data.get(field)
            if value is None or str(value).strip() == "":
                result.add_error(field, "This field is required")
        
        return result
    
    @staticmethod
    def validate_integer(value: Any, field_name: str, min_val: int = None, max_val: int = None) -> Optional[str]:
        """Validate integer value with optional bounds"""
        if value is None:
            return f"{field_name.capitalize()} is required"
        
        try:
            int_val = int(value)
            
            if min_val is not None and int_val < min_val:
                return f"{field_name.capitalize()} must be at least {min_val}"
            
            if max_val is not None and int_val > max_val:
                return f"{field_name.capitalize()} must be at most {max_val}"
            
            return None
            
        except (ValueError, TypeError):
            return f"{field_name.capitalize()} must be a valid number"
    
    @staticmethod
    def validate_string_length(value: Any, field_name: str, min_length: int = None, max_length: int = None) -> Optional[str]:
        """Validate string length"""
        if value is None:
            return f"{field_name.capitalize()} is required"
        
        str_val = str(value)
        
        if min_length is not None and len(str_val) < min_length:
            return f"{field_name.capitalize()} must be at least {min_length} characters long"
        
        if max_length is not None and len(str_val) > max_length:
            return f"{field_name.capitalize()} must be {max_length} characters or less"
        
        return None
    
    @staticmethod
    def validate_choice(value: Any, field_name: str, valid_choices: List[str]) -> Optional[str]:
        """Validate that value is in allowed choices"""
        if value is None:
            return f"{field_name.capitalize()} is required"
        
        str_val = str(value).strip()
        
        if str_val not in valid_choices:
            choices_str = ", ".join(valid_choices)
            return f"{field_name.capitalize()} must be one of: {choices_str}"
        
        return None

# Convenience functions for common validations
def validate_expense(data: Dict[str, Any]) -> ValidationResult:
    """Convenience function to validate expense data"""
    return ExpenseValidator.validate_expense_data(data)

def validate_login(data: Dict[str, Any]) -> ValidationResult:
    """Convenience function to validate login data"""
    return AuthValidator.validate_login_data(data)

def validate_registration(data: Dict[str, Any]) -> ValidationResult:
    """Convenience function to validate registration data"""
    return AuthValidator.validate_registration_data(data)