"""Insights Service - Generate performance insights for users."""

from datetime import date, timedelta
from app.db_connect import get_db


def get_user_insights(user_id):
    """Get performance insights for a user."""
    db = get_db()
    today = date.today()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    insights = []

    # 1. Streak insight
    cursor = db.execute('''
        SELECT current_streak, longest_streak FROM user_streaks WHERE user_id = %s
    ''', (user_id,))
    streak = cursor.fetchone()
    if streak and streak['current_streak'] > 0:
        if streak['current_streak'] >= streak['longest_streak'] and streak['current_streak'] >= 3:
            insights.append({
                'type': 'streak_record',
                'icon': '🔥',
                'title': 'New Record!',
                'message': f"You're on a {streak['current_streak']}-day streak - your best ever!",
                'color': 'warning'
            })
        elif streak['current_streak'] >= 7:
            insights.append({
                'type': 'streak_milestone',
                'icon': '🎯',
                'title': 'Week Warrior',
                'message': f"You've studied for {streak['current_streak']} days straight!",
                'color': 'success'
            })

    # 2. Study time insight
    cursor = db.execute('''
        SELECT COALESCE(SUM(duration), 0) as total_minutes
        FROM study_sessions
        WHERE user_id = %s AND created_at >= %s
    ''', (user_id, week_ago))
    study_time = cursor.fetchone()
    if study_time and study_time['total_minutes'] >= 60:
        hours = study_time['total_minutes'] // 60
        insights.append({
            'type': 'study_time',
            'icon': '📚',
            'title': 'Study Champion',
            'message': f"You've studied for {hours}+ hours this week!",
            'color': 'primary'
        })

    # 3. Flashcard mastery insight
    cursor = db.execute('''
        SELECT COUNT(*) as mastered
        FROM flashcards f
        JOIN flashcard_decks d ON f.deck_id = d.id
        WHERE d.user_id = %s AND f.repetitions >= 3 AND f.ease_factor >= 2.5
    ''', (user_id,))
    mastered = cursor.fetchone()
    if mastered and mastered['mastered'] >= 10:
        insights.append({
            'type': 'mastery',
            'icon': '🧠',
            'title': 'Memory Master',
            'message': f"You've mastered {mastered['mastered']} flashcards!",
            'color': 'info'
        })

    # 4. Quiz performance insight
    cursor = db.execute('''
        SELECT AVG(score * 100.0 / NULLIF(total, 0)) as avg_score, COUNT(*) as count
        FROM quiz_attempts
        WHERE user_id = %s AND completed_at >= %s
    ''', (user_id, week_ago))
    quiz_stats = cursor.fetchone()
    if quiz_stats and quiz_stats['count'] >= 3 and quiz_stats['avg_score']:
        avg = round(quiz_stats['avg_score'])
        if avg >= 80:
            insights.append({
                'type': 'quiz_ace',
                'icon': '⭐',
                'title': 'Quiz Ace',
                'message': f"You're averaging {avg}% on quizzes this week!",
                'color': 'success'
            })

    # 5. Consistency insight
    cursor = db.execute('''
        SELECT COUNT(DISTINCT DATE(created_at)) as active_days
        FROM study_sessions
        WHERE user_id = %s AND created_at >= %s
    ''', (user_id, week_ago))
    consistency = cursor.fetchone()
    if consistency and consistency['active_days'] >= 5:
        insights.append({
            'type': 'consistency',
            'icon': '📈',
            'title': 'Super Consistent',
            'message': f"You studied {consistency['active_days']} out of 7 days!",
            'color': 'primary'
        })

    # 6. Growth insight (compare this week to last week)
    cursor = db.execute('''
        SELECT COALESCE(SUM(duration), 0) as this_week
        FROM study_sessions
        WHERE user_id = %s AND DATE(created_at) >= %s
    ''', (user_id, week_ago))
    this_week = cursor.fetchone()

    two_weeks_ago = today - timedelta(days=14)
    cursor = db.execute('''
        SELECT COALESCE(SUM(duration), 0) as last_week
        FROM study_sessions
        WHERE user_id = %s AND DATE(created_at) >= %s AND DATE(created_at) < %s
    ''', (user_id, two_weeks_ago, week_ago))
    last_week = cursor.fetchone()

    if this_week and last_week and last_week['last_week'] > 0:
        growth = ((this_week['this_week'] - last_week['last_week']) / last_week['last_week']) * 100
        if growth >= 25:
            insights.append({
                'type': 'growth',
                'icon': '🚀',
                'title': 'On Fire!',
                'message': f"You're studying {round(growth)}% more than last week!",
                'color': 'success'
            })

    # Return top 3 insights
    return insights[:3]


def get_study_summary(user_id):
    """Get a weekly study summary for email/dashboard."""
    db = get_db()
    today = date.today()
    week_ago = today - timedelta(days=7)

    summary = {
        'total_study_minutes': 0,
        'cards_reviewed': 0,
        'quizzes_completed': 0,
        'current_streak': 0,
        'days_studied': 0,
        'mastery_level': 0
    }

    # Study time
    cursor = db.execute('''
        SELECT COALESCE(SUM(duration), 0) as total
        FROM study_sessions
        WHERE user_id = %s AND DATE(created_at) >= %s
    ''', (user_id, week_ago))
    result = cursor.fetchone()
    summary['total_study_minutes'] = result['total'] if result else 0

    # Cards reviewed
    cursor = db.execute('''
        SELECT COUNT(*) as count
        FROM study_sessions
        WHERE user_id = %s AND activity_type = 'flashcards' AND DATE(created_at) >= %s
    ''', (user_id, week_ago))
    result = cursor.fetchone()
    summary['cards_reviewed'] = result['count'] if result else 0

    # Quizzes
    cursor = db.execute('''
        SELECT COUNT(*) as count FROM quiz_attempts
        WHERE user_id = %s AND DATE(completed_at) >= %s
    ''', (user_id, week_ago))
    result = cursor.fetchone()
    summary['quizzes_completed'] = result['count'] if result else 0

    # Streak
    cursor = db.execute('SELECT current_streak FROM user_streaks WHERE user_id = %s', (user_id,))
    result = cursor.fetchone()
    summary['current_streak'] = result['current_streak'] if result else 0

    # Days studied
    cursor = db.execute('''
        SELECT COUNT(DISTINCT DATE(created_at)) as days
        FROM study_sessions
        WHERE user_id = %s AND DATE(created_at) >= %s
    ''', (user_id, week_ago))
    result = cursor.fetchone()
    summary['days_studied'] = result['days'] if result else 0

    # Overall mastery (cards with high ease factor)
    cursor = db.execute('''
        SELECT COUNT(*) as mastered,
               (SELECT COUNT(*) FROM flashcards f2 JOIN flashcard_decks d2 ON f2.deck_id = d2.id WHERE d2.user_id = %s) as total
        FROM flashcards f
        JOIN flashcard_decks d ON f.deck_id = d.id
        WHERE d.user_id = %s AND f.repetitions >= 3
    ''', (user_id, user_id))
    result = cursor.fetchone()
    if result and result['total'] > 0:
        summary['mastery_level'] = round((result['mastered'] / result['total']) * 100)

    return summary
