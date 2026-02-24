"""Notifications Blueprint - In-app notification system."""

from flask import Blueprint, render_template, request, jsonify, session
from app.blueprints.auth import login_required
from app.services.notification_service import (
    get_notifications,
    get_unread_count,
    mark_as_read,
    mark_all_as_read,
    delete_notification
)

notifications = Blueprint('notifications', __name__)


@notifications.route('/')
@login_required
def list_notifications():
    """List all notifications for the user."""
    user_id = session['user_id']
    all_notifications = get_notifications(user_id, limit=50)
    unread_count = get_unread_count(user_id)

    return render_template('notifications/index.html',
                           notifications=all_notifications,
                           unread_count=unread_count)


@notifications.route('/unread-count')
@login_required
def api_unread_count():
    """Get unread notification count (for badge)."""
    user_id = session['user_id']
    count = get_unread_count(user_id)
    return jsonify({'count': count})


@notifications.route('/recent')
@login_required
def api_recent():
    """Get recent notifications for dropdown."""
    user_id = session['user_id']
    recent = get_notifications(user_id, limit=10)
    unread_count = get_unread_count(user_id)

    # Convert to JSON-serializable format
    notifications_list = []
    for n in recent:
        notifications_list.append({
            'id': n['id'],
            'type': n['type'],
            'title': n['title'],
            'message': n['message'],
            'link': n['link'],
            'is_read': n['is_read'],
            'from_username': n.get('from_username'),
            'created_at': n['created_at'].isoformat() if n['created_at'] else None
        })

    return jsonify({
        'notifications': notifications_list,
        'unread_count': unread_count
    })


@notifications.route('/mark-read/<int:notification_id>', methods=['POST'])
@login_required
def api_mark_read(notification_id):
    """Mark a notification as read."""
    user_id = session['user_id']
    mark_as_read(notification_id, user_id)
    return jsonify({'success': True})


@notifications.route('/mark-all-read', methods=['POST'])
@login_required
def api_mark_all_read():
    """Mark all notifications as read."""
    user_id = session['user_id']
    mark_all_as_read(user_id)
    return jsonify({'success': True})


@notifications.route('/delete/<int:notification_id>', methods=['POST'])
@login_required
def api_delete(notification_id):
    """Delete a notification."""
    user_id = session['user_id']
    delete_notification(notification_id, user_id)
    return jsonify({'success': True})
