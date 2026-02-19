"""Pomodoro Timer Blueprint - Focus timer with work/break intervals."""

from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from app.db_connect import get_db
from app.blueprints.auth import login_required

pomodoro = Blueprint('pomodoro', __name__)


@pomodoro.route('/')
@login_required
def timer():
    """Display the Pomodoro timer page."""
    db = get_db()
    user_id = session['user_id']

    # Get user settings
    cursor = db.execute('''
        SELECT pomodoro_work_duration, pomodoro_short_break,
               pomodoro_long_break, pomodoro_sessions_until_long
        FROM user_settings WHERE user_id = %s
    ''', (user_id,))
    settings = cursor.fetchone()

    if not settings:
        # Create default settings
        db.execute('''
            INSERT IGNORE INTO user_settings (user_id) VALUES (%s)
        ''', (user_id,))
        db.commit()
        settings = {
            'pomodoro_work_duration': 25,
            'pomodoro_short_break': 5,
            'pomodoro_long_break': 15,
            'pomodoro_sessions_until_long': 4
        }

    # Get user's classes for the timer
    cursor = db.execute(
        'SELECT id, name, color FROM classes WHERE user_id = %s ORDER BY name',
        (user_id,)
    )
    classes = cursor.fetchall()

    # Get today's stats
    cursor = db.execute('''
        SELECT COUNT(*) as sessions_today,
               SUM(duration) as minutes_today
        FROM pomodoro_sessions
        WHERE user_id = %s AND completed = 1
        AND DATE(completed_at) = CURDATE()
        AND session_type = 'work'
    ''', (user_id,))
    today_stats = cursor.fetchone()

    return render_template('pomodoro/timer.html',
                          settings=settings,
                          classes=classes,
                          today_stats=today_stats)


@pomodoro.route('/start', methods=['POST'])
@login_required
def start_session():
    """Start a new Pomodoro session."""
    db = get_db()
    user_id = session['user_id']

    data = request.get_json()
    session_type = data.get('type', 'work')  # work, short_break, long_break
    duration = data.get('duration', 25)
    class_id = data.get('class_id')

    cursor = db.execute('''
        INSERT INTO pomodoro_sessions (user_id, class_id, session_type, duration)
        VALUES (%s, %s, %s, %s)
    ''', (user_id, class_id if class_id else None, session_type, duration))
    db.commit()

    return jsonify({
        'success': True,
        'session_id': cursor.lastrowid
    })


@pomodoro.route('/complete/<int:session_id>', methods=['POST'])
@login_required
def complete_session(session_id):
    """Mark a Pomodoro session as completed."""
    db = get_db()
    user_id = session['user_id']

    # Verify session belongs to user
    cursor = db.execute('''
        SELECT * FROM pomodoro_sessions
        WHERE id = %s AND user_id = %s
    ''', (session_id, user_id))
    pomo_session = cursor.fetchone()

    if not pomo_session:
        return jsonify({'success': False, 'error': 'Session not found'}), 404

    db.execute('''
        UPDATE pomodoro_sessions
        SET completed = 1, completed_at = CURRENT_TIMESTAMP
        WHERE id = %s
    ''', (session_id,))

    # If it was a work session, also log to study_sessions for analytics
    if pomo_session['session_type'] == 'work':
        db.execute('''
            INSERT INTO study_sessions (user_id, class_id, activity_type, duration)
            VALUES (%s, %s, 'pomodoro', %s)
        ''', (user_id, pomo_session['class_id'], pomo_session['duration']))

    db.commit()

    # Check for achievements
    check_pomodoro_achievements(user_id)

    return jsonify({'success': True})


@pomodoro.route('/cancel/<int:session_id>', methods=['POST'])
@login_required
def cancel_session(session_id):
    """Cancel a Pomodoro session (delete it)."""
    db = get_db()
    user_id = session['user_id']

    db.execute('''
        DELETE FROM pomodoro_sessions
        WHERE id = %s AND user_id = %s AND completed = 0
    ''', (session_id, user_id))
    db.commit()

    return jsonify({'success': True})


@pomodoro.route('/active')
@login_required
def get_active():
    """Get active session and settings for the widget."""
    db = get_db()
    user_id = session['user_id']

    # Get user settings
    cursor = db.execute('''
        SELECT pomodoro_work_duration, pomodoro_short_break,
               pomodoro_long_break, pomodoro_sessions_until_long
        FROM user_settings WHERE user_id = %s
    ''', (user_id,))
    settings = cursor.fetchone()

    if not settings:
        settings = {
            'pomodoro_work_duration': 25,
            'pomodoro_short_break': 5,
            'pomodoro_long_break': 15,
            'pomodoro_sessions_until_long': 4
        }

    # Get user's classes
    cursor = db.execute(
        'SELECT id, name, color FROM classes WHERE user_id = %s ORDER BY name',
        (user_id,)
    )
    classes = [dict(c) for c in cursor.fetchall()]

    # Get today's completed sessions count
    cursor = db.execute('''
        SELECT COUNT(*) as count FROM pomodoro_sessions
        WHERE user_id = %s AND completed = 1
        AND DATE(completed_at) = CURDATE()
        AND session_type = 'work'
    ''', (user_id,))
    today_sessions = cursor.fetchone()['count']

    return jsonify({
        'success': True,
        'settings': dict(settings) if hasattr(settings, 'keys') else settings,
        'classes': classes,
        'today_sessions': today_sessions
    })


@pomodoro.route('/stats')
@login_required
def get_stats():
    """Get Pomodoro statistics."""
    db = get_db()
    user_id = session['user_id']

    # Today's stats
    cursor = db.execute('''
        SELECT COUNT(*) as sessions,
               COALESCE(SUM(duration), 0) as minutes
        FROM pomodoro_sessions
        WHERE user_id = %s AND completed = 1
        AND DATE(completed_at) = CURDATE()
        AND session_type = 'work'
    ''', (user_id,))
    today = cursor.fetchone()

    # This week's stats
    cursor = db.execute('''
        SELECT COUNT(*) as sessions,
               COALESCE(SUM(duration), 0) as minutes
        FROM pomodoro_sessions
        WHERE user_id = %s AND completed = 1
        AND DATE(completed_at) >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
        AND session_type = 'work'
    ''', (user_id,))
    week = cursor.fetchone()

    # All time stats
    cursor = db.execute('''
        SELECT COUNT(*) as sessions,
               COALESCE(SUM(duration), 0) as minutes
        FROM pomodoro_sessions
        WHERE user_id = %s AND completed = 1
        AND session_type = 'work'
    ''', (user_id,))
    all_time = cursor.fetchone()

    # Stats by class (this week)
    cursor = db.execute('''
        SELECT c.name, c.color, COUNT(*) as sessions,
               COALESCE(SUM(p.duration), 0) as minutes
        FROM pomodoro_sessions p
        JOIN classes c ON p.class_id = c.id
        WHERE p.user_id = %s AND p.completed = 1
        AND DATE(p.completed_at) >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
        AND p.session_type = 'work'
        GROUP BY c.id
        ORDER BY minutes DESC
    ''', (user_id,))
    by_class = cursor.fetchall()

    return jsonify({
        'success': True,
        'today': {'sessions': today['sessions'], 'minutes': today['minutes']},
        'week': {'sessions': week['sessions'], 'minutes': week['minutes']},
        'all_time': {'sessions': all_time['sessions'], 'minutes': all_time['minutes']},
        'by_class': by_class
    })


@pomodoro.route('/settings', methods=['POST'])
@login_required
def update_settings():
    """Update Pomodoro settings."""
    db = get_db()
    user_id = session['user_id']

    data = request.get_json()
    work_duration = data.get('work_duration', 25)
    short_break = data.get('short_break', 5)
    long_break = data.get('long_break', 15)
    sessions_until_long = data.get('sessions_until_long', 4)

    # Validate
    work_duration = max(1, min(60, int(work_duration)))
    short_break = max(1, min(30, int(short_break)))
    long_break = max(1, min(60, int(long_break)))
    sessions_until_long = max(2, min(10, int(sessions_until_long)))

    db.execute('''
        UPDATE user_settings
        SET pomodoro_work_duration = %s,
            pomodoro_short_break = %s,
            pomodoro_long_break = %s,
            pomodoro_sessions_until_long = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE user_id = %s
    ''', (work_duration, short_break, long_break, sessions_until_long, user_id))
    db.commit()

    return jsonify({'success': True})


def check_pomodoro_achievements(user_id):
    """Check and award Pomodoro-related achievements."""
    db = get_db()

    # Get total completed work sessions
    cursor = db.execute('''
        SELECT COUNT(*) as total FROM pomodoro_sessions
        WHERE user_id = %s AND completed = 1 AND session_type = 'work'
    ''', (user_id,))
    total = cursor.fetchone()['total']

    # Check for milestones
    milestones = [
        (10, 'pomodoro_10'),
        (50, 'pomodoro_50'),
        (100, 'pomodoro_100'),
        (500, 'pomodoro_500')
    ]

    for count, achievement_type in milestones:
        if total >= count:
            # Check if already earned
            cursor = db.execute('''
                SELECT id FROM achievements
                WHERE user_id = %s AND achievement_type = %s
            ''', (user_id, achievement_type))
            if not cursor.fetchone():
                db.execute('''
                    INSERT INTO achievements (user_id, achievement_type)
                    VALUES (%s, %s)
                ''', (user_id, achievement_type))
                db.commit()
