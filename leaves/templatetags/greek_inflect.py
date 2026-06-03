"""
Template filters for Greek inflection (nominative → accusative).

Rules:
  -ος  → -ο   (Γεώργιος → Γεώργιο, Νικολόπουλος → Νικολόπουλο)
  -ας  → -α   (Ανδρέας → Ανδρέα, Μπαλαδάκης → Μπαλαδάκη — handled by -ης rule)
  -ης  → -η   (Μπαλαδάκης → Μπαλαδάκη, Πέτρου → Πέτρου — unchanged)
  Most female names unchanged (ending in -α, -η, -ου)
"""

from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()


def _to_accusative(word):
    """Convert a single Greek word from nominative to accusative."""
    if not word or len(word) < 2:
        return word
    
    # Second declension masculine: -ος → -ο
    if word.endswith('ος') and len(word) > 2:
        return word[:-2] + 'ο'
    
    # First declension masculine: -ας → -α (only if preceded by vowel)
    if word.endswith('ας') and len(word) > 2:
        return word[:-2] + 'α'
    
    # First declension masculine: -ης → -η
    if word.endswith('ης') and len(word) > 2:
        return word[:-2] + 'η'
    
    # Unchanged (most feminine, irregular)
    return word


@register.filter
@stringfilter
def accusative(value):
    """
    Convert a full name from nominative to accusative.
    
    Usage: {{ user.full_name|accusative }}
    Example: "Γεώργιος Νικολόπουλος" → "Γεώργιο Νικολόπουλο"
    """
    words = value.split()
    converted = [_to_accusative(w) for w in words]
    return ' '.join(converted)
