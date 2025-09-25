"""
Multi-item expense parsing support
Converts multi-item messages into multiple Canonical Commands
"""

import re
import logging
from typing import List, Dict, Any
from utils.canonical_command import CanonicalCommand, CCSlots

logger = logging.getLogger("finbrain.multi_item")

class MultiItemParser:
    """Parse and handle multi-item expense messages"""
    
    def __init__(self):
        # Patterns for detecting multi-item messages
        self.multi_patterns = [
            r'(\d+)\s+(?:for|@)\s+(\w+)[,;]\s+(\d+)\s+(?:for|@)\s+(\w+)',  # "100 for food, 200 for transport"
            r'(\w+)\s+(\d+)[,;]\s+(\w+)\s+(\d+)',  # "lunch 100, taxi 200"
            r'total\s+(\d+).*breakdown.*',  # "total 500 breakdown: ..."
        ]
        
    def detect_multi_item(self, text: str) -> bool:
        """Check if message contains multiple items"""
        # Look for separators and multiple amounts
        separators = [',', ';', '+', 'and', 'plus']
        amounts = re.findall(r'\d+(?:\.\d+)?', text.lower())
        
        # Multiple amounts with separators suggests multi-item
        if len(amounts) >= 2:
            for sep in separators:
                if sep in text.lower():
                    return True
                    
        # Check specific patterns
        for pattern in self.multi_patterns:
            if re.search(pattern, text.lower()):
                return True
                
        return False
    
    def parse_items(self, text: str) -> List[Dict[str, Any]]:
        """
        Parse multi-item message into separate items
        Returns list of item dictionaries
        """
        items = []
        text_lower = text.lower()
        
        # Try pattern-based extraction first
        # Pattern: "amount for category" style
        pattern = r'(\d+(?:\.\d+)?)\s+(?:for|@|taka|bdt|৳)?\s*([^,;]+)'
        matches = re.findall(pattern, text_lower)
        
        if matches and len(matches) > 1:
            for amount_str, desc in matches:
                try:
                    amount = float(amount_str)
                    desc = desc.strip()
                    
                    # Extract category hint from description
                    category = self._infer_category(desc)
                    
                    items.append({
                        'amount': amount,
                        'merchant_text': desc,
                        'category': category,
                        'note': f"Part of multi-item: {desc}"
                    })
                except ValueError:
                    continue
        
        # Alternative pattern: "category amount" style
        if not items:
            pattern2 = r'([a-z]+)\s+(\d+(?:\.\d+)?)'
            matches2 = re.findall(pattern2, text_lower)
            
            if matches2 and len(matches2) > 1:
                for desc, amount_str in matches2:
                    try:
                        amount = float(amount_str)
                        category = self._infer_category(desc)
                        
                        items.append({
                            'amount': amount,
                            'merchant_text': desc,
                            'category': category,
                            'note': f"Part of multi-item: {desc}"
                        })
                    except ValueError:
                        continue
        
        return items
    
    def _infer_category(self, text: str) -> str:
        """Simple category inference from text"""
        # Category mappings
        categories = {
            'food': ['food', 'lunch', 'dinner', 'breakfast', 'snack', 'meal'],
            'transport': ['taxi', 'uber', 'bus', 'transport', 'ride', 'metro'],
            'groceries': ['groceries', 'grocery', 'market', 'bazar'],
            'utilities': ['electric', 'water', 'gas', 'internet', 'phone', 'bill'],
            'entertainment': ['movie', 'game', 'fun', 'entertainment'],
            'coffee': ['coffee', 'tea', 'cafe', 'starbucks'],
        }
        
        text_lower = text.lower()
        for category, keywords in categories.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return category
                    
        return 'unknown'
    
    def split_into_commands(self, base_cc: CanonicalCommand, items: List[Dict]) -> List[CanonicalCommand]:
        """
        Split multi-item CC into multiple single-item CCs
        
        Args:
            base_cc: The original multi-item Canonical Command
            items: List of parsed items
            
        Returns:
            List of individual Canonical Commands
        """
        commands = []
        
        for i, item in enumerate(items):
            # Create new CC for each item
            cc = CanonicalCommand(
                schema_version=base_cc.schema_version,
                schema_hash=base_cc.schema_hash,
                cc_id=f"{base_cc.cc_id}_item_{i}",
                user_id=base_cc.user_id,
                intent=base_cc.intent,
                confidence=base_cc.confidence * 0.9,  # Slightly lower confidence for splits
                decision=base_cc.decision,
                source_text=base_cc.source_text,
                model_version=base_cc.model_version,
                ui_note=f"Item {i+1}/{len(items)}: {item.get('merchant_text', 'expense')}"
            )
            
            # Create slots for this item with None guards
            cc.slots = CCSlots(
                amount=item.get('amount'),
                currency=base_cc.slots.currency if base_cc.slots else 'BDT',
                time_expr=base_cc.slots.time_expr if base_cc.slots else None,
                time_abs=base_cc.slots.time_abs if base_cc.slots else None,
                merchant_text=item.get('merchant_text'),
                category=item.get('category'),
                note=item.get('note')
            )
            
            commands.append(cc)
            
        return commands

# Global parser instance
multi_item_parser = MultiItemParser()