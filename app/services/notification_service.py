"""
Service for creating and managing user notifications.
"""
from app.db_connect import get_db


def create_notification(user_id, notification_type, title, message=None, link=None, from_user_id=None):
    """
    Create a notification for a user.

    Args:
        user_id: The user to notify
        notification_type: Type of notification (friend_request, friend_accepted, resource_shared, etc.)
        title: Short title for the notification
        message: Optional longer message
        link: Optional link to navigate to
        from_user_id: Optional user who triggered the notification
    """
    db = get_db()
    db.execute('''
        INSERT INTO notifications (user_id, type, title, message, link, from_user_id)
        VALUES (%s, %s, %s, %s, %s, %s)
    ''', (user_id, notification_type, title, message, link, from_user_id))
    db.commit()


def get_notifications(user_id, limit=20, unread_only=False):
    """Get notifications for a user."""
    db = get_db()
    query = '''
        SELECT n.*, u.username as from_username
        FROM notifications n
        LEFT JOIN users u ON n.from_user_id = u.id
        WHERE n.user_id = %s
    '''
    if unread_only:
        query += ' AND n.is_read = 0'
    query += ' ORDER BY n.created_at DESC LIMIT %s'

    cursor = db.execute(query, (user_id, limit))
    return cursor.fetchall()


def get_unread_count(user_id):
    """Get count of unread notifications."""
    db = get_db()
    cursor = db.execute(
        'SELECT COUNT(*) as count FROM notifications WHERE user_id = %s AND is_read = 0',
        (user_id,)
    )
    result = cursor.fetchone()
    return result['count'] if result else 0


def mark_as_read(notification_id, user_id):
    """Mark a single notification as read."""
    db = get_db()
    db.execute(
        'UPDATE notifications SET is_read = 1 WHERE id = %s AND user_id = %s',
        (notification_id, user_id)
    )
    db.commit()


def mark_all_as_read(user_id):
    """Mark all notifications as read for a user."""
    db = get_db()
    db.execute(
        'UPDATE notifications SET is_read = 1 WHERE user_id = %s AND is_read = 0',
        (user_id,)
    )
    db.commit()


def delete_notification(notification_id, user_id):
    """Delete a notification."""
    db = get_db()
    db.execute(
        'DELETE FROM notifications WHERE id = %s AND user_id = %s',
        (notification_id, user_id)
    )
    db.commit()


# Notification type helpers
def notify_friend_request(to_user_id, from_user_id, from_username):
    """Notify user of a friend request."""
    create_notification(
        user_id=to_user_id,
        notification_type='friend_request',
        title=f'{from_username} wants to be your friend',
        link='/friends',
        from_user_id=from_user_id
    )


def notify_friend_accepted(to_user_id, from_user_id, from_username):
    """Notify user their friend request was accepted."""
    create_notification(
        user_id=to_user_id,
        notification_type='friend_accepted',
        title=f'{from_username} accepted your friend request',
        link='/friends',
        from_user_id=from_user_id
    )


def notify_resource_shared(to_user_id, from_user_id, from_username, resource_type, resource_title, resource_link):
    """Notify user that a resource was shared with them."""
    create_notification(
        user_id=to_user_id,
        notification_type='resource_shared',
        title=f'{from_username} shared "{resource_title}" with you',
        message=f'You now have access to this {resource_type.replace("_", " ")}',
        link=resource_link,
        from_user_id=from_user_id
    )
