"""Friends Blueprint - Friend system for sharing and collaboration."""

import secrets
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from app.db_connect import get_db
from app.blueprints.auth import login_required
from app.services.notification_service import notify_friend_request, notify_friend_accepted

friends = Blueprint('friends', __name__)


@friends.route('/')
@login_required
def index():
    """List friends and pending requests."""
    db = get_db()
    user_id = session['user_id']

    # Get accepted friends (where I sent request or they sent request)
    cursor = db.execute('''
        SELECT u.id, u.username, u.email, f.created_at as friends_since,
               us.profile_picture
        FROM friendships f
        JOIN users u ON (
            CASE
                WHEN f.user_id = %s THEN f.friend_id = u.id
                ELSE f.user_id = u.id
            END
        )
        LEFT JOIN user_settings us ON u.id = us.user_id
        WHERE (f.user_id = %s OR f.friend_id = %s)
        AND f.status = 'accepted'
        ORDER BY u.username
    ''', (user_id, user_id, user_id))
    friends_list = cursor.fetchall()

    # Get pending requests received
    cursor = db.execute('''
        SELECT f.id as friendship_id, u.id as user_id, u.username, u.email,
               f.created_at, us.profile_picture
        FROM friendships f
        JOIN users u ON f.user_id = u.id
        LEFT JOIN user_settings us ON u.id = us.user_id
        WHERE f.friend_id = %s AND f.status = 'pending'
        ORDER BY f.created_at DESC
    ''', (user_id,))
    pending_requests = cursor.fetchall()

    # Get pending requests sent
    cursor = db.execute('''
        SELECT f.id as friendship_id, u.id as user_id, u.username, u.email,
               f.created_at, us.profile_picture
        FROM friendships f
        JOIN users u ON f.friend_id = u.id
        LEFT JOIN user_settings us ON u.id = us.user_id
        WHERE f.user_id = %s AND f.status = 'pending'
        ORDER BY f.created_at DESC
    ''', (user_id,))
    sent_requests = cursor.fetchall()

    return render_template('friends/index.html',
                           friends=friends_list,
                           pending_requests=pending_requests,
                           sent_requests=sent_requests)


@friends.route('/search')
@login_required
def search():
    """Search for users by username."""
    db = get_db()
    user_id = session['user_id']
    query = request.args.get('q', '').strip()

    if not query or len(query) < 2:
        return jsonify({'users': []})

    # Search users, excluding self
    cursor = db.execute('''
        SELECT u.id, u.username, us.profile_picture,
               (SELECT status FROM friendships
                WHERE (user_id = %s AND friend_id = u.id)
                   OR (user_id = u.id AND friend_id = %s)
                LIMIT 1) as friendship_status
        FROM users u
        LEFT JOIN user_settings us ON u.id = us.user_id
        WHERE u.id != %s
        AND u.username LIKE %s
        LIMIT 10
    ''', (user_id, user_id, user_id, f'%{query}%'))
    users = cursor.fetchall()

    users_list = []
    for u in users:
        users_list.append({
            'id': u['id'],
            'username': u['username'],
            'profile_picture': u['profile_picture'],
            'friendship_status': u['friendship_status']
        })

    return jsonify({'users': users_list})


@friends.route('/request/<int:friend_id>', methods=['POST'])
@login_required
def send_request(friend_id):
    """Send a friend request."""
    db = get_db()
    user_id = session['user_id']

    if friend_id == user_id:
        return jsonify({'success': False, 'error': 'Cannot add yourself'}), 400

    # Check if user exists
    cursor = db.execute('SELECT username FROM users WHERE id = %s', (friend_id,))
    friend = cursor.fetchone()
    if not friend:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    # Check if friendship already exists
    cursor = db.execute('''
        SELECT id, status FROM friendships
        WHERE (user_id = %s AND friend_id = %s)
           OR (user_id = %s AND friend_id = %s)
    ''', (user_id, friend_id, friend_id, user_id))
    existing = cursor.fetchone()

    if existing:
        if existing['status'] == 'accepted':
            return jsonify({'success': False, 'error': 'Already friends'}), 400
        elif existing['status'] == 'pending':
            return jsonify({'success': False, 'error': 'Request already pending'}), 400
        elif existing['status'] == 'blocked':
            return jsonify({'success': False, 'error': 'Unable to send request'}), 400

    # Create friend request
    db.execute('''
        INSERT INTO friendships (user_id, friend_id, status)
        VALUES (%s, %s, 'pending')
    ''', (user_id, friend_id))
    db.commit()

    # Get sender's username for notification
    cursor = db.execute('SELECT username FROM users WHERE id = %s', (user_id,))
    sender = cursor.fetchone()

    # Notify the recipient
    notify_friend_request(friend_id, user_id, sender['username'])

    return jsonify({'success': True, 'message': 'Friend request sent'})


@friends.route('/accept/<int:friendship_id>', methods=['POST'])
@login_required
def accept_request(friendship_id):
    """Accept a friend request."""
    db = get_db()
    user_id = session['user_id']

    # Verify this request is for the current user
    cursor = db.execute('''
        SELECT f.*, u.username as requester_username
        FROM friendships f
        JOIN users u ON f.user_id = u.id
        WHERE f.id = %s AND f.friend_id = %s AND f.status = 'pending'
    ''', (friendship_id, user_id))
    friendship = cursor.fetchone()

    if not friendship:
        return jsonify({'success': False, 'error': 'Request not found'}), 404

    # Accept the request
    db.execute('''
        UPDATE friendships
        SET status = 'accepted', accepted_at = CURRENT_TIMESTAMP
        WHERE id = %s
    ''', (friendship_id,))
    db.commit()

    # Get accepter's username for notification
    cursor = db.execute('SELECT username FROM users WHERE id = %s', (user_id,))
    accepter = cursor.fetchone()

    # Notify the requester
    notify_friend_accepted(friendship['user_id'], user_id, accepter['username'])

    return jsonify({'success': True, 'message': 'Friend request accepted'})


@friends.route('/decline/<int:friendship_id>', methods=['POST'])
@login_required
def decline_request(friendship_id):
    """Decline a friend request."""
    db = get_db()
    user_id = session['user_id']

    # Verify this request is for the current user
    db.execute('''
        DELETE FROM friendships
        WHERE id = %s AND friend_id = %s AND status = 'pending'
    ''', (friendship_id, user_id))
    db.commit()

    return jsonify({'success': True, 'message': 'Friend request declined'})


@friends.route('/remove/<int:friend_id>', methods=['POST'])
@login_required
def remove_friend(friend_id):
    """Remove a friend."""
    db = get_db()
    user_id = session['user_id']

    # Delete friendship (either direction)
    db.execute('''
        DELETE FROM friendships
        WHERE (user_id = %s AND friend_id = %s)
           OR (user_id = %s AND friend_id = %s)
    ''', (user_id, friend_id, friend_id, user_id))
    db.commit()

    return jsonify({'success': True, 'message': 'Friend removed'})


@friends.route('/invite/create', methods=['POST'])
@login_required
def create_invite():
    """Generate an invite link."""
    db = get_db()
    user_id = session['user_id']

    # Generate unique code
    invite_code = secrets.token_urlsafe(16)

    # Create invite (expires in 7 days by default)
    db.execute('''
        INSERT INTO friend_invites (user_id, invite_code, uses_remaining)
        VALUES (%s, %s, 5)
    ''', (user_id, invite_code))
    db.commit()

    invite_url = url_for('friends.accept_invite', code=invite_code, _external=True)

    return jsonify({
        'success': True,
        'invite_code': invite_code,
        'invite_url': invite_url
    })


@friends.route('/invite/<code>')
@login_required
def accept_invite(code):
    """Accept an invite link and become friends."""
    db = get_db()
    user_id = session['user_id']

    # Find the invite
    cursor = db.execute('''
        SELECT fi.*, u.username as inviter_username
        FROM friend_invites fi
        JOIN users u ON fi.user_id = u.id
        WHERE fi.invite_code = %s
        AND fi.uses_remaining > 0
        AND (fi.expires_at IS NULL OR fi.expires_at > CURRENT_TIMESTAMP)
    ''', (code,))
    invite = cursor.fetchone()

    if not invite:
        flash('Invalid or expired invite link', 'danger')
        return redirect(url_for('friends.index'))

    if invite['user_id'] == user_id:
        flash('Cannot use your own invite link', 'warning')
        return redirect(url_for('friends.index'))

    # Check if already friends
    cursor = db.execute('''
        SELECT id FROM friendships
        WHERE (user_id = %s AND friend_id = %s)
           OR (user_id = %s AND friend_id = %s)
    ''', (user_id, invite['user_id'], invite['user_id'], user_id))

    if cursor.fetchone():
        flash(f'You are already friends with {invite["inviter_username"]}', 'info')
        return redirect(url_for('friends.index'))

    # Create accepted friendship directly
    db.execute('''
        INSERT INTO friendships (user_id, friend_id, status, accepted_at)
        VALUES (%s, %s, 'accepted', CURRENT_TIMESTAMP)
    ''', (invite['user_id'], user_id))

    # Decrement uses
    db.execute('''
        UPDATE friend_invites SET uses_remaining = uses_remaining - 1
        WHERE id = %s
    ''', (invite['id'],))
    db.commit()

    # Get current user's username for notification
    cursor = db.execute('SELECT username FROM users WHERE id = %s', (user_id,))
    current_user = cursor.fetchone()

    # Notify the inviter
    notify_friend_accepted(invite['user_id'], user_id, current_user['username'])

    flash(f'You are now friends with {invite["inviter_username"]}!', 'success')
    return redirect(url_for('friends.index'))


def get_friends_list(user_id):
    """Helper function to get list of friend user IDs."""
    db = get_db()
    cursor = db.execute('''
        SELECT
            CASE
                WHEN user_id = %s THEN friend_id
                ELSE user_id
            END as friend_id
        FROM friendships
        WHERE (user_id = %s OR friend_id = %s)
        AND status = 'accepted'
    ''', (user_id, user_id, user_id))
    return [row['friend_id'] for row in cursor.fetchall()]


def are_friends(user_id, other_user_id):
    """Check if two users are friends."""
    db = get_db()
    cursor = db.execute('''
        SELECT id FROM friendships
        WHERE ((user_id = %s AND friend_id = %s)
            OR (user_id = %s AND friend_id = %s))
        AND status = 'accepted'
    ''', (user_id, other_user_id, other_user_id, user_id))
    return cursor.fetchone() is not None
