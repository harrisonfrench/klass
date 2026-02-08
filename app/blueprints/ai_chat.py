"""AI Chat Blueprint - AI Tutor Chat Interface."""

import re
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from app.db_connect import get_db
from app.services.ai_service import chat_with_tutor
from app.blueprints.auth import login_required

ai_chat = Blueprint('ai_chat', __name__)


@ai_chat.route('/')
@login_required
def chat_home():
    """Main chat interface."""
    db = get_db()
    user_id = session['user_id']

    # Get user's classes for context selection
    cursor = db.execute(
        'SELECT id, name, code, color FROM classes WHERE user_id = ? ORDER BY name',
        (user_id,)
    )
    classes = cursor.fetchall()

    # Get recent chat sessions
    cursor = db.execute('''
        SELECT cs.*, c.name as class_name, c.color as class_color
        FROM chat_sessions cs
        LEFT JOIN classes c ON cs.class_id = c.id
        WHERE cs.user_id = ?
        ORDER BY cs.updated_at DESC
        LIMIT 10
    ''', (user_id,))
    sessions = cursor.fetchall()

    return render_template('ai_chat/chat.html', classes=classes, sessions=sessions)


@ai_chat.route('/session/<int:session_id>')
@login_required
def view_session(session_id):
    """View a specific chat session."""
    db = get_db()
    user_id = session['user_id']

    # Get session (verify ownership)
    cursor = db.execute('''
        SELECT cs.*, c.name as class_name, c.color as class_color
        FROM chat_sessions cs
        LEFT JOIN classes c ON cs.class_id = c.id
        WHERE cs.id = ? AND cs.user_id = ?
    ''', (session_id, user_id))
    chat_session = cursor.fetchone()

    if not chat_session:
        flash('Chat session not found.', 'error')
        return redirect(url_for('ai_chat.chat_home'))

    # Get messages
    cursor = db.execute('''
        SELECT * FROM chat_messages
        WHERE session_id = ?
        ORDER BY created_at ASC
    ''', (session_id,))
    messages = cursor.fetchall()

    # Get user's classes
    cursor = db.execute(
        'SELECT id, name, code, color FROM classes WHERE user_id = ? ORDER BY name',
        (user_id,)
    )
    classes = cursor.fetchall()

    # Get recent sessions
    cursor = db.execute('''
        SELECT cs.*, c.name as class_name, c.color as class_color
        FROM chat_sessions cs
        LEFT JOIN classes c ON cs.class_id = c.id
        WHERE cs.user_id = ?
        ORDER BY cs.updated_at DESC
        LIMIT 10
    ''', (user_id,))
    sessions = cursor.fetchall()

    return render_template(
        'ai_chat/chat.html',
        classes=classes,
        sessions=sessions,
        current_session=chat_session,
        messages=messages
    )


@ai_chat.route('/session/new', methods=['POST'])
@login_required
def new_session():
    """Create a new chat session."""
    db = get_db()
    user_id = session['user_id']

    data = request.get_json() if request.is_json else request.form
    class_id = data.get('class_id')
    title = data.get('title', 'New Chat')

    # Validate class if provided
    if class_id:
        cursor = db.execute(
            'SELECT id FROM classes WHERE id = ? AND user_id = ?',
            (class_id, user_id)
        )
        if not cursor.fetchone():
            class_id = None

    cursor = db.execute('''
        INSERT INTO chat_sessions (user_id, class_id, title)
        VALUES (?, ?, ?)
    ''', (user_id, class_id, title))
    db.commit()

    session_id = cursor.lastrowid

    if request.is_json:
        return jsonify({'success': True, 'session_id': session_id})

    return redirect(url_for('ai_chat.view_session', session_id=session_id))


@ai_chat.route('/session/<int:session_id>/message', methods=['POST'])
@login_required
def send_message(session_id):
    """Send a message and get AI response."""
    db = get_db()
    user_id = session['user_id']

    # Verify session ownership
    cursor = db.execute('''
        SELECT cs.*, c.name as class_name
        FROM chat_sessions cs
        LEFT JOIN classes c ON cs.class_id = c.id
        WHERE cs.id = ? AND cs.user_id = ?
    ''', (session_id, user_id))
    chat_session = cursor.fetchone()

    if not chat_session:
        return jsonify({'success': False, 'error': 'Session not found'}), 404

    data = request.get_json()
    message = data.get('message', '').strip()

    if not message:
        return jsonify({'success': False, 'error': 'No message provided'}), 400

    # Save user message
    db.execute('''
        INSERT INTO chat_messages (session_id, role, content)
        VALUES (?, 'user', ?)
    ''', (session_id, message))
    db.commit()

    # Get conversation history
    cursor = db.execute('''
        SELECT role, content FROM chat_messages
        WHERE session_id = ?
        ORDER BY created_at ASC
    ''', (session_id,))
    history = [dict(row) for row in cursor.fetchall()]

    # Get context notes if class is selected
    context_notes = []
    if chat_session.get('class_id'):
        cursor = db.execute('''
            SELECT title, content FROM notes
            WHERE class_id = ?
            ORDER BY updated_at DESC
            LIMIT 5
        ''', (chat_session['class_id'],))
        context_notes = cursor.fetchall()

        # Clean HTML from notes content
        for note in context_notes:
            if note.get('content'):
                note['content'] = re.sub(r'<[^>]+>', '', note['content'])

    try:
        # Get AI response
        ai_response = chat_with_tutor(
            message=message,
            context_notes=[dict(n) for n in context_notes] if context_notes else None,
            conversation_history=history[:-1],  # Exclude the message we just added
            class_name=chat_session.get('class_name')
        )

        # Save AI response
        db.execute('''
            INSERT INTO chat_messages (session_id, role, content)
            VALUES (?, 'assistant', ?)
        ''', (session_id, ai_response))

        # Update session timestamp and title if it's the first message
        cursor = db.execute(
            'SELECT COUNT(*) as count FROM chat_messages WHERE session_id = ?',
            (session_id,)
        )
        if cursor.fetchone()['count'] <= 2:
            # Update title based on first message
            title = message[:50] + ('...' if len(message) > 50 else '')
            db.execute(
                'UPDATE chat_sessions SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (title, session_id)
            )
        else:
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


@ai_chat.route('/session/<int:session_id>/delete', methods=['POST'])
@login_required
def delete_session(session_id):
    """Delete a chat session."""
    db = get_db()
    user_id = session['user_id']

    # Verify ownership
    cursor = db.execute(
        'SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?',
        (session_id, user_id)
    )
    if not cursor.fetchone():
        if request.is_json:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        flash('Session not found.', 'error')
        return redirect(url_for('ai_chat.chat_home'))

    db.execute('DELETE FROM chat_messages WHERE session_id = ?', (session_id,))
    db.execute('DELETE FROM chat_sessions WHERE id = ?', (session_id,))
    db.commit()

    if request.is_json:
        return jsonify({'success': True})

    flash('Chat deleted.', 'success')
    return redirect(url_for('ai_chat.chat_home'))


@ai_chat.route('/session/<int:session_id>/clear', methods=['POST'])
@login_required
def clear_session(session_id):
    """Clear messages from a chat session."""
    db = get_db()
    user_id = session['user_id']

    # Verify ownership
    cursor = db.execute(
        'SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?',
        (session_id, user_id)
    )
    if not cursor.fetchone():
        return jsonify({'success': False, 'error': 'Session not found'}), 404

    db.execute('DELETE FROM chat_messages WHERE session_id = ?', (session_id,))
    db.execute(
        'UPDATE chat_sessions SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
        ('New Chat', session_id)
    )
    db.commit()

    return jsonify({'success': True})
