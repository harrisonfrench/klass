import re
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from app.db_connect import get_db
from app.services.ai_service import summarize_text, expand_text, cleanup_text, transform_text, generate_flashcards, chat_with_tutor
from app.blueprints.auth import login_required

notes = Blueprint('notes', __name__)


@notes.route('/')
@login_required
def list_notes():
    """List all notes across all classes for the current user."""
    db = get_db()

    # Get all notes with class info, pinned first, then by updated_at
    cursor = db.execute('''
        SELECT n.*, c.name as class_name, c.code as class_code, c.color as class_color
        FROM notes n
        JOIN classes c ON n.class_id = c.id
        WHERE c.user_id = ?
        ORDER BY n.is_pinned DESC, n.updated_at DESC
    ''', (session['user_id'],))
    all_notes = cursor.fetchall()

    # Get all classes for the "new note" dropdown
    cursor = db.execute(
        'SELECT * FROM classes WHERE user_id = ? ORDER BY name ASC',
        (session['user_id'],)
    )
    classes = cursor.fetchall()

    return render_template('notes/list.html', notes=all_notes, classes=classes)


@notes.route('/<int:note_id>')
@login_required
def view_note(note_id):
    """View/edit a note in the Notion-style editor."""
    db = get_db()

    cursor = db.execute('''
        SELECT n.*, c.name as class_name, c.code as class_code, c.color as class_color, c.id as class_id
        FROM notes n
        JOIN classes c ON n.class_id = c.id
        WHERE n.id = ? AND c.user_id = ?
    ''', (note_id, session['user_id']))
    note = cursor.fetchone()

    if not note:
        flash('Note not found.', 'error')
        return redirect(url_for('notes.list_notes'))

    return render_template('notes/editor.html', note=note)


@notes.route('/<int:note_id>/update', methods=['POST'])
@login_required
def update_note(note_id):
    """Update note title, content, and/or class (supports AJAX)."""
    db = get_db()

    # Check if note exists and belongs to user
    cursor = db.execute('''
        SELECT n.* FROM notes n
        JOIN classes c ON n.class_id = c.id
        WHERE n.id = ? AND c.user_id = ?
    ''', (note_id, session['user_id']))
    note = cursor.fetchone()

    if not note:
        if request.is_json:
            return jsonify({'success': False, 'error': 'Note not found'}), 404
        flash('Note not found.', 'error')
        return redirect(url_for('notes.list_notes'))

    # Get data from JSON or form
    if request.is_json:
        data = request.get_json()
        title = data.get('title', note['title'])
        content = data.get('content', note['content'])
        new_class_id = data.get('class_id')
    else:
        title = request.form.get('title', note['title'])
        content = request.form.get('content', note['content'])
        new_class_id = request.form.get('class_id')

    # If changing class, verify new class belongs to user
    if new_class_id and int(new_class_id) != note['class_id']:
        cursor = db.execute(
            'SELECT id FROM classes WHERE id = ? AND user_id = ?',
            (new_class_id, session['user_id'])
        )
        if not cursor.fetchone():
            if request.is_json:
                return jsonify({'success': False, 'error': 'Invalid class'}), 400
            flash('Invalid class.', 'error')
            return redirect(url_for('notes.view_note', note_id=note_id))

        # Update note with new class
        db.execute('''
            UPDATE notes
            SET title = ?, content = ?, class_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (title, content, new_class_id, note_id))
    else:
        # Update note without changing class
        db.execute('''
            UPDATE notes
            SET title = ?, content = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (title, content, note_id))

    db.commit()

    if request.is_json:
        return jsonify({'success': True, 'message': 'Note saved'})

    flash('Note saved.', 'success')
    return redirect(url_for('notes.view_note', note_id=note_id))


@notes.route('/<int:note_id>/delete', methods=['POST'])
@login_required
def delete_note(note_id):
    """Delete a note."""
    db = get_db()

    cursor = db.execute('''
        SELECT n.*, c.id as class_id
        FROM notes n
        JOIN classes c ON n.class_id = c.id
        WHERE n.id = ? AND c.user_id = ?
    ''', (note_id, session['user_id']))
    note = cursor.fetchone()

    if not note:
        flash('Note not found.', 'error')
        return redirect(url_for('notes.list_notes'))

    class_id = note['class_id']

    db.execute('DELETE FROM notes WHERE id = ?', (note_id,))
    db.commit()

    flash('Note deleted.', 'success')

    # Redirect to class detail if came from there, otherwise to notes list
    referrer = request.referrer
    if referrer and f'/classes/{class_id}' in referrer:
        return redirect(url_for('classes.view_class', class_id=class_id))

    return redirect(url_for('notes.list_notes'))


@notes.route('/<int:note_id>/pin', methods=['POST'])
@login_required
def toggle_pin(note_id):
    """Toggle note pinned status."""
    db = get_db()

    cursor = db.execute('''
        SELECT n.* FROM notes n
        JOIN classes c ON n.class_id = c.id
        WHERE n.id = ? AND c.user_id = ?
    ''', (note_id, session['user_id']))
    note = cursor.fetchone()

    if not note:
        if request.is_json:
            return jsonify({'success': False, 'error': 'Note not found'}), 404
        flash('Note not found.', 'error')
        return redirect(url_for('notes.list_notes'))

    new_status = 0 if note['is_pinned'] else 1

    db.execute('UPDATE notes SET is_pinned = ? WHERE id = ?', (new_status, note_id))
    db.commit()

    if request.is_json:
        return jsonify({'success': True, 'is_pinned': new_status})

    flash('Note ' + ('pinned' if new_status else 'unpinned') + '.', 'success')
    return redirect(request.referrer or url_for('notes.list_notes'))


@notes.route('/create/<int:class_id>', methods=['POST'])
@login_required
def create_note(class_id):
    """Create a new note in a class."""
    db = get_db()

    # Check if class exists and belongs to user
    cursor = db.execute(
        'SELECT * FROM classes WHERE id = ? AND user_id = ?',
        (class_id, session['user_id'])
    )
    class_data = cursor.fetchone()

    if not class_data:
        flash('Class not found.', 'error')
        return redirect(url_for('classes.list_classes'))

    # Create new note with default title
    cursor = db.execute('''
        INSERT INTO notes (class_id, title, content)
        VALUES (?, 'Untitled', '')
    ''', (class_id,))
    db.commit()

    note_id = cursor.lastrowid

    # Redirect to editor
    return redirect(url_for('notes.view_note', note_id=note_id))


@notes.route('/<int:note_id>/summarize', methods=['POST'])
@login_required
def summarize_note(note_id):
    """Summarize note content using AI."""
    db = get_db()

    cursor = db.execute('''
        SELECT n.* FROM notes n
        JOIN classes c ON n.class_id = c.id
        WHERE n.id = ? AND c.user_id = ?
    ''', (note_id, session['user_id']))
    note = cursor.fetchone()

    if not note:
        return jsonify({'success': False, 'error': 'Note not found'}), 404

    content = note['content']

    # Strip HTML tags for AI processing
    if content:
        clean_content = re.sub(r'<[^>]+>', '', content)
        clean_content = clean_content.strip()
    else:
        clean_content = ''

    if not clean_content:
        return jsonify({'success': False, 'error': 'Note is empty. Add some content first.'}), 400

    try:
        summary = summarize_text(clean_content)
        return jsonify({'success': True, 'summary': summary})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': f'AI service error: {str(e)}'}), 500


@notes.route('/<int:note_id>/expand', methods=['POST'])
@login_required
def expand_note(note_id):
    """Expand selected text using AI."""
    db = get_db()

    cursor = db.execute('''
        SELECT n.* FROM notes n
        JOIN classes c ON n.class_id = c.id
        WHERE n.id = ? AND c.user_id = ?
    ''', (note_id, session['user_id']))
    note = cursor.fetchone()

    if not note:
        return jsonify({'success': False, 'error': 'Note not found'}), 404

    data = request.get_json()
    selected_text = data.get('text', '').strip()

    if not selected_text:
        return jsonify({'success': False, 'error': 'No text selected to expand'}), 400

    # Get context from the note
    context = re.sub(r'<[^>]+>', '', note['content'] or '')

    try:
        expanded = expand_text(selected_text, context[:1000])  # Limit context
        return jsonify({'success': True, 'expanded': expanded})
    except Exception as e:
        return jsonify({'success': False, 'error': f'AI service error: {str(e)}'}), 500


@notes.route('/<int:note_id>/cleanup', methods=['POST'])
@login_required
def cleanup_note(note_id):
    """Clean up note grammar and formatting using AI."""
    db = get_db()

    cursor = db.execute('''
        SELECT n.* FROM notes n
        JOIN classes c ON n.class_id = c.id
        WHERE n.id = ? AND c.user_id = ?
    ''', (note_id, session['user_id']))
    note = cursor.fetchone()

    if not note:
        return jsonify({'success': False, 'error': 'Note not found'}), 404

    content = note['content']
    if content:
        clean_content = re.sub(r'<[^>]+>', '', content).strip()
    else:
        clean_content = ''

    if not clean_content:
        return jsonify({'success': False, 'error': 'Note is empty'}), 400

    try:
        cleaned = cleanup_text(clean_content)
        return jsonify({'success': True, 'cleaned': cleaned})
    except Exception as e:
        return jsonify({'success': False, 'error': f'AI service error: {str(e)}'}), 500


@notes.route('/<int:note_id>/ai-transform', methods=['POST'])
@login_required
def ai_transform(note_id):
    """Transform selected text using AI (improve, proofread, simplify, etc.)."""
    db = get_db()

    cursor = db.execute('''
        SELECT n.* FROM notes n
        JOIN classes c ON n.class_id = c.id
        WHERE n.id = ? AND c.user_id = ?
    ''', (note_id, session['user_id']))
    note = cursor.fetchone()

    if not note:
        return jsonify({'success': False, 'error': 'Note not found'}), 404

    data = request.get_json()
    text = data.get('text', '').strip()
    action = data.get('action', '')

    if not text:
        return jsonify({'success': False, 'error': 'No text provided'}), 400

    if not action:
        return jsonify({'success': False, 'error': 'No action specified'}), 400

    try:
        result = transform_text(text, action)
        return jsonify({'success': True, 'result': result})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': f'AI service error: {str(e)}'}), 500


@notes.route('/<int:note_id>/generate-flashcards', methods=['POST'])
@login_required
def generate_flashcards_from_note(note_id):
    """Generate flashcards from note content using AI."""
    db = get_db()

    cursor = db.execute('''
        SELECT n.*, c.id as class_id
        FROM notes n
        JOIN classes c ON n.class_id = c.id
        WHERE n.id = ? AND c.user_id = ?
    ''', (note_id, session['user_id']))
    note = cursor.fetchone()

    if not note:
        return jsonify({'success': False, 'error': 'Note not found'}), 404

    content = note['content']
    if content:
        clean_content = re.sub(r'<[^>]+>', '', content).strip()
    else:
        clean_content = ''

    if not clean_content:
        return jsonify({'success': False, 'error': 'Note is empty'}), 400

    data = request.get_json() or {}
    num_cards = data.get('num_cards', 10)

    try:
        cards = generate_flashcards(clean_content, num_cards)
        return jsonify({
            'success': True,
            'cards': cards,
            'class_id': note['class_id'],
            'note_title': note['title']
        })
    except Exception as e:
        return jsonify({'success': False, 'error': f'AI service error: {str(e)}'}), 500


@notes.route('/<int:note_id>/ask-ai', methods=['POST'])
@login_required
def ask_ai_about_note(note_id):
    """Ask AI a question about the current note."""
    db = get_db()

    # Get the note and verify ownership
    cursor = db.execute('''
        SELECT n.*, c.name as class_name
        FROM notes n
        JOIN classes c ON n.class_id = c.id
        WHERE n.id = ? AND c.user_id = ?
    ''', (note_id, session['user_id']))
    note = cursor.fetchone()

    if not note:
        return jsonify({'success': False, 'error': 'Note not found'}), 404

    data = request.get_json()
    if not data or not data.get('message'):
        return jsonify({'success': False, 'error': 'No message provided'}), 400

    message = data.get('message', '').strip()
    conversation_history = data.get('history', [])

    # Clean note content for context
    content = note['content'] or ''
    if content:
        clean_content = re.sub(r'<[^>]+>', '', content).strip()
    else:
        clean_content = ''

    # Prepare note context
    context_notes = [{
        'title': note['title'] or 'Untitled Note',
        'content': clean_content[:3000]
    }] if clean_content else None

    try:
        response = chat_with_tutor(
            message=message,
            context_notes=context_notes,
            conversation_history=conversation_history,
            class_name=note['class_name']
        )
        return jsonify({
            'success': True,
            'response': response
        })
    except Exception as e:
        return jsonify({'success': False, 'error': f'AI service error: {str(e)}'}), 500
