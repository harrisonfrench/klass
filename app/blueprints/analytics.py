"""Analytics Blueprint - Progress tracking and study insights."""

from flask import Blueprint, render_template, jsonify, session, request
from app.db_connect import get_db
from app.blueprints.auth import login_required
from datetime import datetime, timedelta

analytics = Blueprint('analytics', __name__)

# Achievement definitions
ACHIEVEMENTS = {
    'streak_3': {'name': '3 Day Streak', 'description': 'Study 3 days in a row', 'icon': 'flame', 'color': '#f59e0b'},
    'streak_7': {'name': 'Week Warrior', 'description': 'Study 7 days in a row', 'icon': 'flame', 'color': '#f97316'},
    'streak_30': {'name': 'Monthly Master', 'description': 'Study 30 days in a row', 'icon': 'flame', 'color': '#ef4444'},
    'cards_50': {'name': 'Card Collector', 'description': 'Review 50 flashcards', 'icon': 'layers', 'color': '#8b5cf6'},
    'cards_100': {'name': 'Card Master', 'description': 'Review 100 flashcards', 'icon': 'layers', 'color': '#7c3aed'},
    'cards_500': {'name': 'Card Legend', 'description': 'Review 500 flashcards', 'icon': 'layers', 'color': '#6d28d9'},
    'quiz_perfect': {'name': 'Perfect Score', 'description': 'Score 100% on a quiz', 'icon': 'check-circle', 'color': '#22c55e'},
    'quiz_10': {'name': 'Quiz Taker', 'description': 'Complete 10 quizzes', 'icon': 'check-circle', 'color': '#10b981'},
    'pomodoro_10': {'name': 'Focus Starter', 'description': 'Complete 10 Pomodoro sessions', 'icon': 'clock', 'color': '#0ea5e9'},
    'pomodoro_50': {'name': 'Focus Pro', 'description': 'Complete 50 Pomodoro sessions', 'icon': 'clock', 'color': '#0284c7'},
    'pomodoro_100': {'name': 'Focus Master', 'description': 'Complete 100 Pomodoro sessions', 'icon': 'clock', 'color': '#0369a1'},
    'pomodoro_500': {'name': 'Focus Legend', 'description': 'Complete 500 Pomodoro sessions', 'icon': 'clock', 'color': '#075985'},
    'notes_10': {'name': 'Note Taker', 'description': 'Create 10 notes', 'icon': 'file-text', 'color': '#ec4899'},
    'first_class': {'name': 'Getting Started', 'description': 'Create your first class', 'icon': 'book', 'color': '#6366f1'},
}


@analytics.route('/')
@login_required
def dashboard():
    """Main analytics dashboard."""
    db = get_db()
    user_id = session['user_id']

    # Update streak
    update_user_streak(db, user_id)

    # Get overall stats
    stats = get_overall_stats(db, user_id)

    # Get recent quiz attempts for the chart
    quiz_data = get_quiz_trend_data(db, user_id)

    # Get flashcard mastery data
    flashcard_data = get_flashcard_mastery(db, user_id)

    # Get class performance
    class_performance = get_class_performance(db, user_id)

    # Get study activity (last 30 days)
    activity_data = get_study_activity(db, user_id)

    # Get streak data
    streak_data = get_user_streak(db, user_id)

    # Get goals
    goals = get_user_goals(db, user_id)

    # Get achievements
    achievements = get_user_achievements(db, user_id)

    # Check for new achievements
    check_achievements(db, user_id)

    return render_template(
        'analytics/dashboard.html',
        stats=stats,
        quiz_data=quiz_data,
        flashcard_data=flashcard_data,
        class_performance=class_performance,
        activity_data=activity_data,
        streak_data=streak_data,
        goals=goals,
        achievements=achievements,
        achievement_defs=ACHIEVEMENTS
    )


@analytics.route('/api/quiz-trends')
@login_required
def api_quiz_trends():
    """API endpoint for quiz trend data."""
    db = get_db()
    user_id = session['user_id']
    return jsonify(get_quiz_trend_data(db, user_id))


@analytics.route('/api/flashcard-progress')
@login_required
def api_flashcard_progress():
    """API endpoint for flashcard mastery data."""
    db = get_db()
    user_id = session['user_id']
    return jsonify(get_flashcard_mastery(db, user_id))


@analytics.route('/api/activity')
@login_required
def api_activity():
    """API endpoint for study activity data."""
    db = get_db()
    user_id = session['user_id']
    return jsonify(get_study_activity(db, user_id))


@analytics.route('/goals', methods=['POST'])
@login_required
def create_goal():
    """Create a new study goal."""
    db = get_db()
    user_id = session['user_id']

    data = request.get_json()
    goal_type = data.get('goal_type')
    target_value = data.get('target_value', 0)

    if goal_type not in ['daily_minutes', 'weekly_quizzes', 'cards_reviewed', 'pomodoro_sessions']:
        return jsonify({'success': False, 'error': 'Invalid goal type'}), 400

    # Delete existing goal of same type
    db.execute('DELETE FROM study_goals WHERE user_id = %s AND goal_type = %s', (user_id, goal_type))

    # Create new goal
    db.execute('''
        INSERT INTO study_goals (user_id, goal_type, target_value, period_start)
        VALUES (%s, %s, %s, CURDATE())
    ''', (user_id, goal_type, target_value))
    db.commit()

    return jsonify({'success': True})


@analytics.route('/goals/<int:goal_id>', methods=['DELETE'])
@login_required
def delete_goal(goal_id):
    """Delete a study goal."""
    db = get_db()
    user_id = session['user_id']

    db.execute('DELETE FROM study_goals WHERE id = %s AND user_id = %s', (goal_id, user_id))
    db.commit()

    return jsonify({'success': True})


def get_overall_stats(db, user_id):
    """Get overall user statistics."""
    stats = {}

    # Total quizzes taken
    cursor = db.execute('''
        SELECT COUNT(*) as count FROM quiz_attempts
        WHERE user_id = %s
    ''', (user_id,))
    stats['total_quizzes'] = cursor.fetchone()['count']

    # Average quiz score
    cursor = db.execute('''
        SELECT AVG(score) as avg_score FROM quiz_attempts
        WHERE user_id = %s
    ''', (user_id,))
    result = cursor.fetchone()
    stats['avg_quiz_score'] = round(result['avg_score'] or 0, 1)

    # Total flashcards studied
    cursor = db.execute('''
        SELECT COUNT(*) as count FROM flashcards f
        JOIN flashcard_decks d ON f.deck_id = d.id
        WHERE d.user_id = %s AND f.times_reviewed > 0
    ''', (user_id,))
    stats['flashcards_studied'] = cursor.fetchone()['count']

    # Total notes created
    cursor = db.execute('''
        SELECT COUNT(*) as count FROM notes
        WHERE class_id IN (SELECT id FROM classes WHERE user_id = %s)
    ''', (user_id,))
    stats['total_notes'] = cursor.fetchone()['count']

    # Study streak (days with activity)
    cursor = db.execute('''
        SELECT COUNT(DISTINCT DATE(created_at)) as days
        FROM study_sessions
        WHERE user_id = %s AND created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
    ''', (user_id,))
    stats['study_days'] = cursor.fetchone()['days']

    # Mastered flashcards (confidence >= 4)
    cursor = db.execute('''
        SELECT COUNT(*) as count FROM flashcards f
        JOIN flashcard_decks d ON f.deck_id = d.id
        WHERE d.user_id = %s AND f.confidence >= 4
    ''', (user_id,))
    stats['mastered_cards'] = cursor.fetchone()['count']

    return stats


def get_quiz_trend_data(db, user_id):
    """Get quiz scores over time for charting."""
    cursor = db.execute('''
        SELECT
            date(qa.completed_at) as date,
            q.title as quiz_title,
            qa.score as score
        FROM quiz_attempts qa
        JOIN quizzes q ON qa.quiz_id = q.id
        WHERE qa.user_id = %s
        ORDER BY qa.completed_at DESC
        LIMIT 20
    ''', (user_id,))

    attempts = cursor.fetchall()

    # Format for Chart.js
    labels = []
    scores = []
    quiz_names = []

    for attempt in reversed(attempts):
        labels.append(attempt['date'])
        scores.append(attempt['score'])
        quiz_names.append(attempt['quiz_title'])

    return {
        'labels': labels,
        'scores': scores,
        'quiz_names': quiz_names
    }


def get_flashcard_mastery(db, user_id):
    """Get flashcard mastery by deck."""
    cursor = db.execute('''
        SELECT
            d.id,
            d.title,
            COUNT(f.id) as total_cards,
            SUM(CASE WHEN f.confidence >= 4 THEN 1 ELSE 0 END) as mastered,
            SUM(CASE WHEN f.confidence >= 2 AND f.confidence < 4 THEN 1 ELSE 0 END) as learning,
            SUM(CASE WHEN f.confidence < 2 OR f.confidence IS NULL THEN 1 ELSE 0 END) as new_cards,
            AVG(f.confidence) as avg_confidence
        FROM flashcard_decks d
        LEFT JOIN flashcards f ON d.id = f.deck_id
        WHERE d.user_id = %s
        GROUP BY d.id
        ORDER BY d.title
    ''', (user_id,))

    decks = []
    for row in cursor.fetchall():
        total = row['total_cards'] or 0
        mastered = row['mastered'] or 0
        mastery_percent = round((mastered / total * 100) if total > 0 else 0)

        decks.append({
            'id': row['id'],
            'title': row['title'],
            'total_cards': total,
            'mastered': mastered,
            'learning': row['learning'] or 0,
            'new_cards': row['new_cards'] or 0,
            'mastery_percent': mastery_percent,
            'avg_confidence': round(row['avg_confidence'] or 0, 1)
        })

    return decks


def get_class_performance(db, user_id):
    """Get performance metrics by class."""
    cursor = db.execute('''
        SELECT
            c.id,
            c.name,
            c.color,
            (SELECT COUNT(*) FROM notes WHERE class_id = c.id) as note_count,
            (SELECT COUNT(*) FROM flashcard_decks WHERE class_id = c.id) as deck_count,
            (SELECT COUNT(*) FROM quizzes WHERE class_id = c.id) as quiz_count,
            (SELECT AVG(qa.score) FROM quiz_attempts qa
             JOIN quizzes q ON qa.quiz_id = q.id
             WHERE q.class_id = c.id AND qa.user_id = %s) as avg_score
        FROM classes c
        WHERE c.user_id = %s
        ORDER BY c.name
    ''', (user_id, user_id))

    classes = []
    for row in cursor.fetchall():
        classes.append({
            'id': row['id'],
            'name': row['name'],
            'color': row['color'],
            'note_count': row['note_count'],
            'deck_count': row['deck_count'],
            'quiz_count': row['quiz_count'],
            'avg_score': round(row['avg_score'] or 0, 1)
        })

    return classes


def get_study_activity(db, user_id):
    """Get study activity for the last 30 days."""
    # Generate all dates in the last 30 days
    today = datetime.now().date()
    dates = [(today - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]

    # Get actual activity counts
    cursor = db.execute('''
        SELECT
            DATE(created_at) as date,
            COUNT(*) as count
        FROM study_sessions
        WHERE user_id = %s AND created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
        GROUP BY DATE(created_at)
    ''', (user_id,))

    activity_map = {row['date']: row['count'] for row in cursor.fetchall()}

    # Also count quiz attempts as activity
    cursor = db.execute('''
        SELECT
            DATE(completed_at) as date,
            COUNT(*) as count
        FROM quiz_attempts
        WHERE user_id = %s AND completed_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
        GROUP BY DATE(completed_at)
    ''', (user_id,))

    for row in cursor.fetchall():
        date = row['date']
        if date in activity_map:
            activity_map[date] += row['count']
        else:
            activity_map[date] = row['count']

    # Build the activity array
    activity = []
    for date in dates:
        count = activity_map.get(date, 0)
        activity.append({
            'date': date,
            'count': count,
            'level': min(count, 4)  # 0-4 intensity levels
        })

    return activity


def get_user_streak(db, user_id):
    """Get user's streak data."""
    cursor = db.execute('''
        SELECT current_streak, longest_streak, last_study_date
        FROM user_streaks WHERE user_id = %s
    ''', (user_id,))
    streak = cursor.fetchone()

    if streak:
        return {
            'current': streak['current_streak'],
            'longest': streak['longest_streak'],
            'last_date': streak['last_study_date']
        }
    return {'current': 0, 'longest': 0, 'last_date': None}


def update_user_streak(db, user_id):
    """Update user's streak based on activity."""
    today = datetime.now().date().isoformat()
    yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()

    # Check if there was activity today
    cursor = db.execute('''
        SELECT COUNT(*) as count FROM (
            SELECT created_at FROM study_sessions WHERE user_id = %s AND DATE(created_at) = CURDATE()
            UNION ALL
            SELECT completed_at FROM quiz_attempts WHERE user_id = %s AND DATE(completed_at) = CURDATE()
            UNION ALL
            SELECT completed_at FROM pomodoro_sessions WHERE user_id = %s AND completed = 1 AND DATE(completed_at) = CURDATE()
        )
    ''', (user_id, user_id, user_id))
    has_activity_today = cursor.fetchone()['count'] > 0

    if not has_activity_today:
        return

    # Get current streak data
    cursor = db.execute('''
        SELECT current_streak, longest_streak, last_study_date
        FROM user_streaks WHERE user_id = %s
    ''', (user_id,))
    streak = cursor.fetchone()

    if streak:
        last_date = streak['last_study_date']
        current = streak['current_streak']
        longest = streak['longest_streak']

        if last_date == today:
            return  # Already updated today
        elif last_date == yesterday:
            current += 1
        else:
            current = 1  # Streak broken, start new

        longest = max(longest, current)

        db.execute('''
            UPDATE user_streaks
            SET current_streak = %s, longest_streak = %s, last_study_date = %s
            WHERE user_id = %s
        ''', (current, longest, today, user_id))
    else:
        db.execute('''
            INSERT INTO user_streaks (user_id, current_streak, longest_streak, last_study_date)
            VALUES (%s, 1, 1, %s)
        ''', (user_id, today))

    db.commit()


def get_user_goals(db, user_id):
    """Get user's study goals with progress."""
    cursor = db.execute('''
        SELECT id, goal_type, target_value, period_start
        FROM study_goals WHERE user_id = %s
    ''', (user_id,))
    goals = []

    for row in cursor.fetchall():
        goal_type = row['goal_type']
        target = row['target_value']
        period_start = row['period_start']

        # Calculate current value based on goal type
        if goal_type == 'daily_minutes':
            cursor2 = db.execute('''
                SELECT COALESCE(SUM(duration), 0) as total FROM study_sessions
                WHERE user_id = %s AND DATE(created_at) = CURDATE()
            ''', (user_id,))
            current = cursor2.fetchone()['total']
        elif goal_type == 'weekly_quizzes':
            cursor2 = db.execute('''
                SELECT COUNT(*) as count FROM quiz_attempts
                WHERE user_id = %s AND DATE(completed_at) >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            ''', (user_id,))
            current = cursor2.fetchone()['count']
        elif goal_type == 'cards_reviewed':
            cursor2 = db.execute('''
                SELECT COUNT(*) as count FROM flashcards f
                JOIN flashcard_decks d ON f.deck_id = d.id
                WHERE d.user_id = %s AND DATE(f.last_reviewed) = DATE('now')
            ''', (user_id,))
            current = cursor2.fetchone()['count']
        elif goal_type == 'pomodoro_sessions':
            cursor2 = db.execute('''
                SELECT COUNT(*) as count FROM pomodoro_sessions
                WHERE user_id = %s AND completed = 1 AND DATE(completed_at) = CURDATE()
                AND session_type = 'work'
            ''', (user_id,))
            current = cursor2.fetchone()['count']
        else:
            current = 0

        progress = min(100, int((current / target * 100) if target > 0 else 0))

        goals.append({
            'id': row['id'],
            'type': goal_type,
            'target': target,
            'current': current,
            'progress': progress,
            'label': get_goal_label(goal_type)
        })

    return goals


def get_goal_label(goal_type):
    """Get human-readable label for goal type."""
    labels = {
        'daily_minutes': 'Daily Study Minutes',
        'weekly_quizzes': 'Weekly Quizzes',
        'cards_reviewed': 'Cards Today',
        'pomodoro_sessions': 'Pomodoros Today'
    }
    return labels.get(goal_type, goal_type)


def get_user_achievements(db, user_id):
    """Get user's earned achievements."""
    cursor = db.execute('''
        SELECT achievement_type, earned_at
        FROM achievements WHERE user_id = %s
        ORDER BY earned_at DESC
    ''', (user_id,))

    achievements = []
    for row in cursor.fetchall():
        ach_type = row['achievement_type']
        if ach_type in ACHIEVEMENTS:
            achievements.append({
                'type': ach_type,
                'earned_at': row['earned_at'],
                **ACHIEVEMENTS[ach_type]
            })

    return achievements


def check_achievements(db, user_id):
    """Check and award any new achievements."""
    earned = set()
    cursor = db.execute('SELECT achievement_type FROM achievements WHERE user_id = %s', (user_id,))
    for row in cursor.fetchall():
        earned.add(row['achievement_type'])

    new_achievements = []

    # Check streak achievements
    cursor = db.execute('SELECT current_streak FROM user_streaks WHERE user_id = %s', (user_id,))
    streak = cursor.fetchone()
    if streak:
        if streak['current_streak'] >= 3 and 'streak_3' not in earned:
            new_achievements.append('streak_3')
        if streak['current_streak'] >= 7 and 'streak_7' not in earned:
            new_achievements.append('streak_7')
        if streak['current_streak'] >= 30 and 'streak_30' not in earned:
            new_achievements.append('streak_30')

    # Check flashcard achievements
    cursor = db.execute('''
        SELECT SUM(f.times_reviewed) as total FROM flashcards f
        JOIN flashcard_decks d ON f.deck_id = d.id
        WHERE d.user_id = %s
    ''', (user_id,))
    result = cursor.fetchone()
    total_reviews = result['total'] or 0
    if total_reviews >= 50 and 'cards_50' not in earned:
        new_achievements.append('cards_50')
    if total_reviews >= 100 and 'cards_100' not in earned:
        new_achievements.append('cards_100')
    if total_reviews >= 500 and 'cards_500' not in earned:
        new_achievements.append('cards_500')

    # Check quiz achievements
    cursor = db.execute('SELECT COUNT(*) as count FROM quiz_attempts WHERE user_id = %s', (user_id,))
    quiz_count = cursor.fetchone()['count']
    if quiz_count >= 10 and 'quiz_10' not in earned:
        new_achievements.append('quiz_10')

    cursor = db.execute('SELECT score FROM quiz_attempts WHERE user_id = %s AND score = 100', (user_id,))
    if cursor.fetchone() and 'quiz_perfect' not in earned:
        new_achievements.append('quiz_perfect')

    # Check notes achievement
    cursor = db.execute('''
        SELECT COUNT(*) as count FROM notes
        WHERE class_id IN (SELECT id FROM classes WHERE user_id = %s)
    ''', (user_id,))
    note_count = cursor.fetchone()['count']
    if note_count >= 10 and 'notes_10' not in earned:
        new_achievements.append('notes_10')

    # Check first class
    cursor = db.execute('SELECT COUNT(*) as count FROM classes WHERE user_id = %s', (user_id,))
    if cursor.fetchone()['count'] >= 1 and 'first_class' not in earned:
        new_achievements.append('first_class')

    # Award new achievements
    for ach_type in new_achievements:
        db.execute('''
            INSERT INTO achievements (user_id, achievement_type)
            VALUES (%s, %s)
        ''', (user_id, ach_type))

    if new_achievements:
        db.commit()

    return new_achievements
