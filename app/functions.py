"""Shared utility functions for the entire application."""

import re
from html import escape


def strip_html(text):
    """Remove HTML tags from text.

    Args:
        text: Input text potentially containing HTML

    Returns:
        str: Text with HTML tags removed
    """
    if not text:
        return ''
    return re.sub(r'<[^>]+>', '', text).strip()


def truncate_text(text, max_length=100, suffix='...'):
    """Truncate text to max_length characters at word boundary.

    Args:
        text: Text to truncate
        max_length: Maximum length including suffix
        suffix: String to append when truncated

    Returns:
        str: Truncated text
    """
    if not text or len(text) <= max_length:
        return text or ''
    truncated = text[:max_length - len(suffix)]
    # Try to break at word boundary
    last_space = truncated.rfind(' ')
    if last_space > max_length // 2:
        truncated = truncated[:last_space]
    return truncated + suffix


def sanitize_input(text):
    """Sanitize user input for safe display.

    Args:
        text: Raw user input

    Returns:
        str: HTML-escaped and stripped text
    """
    if not text:
        return ''
    return escape(text.strip())


def validate_email(email):
    """Validate email format.

    Args:
        email: Email address to validate

    Returns:
        bool: True if valid format
    """
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))


def format_duration(seconds):
    """Format seconds into human-readable duration.

    Args:
        seconds: Duration in seconds

    Returns:
        str: Formatted duration (e.g., "1h 30m" or "45m")
    """
    if not seconds or seconds < 0:
        return '0m'

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)

    if hours > 0:
        return f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"
    return f"{minutes}m"


def safe_int(value, default=0):
    """Safely convert value to integer.

    Args:
        value: Value to convert
        default: Default if conversion fails

    Returns:
        int: Converted integer or default
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def pluralize(count, singular, plural=None):
    """Return singular or plural form based on count.

    Args:
        count: Number of items
        singular: Singular form of word
        plural: Plural form (defaults to singular + 's')

    Returns:
        str: Appropriate form of the word
    """
    if plural is None:
        plural = singular + 's'
    return singular if count == 1 else plural
