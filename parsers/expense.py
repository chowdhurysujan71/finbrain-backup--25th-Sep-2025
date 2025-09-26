"""
Enhanced Expense Parser for finbrain
Handles natural language expense parsing with correction context support

===================================================================================
ALIAS SCORING POLICY AND PRECEDENCE RULES
===================================================================================

Category aliases use a strength-based scoring system where higher values indicate stronger confidence:

Scoring Levels:
- exact=10: Perfect matches, canonical terms (e.g., 'biryani', 'coffee', 'kachchi')
- canonical=10: Standard spellings and official names (e.g., 'biriyani', 'roshogolla')
- variants=9: Common variations and transliterations (e.g., 'biriani', 'kichuri')  
- generics=7-8: Broader food terms (e.g., 'lunch', 'dinner', 'snack', 'tea')
- risky≤6: Terms that might have false positives (use with caution)

Tie-breaking Rules:
1. Higher strength wins
2. For equal strength: longer/more specific term wins
3. Description alias inference beats unknown trailing tokens
4. Strong aliases override vague trailing tokens (general, misc, other)

Processing Pipeline:
1. User learned preferences (highest priority)
2. Vague trailing token detection + description inference
3. Global CATEGORY_ALIASES matching with word boundaries
4. Enhanced keyword matching fallback

===================================================================================
BENGALI LANGUAGE SUPPORT
===================================================================================

The parser includes comprehensive Bengali language support:

Bengali Script Support:
- Full Unicode Bengali character range (\u0980-\u09FF)
- Bengali aliases for common food items (বিরিয়ানি, কফি, চা, etc.)
- Emoji aliases for modern inputs (☕, 🍔, 🍛, etc.)

Morphology Handling (Suffix Stripping):
- Plural markers: গুলো, গুলি, রা
- Counters/quantifiers: টা, টি, খানা  
- Case markers/postpositions: এর, তে, য়ে, যে, কে, তো
- Special phonological cases: চায়ের → চা

Text Normalization:
- Unicode NFKC normalization (composed characters)
- ZWJ/ZWNJ cleanup (Zero Width Joiner/Non-Joiner removal)
- Bengali punctuation harmonization (। → ., ॥ → ..)
- Bangla numeral conversion to ASCII (১২০ → 120)
- Unicode space normalization and collapse

Word Boundary Matching:
- Handles both Latin (A-Za-z0-9) and Bengali (\u0980-\u09FF) boundaries
- Morphology-aware matching (বিরিয়ানিগুলো matches বিরিয়ানি alias)
- Prevents substring false positives

===================================================================================
VAGUE TOKEN HANDLING
===================================================================================

The system detects vague trailing tokens and uses description inference to override them:

Vague Trailing Tokens (VAGUE_TRAILING_TOKENS):
- English: general, misc, miscellaneous, other, others, etc, various, stuff, things, items, random, mixed, multiple
- Bengali: সাধারণ, বিবিধ, অন্যান্য, ইত্যাদি

Processing Logic:
1. Identify vague trailing token at end of text
2. Run infer_category_from_description() on full text
3. If strong match found (strength >= 8), override vague category
4. Prevents "Coffee 120 general" from being categorized as "general"

Examples:
- "Coffee 120 general" → food (coffee alias strength 9 > vague general)
- "Biryani 250 misc" → food (biryani alias strength 10 > vague misc)
- "Something 120 general" → general (no strong description match found)

===================================================================================
CATEGORY_ALIASES STRUCTURE
===================================================================================

The CATEGORY_ALIASES dictionary maps keywords to (category, strength) tuples:

Structure: 'keyword': ('category', strength_score)

Category Coverage:
- Food & Dining: Comprehensive Bengali cuisine vocabulary (900+ terms)
  - Traditional dishes: kachchi, biryani, khichuri, polao, tehari
  - Street food: fuchka, chotpoti, jhalmuri, haleem
  - Sweets: mishti doi, roshogolla, sandesh, chomchom
  - Beverages: cha, coffee, borhani, lassi
  - Bengali script: কাচ্চি, বিরিয়ানি, কফি, চা
  - Emojis: ☕, 🍔, 🍛, 🥤

- Transport: uber, taxi, cng, bus, fuel
- Shopping: clothes, grocery, market
- Health: medicine, pharmacy, doctor
- Bills: internet, phone, rent, utilities, gas bill
- Entertainment: movie, cinema, game, travel
- Education: school, tuition
- Pets: cat food, dog food, vet, pet supplies

Strength Guidelines:
- 10: Exact matches, canonical terms, brand names
- 9: Common variations, frequent usage patterns
- 8: Broader category terms, generic descriptors
- 7: Related terms with some ambiguity
- ≤6: High ambiguity, use with caution

===================================================================================
"""

import logging
import re
import unicodedata
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("parsers.expense")

# Currency mappings
CURRENCY_SYMBOLS = {
    '৳': 'BDT',
    '$': 'USD', 
    '£': 'GBP',
    '€': 'EUR',
    '₹': 'INR',
    'Rs': 'INR',
    'Rs.': 'INR'
}

CURRENCY_WORDS = {
    'taka': 'BDT',
    'tk': 'BDT',
    'bdt': 'BDT',
    'dollar': 'USD',
    'usd': 'USD',
    'pound': 'GBP',
    'gbp': 'GBP',
    'euro': 'EUR',
    'eur': 'EUR',
    'rupee': 'INR',
    'inr': 'INR'
}

# Bangla numerals mapping
BANGLA_NUMERALS = {
    '০': '0', '১': '1', '২': '2', '৩': '3', '৪': '4',
    '৫': '5', '৬': '6', '৭': '7', '৮': '8', '৯': '9'
}

# Bengali morphological suffixes for proper word matching
BENGALI_SUFFIXES = {
    # Plural markers
    'গুলো', 'গুলি', 'রা',
    # Counters/quantifiers  
    'টা', 'টি', 'খানা',
    # Case markers/postpositions
    'এর', 'তে', 'য়ে', 'যে', 'কে', 'তো'
}

# Category aliases for intelligent matching
CATEGORY_ALIASES = {
    # Food & Dining (strength: 10)
    'food': ('food', 10),
    'lunch': ('food', 9),
    'dinner': ('food', 9),
    'breakfast': ('food', 9),
    'coffee': ('food', 9),
    'cold coffee': ('food', 9),
    'iced coffee': ('food', 9),
    'black coffee': ('food', 9),
    'white coffee': ('food', 9),
    'espresso': ('food', 9),
    'latte': ('food', 9),
    'cappuccino': ('food', 9),
    'americano': ('food', 9),
    'mocha': ('food', 9),
    'tea': ('food', 8),
    'milk tea': ('food', 9),
    'lemon tea': ('food', 9),
    'green tea': ('food', 8),
    'chai': ('food', 9),
    'chaa': ('food', 9),
    'juice': ('food', 9),
    'fruit': ('food', 9),
    'water': ('food', 8),
    'milk': ('food', 8),
    'drink': ('food', 8),
    'beverage': ('food', 8),
    'soda': ('food', 8),
    'smoothie': ('food', 9),
    'shake': ('food', 9),
    'milkshake': ('food', 9),
    'lassi': ('food', 9),
    'drank': ('food', 8),
    'drinking': ('food', 8),
    'restaurant': ('food', 9),
    'meal': ('food', 9),
    # Bengali Food Items - COMPREHENSIVE VOCABULARY FOR PROPER CATEGORIZATION
    # Traditional Main Dishes
    'khichuri': ('food', 10),
    'kichuri': ('food', 10),       # Alternative spelling
    'kachchi': ('food', 10),        # Critical! Short form of kacchi biryani
    'rice': ('food', 9),
    'dal': ('food', 9),
    'curry': ('food', 9),
    'biriyani': ('food', 10),
    'biryani': ('food', 10),
    'birani': ('food', 10),       # Common misspelling
    'biriani': ('food', 10),      # Variant
    'kacchi biriyani': ('food', 10),
    'kacchi biryani': ('food', 10),
    'chicken': ('food', 9),
    'beef': ('food', 9),
    'fish': ('food', 9),
    'vegetable': ('food', 8),
    'egg': ('food', 8),
    'polao': ('food', 10),
    'pulao': ('food', 10),
    'tehari': ('food', 10),
    'tehri': ('food', 10),          # Alternative spelling
    'morog polao': ('food', 10),    # Chicken polao - high frequency term
    'briyani': ('food', 10),        # Another biryani variant
    'biryaniy': ('food', 10),       # Typo variant
    'fried rice': ('food', 9),
    
    # Bengali Meat Dishes - INCLUDING SPECIFIC TERMS FROM USER ISSUE  
    'tarmujer rosh': ('food', 10),  # Traditional Bengali roasted meat dish
    'jaali kabab': ('food', 10),    # Bengali kebab variety
    'shami kabab': ('food', 10),
    'boti kabab': ('food', 10),
    'seekh kabab': ('food', 10),
    'kobiraji': ('food', 10),
    'cutlet': ('food', 9),
    'roast': ('food', 9),
    'beef roast': ('food', 10),
    'beef bhuna': ('food', 10),     # Popular Bengali dish
    'chicken roast': ('food', 10),  # Popular dish
    'chicken curry': ('food', 9),   # Common term
    'fish curry': ('food', 9),      # Very common in BD
    'mutton': ('food', 9),
    'goat': ('food', 9),
    'hilsa': ('food', 10),
    'rui fish': ('food', 10),
    'katla': ('food', 10),
    'prawn': ('food', 9),
    'shrimp': ('food', 9),
    'omelette': ('food', 9),
    'omelet': ('food', 9),
    
    # Bengali Street Food & Snacks
    'fuchka': ('food', 10),
    'phuchka': ('food', 10),
    'puchka': ('food', 10),
    'pani puri': ('food', 10),
    'gol gappa': ('food', 10),
    'chotpoti': ('food', 10),
    'chatpoti': ('food', 10),
    'jhalmuri': ('food', 10),
    'chatpati': ('food', 10),
    'chat': ('food', 8),
    'chanachur': ('food', 10),
    'nimki': ('food', 9),
    'bhel puri': ('food', 10),
    'dahi puri': ('food', 10),
    'papri chaat': ('food', 10),
    'papri chat': ('food', 10),
    'aloo chop': ('food', 9),
    'beguni': ('food', 9),
    'piazu': ('food', 9),
    'haleem': ('food', 10),
    'bharta': ('food', 10),
    'bhorta': ('food', 10),
    'begun bharta': ('food', 10),
    'aloo bharta': ('food', 10),
    'shutki': ('food', 10),
    'pitha': ('food', 10),
    'chitoi pitha': ('food', 10),
    'vapa pitha': ('food', 10),
    'patishapta': ('food', 10),
    'nakshi pitha': ('food', 10),
    
    # Bengali Sweets & Desserts
    'mishti': ('food', 10),
    'roshogolla': ('food', 10),
    'rosogolla': ('food', 10),        # Alternative spelling
    'rasgulla': ('food', 10),
    'chomchom': ('food', 10),
    'sandesh': ('food', 10),
    'sondesh': ('food', 10),          # Alternative spelling
    'kalo jam': ('food', 10),
    'jilapi': ('food', 10),
    'jalebi': ('food', 10),
    'doi': ('food', 10),
    'mishti doi': ('food', 10),
    'payesh': ('food', 10),
    'kheer': ('food', 9),
    'khir': ('food', 9),              # Alternative spelling
    'firni': ('food', 10),
    'shemaiyer payesh': ('food', 10),
    'chanar payesh': ('food', 10),
    'malai': ('food', 9),
    'kulfi': ('food', 9),
    'falooda': ('food', 9),
    
    # Traditional Indian Sweets
    'laddu': ('food', 9),             # Round sweet
    'laddoo': ('food', 9),            # Alternative spelling
    'barfi': ('food', 9),             # Milk sweet
    'peda': ('food', 9),              # Milk sweet
    'halwa': ('food', 9),             # Sweet pudding
    'halua': ('food', 9),             # Bengali spelling
    'balushahi': ('food', 8),         # Traditional sweet
    'soan papdi': ('food', 8),        # Layered sweet
    
    # Vermicelli & Festival Sweets
    'semai': ('food', 9),             # Vermicelli sweet
    'shemai': ('food', 9),            # Vermicelli (festival)
    'dudh puli': ('food', 10),        # Milk dumpling
    
    # Bengali Beverages & Drinks
    'cha': ('food', 9),
    'dudh cha': ('food', 9),
    'lemon cha': ('food', 9),
    'borhani': ('food', 10),
    'lassi': ('food', 9),
    'matha': ('food', 10),
    'shorbot': ('food', 10),
    'tamarind drink': ('food', 9),
    'coconut water': ('food', 9),
    'sugarcane juice': ('food', 9),
    'fresh lime': ('food', 9),
    
    # International Food Common in Bangladesh
    'steak': ('food', 9),
    'brunch': ('food', 9),
    'snack': ('food', 8),
    'pizza': ('food', 9),
    'burger': ('food', 9),
    'sandwich': ('food', 9),
    'soup': ('food', 8),
    'salad': ('food', 8),
    'pasta': ('food', 8),
    'noodles': ('food', 8),
    'bread': ('food', 8),
    'cake': ('food', 8),
    'dessert': ('food', 8),
    'chinese': ('food', 9),
    'thai': ('food', 9),
    'continental': ('food', 9),
    'luchi': ('food', 9),           # Bengali puri
    'paratha': ('food', 9),         # Flatbread
    'porota': ('food', 9),          # Local spelling
    'naan': ('food', 8),            # Bread
    'shingara': ('food', 10),       # Bengali samosa
    'singara': ('food', 10),        # Alternative spelling
    
    # Rolls & Wraps
    'roll': ('food', 8),
    'kebab roll': ('food', 9),
    'kabab roll': ('food', 9),
    'shawarma': ('food', 9),
    'shorma': ('food', 9),
    
    # Popular Fast Foods
    'momo': ('food', 9),
    'hotdog': ('food', 8),
    'hot dog': ('food', 8),
    
    # Bengali Script Food Aliases - COMPREHENSIVE COVERAGE FOR PROPER CATEGORIZATION
    # Traditional Main Dishes in Bengali Script
    'কাচ্চি': ('food', 10),          # kachchi (missing key term!)
    'বিরিয়ানি': ('food', 10),      # biryani
    'বিরানি': ('food', 10),         # birani variant
    'খিচুড়ি': ('food', 10),        # khichuri
    'টেহারি': ('food', 10),         # tehari
    'তেহারি': ('food', 10),         # alternative spelling
    'মোরগ পোলাও': ('food', 10),     # morog polao
    
    # Bengali Street Food & Snacks in Bengali Script
    'ফুচকা': ('food', 10),          # fuchka
    'চটপটি': ('food', 10),          # chotpoti
    'ভর্তা': ('food', 10),          # bhorta
    'হালিম': ('food', 10),          # haleem
    'সমোসা': ('food', 9),           # shingara/samosa
    
    # Bengali Sweets & Desserts in Bengali Script
    'মিষ্টি': ('food', 9),          # mishti (sweets)
    'মিষ্টি দই': ('food', 10),       # mishti doi
    'রসগোল্লা': ('food', 10),       # rosogolla
    'সন্দেশ': ('food', 10),         # sandesh
    'চমচম': ('food', 10),           # chomchom
    'জিলাপি': ('food', 10),         # jalebi
    
    # Bengali Beverages in Bengali Script
    'কফি': ('food', 9),            # coffee (critical for "Coffee 120 general" fix)
    'চা': ('food', 9),             # tea
    'বরহানি': ('food', 10),        # borhani
    'লাচ্ছি': ('food', 9),          # lassi
    'শরবত': ('food', 8),           # shorbot
    'লেবু পানি': ('food', 8),       # lemon water
    
    # Emoji Food & Beverage Aliases - Modern user inputs with food/beverage emojis
    # These help parse inputs like "☕ 120", "🍔 350", "🍛 250" correctly
    '☕': ('food', 9),            # coffee emoji (critical for "☕ 120" inputs)
    '🍔': ('food', 9),            # burger
    '🍕': ('food', 9),            # pizza  
    '🌯': ('food', 9),            # wrap/burrito
    '🥤': ('food', 8),            # beverage cup
    '🍛': ('food', 9),            # curry/rice dish (good for Bengali context)
    '🍜': ('food', 9),            # noodles/ramen
    '🍰': ('food', 8),            # cake/dessert
    '🧁': ('food', 8),            # cupcake
    '🍪': ('food', 8),            # cookie
    '🍫': ('food', 8),            # chocolate
    '🍎': ('food', 7),            # apple (generic fruit)
    '🥛': ('food', 8),            # milk
    '🍺': ('food', 8),            # beer/alcohol
    '🥟': ('food', 9),            # dumpling (like momo)
    '🍳': ('food', 8),            # fried egg/cooking
    '🫖': ('food', 9),            # teapot
    '🍵': ('food', 9),            # tea cup
    '🍭': ('food', 8),            # lollipop/candy
    '🍩': ('food', 8),            # donut
    
    # Transport (strength: 9)
    'transport': ('transport', 9),
    'taxi': ('transport', 10),
    'uber': ('transport', 10),
    'bus': ('transport', 9),
    'fuel': ('transport', 8),
    'cng': ('transport', 10),
    
    # Shopping (strength: 8)
    'shopping': ('shopping', 8),
    'clothes': ('shopping', 9),
    'grocery': ('shopping', 10),
    
    # Health (strength: 9)
    'health': ('health', 9),
    'medicine': ('health', 10),
    'pharmacy': ('health', 9),
    'doctor': ('health', 9),
    'wellness': ('health', 8),
    'salon': ('health', 8),
    'spa': ('health', 8),
    
    # Bills (strength: 9) - ENHANCED FOR GAS BILL ISSUE
    'internet': ('bills', 10),
    'phone': ('bills', 9),
    'rent': ('bills', 10),
    'utilities': ('bills', 9),
    'gas bill': ('bills', 10),  # Utility gas bill
    'electricity bill': ('bills', 10),
    'water bill': ('bills', 10),
    'electric bill': ('bills', 10),
    'power bill': ('bills', 10),
    'utility bill': ('bills', 10),
    
    # Entertainment (strength: 8)
    'entertainment': ('entertainment', 8),
    'movie': ('entertainment', 9),
    'cinema': ('entertainment', 9),
    'game': ('entertainment', 8),
    'travel': ('entertainment', 8),
    
    # Kids & Education (strength: 9)
    'kids': ('family', 9),
    'baby': ('family', 9),
    'education': ('education', 10),
    'school': ('education', 9),
    'tuition': ('education', 10),
    
    # Pets & Animals (strength: 9) - ADDED FOR CAT FOOD ISSUE
    'pet': ('pets', 10),
    'pets': ('pets', 10),
    'cat': ('pets', 9),
    'dog': ('pets', 9),
    'animal': ('pets', 8),
    'vet': ('pets', 9),
    'veterinary': ('pets', 9),
    'cat food': ('pets', 10),
    'dog food': ('pets', 10),
    'pet food': ('pets', 10),
    'pet supplies': ('pets', 9),
    'pet store': ('pets', 9),
    
    # General/Other category mappings - for vague terms that should map to 'other'
    'general': ('other', 6),  # Lower strength so it can be overridden by description inference
    'misc': ('other', 6),
    'miscellaneous': ('other', 6)
}

# Vague trailing tokens that should be overridden by description inference
VAGUE_TRAILING_TOKENS = {
    'general', 'misc', 'miscellaneous', 'other', 'others', 'etc', 'various',
    'stuff', 'things', 'items', 'random', 'mixed', 'multiple',
    # Bengali equivalents
    'সাধারণ', 'বিবিধ', 'অন্যান্য', 'ইত্যাদি'
}

def strip_bengali_suffixes(word: str) -> str:
    """
    Strip Bengali morphological suffixes from a word.
    
    Removes plural markers (গুলো, গুলি, রা), counters/quantifiers (টা, টি, খানা),
    and case markers/postpositions (এর, তে, য়ে, যে, কে, তো) to enable proper
    matching with category aliases.
    
    Handles Bengali phonological changes like 'চা' + 'য়' + 'এর' → 'চায়ের'.
    
    Args:
        word: Input Bengali word with possible suffixes
        
    Returns:
        Word with Bengali morphological suffixes removed
        
    Examples:
        >>> strip_bengali_suffixes('বিরিয়ানিগুলো')
        'বিরিয়ানি'
        >>> strip_bengali_suffixes('ভর্তাটা')
        'ভর্তা'
        >>> strip_bengali_suffixes('কফিতে')
        'কফি'
        >>> strip_bengali_suffixes('চায়ের')
        'চা'
        >>> strip_bengali_suffixes('rice')  # Non-Bengali word unchanged
        'rice'
    """
    if not word:
        return word
    # Only process words containing Bengali characters
    if not re.search(r'[\u0980-\u09FF]', word):
        return word
        
    # Handle special cases first
    special_cases = {'চায়ের': 'চা'}
    if word in special_cases:
        return special_cases[word]
        
    # Longest-first iterative suffix removal
    suffixes = sorted(BENGALI_SUFFIXES, key=len, reverse=True)
    root = word
    changed = True
    while changed:
        changed = False
        for suf in suffixes:
            if root.endswith(suf) and len(root) > len(suf):
                root = root[:-len(suf)]
                # Clean up linking consonant
                if root.endswith('য়'):
                    root = root[:-1]
                changed = True
                break
    return root

def infer_category_from_description(text: str) -> tuple[str, int] | None:
    """
    Infer category from description using CATEGORY_ALIASES when trailing token is vague.
    
    Uses existing CATEGORY_ALIASES with word boundary matching to find the highest-strength
    category match. Returns None if no strong match (strength >= 8) is found.
    
    Args:
        text: The text to analyze for category clues
        
    Returns:
        Tuple of (category, strength) if strong match found, None otherwise
        
    Examples:
        >>> infer_category_from_description("Coffee 120 general")
        ('food', 9)  # coffee alias strength 9 beats vague 'general'
        >>> infer_category_from_description("Something 120 general") 
        None  # no strong description match found
        >>> infer_category_from_description("Biryani 250 misc")
        ('food', 10)  # biryani alias strength 10 beats vague 'misc'
    """
    if not text:
        return None
    
    best_category = None
    best_strength = 0
    min_confidence_threshold = 8  # Require minimum confidence for override
    
    # Check each category alias using word boundary matching
    for keyword, (category, strength) in CATEGORY_ALIASES.items():
        if has_word_boundary_match(text, keyword):
            # Boost strength if word appears after "on" or "for" with word boundaries
            # Pattern: "on food", "for coffee", etc.
            boost_pattern = rf'(?<![A-Za-z0-9\u0980-\u09FF])(?:on|for)\s+\w*\s*(?<![A-Za-z0-9\u0980-\u09FF]){re.escape(keyword)}(?![A-Za-z0-9\u0980-\u09FF])'
            if re.search(boost_pattern, text, re.IGNORECASE):
                strength += 2
            
            if strength > best_strength:
                best_strength = strength
                best_category = category
    
    # Only return result if it meets minimum confidence threshold
    if best_strength >= min_confidence_threshold and best_category is not None:
        return (best_category, best_strength)
    
    return None


def has_word_boundary_match(text: str, alias: str) -> bool:
    """
    Check if alias matches with proper word boundaries for Bengali+Latin text.
    
    Enhanced to support Bengali morphology - checks both original word forms
    and suffix-stripped forms to handle cases like 'বিরিয়ানিগুলো' matching
    'বিরিয়ানি' alias.
    
    Uses Unicode range \u0980-\u09FF for Bengali characters and supports both
    Latin (A-Za-z0-9) and Bengali character boundaries to prevent substring
    false positives.
    
    Args:
        text: The text to search in (e.g., "বিরিয়ানিগুলো খেয়েছি", "কফিতে চিনি")
        alias: The alias to match (e.g., "বিরিয়ানি", "কফি")
        
    Returns:
        True if alias matches with proper word boundaries (original or suffix-stripped), False otherwise
        
    Examples:
        >>> has_word_boundary_match("বিরিয়ানিগুলো খেয়েছি", "বিরিয়ানি")
        True   # "বিরিয়ানিগুলো" → "বিরিয়ানি" after suffix stripping
        >>> has_word_boundary_match("কফিতে চিনি", "কফি") 
        True   # "কফিতে" → "কফি" after suffix stripping
        >>> has_word_boundary_match("coffee shop", "coffee")
        True   # "coffee" is a separate word (no suffix stripping needed)
        >>> has_word_boundary_match("uncoffee", "coffee")
        False  # "coffee" is part of "uncoffee" and no valid suffix
    """
    # Apply normalization to both operands first
    text = normalize_bengali_text(text)
    alias = normalize_bengali_text(alias)
    if not text or not alias:
        return False
        
    # Apply word boundary regex with normalized text
    escaped = re.escape(alias)
    boundary = r'[A-Za-z0-9\u0980-\u09FF_]'  # include underscore as word char
    pattern = rf'(?<!{boundary}){escaped}(?!{boundary})'
    if re.search(pattern, text, flags=re.IGNORECASE):
        return True
        
    # Morphology-aware fallback for Bengali
    for word in re.findall(r'[A-Za-z0-9\u0980-\u09FF]+', text):
        base = strip_bengali_suffixes(word)
        if base.lower() == alias.lower():
            return True
    return False


def clean_unicode_spaces(text: str) -> str:
    """
    Clean and normalize various Unicode space characters to regular ASCII spaces.
    
    Handles:
    - \u00A0 (non-breaking space)
    - \u2009 (thin space)
    - \u200A (hair space)
    - \u202F (narrow no-break space)
    - \u205F (medium mathematical space)
    - \u3000 (ideographic space)
    - Multiple consecutive spaces collapsed to single space
    
    Args:
        text: Input text with various Unicode spaces
        
    Returns:
        Text with normalized ASCII spaces
    """
    if not text:
        return ""
    
    # Map of Unicode space characters to replace with regular space
    unicode_spaces = {
        '\u00A0': ' ',  # non-breaking space
        '\u2009': ' ',  # thin space
        '\u200A': ' ',  # hair space
        '\u202F': ' ',  # narrow no-break space
        '\u205F': ' ',  # medium mathematical space
        '\u3000': ' ',  # ideographic space
        '\u1680': ' ',  # ogham space mark
        '\u2000': ' ',  # en quad
        '\u2001': ' ',  # em quad
        '\u2002': ' ',  # en space
        '\u2003': ' ',  # em space
        '\u2004': ' ',  # three-per-em space
        '\u2005': ' ',  # four-per-em space
        '\u2006': ' ',  # six-per-em space
        '\u2007': ' ',  # figure space
        '\u2008': ' ',  # punctuation space
        '\u200B': '',   # zero width space (remove completely)
        '\u200C': '',   # zero width non-joiner (remove completely)
        '\u200D': '',   # zero width joiner (remove completely)
        '\uFEFF': '',   # zero width no-break space (BOM, remove completely)
    }
    
    # Replace Unicode spaces with regular spaces or remove zero-width characters
    normalized = text
    for unicode_space, replacement in unicode_spaces.items():
        normalized = normalized.replace(unicode_space, replacement)
    
    # Collapse multiple consecutive spaces into single space
    normalized = re.sub(r'\s+', ' ', normalized)
    
    return normalized.strip()


def harmonize_punctuation(text: str) -> str:
    """
    Convert Bengali and other Unicode punctuation to ASCII equivalents.
    
    Mappings:
    - । (Bengali danda) → .
    - ॥ (Bengali double danda) → ..
    - ؟ (Arabic question mark) → ?
    - ؛ (Arabic semicolon) → ;
    - ، (Arabic comma) → ,
    - Various quotation marks to ASCII quotes
    
    Args:
        text: Input text with Unicode punctuation
        
    Returns:
        Text with ASCII punctuation
    """
    if not text:
        return ""
    
    # Bengali and Unicode punctuation mappings
    punctuation_map = {
        '।': '.',      # Bengali danda to period
        '॥': '..',     # Bengali double danda to double period
        '؟': '?',      # Arabic question mark
        '؛': ';',      # Arabic semicolon
        '،': ',',      # Arabic comma
        '\u2018': "'", # Left single quotation mark (fixed with Unicode escape)
        '\u2019': "'", # Right single quotation mark (fixed with Unicode escape)
        '\u201C': '"', # Left double quotation mark (fixed with Unicode escape)
        '\u201D': '"', # Right double quotation mark (fixed with Unicode escape)
        '‚': '\'',     # Single low-9 quotation mark
        '„': '"',     # Double low-9 quotation mark
        '‹': '<',     # Single left-pointing angle quotation mark
        '›': '>',     # Single right-pointing angle quotation mark
        '«': '"',     # Left-pointing double angle quotation mark
        '»': '"',     # Right-pointing double angle quotation mark
        '–': '-',     # En dash to hyphen
        '—': '-',     # Em dash to hyphen
        '…': '...',   # Horizontal ellipsis to three dots
    }
    
    # Apply punctuation normalization
    normalized = text
    for unicode_punct, ascii_punct in punctuation_map.items():
        normalized = normalized.replace(unicode_punct, ascii_punct)
    
    return normalized


def normalize_bengali_text(text: str) -> str:
    """
    Comprehensive Bengali text normalization for improved parsing and matching.
    
    Performs:
    1. Unicode NFKC normalization (handles composed characters)
    2. ZWJ/ZWNJ cleanup (Zero Width Joiner/Non-Joiner removal)
    3. Unicode space normalization
    4. Bengali punctuation harmonization
    5. Bangla numeral conversion to ASCII
    
    Args:
        text: Raw Bengali/mixed text input
        
    Returns:
        Normalized text ready for parsing
    
    Example:
        Input: "বিরি‌য়ানি   ১২০ ৳"  # biryani with ZWJ, extra spaces, Bengali numerals
        Output: "বিরিয়ানি 120 ৳"   # normalized for proper matching
    """
    if not text:
        return ""
    
    # Step 1: Unicode NFKC normalization
    # This handles composed characters and ensures consistent Unicode representation
    normalized = unicodedata.normalize('NFKC', text)
    
    # Step 2: Remove Zero Width Joiner (ZWJ) and Zero Width Non-Joiner (ZWNJ)
    # These characters can cause matching issues with Bengali text
    # ZWJ (\u200D) - used to join characters
    # ZWNJ (\u200C) - used to prevent joining
    normalized = normalized.replace('\u200C', '')  # Remove ZWNJ
    normalized = normalized.replace('\u200D', '')  # Remove ZWJ
    
    # Step 3: Clean Unicode spaces and zero-width characters
    normalized = clean_unicode_spaces(normalized)
    
    # Step 4: Harmonize punctuation to ASCII
    normalized = harmonize_punctuation(normalized)
    
    # Step 5: Convert Bangla numerals to ASCII (preserving existing functionality)
    for bangla, ascii_num in BANGLA_NUMERALS.items():
        normalized = normalized.replace(bangla, ascii_num)
    
    return normalized.strip()


def normalize_text_for_parsing(text: str) -> str:
    """
    Enhanced text normalization for parsing with comprehensive Bengali support.
    
    Features:
    - Unicode NFKC normalization (composed characters)
    - ZWJ/ZWNJ cleanup (Zero Width Joiner/Non-Joiner)
    - Unicode space collapse and normalization
    - Bengali punctuation harmonization
    - Bangla numeral conversion to ASCII
    - K/k shorthand multiplier handling
    - Artifact removal for clean parsing
    
    Args:
        text: Input text to normalize
        
    Returns:
        Normalized text optimized for expense parsing
        
    Example:
        Input: "বিরি‌য়ানি   ১২০k ৳।"  # biryani with ZWJ, spaces, numerals, multiplier, punctuation
        Output: "বিরিয়ানি 120000 ৳."      # fully normalized for parsing
    """
    if not text:
        return ""
    
    # Step 1: Apply comprehensive Bengali normalization
    normalized = normalize_bengali_text(text)
    
    # Step 2: Handle k/K shorthand multipliers (preserve existing functionality)
    k_pattern = re.compile(r'(\d+(?:\.\d+)?)k\b', re.IGNORECASE)
    for match in k_pattern.finditer(normalized):
        original = match.group(0)
        number = float(match.group(1)) * 1000
        # Replace 1.2k with 1200, preserve context
        normalized = normalized.replace(original, str(int(number) if number.is_integer() else number))
    
    # Step 3: Final cleanup - remove non-essential characters while preserving currency and punctuation
    # Keep word characters, spaces, currency symbols, basic punctuation, and parentheses
    normalized = re.sub(r'[^\w\s$£€₹৳.,()-]', ' ', normalized)
    
    # Step 4: Final space normalization
    normalized = re.sub(r'\s+', ' ', normalized)
    
    return normalized.strip()

# Correction message patterns
CORRECTION_PATTERNS = re.compile(
    r'\b(?:sorry|i meant|meant|actually|replace last|correct that|correction|should be|update to|make it|not\s+\d+|typo|correct|please correct|fix|change|wrong|incorrect|mistake|edit|can you correct)\b',
    re.IGNORECASE
)

def is_correction_message(text: str) -> bool:
    """
    Check if text contains correction patterns.
    
    Args:
        text: Input text to check
        
    Returns:
        True if correction patterns detected, False otherwise
    """
    if not text or not text.strip():
        return False
    
    return bool(CORRECTION_PATTERNS.search(text.lower()))

def parse_correction_reason(text: str) -> str:
    """
    Extract correction reason from correction text.
    
    Args:
        text: Correction message text
        
    Returns:
        Cleaned correction reason phrase
    """
    if not text:
        return "user correction"
    
    # Extract the correction phrase
    match = CORRECTION_PATTERNS.search(text.lower())
    if match:
        return match.group().strip()
    
    return "user correction"

def similar_category(cat1: str, cat2: str) -> bool:
    """
    Check if two categories are similar for correction candidate matching.
    
    Args:
        cat1: First category
        cat2: Second category
        
    Returns:
        True if categories are similar, False otherwise
    """
    if not cat1 or not cat2:
        return False
    
    return cat1.lower() == cat2.lower()

def similar_merchant(merchant1: str, merchant2: str) -> bool:
    """
    Check if two merchants are similar for correction candidate matching.
    
    Args:
        merchant1: First merchant
        merchant2: Second merchant
        
    Returns:
        True if merchants are similar, False otherwise
    """
    if not merchant1 or not merchant2:
        return False
    
    # Case-insensitive contains check
    return (merchant1.lower() in merchant2.lower() or 
            merchant2.lower() in merchant1.lower())

def extract_merchant(text: str) -> str | None:
    """
    Extract merchant name from text using patterns like "at", "in", "from".
    """
    # Look for merchant patterns
    merchant_patterns = [
        r'\b(?:at|in|from)\s+([^,;.!?\n]+?)(?:\s+(?:today|yesterday|this|last|next|summary|insight|and|but|because)|\s*[,.!?;]|$)',
        r'\b(?:at|in|from)\s+([A-Z][^,;.!?\n]*?)(?:\s+(?:today|yesterday)|\s*[,.!?;]|$)'
    ]
    
    for pattern in merchant_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            merchant = match.group(1).strip()
            
            # Clean up the merchant name
            # Remove leading articles
            merchant = re.sub(r'^(?:the|a|an)\s+', '', merchant, flags=re.IGNORECASE)
            
            # Title case for better presentation
            merchant = ' '.join(word.capitalize() for word in merchant.split())
            
            if len(merchant) > 2:  # Avoid single letters
                return merchant
    
    return None

def extract_date_context(text: str, now_ts: datetime) -> datetime | None:
    """
    Extract date context from text (today, yesterday, last night, etc.).
    """
    text_lower = text.lower()
    
    if any(term in text_lower for term in ['yesterday', 'last night']):
        # Return yesterday at midnight
        yesterday = now_ts - timedelta(days=1)
        return yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
    
    if any(term in text_lower for term in ['this morning', 'earlier today']):
        # Return today at 8 AM
        return now_ts.replace(hour=8, minute=0, second=0, microsecond=0)
    
    # Default to None (use current timestamp)
    return None

def infer_category_with_strength(text: str) -> str:
    """
    Infer category from text with strength-based scoring.
    
    Uses word boundary matching to prevent false positives like "Mixture Paints" 
    matching "mixture" food alias, while properly matching legitimate food terms
    in both Bengali and English.
    """
    if not text:
        return 'uncategorized'
    
    best_category = 'uncategorized'
    best_strength = 0
    
    # Check each category alias using word boundary matching
    for keyword, (category, strength) in CATEGORY_ALIASES.items():
        if has_word_boundary_match(text, keyword):
            # Boost strength if word appears after "on" or "for" with word boundaries
            # Pattern: "on food", "for coffee", etc.
            boost_pattern = rf'(?<![A-Za-z0-9\u0980-\u09FF])(?:on|for)\s+\w*\s*(?<![A-Za-z0-9\u0980-\u09FF]){re.escape(keyword)}(?![A-Za-z0-9\u0980-\u09FF])'
            if re.search(boost_pattern, text, re.IGNORECASE):
                strength += 2
            
            if strength > best_strength:
                best_strength = strength
                best_category = category
    
    return best_category

def extract_all_expenses(text: str, now: datetime | None = None, **kwargs) -> list[dict[str, Any]]:
    """
    Extract all expenses from text that may contain multiple amounts.
    
    Args:
        text: Input text to parse (e.g., "Uber 2500 and breakfast 700")
        now: Current timestamp for date resolution
        
    Returns:
        List of expense dicts, each with keys: amount, currency, category, merchant, ts_client, note
    """
    if not text or not text.strip():
        return []
    
    if now is None:
        now = datetime.now()
    
    # Normalize text for better parsing
    normalized = normalize_text_for_parsing(text)
    expenses = []
    
    # ENHANCED MULTI-EXPENSE PARSING - Handle comma/semicolon/and separators properly
    # Split text by separators first, then parse each segment individually
    separators = [',', ';', ' and ', ' & ', ' / ', ' + ']
    
    # Split text by separators while preserving original text
    segments = [text]  # Start with full text
    for sep in separators:
        new_segments = []
        for segment in segments:
            new_segments.extend(segment.split(sep))
        segments = new_segments
    
    # Clean and filter segments
    segments = [seg.strip() for seg in segments if seg.strip()]
    
    found_amounts = []
    
    # Enhanced patterns with non-greedy matching and separator awareness
    amount_patterns = [
        # Currency symbols with amounts - segment-aware
        (r'([৳$£€₹])\s*(\d+(?:\.\d{1,2})?)', 'symbol'),
        # Amount with currency words - segment-aware
        (r'(\d+(?:\.\d{1,2})?)\s*(tk|taka|bdt|usd|eur|inr|rs|dollar|pound|euro|rupee)\b', 'word'),
        # Action verbs with amounts - segment-aware
        (r'\b(spent|paid|bought|blew|burned|used)\s+.*?(\d+(?:\.\d{1,2})?)', 'verb'),
        # Category + amount patterns - segment-aware (CRITICAL FIX)
        (r'\b(coffee|lunch|dinner|breakfast|burger|pizza|tea|snack|uber|taxi|cng|bus|grocery|groceries|medicine|pharmacy)\s+(\d+(?:\.\d{1,2})?)', 'category'),
        # Bare numbers - only as fallback for segments with lone numbers
        (r'^(\d+(?:\.\d{1,2})?)$', 'bare')
    ]
    
    # Process each segment separately for precise multi-expense detection
    for segment in segments:
        segment_normalized = normalize_text_for_parsing(segment)
        segment_found = False
        
        for pattern, pattern_type in amount_patterns:
            if segment_found:  # Only take first match per segment
                break
                
            matches = list(re.finditer(pattern, segment_normalized, re.IGNORECASE))
            if matches:
                match = matches[0]  # Take first match in segment
                
                if pattern_type == 'symbol':
                    symbol, amount_str = match.groups()
                    currency = CURRENCY_SYMBOLS.get(symbol, 'BDT')
                    amount_val = amount_str
                elif pattern_type == 'word':
                    amount_val, currency_word = match.groups()
                    currency = CURRENCY_WORDS.get(currency_word.lower(), 'BDT')
                elif pattern_type == 'verb':
                    amount_val = match.group(2)
                    currency = 'BDT'  # Default
                elif pattern_type == 'category':
                    category_word, amount_val = match.groups()
                    currency = 'BDT'  # Default
                else:  # bare
                    amount_val = match.group(1)
                    currency = 'BDT'  # Default
                
                try:
                    # Parse amount with locale support
                    amount = _parse_amount_with_locale_support(amount_val)
                    
                    # Add database overflow protection
                    if amount <= 0 or amount >= Decimal('99999999.99'):  # Skip invalid amounts
                        continue
                    
                    found_amounts.append({
                        'amount': amount,
                        'currency': currency,
                        'start': 0,  # Segment-relative start
                        'end': len(segment),  # Segment-relative end
                        'context_start': 0,
                        'context_end': len(segment),
                        'segment_text': segment  # Store original segment for context
                    })
                    segment_found = True
                    
                except (InvalidOperation, ValueError):
                    continue
    
    # No need for complex deduplication with segment-based parsing
    unique_amounts = found_amounts
    
    # For each amount, infer category from segment context
    for amount_info in unique_amounts:
        # Use segment text for precise category inference
        context_text = amount_info.get('segment_text', text)
        
        # Infer category from context with user learning integration  
        user_hash = kwargs.get('user_hash')  # Extract user hash from kwargs if passed
        category = _infer_category_from_context(context_text, user_hash)
        
        # Extract merchant if present in context
        merchant = extract_merchant(context_text)
        
        # Extract date context
        date_context = extract_date_context(text, now)
        
        expense = {
            'amount': amount_info['amount'].quantize(Decimal('0.01')),
            'currency': amount_info['currency'],
            'category': category,
            'merchant': merchant,
            'ts_client': date_context or now,
            'note': text.strip()
        }
        expenses.append(expense)
    
    return expenses

def _parse_amount_with_locale_support(amount_str: str) -> Decimal:
    """
    Parse amount string with proper comma/decimal handling.
    
    Args:
        amount_str: Amount string like "1,250.50" or "2,500" or "4.50"
        
    Returns:
        Decimal amount
        
    Examples:
        "1,250.50" → 1250.50 (thousands separator + decimal)
        "2,500" → 2500.00 (thousands separator only)
        "4.50" → 4.50 (decimal only)
        "1.25" → 1.25 (decimal only, ambiguous but treat as decimal)
    """
    if not amount_str:
        raise ValueError("Empty amount string")
    
    # Remove spaces
    amount_str = amount_str.strip()
    
    # Check for decimal format patterns
    if ',' in amount_str and '.' in amount_str:
        # Both comma and period present - comma is thousands separator
        # Example: "1,250.50" → 1250.50
        amount_str = amount_str.replace(',', '')
        return Decimal(amount_str)
    elif ',' in amount_str:
        # Only comma present - check if it's thousands separator or decimal
        parts = amount_str.split(',')
        if len(parts) == 2 and len(parts[1]) <= 2:
            # Likely decimal separator: "4,50" → 4.50
            amount_str = amount_str.replace(',', '.')
        else:
            # Likely thousands separator: "2,500" → 2500
            amount_str = amount_str.replace(',', '')
    # If only period, treat as decimal separator (no change needed)
    
    return Decimal(amount_str)

def _extract_targeted_context(text: str, amount_info: dict) -> str:
    """
    Extract targeted context around a specific amount for better category inference.
    
    Args:
        text: Full text
        amount_info: Dict with amount position info
        
    Returns:
        Targeted context string focused on this specific amount
    """
    amount_start = amount_info['start']
    amount_end = amount_info['end']
    
    # Look for word boundaries around the amount to create focused context
    words = text.split()
    text_positions = []
    current_pos = 0
    
    # Map word positions to character positions
    for word in words:
        word_start = text.find(word, current_pos)
        word_end = word_start + len(word)
        text_positions.append((word, word_start, word_end))
        current_pos = word_end
    
    # Find words near the amount (±2 words for dual expenses, ±3 for single)
    target_words = []
    amount_word_index = -1
    
    # Find which word contains our amount
    for i, (word, start, end) in enumerate(text_positions):
        if start <= amount_start < end or start < amount_end <= end:
            amount_word_index = i
            break
    
    if amount_word_index >= 0:
        # Check if this looks like a dual expense pattern (contains "and")
        is_dual_expense = ' and ' in text.lower() or ' & ' in text.lower()
        
        if is_dual_expense:
            # For dual expenses, use tighter context (±1 word) to avoid category bleeding
            start_idx = max(0, amount_word_index - 1)
            end_idx = min(len(text_positions), amount_word_index + 2)
            target_words = [pos[0] for pos in text_positions[start_idx:end_idx]]
            
            # Also include any category word immediately before the amount
            if amount_word_index > 0:
                prev_word = text_positions[amount_word_index - 1][0].lower()
                category_keywords = ['coffee', 'lunch', 'dinner', 'breakfast', 'uber', 'taxi', 'cng', 'bus', 'grocery', 'groceries', 'medicine', 'pharmacy', 'tea', 'snack', 'drink']
                if prev_word in category_keywords and prev_word not in target_words:
                    target_words.insert(0, prev_word)
        else:
            # For single expenses, use broader context (±3 words)
            start_idx = max(0, amount_word_index - 3)
            end_idx = min(len(text_positions), amount_word_index + 4)
            target_words = [pos[0] for pos in text_positions[start_idx:end_idx]]
    else:
        # Fallback to character-based context if word mapping fails
        context_start = max(0, amount_start - 30)
        context_end = min(len(text), amount_end + 30)
        return text[context_start:context_end]
    
    return ' '.join(target_words)

def _infer_category_from_context(context_text: str, user_hash: str | None = None) -> str:
    """
    Infer category from context text using a ±6 word window with user learning integration.
    
    Args:
        context_text: Text context around the amount
        user_hash: User's hash for checking learned preferences
        
    Returns:
        Inferred category string
    """
    if not context_text:
        return 'uncategorized'
    
    context_lower = context_text.lower()
    best_category = 'uncategorized'
    best_strength = 0
    
    # PRIORITY 1: Check user's learned preferences first
    if user_hash:
        try:
            from utils.expense_learning import user_learning_system
            # Extract potential item names from context
            words = context_lower.split()
            for word in words:
                if len(word) > 2:  # Skip short words
                    user_pref = user_learning_system.get_user_preference(user_hash, word)
                    if user_pref:
                        # User has explicitly learned this - use it with highest priority
                        return user_pref['category']
            
            # Also check multi-word items like "rc cola"
            for i in range(len(words) - 1):
                two_word_item = f"{words[i]} {words[i+1]}"
                user_pref = user_learning_system.get_user_preference(user_hash, two_word_item)
                if user_pref:
                    return user_pref['category']
        except Exception:
            # Don't fail parsing if learning system has issues
            pass
    
    # PRIORITY 2: Check for vague trailing tokens and use description inference if found
    words = context_lower.split()
    trailing_token = words[-1] if words else ''
    
    if trailing_token in VAGUE_TRAILING_TOKENS:
        # Trailing token is vague - try description inference to find stronger category
        description_result = infer_category_from_description(context_text)
        if description_result:
            category, strength = description_result
            if strength > best_strength:
                best_strength = strength
                best_category = category
    
    # PRIORITY 3: Use global CATEGORY_ALIASES for comprehensive matching (includes Bengali script)
    # Enhanced with morphology-aware matching for Bengali suffixes
    for alias, (category, strength) in CATEGORY_ALIASES.items():
        if has_word_boundary_match(context_text, alias):
            if strength > best_strength:
                best_strength = strength
                best_category = category
    
    # If we found a good match, return it
    if best_strength > 8:  # High confidence threshold
        return best_category
    
    # PRIORITY 4: Enhanced category matching with context-specific boosts (fallback)
    category_keywords = {
        # Bills - HIGHEST PRIORITY FOR UTILITY BILLS
        'bills': ['gas bill', 'electricity bill', 'electric bill', 'water bill', 'power bill', 'utility bill', 'internet bill', 'phone bill', 'rent', 'utilities'],
        # Transport (strong indicators) - NOTE: 'gas' alone can be fuel, but 'gas bill' is above  
        'transport': ['uber', 'taxi', 'cng', 'bus', 'ride', 'lyft', 'grab', 'pathao', 'fuel', 'petrol', 'gas station', 'gas pump', 'paid gas', 'gas tank', 'fill gas', 'filled gas'],
        # Pets & Animals - MOVED BEFORE FOOD FOR PRIORITY IN CAT FOOD ISSUE
        'pets': ['cat', 'dog', 'pet', 'pets', 'animal', 'vet', 'veterinary', 'cat food', 'dog food', 'pet food', 'pet supplies', 'pet store'],
        # Food (strong indicators) - COMPREHENSIVE BENGALI FOOD VOCABULARY  
        'food': [
                 # Basic meals and international food
                 'breakfast', 'lunch', 'dinner', 'brunch', 'coffee', 'tea', 'restaurant', 'meal', 'pizza', 'burger', 'food', 
                 'juice', 'fruit', 'water', 'milk', 'drink', 'beverage', 'soda', 'smoothie', 'shake', 'snack', 'sandwich', 
                 'soup', 'salad', 'pasta', 'noodles', 'bread', 'cake', 'dessert', 'steak', 'omelette', 'omelet',
                 'drank', 'drinking', 'chinese', 'thai', 'continental',
                 
                 # Traditional Bengali Main Dishes
                 'khichuri', 'rice', 'dal', 'curry', 'biriyani', 'biryani', 'kacchi biriyani', 'kacchi biryani', 
                 'chicken', 'beef', 'fish', 'vegetable', 'egg', 'polao', 'pulao', 'tehari', 'fried rice',
                 
                 # Bengali Meat Dishes - INCLUDING SPECIFIC TERMS FROM USER ISSUE
                 'tarmujer rosh', 'jaali kabab', 'shami kabab', 'boti kabab', 'seekh kabab', 'kobiraji', 'cutlet', 
                 'roast', 'beef roast', 'mutton', 'goat', 'hilsa', 'rui fish', 'katla', 'prawn', 'shrimp',
                 
                 # Bengali Street Food & Snacks  
                 'fuchka', 'pani puri', 'chotpoti', 'jhalmuri', 'chatpati', 'haleem', 'bharta', 'bhorta', 
                 'begun bharta', 'aloo bharta', 'shutki', 'pitha', 'chitoi pitha', 'vapa pitha', 'patishapta', 
                 'nakshi pitha',
                 
                 # Bengali Sweets & Desserts
                 'mishti', 'roshogolla', 'rasgulla', 'chomchom', 'sandesh', 'kalo jam', 'jilapi', 'jalebi', 
                 'doi', 'mishti doi', 'payesh', 'kheer', 'firni', 'shemaiyer payesh', 'chanar payesh', 
                 'malai', 'kulfi', 'falooda',
                 
                 # Bengali Beverages & Drinks  
                 'cha', 'dudh cha', 'lemon cha', 'borhani', 'lassi', 'matha', 'shorbot', 'tamarind drink', 
                 'coconut water', 'sugarcane juice', 'fresh lime'
                 ],
        # Shopping
        'shopping': ['shopping', 'clothes', 'grocery', 'groceries', 'market', 'store', 'buy', 'bought'],
        # Health
        'health': ['medicine', 'pharmacy', 'doctor', 'hospital', 'medical', 'health'],
        # Bills
        'bills': ['internet', 'phone', 'rent', 'utilities', 'bill', 'electricity', 'water'],
        # Entertainment
        'entertainment': ['movie', 'cinema', 'game', 'entertainment', 'travel', 'vacation']
    }
    
    for category, keywords in category_keywords.items():
        for keyword in keywords:
            if has_word_boundary_match(context_text, keyword):
                # Base strength
                strength = 8
                
                # Boost if keyword appears multiple times - use word boundary matches for counting
                keyword_matches = len(re.findall(rf'(?<![A-Za-z0-9\u0980-\u09FF_]){re.escape(keyword)}(?![A-Za-z0-9\u0980-\u09FF_])', context_text, re.IGNORECASE))
                if keyword_matches > 1:
                    strength += 2
                
                # Boost for exact category matches
                if keyword in ['uber', 'taxi', 'breakfast', 'lunch', 'dinner', 'grocery']:
                    strength += 3
                    
                # Extra boost for pet-specific keywords to override generic "food"
                if keyword in ['cat', 'dog', 'cat food', 'dog food', 'pet food', 'vet']:
                    strength += 5
                
                if strength > best_strength:
                    best_strength = strength
                    best_category = category
    
    return best_category

def parse_expense(text: str, now: datetime, correction_context: bool = False) -> dict[str, Any] | None:
    """
    Enhanced expense parser with correction context support.
    Preserved for backward compatibility - returns first expense from extract_all_expenses.
    
    Args:
        text: Input text to parse
        now: Current timestamp for date resolution
        correction_context: True if parsing a correction message
        
    Returns:
        Dict with keys: amount, currency, category, merchant, ts_client, note
        Returns None if no valid expense found
    """
    if not text or not text.strip():
        return None
    
    # For correction context, support bare numbers and k shorthand
    if correction_context:
        # Normalize text for better parsing
        normalized = normalize_text_for_parsing(text)
        
        # Pattern 1: Bare numbers (allow None for other fields to be inherited)
        bare_number_match = re.search(r'\b(\d{1,7}(?:[.,]\d{1,2})?)\b', normalized)
        if bare_number_match:
            try:
                amount = Decimal(bare_number_match.group(1).replace(',', '.'))
                return {
                    'amount': amount,
                    'currency': None,  # Will be inherited from candidate
                    'category': None,  # Will be inherited from candidate  
                    'merchant': None,  # Will be inherited from candidate
                    'ts_client': now,
                    'note': text.strip(),
                    'correction_context': True
                }
            except (InvalidOperation, ValueError):
                pass
    
    # Use multi-expense parser and return first result
    all_expenses = extract_all_expenses(text, now)
    return all_expenses[0] if all_expenses else None

def _parse_standard_expense(normalized: str, original_text: str, now_ts: datetime) -> dict[str, Any] | None:
    """
    Standard expense parsing logic.
    
    Args:
        normalized: Normalized text for parsing
        original_text: Original input text
        now_ts: Current timestamp for date resolution
        
    Returns:
        Dict with parsed expense data or None if no valid expense found
    """
    normalized_text = normalized
    
    result = {
        'amount': None,
        'currency': 'BDT',  # Default to BDT
        'category': 'uncategorized',
        'merchant': None,
        'ts_client': None,
        'note': original_text
    }
    
    # Step 1: Extract amount and currency
    amount_found = False
    
    # Try currency symbols first (highest priority)
    for symbol, currency_code in CURRENCY_SYMBOLS.items():
        pattern = rf'{re.escape(symbol)}\s*(\d+(?:\.\d{{1,2}})?)'
        match = re.search(pattern, normalized_text)
        if match:
            try:
                result['amount'] = Decimal(match.group(1))
                result['currency'] = currency_code
                amount_found = True
                break
            except InvalidOperation:
                continue
    
    # Try currency words
    if not amount_found:
        for word, currency_code in CURRENCY_WORDS.items():
            # Pattern: amount + currency word OR currency word + amount
            patterns = [
                rf'\b(\d+(?:\.\d{{1,2}})?)\s*{re.escape(word)}\b',
                rf'\b{re.escape(word)}\s*(\d+(?:\.\d{{1,2}})?)\b'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, normalized_text, re.IGNORECASE)
                if match:
                    try:
                        result['amount'] = Decimal(match.group(1))
                        result['currency'] = currency_code
                        amount_found = True
                        break
                    except InvalidOperation:
                        continue
            
            if amount_found:
                break
    
    # Try action verbs (spent, paid, bought, etc.)
    if not amount_found:
        action_pattern = re.compile(r'\b(spent|paid|bought|blew|burned|used)\b.*?(\d+(?:\.\d{1,2})?)', re.IGNORECASE)
        match = action_pattern.search(normalized_text)
        if match:
            try:
                result['amount'] = Decimal(match.group(2))
                amount_found = True
            except InvalidOperation:
                pass
    
    # Try first numeric token as fallback
    if not amount_found:
        # Find first number that's not a year or date
        number_pattern = re.compile(r'\b(\d+(?:\.\d{1,2})?)\b')
        for match in number_pattern.finditer(normalized_text):
            num_str = match.group(1)
            num_val = float(num_str)
            
            # Skip if looks like a year (1900-2100)
            if 1900 <= num_val <= 2100:
                continue
            
            # Skip if followed by month names
            following_text = normalized_text[match.end():match.end()+20].lower()
            if any(month in following_text for month in ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
                                                        'jul', 'aug', 'sep', 'oct', 'nov', 'dec']):
                continue
            
            try:
                result['amount'] = Decimal(num_str)
                amount_found = True
                break
            except InvalidOperation:
                continue
    
    # If no amount found, return None
    if not amount_found or not result['amount']:
        return None
    
    # Step 2: Extract merchant
    result['merchant'] = extract_merchant(original_text)
    
    # Step 3: Infer category
    result['category'] = infer_category_with_strength(original_text)
    
    # Step 4: Extract date context
    date_context = extract_date_context(original_text, now_ts)
    if date_context:
        result['ts_client'] = date_context
    else:
        result['ts_client'] = now_ts
    
    # Clip amount to two decimal places
    result['amount'] = result['amount'].quantize(Decimal('0.01'))
    
    return result

def parse_amount_currency_category(text: str) -> dict[str, Any]:
    """
    Parse expense text and extract amount, currency, category, and note.
    
    Args:
        text: Input text like "Spent 100 on lunch" or "৳100 coffee"
        
    Returns:
        Dict with keys: amount (Decimal), currency (str), category (str), note (str)
        Returns empty dict if no amount found.
    """
    if not text or not text.strip():
        return {}
    
    # Use the main parse_expense function and adapt the result
    result = parse_expense(text, datetime.now())
    if not result:
        return {}
    
    return {
        'amount': result.get('amount'),
        'currency': result.get('currency', 'BDT'),
        'category': result.get('category', 'uncategorized'),
        'note': result.get('note', text.strip())
    }