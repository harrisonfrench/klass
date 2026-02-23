"""Settings Blueprint - User preferences and settings."""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, Response
from werkzeug.security import generate_password_hash, check_password_hash
from app.db_connect import get_db
from app.blueprints.auth import login_required
from app.services.export_service import export_notes_markdown, export_flashcards_csv, export_full_backup

settings = Blueprint('settings', __name__)


@settings.route('/')
@login_required
def preferences():
    """User preferences page."""
    db = get_db()
    user_id = session['user_id']

    # Get user info
    cursor = db.execute(
        'SELECT id, email, username, created_at FROM users WHERE id = %s',
        (user_id,)
    )
    user = cursor.fetchone()

    # Get user settings
    cursor = db.execute(
        'SELECT * FROM user_settings WHERE user_id = %s',
        (user_id,)
    )
    user_settings = cursor.fetchone()

    if not user_settings:
        # Create default settings
        db.execute(
            'INSERT INTO user_settings (user_id) VALUES (%s)',
            (user_id,)
        )
        db.commit()
        cursor = db.execute(
            'SELECT * FROM user_settings WHERE user_id = %s',
            (user_id,)
        )
        user_settings = cursor.fetchone()

    # Get stats
    cursor = db.execute(
        'SELECT COUNT(*) as count FROM classes WHERE user_id = %s',
        (user_id,)
    )
    class_count = cursor.fetchone()['count']

    cursor = db.execute('''
        SELECT COUNT(*) as count FROM notes n
        JOIN classes c ON n.class_id = c.id
        WHERE c.user_id = %s
    ''', (user_id,))
    notes_count = cursor.fetchone()['count']

    cursor = db.execute('''
        SELECT COUNT(*) as count FROM flashcard_decks d
        JOIN classes c ON d.class_id = c.id
        WHERE c.user_id = %s
    ''', (user_id,))
    deck_count = cursor.fetchone()['count']

    cursor = db.execute('''
        SELECT COUNT(*) as count FROM quizzes q
        JOIN classes c ON q.class_id = c.id
        WHERE c.user_id = %s
    ''', (user_id,))
    quiz_count = cursor.fetchone()['count']

    stats = {
        'classes': class_count,
        'notes': notes_count,
        'decks': deck_count,
        'quizzes': quiz_count
    }

    return render_template(
        'settings/preferences.html',
        user=user,
        settings=user_settings,
        stats=stats
    )


@settings.route('/update-profile', methods=['POST'])
@login_required
def update_profile():
    """Update user profile."""
    db = get_db()
    user_id = session['user_id']

    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip().lower()

    if not username or len(username) < 3:
        flash('Username must be at least 3 characters.', 'error')
        return redirect(url_for('settings.preferences'))

    if not email:
        flash('Email is required.', 'error')
        return redirect(url_for('settings.preferences'))

    # Check if username is taken by another user
    cursor = db.execute(
        'SELECT id FROM users WHERE username = %s AND id != %s',
        (username, user_id)
    )
    if cursor.fetchone():
        flash('Username is already taken.', 'error')
        return redirect(url_for('settings.preferences'))

    # Check if email is taken by another user
    cursor = db.execute(
        'SELECT id FROM users WHERE email = %s AND id != %s',
        (email, user_id)
    )
    if cursor.fetchone():
        flash('Email is already registered.', 'error')
        return redirect(url_for('settings.preferences'))

    db.execute(
        'UPDATE users SET username = %s, email = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s',
        (username, email, user_id)
    )
    db.commit()

    session['username'] = username
    flash('Profile updated successfully.', 'success')
    return redirect(url_for('settings.preferences'))


@settings.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """Change user password."""
    db = get_db()
    user_id = session['user_id']

    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    if not current_password:
        flash('Current password is required.', 'error')
        return redirect(url_for('settings.preferences'))

    if not new_password or len(new_password) < 6:
        flash('New password must be at least 6 characters.', 'error')
        return redirect(url_for('settings.preferences'))

    if new_password != confirm_password:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('settings.preferences'))

    # Verify current password
    cursor = db.execute('SELECT password_hash FROM users WHERE id = %s', (user_id,))
    user = cursor.fetchone()

    if not check_password_hash(user['password_hash'], current_password):
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('settings.preferences'))

    # Update password
    db.execute(
        'UPDATE users SET password_hash = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s',
        (generate_password_hash(new_password), user_id)
    )
    db.commit()

    flash('Password changed successfully.', 'success')
    return redirect(url_for('settings.preferences'))


@settings.route('/update-preferences', methods=['POST'])
@login_required
def update_preferences():
    """Update user preferences."""
    db = get_db()
    user_id = session['user_id']

    theme = request.form.get('theme', 'light')
    if theme not in ('light', 'dark'):
        theme = 'light'
    default_class_color = request.form.get('default_class_color', '#6366f1')
    ai_features_enabled = 1 if request.form.get('ai_features_enabled') else 0

    db.execute('''
        UPDATE user_settings
        SET theme = %s, default_class_color = %s, ai_features_enabled = %s, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = %s
    ''', (theme, default_class_color, ai_features_enabled, user_id))
    db.commit()

    flash('Preferences saved.', 'success')
    return redirect(url_for('settings.preferences'))


@settings.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    """Delete user account and all data."""
    db = get_db()
    user_id = session['user_id']

    password = request.form.get('password', '')

    # Verify password
    cursor = db.execute('SELECT password_hash FROM users WHERE id = %s', (user_id,))
    user = cursor.fetchone()

    if not check_password_hash(user['password_hash'], password):
        flash('Incorrect password.', 'error')
        return redirect(url_for('settings.preferences'))

    # Delete all user data (cascading deletes should handle most of this)
    db.execute('DELETE FROM chat_messages WHERE session_id IN (SELECT id FROM chat_sessions WHERE user_id = %s)', (user_id,))
    db.execute('DELETE FROM chat_sessions WHERE user_id = %s', (user_id,))
    db.execute('DELETE FROM user_settings WHERE user_id = %s', (user_id,))
    db.execute('DELETE FROM study_sessions WHERE user_id = %s', (user_id,))
    db.execute('DELETE FROM quiz_attempts WHERE user_id = %s', (user_id,))
    db.execute('DELETE FROM quizzes WHERE user_id = %s', (user_id,))
    db.execute('DELETE FROM study_guides WHERE user_id = %s', (user_id,))
    db.execute('DELETE FROM flashcards WHERE deck_id IN (SELECT id FROM flashcard_decks WHERE user_id = %s)', (user_id,))
    db.execute('DELETE FROM flashcard_decks WHERE user_id = %s', (user_id,))
    db.execute('DELETE FROM notes WHERE class_id IN (SELECT id FROM classes WHERE user_id = %s)', (user_id,))
    db.execute('DELETE FROM assignments WHERE class_id IN (SELECT id FROM classes WHERE user_id = %s)', (user_id,))
    db.execute('DELETE FROM calendar_events WHERE class_id IN (SELECT id FROM classes WHERE user_id = %s)', (user_id,))
    db.execute('DELETE FROM classes WHERE user_id = %s', (user_id,))
    db.execute('DELETE FROM users WHERE id = %s', (user_id,))
    db.commit()

    session.clear()
    flash('Your account has been deleted.', 'success')
    return redirect(url_for('auth.login'))


@settings.route('/export/notes')
@login_required
def export_notes():
    """Export all notes as Markdown."""
    db = get_db()
    user_id = session['user_id']

    content, filename = export_notes_markdown(db, user_id)

    return Response(
        content,
        mimetype='text/markdown',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


@settings.route('/export/flashcards')
@login_required
def export_flashcards():
    """Export all flashcards as CSV."""
    db = get_db()
    user_id = session['user_id']

    content, filename = export_flashcards_csv(db, user_id)

    return Response(
        content,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


@settings.route('/export/backup')
@login_required
def export_backup():
    """Export full backup as JSON."""
    db = get_db()
    user_id = session['user_id']

    content, filename = export_full_backup(db, user_id)

    return Response(
        content,
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )
