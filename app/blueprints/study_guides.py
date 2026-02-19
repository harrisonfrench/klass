"""Study Guides Blueprint - AI-generated study guides from notes."""

import re
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from app.db_connect import get_db
from app.services.ai_service import generate_study_guide
from app.blueprints.auth import login_required

study_guides = Blueprint('study_guides', __name__)


@study_guides.route('/')
@login_required
def list_guides():
    """List all study guides for the current user."""
    db = get_db()

    cursor = db.execute('''
        SELECT sg.*, c.name as class_name, c.code as class_code, c.color as class_color
        FROM study_guides sg
        JOIN classes c ON sg.class_id = c.id
        WHERE c.user_id = %s
        ORDER BY sg.created_at DESC
    ''', (session['user_id'],))
    guides = cursor.fetchall()

    # Get classes for creating new guides
    cursor = db.execute(
        'SELECT * FROM classes WHERE user_id = %s ORDER BY name ASC',
        (session['user_id'],)
    )
    classes = cursor.fetchall()

    return render_template('study_guides/list.html', guides=guides, classes=classes)


@study_guides.route('/<int:guide_id>')
@login_required
def view_guide(guide_id):
    """View a study guide."""
    db = get_db()

    cursor = db.execute('''
        SELECT sg.*, c.name as class_name, c.code as class_code, c.color as class_color
        FROM study_guides sg
        JOIN classes c ON sg.class_id = c.id
        WHERE sg.id = %s AND c.user_id = %s
    ''', (guide_id, session['user_id']))
    guide = cursor.fetchone()

    if not guide:
        flash('Study guide not found.', 'error')
        return redirect(url_for('study_guides.list_guides'))

    # Parse source notes if available
    source_note_ids = []
    if guide.get('source_notes'):
        try:
            source_note_ids = json.loads(guide['source_notes'])
        except json.JSONDecodeError:
            pass

    # Get source note titles
    source_notes = []
    if source_note_ids:
        placeholders = ','.join(['%s' for _ in source_note_ids])
        cursor = db.execute(f'''
            SELECT id, title FROM notes WHERE id IN ({placeholders})
        ''', source_note_ids)
        source_notes = cursor.fetchall()

    return render_template('study_guides/view.html', guide=guide, source_notes=source_notes)


@study_guides.route('/generate/<int:class_id>', methods=['GET', 'POST'])
@login_required
def generate_guide(class_id):
    """Generate a new study guide for a class."""
    db = get_db()

    # Get class info (verify belongs to user)
    cursor = db.execute(
        'SELECT * FROM classes WHERE id = %s AND user_id = %s',
        (class_id, session['user_id'])
    )
    class_data = cursor.fetchone()

    if not class_data:
        flash('Class not found.', 'error')
        return redirect(url_for('study_guides.list_guides'))

    # Get notes for this class
    cursor = db.execute('''
        SELECT * FROM notes WHERE class_id = %s ORDER BY updated_at DESC
    ''', (class_id,))
    notes = cursor.fetchall()

    if request.method == 'POST':
        title = request.form.get('title', f"Study Guide - {class_data['name']}")
        selected_notes = request.form.getlist('notes')
        focus_areas = request.form.get('focus_areas', '').strip()

        if not selected_notes:
            flash('Please select at least one note.', 'error')
            return redirect(url_for('study_guides.generate_guide', class_id=class_id))

        # Combine selected notes content
        placeholders = ','.join(['%s' for _ in selected_notes])
        cursor = db.execute(f'''
            SELECT id, title, content FROM notes WHERE id IN ({placeholders})
        ''', selected_notes)
        selected_notes_data = cursor.fetchall()

        combined_content = ""
        for note in selected_notes_data:
            content = note['content'] or ''
            clean_content = re.sub(r'<[^>]+>', '', content).strip()
            if clean_content:
                combined_content += f"\n\n## {note['title']}\n{clean_content}"

        if not combined_content.strip():
            flash('Selected notes are empty.', 'error')
            return redirect(url_for('study_guides.generate_guide', class_id=class_id))

        try:
            # Generate study guide
            focus_list = [f.strip() for f in focus_areas.split(',') if f.strip()] if focus_areas else None
            content = generate_study_guide(combined_content, class_data['name'], focus_list)

            # Save to database
            cursor = db.execute('''
                INSERT INTO study_guides (user_id, class_id, title, content, source_notes)
                VALUES (%s, %s, %s, %s, %s)
            ''', (session['user_id'], class_id, title, content, json.dumps([int(n) for n in selected_notes])))
            db.commit()

            guide_id = cursor.lastrowid
            flash('Study guide generated successfully!', 'success')
            return redirect(url_for('study_guides.view_guide', guide_id=guide_id))

        except Exception as e:
            flash(f'Error generating study guide: {str(e)}', 'error')
            return redirect(url_for('study_guides.generate_guide', class_id=class_id))

    return render_template('study_guides/generate.html', class_data=class_data, notes=notes)


@study_guides.route('/<int:guide_id>/delete', methods=['POST'])
@login_required
def delete_guide(guide_id):
    """Delete a study guide."""
    db = get_db()

    # Verify guide belongs to user
    cursor = db.execute('''
        SELECT sg.id FROM study_guides sg
        JOIN classes c ON sg.class_id = c.id
        WHERE sg.id = %s AND c.user_id = %s
    ''', (guide_id, session['user_id']))
    if not cursor.fetchone():
        flash('Study guide not found.', 'error')
        return redirect(url_for('study_guides.list_guides'))

    db.execute('DELETE FROM study_guides WHERE id = %s', (guide_id,))
    db.commit()

    flash('Study guide deleted.', 'success')
    return redirect(url_for('study_guides.list_guides'))


@study_guides.route('/api/generate', methods=['POST'])
@login_required
def api_generate_guide():
    """API endpoint to generate study guide (AJAX)."""
    db = get_db()

    data = request.get_json()
    class_id = data.get('class_id')
    note_ids = data.get('note_ids', [])
    title = data.get('title', 'Study Guide')
    focus_areas = data.get('focus_areas', [])

    if not class_id:
        return jsonify({'success': False, 'error': 'Class ID required'}), 400

    if not note_ids:
        return jsonify({'success': False, 'error': 'At least one note required'}), 400

    # Get class info (verify belongs to user)
    cursor = db.execute(
        'SELECT name FROM classes WHERE id = %s AND user_id = %s',
        (class_id, session['user_id'])
    )
    class_data = cursor.fetchone()
    if not class_data:
        return jsonify({'success': False, 'error': 'Class not found'}), 404

    # Get notes content
    placeholders = ','.join(['%s' for _ in note_ids])
    cursor = db.execute(f'''
        SELECT id, title, content FROM notes WHERE id IN ({placeholders})
    ''', note_ids)
    notes = cursor.fetchall()

    combined_content = ""
    for note in notes:
        content = note['content'] or ''
        clean_content = re.sub(r'<[^>]+>', '', content).strip()
        if clean_content:
            combined_content += f"\n\n## {note['title']}\n{clean_content}"

    if not combined_content.strip():
        return jsonify({'success': False, 'error': 'Selected notes are empty'}), 400

    try:
        content = generate_study_guide(combined_content, class_data['name'], focus_areas if focus_areas else None)

        cursor = db.execute('''
            INSERT INTO study_guides (user_id, class_id, title, content, source_notes)
            VALUES (?, ?, ?, ?, ?)
        ''', (session['user_id'], class_id, title, content, json.dumps(note_ids)))
        db.commit()

        return jsonify({
            'success': True,
            'guide_id': cursor.lastrowid,
            'message': 'Study guide generated successfully'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
