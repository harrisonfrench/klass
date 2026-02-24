"""
Service for tracking user study streaks and daily activity.
"""
from datetime import date, timedelta
from app.db_connect import get_db


def get_user_streak(user_id):
    """Get the current streak info for a user."""
    db = get_db()
    cursor = db.execute('''
        SELECT current_streak, longest_streak, last_study_date
        FROM user_streaks WHERE user_id = %s
    ''', (user_id,))
    streak = cursor.fetchone()

    if not streak:
        # Create initial streak record
        db.execute('''
            INSERT INTO user_streaks (user_id, current_streak, longest_streak)
            VALUES (%s, 0, 0)
        ''', (user_id,))
        db.commit()
        return {'current_streak': 0, 'longest_streak': 0, 'last_study_date': None}

    return streak


def update_streak(user_id):
    """
    Update the user's streak based on study activity.
    Call this when the user completes a study activity.
    Returns the updated streak info.
    """
    db = get_db()
    today = date.today()

    # Get current streak info
    cursor = db.execute('''
        SELECT current_streak, longest_streak, last_study_date
        FROM user_streaks WHERE user_id = %s
    ''', (user_id,))
    streak = cursor.fetchone()

    if not streak:
        # Create streak record with initial activity
        db.execute('''
            INSERT INTO user_streaks (user_id, current_streak, longest_streak, last_study_date)
            VALUES (%s, 1, 1, %s)
        ''', (user_id, today))
        db.commit()
        return {'current_streak': 1, 'longest_streak': 1, 'last_study_date': today, 'streak_increased': True}

    last_study = streak['last_study_date']
    current = streak['current_streak']
    longest = streak['longest_streak']
    streak_increased = False

    if last_study is None:
        # First activity ever
        current = 1
        streak_increased = True
    elif last_study == today:
        # Already studied today, no change
        pass
    elif last_study == today - timedelta(days=1):
        # Studied yesterday, increment streak
        current += 1
        streak_increased = True
    else:
        # Missed a day (or more), reset streak
        current = 1
        streak_increased = True

    # Update longest streak if needed
    if current > longest:
        longest = current

    # Save updated streak
    db.execute('''
        UPDATE user_streaks
        SET current_streak = %s, longest_streak = %s, last_study_date = %s
        WHERE user_id = %s
    ''', (current, longest, today, user_id))
    db.commit()

    return {
        'current_streak': current,
        'longest_streak': longest,
        'last_study_date': today,
        'streak_increased': streak_increased
    }


def get_today_stats(user_id):
    """Get today's study statistics for a user."""
    db = get_db()
    today = date.today()

    # Get total study time (from study_sessions)
    cursor = db.execute('''
        SELECT COALESCE(SUM(duration), 0) as total_minutes
        FROM study_sessions
        WHERE user_id = %s AND DATE(created_at) = %s
    ''', (user_id, today))
    study_time = cursor.fetchone()

    # Get cards reviewed today
    cursor = db.execute('''
        SELECT COUNT(*) as count
        FROM study_sessions
        WHERE user_id = %s AND activity_type = 'flashcards' AND DATE(created_at) = %s
    ''', (user_id, today))
    cards_reviewed = cursor.fetchone()

    # Get quizzes taken today
    cursor = db.execute('''
        SELECT COUNT(*) as count
        FROM quiz_attempts
        WHERE user_id = %s AND DATE(completed_at) = %s
    ''', (user_id, today))
    quizzes_taken = cursor.fetchone()

    # Get pomodoro sessions today
    cursor = db.execute('''
        SELECT COUNT(*) as count, COALESCE(SUM(duration), 0) as total_minutes
        FROM pomodoro_sessions
        WHERE user_id = %s AND completed = 1 AND session_type = 'work' AND DATE(completed_at) = %s
    ''', (user_id, today))
    pomodoros = cursor.fetchone()

    return {
        'total_minutes': study_time['total_minutes'] if study_time else 0,
        'cards_reviewed': cards_reviewed['count'] if cards_reviewed else 0,
        'quizzes_taken': quizzes_taken['count'] if quizzes_taken else 0,
        'pomodoro_sessions': pomodoros['count'] if pomodoros else 0,
        'pomodoro_minutes': pomodoros['total_minutes'] if pomodoros else 0
    }


def has_studied_today(user_id):
    """Check if user has done any study activity today."""
    db = get_db()
    today = date.today()

    # Check study_sessions
    cursor = db.execute('''
        SELECT 1 FROM study_sessions
        WHERE user_id = %s AND DATE(created_at) = %s
        LIMIT 1
    ''', (user_id, today))
    if cursor.fetchone():
        return True

    # Check quiz_attempts
    cursor = db.execute('''
        SELECT 1 FROM quiz_attempts
        WHERE user_id = %s AND DATE(completed_at) = %s
        LIMIT 1
    ''', (user_id, today))
    if cursor.fetchone():
        return True

    # Check pomodoro sessions
    cursor = db.execute('''
        SELECT 1 FROM pomodoro_sessions
        WHERE user_id = %s AND completed = 1 AND DATE(completed_at) = %s
        LIMIT 1
    ''', (user_id, today))
    if cursor.fetchone():
        return True

    return False


def get_weekly_activity(user_id):
    """Get the last 7 days of study activity for streak visualization."""
    db = get_db()
    today = date.today()
    week_ago = today - timedelta(days=6)

    # Get days with activity
    cursor = db.execute('''
        SELECT DATE(created_at) as study_date, COUNT(*) as activities
        FROM study_sessions
        WHERE user_id = %s AND DATE(created_at) >= %s
        GROUP BY DATE(created_at)
    ''', (user_id, week_ago))
    study_days = {row['study_date']: row['activities'] for row in cursor.fetchall()}

    # Add quiz attempts
    cursor = db.execute('''
        SELECT DATE(completed_at) as study_date, COUNT(*) as activities
        FROM quiz_attempts
        WHERE user_id = %s AND DATE(completed_at) >= %s
        GROUP BY DATE(completed_at)
    ''', (user_id, week_ago))
    for row in cursor.fetchall():
        if row['study_date'] in study_days:
            study_days[row['study_date']] += row['activities']
        else:
            study_days[row['study_date']] = row['activities']

    # Build the 7-day array
    days = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        days.append({
            'date': day.isoformat(),
            'day_name': day.strftime('%a'),
            'has_activity': day in study_days,
            'activity_count': study_days.get(day, 0)
        })

    return days
