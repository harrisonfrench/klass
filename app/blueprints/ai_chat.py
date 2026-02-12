"""AI Chat Blueprint - AI Tutor Chat Widget API."""

import re
from flask import Blueprint, request, jsonify, session
from app.db_connect import get_db
from app.services.ai_service import chat_with_tutor
from app.blueprints.auth import login_required
from app import limiter

ai_chat = Blueprint('ai_chat', __name__)


def get_or_create_session(user_id):
    """Get the user's single chat session, creating one if it doesn't exist."""
    db = get_db()

    # Try to get existing session
    cursor = db.execute(
        'SELECT id FROM chat_sessions WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1',
        (user_id,)
    )
    existing = cursor.fetchone()

    if existing:
        return existing['id']

    # Create new session
    cursor = db.execute(
        'INSERT INTO chat_sessions (user_id, title) VALUES (?, ?)',
        (user_id, 'AI Tutor Chat')
    )
    db.commit()
    return cursor.lastrowid


@ai_chat.route('/classes')
@login_required
def get_classes():
    """Get user's classes for context selection."""
    db = get_db()
    user_id = session['user_id']

    cursor = db.execute(
        'SELECT id, name, code, color FROM classes WHERE user_id = ? ORDER BY name',
        (user_id,)
    )
    classes = [dict(row) for row in cursor.fetchall()]

    return jsonify({'success': True, 'classes': classes})


@ai_chat.route('/messages')
@login_required
def get_messages():
    """Get recent messages for the user's chat session."""
    db = get_db()
    user_id = session['user_id']

    session_id = get_or_create_session(user_id)

    # Get messages (limit to last 50 for performance)
    cursor = db.execute('''
        SELECT role, content FROM chat_messages
        WHERE session_id = ?
        ORDER BY created_at ASC
        LIMIT 50
    ''', (session_id,))
    messages = [dict(row) for row in cursor.fetchall()]

    return jsonify({'success': True, 'messages': messages})


@ai_chat.route('/message', methods=['POST'])
@limiter.limit("20 per minute")
@login_required
def send_message():
    """Send a message and get AI response."""
    db = get_db()
    user_id = session['user_id']

    data = request.get_json()
    message = data.get('message', '').strip() if data else ''
    class_id = data.get('class_id') if data else None

    if not message:
        return jsonify({'success': False, 'error': 'No message provided'}), 400

    session_id = get_or_create_session(user_id)

    # Save user message
    db.execute('''
        INSERT INTO chat_messages (session_id, role, content)
        VALUES (?, 'user', ?)
    ''', (session_id, message))
    db.commit()

    # Get conversation history (last 10 messages for context)
    cursor = db.execute('''
        SELECT role, content FROM chat_messages
        WHERE session_id = ?
        ORDER BY created_at DESC
        LIMIT 10
    ''', (session_id,))
    history = [dict(row) for row in reversed(cursor.fetchall())]

    # Get context notes and class name if class is selected
    context_notes = None
    class_name = None

    if class_id:
        # Verify class belongs to user and get name
        cursor = db.execute(
            'SELECT id, name FROM classes WHERE id = ? AND user_id = ?',
            (class_id, user_id)
        )
        class_data = cursor.fetchone()

        if class_data:
            class_name = class_data['name']

            # Get notes from this class for context
            cursor = db.execute('''
                SELECT title, content FROM notes
                WHERE class_id = ?
                ORDER BY updated_at DESC
                LIMIT 5
            ''', (class_id,))
            notes = cursor.fetchall()

            if notes:
                context_notes = []
                for note in notes:
                    note_dict = dict(note)
                    # Strip HTML from content
                    if note_dict.get('content'):
                        note_dict['content'] = re.sub(r'<[^>]+>', '', note_dict['content'])[:2000]
                    context_notes.append(note_dict)

    try:
        # Get AI response
        ai_response = chat_with_tutor(
            message=message,
            context_notes=context_notes,
            conversation_history=history[:-1],  # Exclude the message we just added
            class_name=class_name
        )

        # Save AI response
        db.execute('''
            INSERT INTO chat_messages (session_id, role, content)
            VALUES (?, 'assistant', ?)
        ''', (session_id, ai_response))

        # Update session timestamp
        db.execute(
            'UPDATE chat_sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (session_id,)
        )
        db.commit()

        return jsonify({
            'success': True,
            'response': ai_response
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@ai_chat.route('/clear', methods=['POST'])
@login_required
def clear_chat():
    """Clear all messages from the user's chat session."""
    db = get_db()
    user_id = session['user_id']

    session_id = get_or_create_session(user_id)

    # Delete all messages
    db.execute('DELETE FROM chat_messages WHERE session_id = ?', (session_id,))
    db.commit()

    return jsonify({'success': True})
