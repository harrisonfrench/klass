from flask import Blueprint, render_template, redirect, url_for, flash, session, g
from functools import wraps
from app.db_connect import get_db
from app.blueprints.auth import login_required
from datetime import datetime, timedelta

admin = Blueprint('admin', __name__, url_prefix='/admin')

# Admin email - only this user can access admin pages
ADMIN_EMAIL = 'harrisonfrench526@gmail.com'


def admin_required(f):
    """Decorator to require admin access for a route."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not g.user or g.user.get('email') != ADMIN_EMAIL:
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def is_admin():
    """Check if current user is admin."""
    return g.user and g.user.get('email') == ADMIN_EMAIL


@admin.route('/')
@admin.route('/dashboard')
@admin_required
def dashboard():
    """Admin dashboard with user stats and analytics."""
    db = get_db()

    # Get total users count
    total_users = db.execute('SELECT COUNT(*) as count FROM users').fetchone()['count']

    # Get total notes count
    total_notes = db.execute('SELECT COUNT(*) as count FROM notes').fetchone()['count']

    # Get total classes count
    total_classes = db.execute('SELECT COUNT(*) as count FROM classes').fetchone()['count']

    # Get total flashcard decks
    total_decks = db.execute('SELECT COUNT(*) as count FROM flashcard_decks').fetchone()['count']

    # Get users with their stats
    users = db.execute('''
        SELECT
            u.id,
            u.username,
            u.email,
            u.created_at,
            COUNT(DISTINCT c.id) as classes_count,
            COUNT(DISTINCT n.id) as notes_count
        FROM users u
        LEFT JOIN classes c ON c.user_id = u.id
        LEFT JOIN notes n ON n.class_id = c.id
        GROUP BY u.id
        ORDER BY u.created_at DESC
    ''').fetchall()

    # Get user signups over last 30 days
    thirty_days_ago = datetime.now() - timedelta(days=30)
    signups_data = db.execute('''
        SELECT DATE(created_at) as date, COUNT(*) as count
        FROM users
        WHERE created_at >= %s
        GROUP BY DATE(created_at)
        ORDER BY date
    ''', (thirty_days_ago,)).fetchall()

    # Format signup data for chart
    signup_labels = [str(row['date']) for row in signups_data]
    signup_values = [row['count'] for row in signups_data]

    # Get activity data (notes created per day)
    activity_data = db.execute('''
        SELECT DATE(n.created_at) as date, COUNT(*) as count
        FROM notes n
        WHERE n.created_at >= %s
        GROUP BY DATE(n.created_at)
        ORDER BY date
    ''', (thirty_days_ago,)).fetchall()

    # Format activity data for chart
    activity_labels = [str(row['date']) for row in activity_data]
    activity_values = [row['count'] for row in activity_data]

    return render_template('admin/dashboard.html',
        total_users=total_users,
        total_notes=total_notes,
        total_classes=total_classes,
        total_decks=total_decks,
        users=users,
        signup_labels=signup_labels,
        signup_values=signup_values,
        activity_labels=activity_labels,
        activity_values=activity_values
    )
