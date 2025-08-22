# Create this file: templatetags/airtable_filters.py
# Make sure to create __init__.py in the templatetags directory

from django import template
from decimal import Decimal
import re

register = template.Library()

@register.filter
def get_min_price(configurations):
    """
    Get the minimum price from a list of configurations
    Usage: {{ property.configurations|get_min_price }}
    """
    if not configurations:
        return None
    
    prices = []
    for config in configurations:
        if config.get('price') and config.get('is_available', True):
            try:
                if isinstance(config['price'], Decimal):
                    prices.append(float(config['price']))
                elif isinstance(config['price'], (int, float)):
                    prices.append(float(config['price']))
                elif isinstance(config['price'], str):
                    # Remove currency symbols and commas
                    clean_price = re.sub(r'[₦,$,\s]', '', config['price'])
                    if clean_price and clean_price.replace('.', '').isdigit():
                        prices.append(float(clean_price))
            except (ValueError, TypeError):
                continue
    
    return min(prices) if prices else None

@register.filter
def format_price(price):
    """
    Format price with proper currency symbol and commas
    Usage: {{ price|format_price }}
    """
    if not price:
        return "Price on Request"
    
    try:
        if isinstance(price, str):
            # If already formatted, return as-is
            if '₦' in price:
                return price
            # Otherwise, try to convert
            clean_price = re.sub(r'[₦,$,\s]', '', price)
            if clean_price and clean_price.replace('.', '').isdigit():
                price = float(clean_price)
            else:
                return "Price on Request"
        
        if isinstance(price, (int, float, Decimal)):
            return f"₦{float(price):,.0f}"
        
    except (ValueError, TypeError):
        pass
    
    return "Price on Request"

@register.filter
def available_configs(configurations):
    """
    Filter configurations to only return available ones
    Usage: {{ property.configurations|available_configs }}
    """
    if not configurations:
        return []
    
    return [config for config in configurations if config.get('is_available', True)]

@register.filter
def first_n_items(items, n):
    """
    Get first n items from a list
    Usage: {{ property.amenities|first_n_items:3 }}
    """
    try:
        n = int(n)
        return items[:n] if items else []
    except (ValueError, TypeError):
        return items if items else []

@register.filter
def remaining_count(items, shown_count):
    """
    Get count of remaining items after showing some
    Usage: {{ property.amenities|remaining_count:3 }}
    """
    try:
        shown_count = int(shown_count)
        total = len(items) if items else 0
        return max(0, total - shown_count)
    except (ValueError, TypeError):
        return 0

@register.filter
def clean_phone(phone):
    """
    Clean phone number for WhatsApp links
    Usage: {{ property.contact_phone|clean_phone }}
    """
    if not phone:
        return '2348000000000'  # Default number
    
    # Remove all non-digits
    cleaned = re.sub(r'\D', '', str(phone))
    
    # If starts with 0, replace with 234
    if cleaned.startswith('0'):
        cleaned = '234' + cleaned[1:]
    # If doesn't start with 234, add it
    elif not cleaned.startswith('234'):
        cleaned = '234' + cleaned
    
    return cleaned

@register.simple_tag
def get_property_by_id(properties, property_id):
    """
    Get a property by its airtable_id
    Usage: {% get_property_by_id properties property_id as property %}
    """
    for prop in properties:
        if prop.get('airtable_id') == property_id:
            return prop
    return None