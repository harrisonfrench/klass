"""Referrals Blueprint - Referral system for user growth."""

import secrets
import string
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from app.db_connect import get_db
from app.blueprints.auth import login_required

referrals = Blueprint('referrals', __name__)

# Referral rewards configuration
REFERRAL_REWARDS = {
    'referrer': {
        'type': 'pro_days',
        'value': 30,  # 1 month of Pro
        'description': '1 month of Klass Pro'
    },
    'referred': {
        'type': 'pro_days',
        'value': 7,  # 1 week of Pro for new user
        'description': '1 week of Klass Pro'
    }
}


def generate_referral_code(length=8):
    """Generate a unique referral code."""
    chars = string.ascii_uppercase + string.digits
    # Remove confusing characters
    chars = chars.replace('O', '').replace('0', '').replace('I', '').replace('1', '').replace('L', '')
    return ''.join(secrets.choice(chars) for _ in range(length))


def get_or_create_referral_code(user_id):
    """Get existing or create new referral code for user."""
    db = get_db()

    cursor = db.execute('SELECT referral_code FROM users WHERE id = %s', (user_id,))
    user = cursor.fetchone()

    if user and user.get('referral_code'):
        return user['referral_code']

    # Generate unique code
    while True:
        code = generate_referral_code()
        cursor = db.execute('SELECT id FROM users WHERE referral_code = %s', (code,))
        if not cursor.fetchone():
            break

    # Save to user
    db.execute('UPDATE users SET referral_code = %s WHERE id = %s', (code, user_id))
    db.commit()

    return code


def apply_referral_reward(user_id, days):
    """Apply Pro days to a user's subscription."""
    db = get_db()

    # Get current subscription
    cursor = db.execute('SELECT * FROM subscriptions WHERE user_id = %s', (user_id,))
    sub = cursor.fetchone()

    if not sub:
        # Create subscription with reward
        end_date = datetime.utcnow() + timedelta(days=days)
        db.execute('''
            INSERT INTO subscriptions (user_id, plan, status, current_period_end)
            VALUES (%s, 'pro_referral', 'active', %s)
        ''', (user_id, end_date))
    elif sub['plan'] == 'free' or sub['status'] != 'active':
        # Upgrade to pro with reward
        end_date = datetime.utcnow() + timedelta(days=days)
        db.execute('''
            UPDATE subscriptions
            SET plan = 'pro_referral', status = 'active', current_period_end = %s
            WHERE user_id = %s
        ''', (end_date, user_id))
    else:
        # Extend existing subscription
        current_end = sub.get('current_period_end') or datetime.utcnow()
        if current_end < datetime.utcnow():
            current_end = datetime.utcnow()
        new_end = current_end + timedelta(days=days)
        db.execute('''
            UPDATE subscriptions
            SET current_period_end = %s
            WHERE user_id = %s
        ''', (new_end, user_id))

    db.commit()


def process_referral(referral_code, new_user_id):
    """Process a referral when a new user signs up."""
    db = get_db()

    # Find referrer by code
    cursor = db.execute('SELECT id FROM users WHERE referral_code = %s', (referral_code,))
    referrer = cursor.fetchone()

    if not referrer:
        return False

    referrer_id = referrer['id']

    # Don't allow self-referral
    if referrer_id == new_user_id:
        return False

    # Check if already referred
    cursor = db.execute('SELECT id FROM referrals WHERE referred_id = %s', (new_user_id,))
    if cursor.fetchone():
        return False

    # Create referral record
    db.execute('''
        INSERT INTO referrals (referrer_id, referred_id, referral_code, status)
        VALUES (%s, %s, %s, 'pending')
    ''', (referrer_id, new_user_id, referral_code))

    # Update user's referred_by
    db.execute('UPDATE users SET referred_by = %s WHERE id = %s', (referrer_id, new_user_id))

    db.commit()

    # Give new user their welcome bonus
    apply_referral_reward(new_user_id, REFERRAL_REWARDS['referred']['value'])

    return True


def complete_referral(referred_id):
    """Complete a referral and grant rewards when referred user becomes active."""
    db = get_db()

    # Get pending referral
    cursor = db.execute('''
        SELECT * FROM referrals
        WHERE referred_id = %s AND status = 'pending' AND reward_granted = 0
    ''', (referred_id,))
    referral = cursor.fetchone()

    if not referral:
        return False

    # Grant reward to referrer
    apply_referral_reward(referral['referrer_id'], REFERRAL_REWARDS['referrer']['value'])

    # Update referral status
    db.execute('''
        UPDATE referrals
        SET status = 'completed', reward_granted = 1, converted_at = CURRENT_TIMESTAMP
        WHERE id = %s
    ''', (referral['id'],))

    db.commit()

    return True


@referrals.route('/')
@login_required
def index():
    """Referral dashboard."""
    user_id = session['user_id']
    db = get_db()

    # Get or create referral code
    referral_code = get_or_create_referral_code(user_id)

    # Get referral stats
    cursor = db.execute('''
        SELECT
            COUNT(*) as total_referrals,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_referrals,
            SUM(CASE WHEN reward_granted = 1 THEN 1 ELSE 0 END) as rewards_earned
        FROM referrals
        WHERE referrer_id = %s
    ''', (user_id,))
    stats = cursor.fetchone()

    # Get recent referrals
    cursor = db.execute('''
        SELECT r.*, u.username, u.email
        FROM referrals r
        JOIN users u ON r.referred_id = u.id
        WHERE r.referrer_id = %s
        ORDER BY r.created_at DESC
        LIMIT 10
    ''', (user_id,))
    recent_referrals = cursor.fetchall()

    # Calculate total days earned
    total_days_earned = (stats['rewards_earned'] or 0) * REFERRAL_REWARDS['referrer']['value']

    return render_template('referrals/index.html',
        referral_code=referral_code,
        stats=stats,
        recent_referrals=recent_referrals,
        total_days_earned=total_days_earned,
        rewards=REFERRAL_REWARDS
    )


@referrals.route('/share')
@login_required
def share_link():
    """Get shareable referral link."""
    user_id = session['user_id']
    referral_code = get_or_create_referral_code(user_id)

    base_url = request.host_url.rstrip('/')
    referral_link = f"{base_url}/auth/register?ref={referral_code}"

    return jsonify({
        'success': True,
        'code': referral_code,
        'link': referral_link
    })


@referrals.route('/stats')
@login_required
def stats():
    """Get referral statistics."""
    user_id = session['user_id']
    db = get_db()

    cursor = db.execute('''
        SELECT
            COUNT(*) as total_referrals,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_referrals,
            SUM(CASE WHEN reward_granted = 1 THEN 1 ELSE 0 END) as rewards_earned
        FROM referrals
        WHERE referrer_id = %s
    ''', (user_id,))
    stats = cursor.fetchone()

    return jsonify({
        'success': True,
        'stats': {
            'total_referrals': stats['total_referrals'] or 0,
            'completed_referrals': stats['completed_referrals'] or 0,
            'rewards_earned': stats['rewards_earned'] or 0,
            'days_earned': (stats['rewards_earned'] or 0) * REFERRAL_REWARDS['referrer']['value']
        }
    })
