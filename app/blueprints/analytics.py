"""Analytics Blueprint - Progress tracking and study insights."""

from flask import Blueprint, render_template, jsonify, session
from app.db_connect import get_db
from app.blueprints.auth import login_required
from datetime import datetime, timedelta

analytics = Blueprint('analytics', __name__)


@analytics.route('/')
@login_required
def dashboard():
    """Main analytics dashboard."""
    db = get_db()
    user_id = session['user_id']

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

    return render_template(
        'analytics/dashboard.html',
        stats=stats,
        quiz_data=quiz_data,
        flashcard_data=flashcard_data,
        class_performance=class_performance,
        activity_data=activity_data
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


def get_overall_stats(db, user_id):
    """Get overall user statistics."""
    stats = {}

    # Total quizzes taken
    cursor = db.execute('''
        SELECT COUNT(*) as count FROM quiz_attempts
        WHERE user_id = ?
    ''', (user_id,))
    stats['total_quizzes'] = cursor.fetchone()['count']

    # Average quiz score
    cursor = db.execute('''
        SELECT AVG(score) as avg_score FROM quiz_attempts
        WHERE user_id = ?
    ''', (user_id,))
    result = cursor.fetchone()
    stats['avg_quiz_score'] = round(result['avg_score'] or 0, 1)

    # Total flashcards studied
    cursor = db.execute('''
        SELECT COUNT(*) as count FROM flashcards f
        JOIN flashcard_decks d ON f.deck_id = d.id
        WHERE d.user_id = ? AND f.times_reviewed > 0
    ''', (user_id,))
    stats['flashcards_studied'] = cursor.fetchone()['count']

    # Total notes created
    cursor = db.execute('''
        SELECT COUNT(*) as count FROM notes
        WHERE class_id IN (SELECT id FROM classes WHERE user_id = ?)
    ''', (user_id,))
    stats['total_notes'] = cursor.fetchone()['count']

    # Study streak (days with activity)
    cursor = db.execute('''
        SELECT COUNT(DISTINCT date(created_at)) as days
        FROM study_sessions
        WHERE user_id = ? AND created_at >= date('now', '-30 days')
    ''', (user_id,))
    stats['study_days'] = cursor.fetchone()['days']

    # Mastered flashcards (confidence >= 4)
    cursor = db.execute('''
        SELECT COUNT(*) as count FROM flashcards f
        JOIN flashcard_decks d ON f.deck_id = d.id
        WHERE d.user_id = ? AND f.confidence >= 4
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
        WHERE qa.user_id = ?
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
        WHERE d.user_id = ?
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
             WHERE q.class_id = c.id AND qa.user_id = ?) as avg_score
        FROM classes c
        WHERE c.user_id = ?
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
            date(created_at) as date,
            COUNT(*) as count
        FROM study_sessions
        WHERE user_id = ? AND created_at >= date('now', '-30 days')
        GROUP BY date(created_at)
    ''', (user_id,))

    activity_map = {row['date']: row['count'] for row in cursor.fetchall()}

    # Also count quiz attempts as activity
    cursor = db.execute('''
        SELECT
            date(completed_at) as date,
            COUNT(*) as count
        FROM quiz_attempts
        WHERE user_id = ? AND completed_at >= date('now', '-30 days')
        GROUP BY date(completed_at)
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
