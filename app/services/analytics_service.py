"""Analytics Service - AI cost monitoring and retention analytics."""

from datetime import date, datetime, timedelta
from app.db_connect import get_db

# Estimated token costs (per 1M tokens, in USD)
AI_COST_RATES = {
    'llama-3.3-70b-versatile': {
        'input': 0.59,
        'output': 0.79
    },
    'llama3-70b-8192': {
        'input': 0.59,
        'output': 0.79
    },
    'default': {
        'input': 0.50,
        'output': 0.70
    }
}


def get_ai_usage_stats(days=30):
    """Get AI usage statistics for the past N days."""
    db = get_db()
    start_date = date.today() - timedelta(days=days)

    # Total requests and tokens
    cursor = db.execute('''
        SELECT
            COUNT(*) as total_requests,
            COALESCE(SUM(tokens_used), 0) as total_tokens,
            SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_requests,
            SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed_requests
        FROM ai_usage_logs
        WHERE DATE(created_at) >= %s
    ''', (start_date,))
    totals = cursor.fetchone()

    # Daily usage breakdown
    cursor = db.execute('''
        SELECT
            DATE(created_at) as date,
            COUNT(*) as requests,
            COALESCE(SUM(tokens_used), 0) as tokens
        FROM ai_usage_logs
        WHERE DATE(created_at) >= %s
        GROUP BY DATE(created_at)
        ORDER BY date
    ''', (start_date,))
    daily_usage = cursor.fetchall()

    # Usage by endpoint
    cursor = db.execute('''
        SELECT
            endpoint,
            COUNT(*) as requests,
            COALESCE(SUM(tokens_used), 0) as tokens
        FROM ai_usage_logs
        WHERE DATE(created_at) >= %s
        GROUP BY endpoint
        ORDER BY requests DESC
    ''', (start_date,))
    by_endpoint = cursor.fetchall()

    # Top users by usage
    cursor = db.execute('''
        SELECT
            u.username,
            u.email,
            COUNT(a.id) as requests,
            COALESCE(SUM(a.tokens_used), 0) as tokens
        FROM ai_usage_logs a
        JOIN users u ON a.user_id = u.id
        WHERE DATE(a.created_at) >= %s
        GROUP BY a.user_id
        ORDER BY tokens DESC
        LIMIT 20
    ''', (start_date,))
    top_users = cursor.fetchall()

    # Calculate estimated cost
    total_tokens = totals['total_tokens'] or 0
    # Assume 70% input, 30% output tokens
    input_tokens = total_tokens * 0.7
    output_tokens = total_tokens * 0.3
    rate = AI_COST_RATES['default']
    estimated_cost = (input_tokens / 1_000_000 * rate['input']) + (output_tokens / 1_000_000 * rate['output'])

    return {
        'totals': {
            'requests': totals['total_requests'] or 0,
            'tokens': total_tokens,
            'successful': totals['successful_requests'] or 0,
            'failed': totals['failed_requests'] or 0,
            'estimated_cost': round(estimated_cost, 2)
        },
        'daily_usage': daily_usage,
        'by_endpoint': by_endpoint,
        'top_users': top_users
    }


def get_ai_cost_per_user():
    """Calculate AI cost per active user and per Pro user."""
    db = get_db()
    thirty_days_ago = date.today() - timedelta(days=30)

    # Get total tokens used
    cursor = db.execute('''
        SELECT COALESCE(SUM(tokens_used), 0) as total_tokens
        FROM ai_usage_logs
        WHERE DATE(created_at) >= %s
    ''', (thirty_days_ago,))
    total_tokens = cursor.fetchone()['total_tokens'] or 0

    # Get active users count (users who have used AI features)
    cursor = db.execute('''
        SELECT COUNT(DISTINCT user_id) as active_users
        FROM ai_usage_logs
        WHERE DATE(created_at) >= %s
    ''', (thirty_days_ago,))
    active_users = cursor.fetchone()['active_users'] or 0

    # Get Pro users count
    cursor = db.execute('''
        SELECT COUNT(DISTINCT user_id) as pro_users
        FROM subscriptions
        WHERE status = 'active' AND plan IN ('pro_monthly', 'pro_yearly', 'pro_referral')
    ''')
    pro_users = cursor.fetchone()['pro_users'] or 0

    # Get Pro user tokens
    cursor = db.execute('''
        SELECT COALESCE(SUM(a.tokens_used), 0) as tokens
        FROM ai_usage_logs a
        JOIN subscriptions s ON a.user_id = s.user_id
        WHERE DATE(a.created_at) >= %s
        AND s.status = 'active'
        AND s.plan IN ('pro_monthly', 'pro_yearly', 'pro_referral')
    ''', (thirty_days_ago,))
    pro_tokens = cursor.fetchone()['tokens'] or 0

    # Calculate costs
    rate = AI_COST_RATES['default']
    total_cost = (total_tokens * 0.7 / 1_000_000 * rate['input']) + (total_tokens * 0.3 / 1_000_000 * rate['output'])
    pro_cost = (pro_tokens * 0.7 / 1_000_000 * rate['input']) + (pro_tokens * 0.3 / 1_000_000 * rate['output'])

    return {
        'total_tokens': total_tokens,
        'total_cost': round(total_cost, 2),
        'active_users': active_users,
        'cost_per_active_user': round(total_cost / active_users, 2) if active_users > 0 else 0,
        'pro_users': pro_users,
        'pro_tokens': pro_tokens,
        'pro_cost': round(pro_cost, 2),
        'cost_per_pro_user': round(pro_cost / pro_users, 2) if pro_users > 0 else 0
    }


def get_retention_metrics():
    """Calculate user retention metrics."""
    db = get_db()
    today = date.today()

    # 7-day retention: users who signed up 7-14 days ago and were active in last 7 days
    cohort_7_start = today - timedelta(days=14)
    cohort_7_end = today - timedelta(days=7)

    cursor = db.execute('''
        SELECT COUNT(*) as cohort_size
        FROM users
        WHERE DATE(created_at) >= %s AND DATE(created_at) < %s
    ''', (cohort_7_start, cohort_7_end))
    cohort_7_size = cursor.fetchone()['cohort_size'] or 0

    cursor = db.execute('''
        SELECT COUNT(DISTINCT u.id) as retained
        FROM users u
        WHERE DATE(u.created_at) >= %s AND DATE(u.created_at) < %s
        AND EXISTS (
            SELECT 1 FROM study_sessions s
            WHERE s.user_id = u.id AND DATE(s.created_at) >= %s
        )
    ''', (cohort_7_start, cohort_7_end, cohort_7_end))
    retained_7 = cursor.fetchone()['retained'] or 0

    # 30-day retention: users who signed up 30-60 days ago and were active in last 30 days
    cohort_30_start = today - timedelta(days=60)
    cohort_30_end = today - timedelta(days=30)

    cursor = db.execute('''
        SELECT COUNT(*) as cohort_size
        FROM users
        WHERE DATE(created_at) >= %s AND DATE(created_at) < %s
    ''', (cohort_30_start, cohort_30_end))
    cohort_30_size = cursor.fetchone()['cohort_size'] or 0

    cursor = db.execute('''
        SELECT COUNT(DISTINCT u.id) as retained
        FROM users u
        WHERE DATE(u.created_at) >= %s AND DATE(u.created_at) < %s
        AND EXISTS (
            SELECT 1 FROM study_sessions s
            WHERE s.user_id = u.id AND DATE(s.created_at) >= %s
        )
    ''', (cohort_30_start, cohort_30_end, cohort_30_end))
    retained_30 = cursor.fetchone()['retained'] or 0

    # Daily active users (DAU)
    cursor = db.execute('''
        SELECT COUNT(DISTINCT user_id) as dau
        FROM study_sessions
        WHERE DATE(created_at) = %s
    ''', (today,))
    dau = cursor.fetchone()['dau'] or 0

    # Weekly active users (WAU)
    week_ago = today - timedelta(days=7)
    cursor = db.execute('''
        SELECT COUNT(DISTINCT user_id) as wau
        FROM study_sessions
        WHERE DATE(created_at) >= %s
    ''', (week_ago,))
    wau = cursor.fetchone()['wau'] or 0

    # Monthly active users (MAU)
    month_ago = today - timedelta(days=30)
    cursor = db.execute('''
        SELECT COUNT(DISTINCT user_id) as mau
        FROM study_sessions
        WHERE DATE(created_at) >= %s
    ''', (month_ago,))
    mau = cursor.fetchone()['mau'] or 0

    return {
        'retention_7_day': round((retained_7 / cohort_7_size * 100), 1) if cohort_7_size > 0 else 0,
        'retention_7_cohort': cohort_7_size,
        'retention_7_retained': retained_7,
        'retention_30_day': round((retained_30 / cohort_30_size * 100), 1) if cohort_30_size > 0 else 0,
        'retention_30_cohort': cohort_30_size,
        'retention_30_retained': retained_30,
        'dau': dau,
        'wau': wau,
        'mau': mau,
        'dau_wau_ratio': round((dau / wau * 100), 1) if wau > 0 else 0,
        'dau_mau_ratio': round((dau / mau * 100), 1) if mau > 0 else 0
    }


def get_engagement_metrics():
    """Get top engagement behaviors."""
    db = get_db()
    thirty_days_ago = date.today() - timedelta(days=30)

    # Activity type breakdown
    cursor = db.execute('''
        SELECT
            activity_type,
            COUNT(*) as count,
            COUNT(DISTINCT user_id) as unique_users
        FROM study_sessions
        WHERE DATE(created_at) >= %s
        GROUP BY activity_type
        ORDER BY count DESC
    ''', (thirty_days_ago,))
    activity_breakdown = cursor.fetchall()

    # Most engaged users
    cursor = db.execute('''
        SELECT
            u.username,
            u.email,
            COUNT(s.id) as sessions,
            COALESCE(SUM(s.duration), 0) as total_minutes
        FROM users u
        JOIN study_sessions s ON s.user_id = u.id
        WHERE DATE(s.created_at) >= %s
        GROUP BY u.id
        ORDER BY sessions DESC
        LIMIT 10
    ''', (thirty_days_ago,))
    top_engaged_users = cursor.fetchall()

    # Streak distribution
    cursor = db.execute('''
        SELECT
            CASE
                WHEN current_streak = 0 THEN '0 days'
                WHEN current_streak BETWEEN 1 AND 3 THEN '1-3 days'
                WHEN current_streak BETWEEN 4 AND 7 THEN '4-7 days'
                WHEN current_streak BETWEEN 8 AND 14 THEN '8-14 days'
                WHEN current_streak BETWEEN 15 AND 30 THEN '15-30 days'
                ELSE '30+ days'
            END as streak_range,
            COUNT(*) as users
        FROM user_streaks
        GROUP BY streak_range
        ORDER BY
            CASE streak_range
                WHEN '0 days' THEN 1
                WHEN '1-3 days' THEN 2
                WHEN '4-7 days' THEN 3
                WHEN '8-14 days' THEN 4
                WHEN '15-30 days' THEN 5
                ELSE 6
            END
    ''')
    streak_distribution = cursor.fetchall()

    return {
        'activity_breakdown': activity_breakdown,
        'top_engaged_users': top_engaged_users,
        'streak_distribution': streak_distribution
    }


def get_subscription_metrics():
    """Get subscription and revenue metrics."""
    db = get_db()

    # Subscription breakdown
    cursor = db.execute('''
        SELECT
            plan,
            status,
            COUNT(*) as count
        FROM subscriptions
        GROUP BY plan, status
        ORDER BY count DESC
    ''')
    subscription_breakdown = cursor.fetchall()

    # Active Pro users
    cursor = db.execute('''
        SELECT COUNT(*) as count
        FROM subscriptions
        WHERE status = 'active' AND plan IN ('pro_monthly', 'pro_yearly')
    ''')
    active_pro = cursor.fetchone()['count'] or 0

    # Referral Pro users
    cursor = db.execute('''
        SELECT COUNT(*) as count
        FROM subscriptions
        WHERE status = 'active' AND plan = 'pro_referral'
    ''')
    referral_pro = cursor.fetchone()['count'] or 0

    # Total users
    cursor = db.execute('SELECT COUNT(*) as count FROM users')
    total_users = cursor.fetchone()['count'] or 0

    # Conversion rate
    conversion_rate = round((active_pro / total_users * 100), 1) if total_users > 0 else 0

    # MRR calculation (simplified)
    cursor = db.execute('''
        SELECT
            SUM(CASE WHEN plan = 'pro_monthly' THEN 7.99 ELSE 0 END) as monthly_mrr,
            SUM(CASE WHEN plan = 'pro_yearly' THEN 49.99/12 ELSE 0 END) as yearly_mrr
        FROM subscriptions
        WHERE status = 'active'
    ''')
    mrr_data = cursor.fetchone()
    mrr = round((mrr_data['monthly_mrr'] or 0) + (mrr_data['yearly_mrr'] or 0), 2)

    return {
        'subscription_breakdown': subscription_breakdown,
        'active_pro': active_pro,
        'referral_pro': referral_pro,
        'total_users': total_users,
        'conversion_rate': conversion_rate,
        'mrr': mrr,
        'arr': round(mrr * 12, 2)
    }


def get_referral_metrics():
    """Get referral program metrics."""
    db = get_db()

    # Total referrals
    cursor = db.execute('SELECT COUNT(*) as count FROM referrals')
    total_referrals = cursor.fetchone()['count'] or 0

    # Completed referrals
    cursor = db.execute("SELECT COUNT(*) as count FROM referrals WHERE status = 'completed'")
    completed_referrals = cursor.fetchone()['count'] or 0

    # Top referrers
    cursor = db.execute('''
        SELECT
            u.username,
            u.email,
            COUNT(r.id) as referrals,
            SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END) as completed
        FROM users u
        JOIN referrals r ON r.referrer_id = u.id
        GROUP BY u.id
        ORDER BY referrals DESC
        LIMIT 10
    ''')
    top_referrers = cursor.fetchall()

    return {
        'total_referrals': total_referrals,
        'completed_referrals': completed_referrals,
        'conversion_rate': round((completed_referrals / total_referrals * 100), 1) if total_referrals > 0 else 0,
        'top_referrers': top_referrers
    }
