#!/usr/bin/env python3
"""
📏 FinBrain Data Consistency Standards
Defines and enforces consistent data formats across the single writer system
"""

import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Union


class DataConsistencyStandards:
    """Centralized data consistency standards for FinBrain"""
    
    # ========================================
    # SOURCE VALUE STANDARDS
    # ========================================
    
    # Valid source types (web-only architecture)
    # Valid source types (web-only architecture)  
    @classmethod
    def get_valid_sources(cls):
        from constants import ALLOWED_SOURCES
        return frozenset(ALLOWED_SOURCES)
    
    @staticmethod
    def validate_source(source: str) -> bool:
        """Validate source value against standards"""
        from constants import ALLOWED_SOURCES
        return source in ALLOWED_SOURCES
    
    @staticmethod
    def normalize_source(source: str) -> str:
        """Normalize source value to standard format"""
        source_clean = source.strip().lower()
        
        # Handle common variations
        source_mapping = {
            'web': 'form',
            'website': 'form',
            'ui': 'form',
            'api': 'form',
            'bot': 'chat',
            'chatbot': 'chat',
            'msg': 'messenger',
            'message': 'messenger',
            'fb': 'messenger'
        }
        
        return source_mapping.get(source_clean, source_clean)
    
    # ========================================
    # CURRENCY STANDARDS
    # ========================================
    
    # Primary currency (Bangladesh Taka)
    DEFAULT_CURRENCY = 'BDT'
    
    # Supported currencies with their properties
    CURRENCY_STANDARDS = {
        'BDT': {
            'name': 'Bangladesh Taka',
            'symbol': '৳',
            'decimal_places': 2,
            'min_amount': 0.01,
            'max_amount': 99999999.99
        },
        'USD': {
            'name': 'US Dollar',
            'symbol': '$',
            'decimal_places': 2,
            'min_amount': 0.01,
            'max_amount': 99999999.99
        },
        'EUR': {
            'name': 'Euro',
            'symbol': '€',
            'decimal_places': 2,
            'min_amount': 0.01,
            'max_amount': 99999999.99
        }
    }
    
    @staticmethod
    def validate_currency(currency: str) -> bool:
        """Validate currency code against standards"""
        return currency in DataConsistencyStandards.CURRENCY_STANDARDS
    
    @staticmethod
    def normalize_currency(currency: str | None) -> str:
        """Normalize currency code to standard format"""
        if not currency:
            return DataConsistencyStandards.DEFAULT_CURRENCY
        
        currency_clean = currency.strip().upper()
        
        # Handle common variations
        currency_mapping = {
            'TAKA': 'BDT',
            'BANGLADESHI_TAKA': 'BDT',
            'BD': 'BDT',
            'DOLLAR': 'USD',
            'US': 'USD',
            'EURO': 'EUR',
            'EU': 'EUR'
        }
        
        normalized = currency_mapping.get(currency_clean, currency_clean)
        
        # Return default if not supported
        if normalized not in DataConsistencyStandards.CURRENCY_STANDARDS:
            return DataConsistencyStandards.DEFAULT_CURRENCY
            
        return normalized
    
    @staticmethod
    def get_currency_info(currency: str) -> dict[str, Any]:
        """Get currency information"""
        return DataConsistencyStandards.CURRENCY_STANDARDS.get(
            currency, 
            DataConsistencyStandards.CURRENCY_STANDARDS[DataConsistencyStandards.DEFAULT_CURRENCY]
        )
    
    # ========================================
    # AMOUNT STANDARDS
    # ========================================
    
    @staticmethod
    def validate_amount(amount: float | Decimal | int, currency: str | None = None) -> bool:
        """Validate amount against currency standards"""
        if currency is None:
            currency = DataConsistencyStandards.DEFAULT_CURRENCY
        
        currency_info = DataConsistencyStandards.get_currency_info(currency)
        amount_decimal = Decimal(str(amount))
        
        min_amount = Decimal(str(currency_info['min_amount']))
        max_amount = Decimal(str(currency_info['max_amount']))
        
        return min_amount <= amount_decimal <= max_amount
    
    @staticmethod
    def normalize_amount(amount: float | str | Decimal, currency: str | None = None) -> Decimal:
        """Normalize amount to standard decimal format"""
        if currency is None:
            currency = DataConsistencyStandards.DEFAULT_CURRENCY
        
        currency_info = DataConsistencyStandards.get_currency_info(currency)
        decimal_places = currency_info['decimal_places']
        
        # Convert to Decimal for precision
        amount_decimal = Decimal(str(amount))
        
        # Round to appropriate decimal places
        return amount_decimal.quantize(
            Decimal('0.01') if decimal_places == 2 else Decimal('0.001'),
            rounding=ROUND_HALF_UP
        )
    
    @staticmethod
    def amount_to_minor_units(amount: float | str | Decimal, currency: str | None = None) -> int:
        """Convert amount to minor units (e.g., cents) for precise storage"""
        if currency is None:
            currency = DataConsistencyStandards.DEFAULT_CURRENCY
        
        currency_info = DataConsistencyStandards.get_currency_info(currency)
        decimal_places = currency_info['decimal_places']
        
        amount_normalized = DataConsistencyStandards.normalize_amount(amount, currency)
        multiplier = 10 ** decimal_places
        
        return int(amount_normalized * multiplier)
    
    @staticmethod
    def minor_units_to_amount(amount_minor: int, currency: str | None = None) -> Decimal:
        """Convert minor units back to decimal amount"""
        if currency is None:
            currency = DataConsistencyStandards.DEFAULT_CURRENCY
        
        currency_info = DataConsistencyStandards.get_currency_info(currency)
        decimal_places = currency_info['decimal_places']
        
        divisor = 10 ** decimal_places
        return Decimal(amount_minor) / divisor
    
    # ========================================
    # CATEGORY STANDARDS
    # ========================================
    
    # Standard expense categories
    STANDARD_CATEGORIES = {
        'food': ['food', 'restaurant', 'dining', 'meal', 'snack', 'grocery'],
        'transport': ['transport', 'taxi', 'bus', 'train', 'travel', 'fuel', 'gas'],
        'shopping': ['shopping', 'clothes', 'electronics', 'purchase', 'buy'],
        'entertainment': ['entertainment', 'movie', 'game', 'fun', 'leisure'],
        'health': ['health', 'medical', 'doctor', 'pharmacy', 'medicine'],
        'utilities': ['utilities', 'electric', 'water', 'gas', 'internet', 'phone'],
        'education': ['education', 'school', 'book', 'course', 'learning'],
        'other': ['other', 'misc', 'miscellaneous', 'general']
    }
    
    @staticmethod
    def normalize_category(category: str) -> str:
        """Normalize category to standard format"""
        if not category:
            return 'other'
        
        category_clean = category.strip().lower()
        
        # Direct match first
        if category_clean in DataConsistencyStandards.STANDARD_CATEGORIES:
            return category_clean
        
        # Fuzzy match against aliases
        for standard_cat, aliases in DataConsistencyStandards.STANDARD_CATEGORIES.items():
            if category_clean in aliases:
                return standard_cat
            
            # Partial match
            for alias in aliases:
                if alias in category_clean or category_clean in alias:
                    return standard_cat
        
        return 'other'  # Default fallback
    
    # ========================================
    # TEXT STANDARDS
    # ========================================
    
    @staticmethod
    def normalize_text(text: str | None, max_length: int | None = None) -> str:
        """Normalize text fields to consistent format"""
        if not text:
            return ''
        
        # Remove excessive whitespace
        normalized = ' '.join(text.strip().split())
        
        # Remove control characters but preserve basic punctuation
        normalized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', normalized)
        
        # Truncate if needed
        if max_length and len(normalized) > max_length:
            normalized = normalized[:max_length].rstrip()
        
        return normalized
    
    @staticmethod
    def normalize_description(description: str | None) -> str:
        """Normalize expense description"""
        return DataConsistencyStandards.normalize_text(description, max_length=500)
    
    @staticmethod
    def normalize_merchant_text(merchant: str | None) -> str:
        """Normalize merchant text"""
        return DataConsistencyStandards.normalize_text(merchant, max_length=200)
    
    # ========================================
    # VALIDATION UTILITIES
    # ========================================
    
    @staticmethod
    def validate_expense_data(expense_data: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalize complete expense data"""
        errors = []
        normalized_data = {}
        
        # Source validation
        source = expense_data.get('source')
        if source:
            if DataConsistencyStandards.validate_source(source):
                normalized_data['source'] = source
            else:
                normalized_source = DataConsistencyStandards.normalize_source(source)
                if DataConsistencyStandards.validate_source(normalized_source):
                    normalized_data['source'] = normalized_source
                else:
                    errors.append(f"Invalid source: {source}")
        else:
            errors.append("Source is required")
        
        # Currency validation
        currency = expense_data.get('currency')
        normalized_currency = DataConsistencyStandards.normalize_currency(currency)
        normalized_data['currency'] = normalized_currency
        
        # Amount validation
        amount = expense_data.get('amount')
        if amount is not None:
            try:
                if DataConsistencyStandards.validate_amount(amount, normalized_currency):
                    normalized_data['amount'] = DataConsistencyStandards.normalize_amount(amount, normalized_currency)
                    normalized_data['amount_minor'] = DataConsistencyStandards.amount_to_minor_units(amount, normalized_currency)
                else:
                    currency_info = DataConsistencyStandards.get_currency_info(normalized_currency)
                    errors.append(f"Amount {amount} outside valid range {currency_info['min_amount']}-{currency_info['max_amount']}")
            except (ValueError, TypeError):
                errors.append(f"Invalid amount format: {amount}")
        else:
            errors.append("Amount is required")
        
        # Category validation
        category = expense_data.get('category')
        if category:
            normalized_data['category'] = DataConsistencyStandards.normalize_category(category)
        else:
            normalized_data['category'] = 'other'
        
        # Text field normalization
        description = expense_data.get('description')
        if description:
            normalized_data['description'] = DataConsistencyStandards.normalize_description(description)
        else:
            errors.append("Description is required")
        
        merchant_text = expense_data.get('merchant_text')
        if merchant_text:
            normalized_data['merchant_text'] = DataConsistencyStandards.normalize_merchant_text(merchant_text)
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'normalized_data': normalized_data
        }

# ========================================
# CONVENIENCE FUNCTIONS
# ========================================

def validate_and_normalize_expense(expense_data: dict[str, Any]) -> dict[str, Any]:
    """
    Convenience function to validate and normalize expense data
    
    Returns:
        Dict with 'valid', 'errors', and 'normalized_data' keys
    """
    return DataConsistencyStandards.validate_expense_data(expense_data)

def get_supported_currencies() -> list[str]:
    """Get list of supported currency codes"""
    return list(DataConsistencyStandards.CURRENCY_STANDARDS.keys())

def get_valid_sources() -> list[str]:
    """Get list of valid source values"""
    from constants import ALLOWED_SOURCES
    return list(ALLOWED_SOURCES)

if __name__ == "__main__":
    # Example usage and validation
    print("📏 FinBrain Data Consistency Standards")
    print("=" * 50)
    
    print(f"✅ Supported Currencies: {get_supported_currencies()}")
    print(f"✅ Default Currency: {DataConsistencyStandards.DEFAULT_CURRENCY}")
    
    # Test data validation
    test_expense = {
        'source': 'chat',  # Should be valid for web-only architecture
        'amount': 123.456,  # Should round to 123.46
        'currency': 'taka',  # Should normalize to 'BDT'
        'category': 'restaurant',  # Should normalize to 'food'
        'description': '  Lunch at   restaurant  \n ',  # Should clean whitespace
        'merchant_text': 'Local Restaurant'
    }
    
    result = validate_and_normalize_expense(test_expense)
    print("\n🧪 Test Validation:")
    print(f"Valid: {result['valid']}")
    if result['errors']:
        print(f"Errors: {result['errors']}")
    print(f"Normalized: {result['normalized_data']}")
    
    print("\n✅ Data Consistency Standards Ready!")