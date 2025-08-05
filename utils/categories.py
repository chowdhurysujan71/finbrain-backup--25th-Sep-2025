"""Smart expense categorization logic"""
import logging

logger = logging.getLogger(__name__)

# Category definitions with keywords and emojis
CATEGORIES = {
    'Food': {
        'emoji': '🍔',
        'keywords': [
            'coffee', 'tea', 'restaurant', 'cafe', 'meal', 'breakfast', 'lunch', 
            'dinner', 'pizza', 'burger', 'rice', 'food', 'eat', 'drink', 'snack',
            'kitchen', 'cook', 'dining', 'buffet', 'takeaway', 'delivery'
        ]
    },
    'Transport': {
        'emoji': '🚗',
        'keywords': [
            'uber', 'taxi', 'bus', 'train', 'petrol', 'gas', 'fuel', 'ride', 
            'transport', 'travel', 'journey', 'metro', 'subway', 'flight', 'airline',
            'car', 'bike', 'motorcycle', 'rickshaw', 'auto'
        ]
    },
    'Shopping': {
        'emoji': '🛍️',
        'keywords': [
            'shop', 'buy', 'purchase', 'clothes', 'electronics', 'gadget', 'phone', 
            'computer', 'shoes', 'dress', 'shirt', 'pants', 'bag', 'watch', 'jewelry',
            'mall', 'store', 'online', 'amazon', 'flipkart'
        ]
    },
    'Groceries': {
        'emoji': '🛒',
        'keywords': [
            'grocery', 'supermarket', 'vegetables', 'fruits', 'milk', 'bread', 
            'market', 'store', 'fresh', 'organic', 'meat', 'fish', 'chicken',
            'spices', 'oil', 'sugar', 'flour', 'dal', 'pulse'
        ]
    },
    'Utilities': {
        'emoji': '💡',
        'keywords': [
            'electricity', 'water', 'gas', 'internet', 'phone', 'bill', 'utility', 
            'subscription', 'wifi', 'mobile', 'broadband', 'cable', 'netflix',
            'spotify', 'insurance', 'rent', 'maintenance'
        ]
    },
    'Entertainment': {
        'emoji': '🎬',
        'keywords': [
            'movie', 'cinema', 'gym', 'fitness', 'game', 'sport', 'music', 
            'concert', 'party', 'club', 'bar', 'theater', 'gaming', 'fun',
            'entertainment', 'hobby', 'book', 'magazine'
        ]
    },
    'Health': {
        'emoji': '🏥',
        'keywords': [
            'doctor', 'medicine', 'hospital', 'clinic', 'pharmacy', 'health', 
            'medical', 'dentist', 'checkup', 'treatment', 'surgery', 'therapy',
            'vitamins', 'supplement', 'prescription', 'ambulance'
        ]
    },
    'Education': {
        'emoji': '📚',
        'keywords': [
            'school', 'university', 'course', 'book', 'tuition', 'training', 
            'education', 'study', 'class', 'lesson', 'workshop', 'seminar',
            'certification', 'degree', 'exam', 'fee'
        ]
    },
    'Personal Care': {
        'emoji': '💅',
        'keywords': [
            'haircut', 'salon', 'spa', 'beauty', 'cosmetics', 'barber', 'massage',
            'facial', 'manicure', 'pedicure', 'skincare', 'perfume', 'shampoo',
            'soap', 'toothpaste', 'grooming'
        ]
    },
    'Misc': {
        'emoji': '💼',
        'keywords': []  # Default category for unmatched expenses
    }
}

def categorize_expense(description):
    """Categorize expense based on description keywords"""
    try:
        if not description:
            return 'Misc'
        
        # Convert to lowercase for matching
        description_lower = description.lower()
        
        # Check each category for keyword matches
        for category_name, category_data in CATEGORIES.items():
            if category_name == 'Misc':
                continue  # Skip Misc as it's the default
            
            keywords = category_data['keywords']
            for keyword in keywords:
                if keyword in description_lower:
                    logger.debug(f"Categorized '{description}' as '{category_name}' (matched: {keyword})")
                    return category_name
        
        # If no matches found, return Misc
        logger.debug(f"No category match found for '{description}', using Misc")
        return 'Misc'
        
    except Exception as e:
        logger.error(f"Error categorizing expense: {str(e)}")
        return 'Misc'

def get_category_emoji(category):
    """Get emoji for a specific category"""
    try:
        return CATEGORIES.get(category, CATEGORIES['Misc'])['emoji']
    except Exception as e:
        logger.error(f"Error getting category emoji: {str(e)}")
        return '💼'

def get_all_categories():
    """Get list of all available categories"""
    try:
        return [
            {
                'name': name,
                'emoji': data['emoji'],
                'keyword_count': len(data['keywords'])
            }
            for name, data in CATEGORIES.items()
        ]
    except Exception as e:
        logger.error(f"Error getting all categories: {str(e)}")
        return []

def add_category_keyword(category, keyword):
    """Add a new keyword to a category (for future enhancements)"""
    try:
        if category in CATEGORIES and keyword:
            keyword_lower = keyword.lower()
            if keyword_lower not in CATEGORIES[category]['keywords']:
                CATEGORIES[category]['keywords'].append(keyword_lower)
                logger.info(f"Added keyword '{keyword}' to category '{category}'")
                return True
        return False
    except Exception as e:
        logger.error(f"Error adding category keyword: {str(e)}")
        return False

def get_category_suggestions(description):
    """Get category suggestions with confidence scores"""
    try:
        if not description:
            return []
        
        description_lower = description.lower()
        suggestions = []
        
        for category_name, category_data in CATEGORIES.items():
            if category_name == 'Misc':
                continue
            
            matches = []
            keywords = category_data['keywords']
            
            for keyword in keywords:
                if keyword in description_lower:
                    matches.append(keyword)
            
            if matches:
                confidence = len(matches) / max(len(keywords), 1)
                suggestions.append({
                    'category': category_name,
                    'confidence': confidence,
                    'matched_keywords': matches,
                    'emoji': category_data['emoji']
                })
        
        # Sort by confidence score
        suggestions.sort(key=lambda x: x['confidence'], reverse=True)
        return suggestions
        
    except Exception as e:
        logger.error(f"Error getting category suggestions: {str(e)}")
        return []
