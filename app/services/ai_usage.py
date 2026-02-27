"""AI Usage Service - Track and limit AI API usage per user."""

from datetime import datetime, timedelta
from functools import wraps
from flask import session, jsonify


# Default limits (can be overridden by tier)
DEFAULT_LIMITS = {
    'hourly': 50,       # Max AI calls per hour
    'daily': 200,       # Max AI calls per day
    'tokens_daily': 100000,  # Max tokens per day
}

# Tier-specific limits
TIER_LIMITS = {
    'free': {
        'hourly': 15,
        'daily': 30,
        'tokens_daily': 15000,
    },
    'pro_monthly': {
        'hourly': 200,
        'daily': 1000,
        'tokens_daily': 1000000,
    },
    'pro_yearly': {
        'hourly': 200,
        'daily': 1000,
        'tokens_daily': 1000000,
    },
}


def get_user_tier(user_id):
    """Get the subscription tier for a user."""
    from app.db_connect import get_db
    db = get_db()

    cursor = db.execute('''
        SELECT plan, status FROM subscriptions WHERE user_id = %s
    ''', (user_id,))
    sub = cursor.fetchone()

    if not sub or sub['status'] != 'active':
        return 'free'

    return sub['plan'] if sub['plan'] in TIER_LIMITS else 'free'


def log_ai_usage(db, user_id, endpoint, tokens_used=0, model=None, success=True, error_message=None):
    """
    Log an AI API call to the database.

    Args:
        db: Database connection
        user_id: The user making the request
        endpoint: Name of the AI endpoint (e.g., 'summarize', 'chat', 'flashcards')
        tokens_used: Number of tokens consumed (if available)
        model: AI model used (e.g., 'llama-3.3-70b-versatile')
        success: Whether the call was successful
        error_message: Error message if failed
    """
    try:
        db.execute('''
            INSERT INTO ai_usage_logs (user_id, endpoint, tokens_used, model, success, error_message)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (user_id, endpoint, tokens_used, model, 1 if success else 0, error_message))
        db.commit()
    except Exception as e:
        # Log failure shouldn't break the main flow
        print(f"Failed to log AI usage: {e}")


def get_usage_stats(db, user_id, period='day'):
    """
    Get AI usage statistics for a user.

    Args:
        db: Database connection
        user_id: The user to check
        period: 'hour' or 'day'

    Returns:
        dict with call_count and tokens_used
    """
    if period == 'hour':
        time_threshold = datetime.utcnow() - timedelta(hours=1)
    else:
        time_threshold = datetime.utcnow() - timedelta(days=1)

    cursor = db.execute('''
        SELECT COUNT(*) as call_count, COALESCE(SUM(tokens_used), 0) as tokens_used
        FROM ai_usage_logs
        WHERE user_id = %s AND created_at >= %s AND success = 1
    ''', (user_id, time_threshold))
    result = cursor.fetchone()

    return {
        'call_count': result['call_count'] if result else 0,
        'tokens_used': result['tokens_used'] if result else 0,
    }


def check_usage_limit(db, user_id, tier='free'):
    """
    Check if user is within their usage limits.

    Args:
        db: Database connection
        user_id: The user to check
        tier: User's subscription tier ('free' or 'pro')

    Returns:
        tuple: (is_allowed, message)
    """
    limits = TIER_LIMITS.get(tier, DEFAULT_LIMITS)

    # Check hourly limit
    hourly_stats = get_usage_stats(db, user_id, 'hour')
    if hourly_stats['call_count'] >= limits['hourly']:
        return False, f"Hourly AI limit reached ({limits['hourly']} calls/hour). Please try again later."

    # Check daily limit
    daily_stats = get_usage_stats(db, user_id, 'day')
    if daily_stats['call_count'] >= limits['daily']:
        return False, f"Daily AI limit reached ({limits['daily']} calls/day). Limits reset at midnight UTC."

    # Check token limit
    if daily_stats['tokens_used'] >= limits['tokens_daily']:
        return False, f"Daily token limit reached. Please try again tomorrow."

    return True, None


def get_remaining_usage(db, user_id, tier='free'):
    """
    Get remaining usage for a user.

    Returns:
        dict with remaining calls and tokens
    """
    limits = TIER_LIMITS.get(tier, DEFAULT_LIMITS)

    hourly_stats = get_usage_stats(db, user_id, 'hour')
    daily_stats = get_usage_stats(db, user_id, 'day')

    return {
        'hourly_remaining': max(0, limits['hourly'] - hourly_stats['call_count']),
        'daily_remaining': max(0, limits['daily'] - daily_stats['call_count']),
        'tokens_remaining': max(0, limits['tokens_daily'] - daily_stats['tokens_used']),
        'hourly_limit': limits['hourly'],
        'daily_limit': limits['daily'],
        'token_limit': limits['tokens_daily'],
    }


def ai_rate_limit(endpoint_name, tokens_estimate=500):
    """
    Decorator to apply AI rate limiting and usage logging to an endpoint.

    Usage:
        @ai_rate_limit('summarize', tokens_estimate=1000)
        def summarize_note(note_id):
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from app.db_connect import get_db

            if 'user_id' not in session:
                return jsonify({'success': False, 'error': 'Authentication required'}), 401

            user_id = session['user_id']
            db = get_db()

            # Get user's subscription tier
            tier = get_user_tier(user_id)

            # Check if user is within limits
            is_allowed, message = check_usage_limit(db, user_id, tier=tier)
            if not is_allowed:
                # Log the blocked attempt
                log_ai_usage(db, user_id, endpoint_name, success=False, error_message='Rate limited')
                return jsonify({
                    'success': False,
                    'error': message,
                    'rate_limited': True,
                }), 429

            # Execute the actual function
            try:
                result = f(*args, **kwargs)

                # Log successful usage (estimate tokens if not available)
                log_ai_usage(db, user_id, endpoint_name, tokens_used=tokens_estimate, model='llama-3.3-70b-versatile')

                return result
            except Exception as e:
                # Log failed usage
                log_ai_usage(db, user_id, endpoint_name, success=False, error_message=str(e))
                raise

        return decorated_function
    return decorator
