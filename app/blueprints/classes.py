import os
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory, session
from werkzeug.utils import secure_filename
from app.db_connect import get_db
from app.syllabus_analyzer import analyze_and_save
from app.blueprints.auth import login_required

classes = Blueprint('classes', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@classes.route('/')
@login_required
def list_classes():
    """List all classes for the current user."""
    db = get_db()
    cursor = db.execute(
        'SELECT * FROM classes WHERE user_id = ? ORDER BY created_at DESC',
        (session['user_id'],)
    )
    all_classes = cursor.fetchall()
    return render_template('classes/list.html', classes=all_classes)


@classes.route('/create', methods=['GET', 'POST'])
@login_required
def create_class():
    """Create a new class."""
    if request.method == 'POST':
        name = request.form.get('name')
        code = request.form.get('code')
        instructor = request.form.get('instructor')
        semester = request.form.get('semester')
        color = request.form.get('color', '#0d6efd')
        description = request.form.get('description')

        if not name:
            flash('Class name is required.', 'error')
            return redirect(url_for('classes.create_class'))

        db = get_db()
        db.execute(
            '''INSERT INTO classes (user_id, name, code, instructor, semester, color, description)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (session['user_id'], name, code, instructor, semester, color, description)
        )
        db.commit()

        flash(f'Class "{name}" created successfully!', 'success')
        return redirect(url_for('classes.list_classes'))

    return render_template('classes/create.html')


@classes.route('/<int:class_id>')
@login_required
def view_class(class_id):
    """View a single class."""
    db = get_db()
    cursor = db.execute(
        'SELECT * FROM classes WHERE id = ? AND user_id = ?',
        (class_id, session['user_id'])
    )
    class_data = cursor.fetchone()

    if not class_data:
        flash('Class not found.', 'error')
        return redirect(url_for('classes.list_classes'))

    # Get assignments
    cursor = db.execute(
        'SELECT * FROM assignments WHERE class_id = ? ORDER BY due_date ASC',
        (class_id,)
    )
    assignments_raw = cursor.fetchall()

    # Auto-mark assignments as completed if due date has passed
    today = date.today()
    assignments = []
    for a in assignments_raw:
        assignment = dict(a)
        if assignment['due_date'] and assignment['status'] != 'completed':
            try:
                due_date = datetime.strptime(assignment['due_date'], '%Y-%m-%d').date()
                if due_date < today:
                    assignment['status'] = 'completed'
            except ValueError:
                pass
        assignments.append(assignment)

    # Get calendar events
    cursor = db.execute(
        'SELECT * FROM calendar_events WHERE class_id = ? ORDER BY event_date ASC',
        (class_id,)
    )
    calendar_events = cursor.fetchall()

    # Get notes for this class
    cursor = db.execute(
        'SELECT * FROM notes WHERE class_id = ? ORDER BY is_pinned DESC, updated_at DESC',
        (class_id,)
    )
    notes = cursor.fetchall()

    # Get flashcard decks for this class with card counts
    cursor = db.execute('''
        SELECT d.*, (SELECT COUNT(*) FROM flashcards WHERE deck_id = d.id) as card_count
        FROM flashcard_decks d
        WHERE d.class_id = ?
        ORDER BY d.updated_at DESC
    ''', (class_id,))
    flashcard_decks = cursor.fetchall()

    # Get study guides for this class
    cursor = db.execute('''
        SELECT * FROM study_guides WHERE class_id = ? ORDER BY created_at DESC
    ''', (class_id,))
    study_guides = cursor.fetchall()

    return render_template(
        'classes/detail.html',
        class_data=class_data,
        assignments=assignments,
        calendar_events=calendar_events,
        notes=notes,
        flashcard_decks=flashcard_decks,
        study_guides=study_guides
    )


@classes.route('/<int:class_id>/update', methods=['POST'])
@login_required
def update_class(class_id):
    """Update a class."""
    name = request.form.get('name')
    code = request.form.get('code')
    instructor = request.form.get('instructor')
    semester = request.form.get('semester')
    color = request.form.get('color', '#0d6efd')
    description = request.form.get('description')

    if not name:
        flash('Class name is required.', 'error')
        return redirect(url_for('classes.view_class', class_id=class_id))

    db = get_db()
    db.execute(
        '''UPDATE classes
           SET name = ?, code = ?, instructor = ?, semester = ?, color = ?, description = ?,
               updated_at = CURRENT_TIMESTAMP
           WHERE id = ? AND user_id = ?''',
        (name, code, instructor, semester, color, description, class_id, session['user_id'])
    )
    db.commit()

    flash(f'Class "{name}" updated successfully!', 'success')
    return redirect(url_for('classes.view_class', class_id=class_id))


@classes.route('/<int:class_id>/delete', methods=['POST'])
@login_required
def delete_class(class_id):
    """Delete a class."""
    db = get_db()

    # Get class info for cleanup (only if owned by user)
    cursor = db.execute(
        'SELECT name, syllabus_filename FROM classes WHERE id = ? AND user_id = ?',
        (class_id, session['user_id'])
    )
    class_data = cursor.fetchone()

    if class_data:
        # Delete syllabus file if exists
        if class_data.get('syllabus_filename'):
            try:
                filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], class_data['syllabus_filename'])
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception:
                pass

        db.execute('DELETE FROM classes WHERE id = ? AND user_id = ?', (class_id, session['user_id']))
        db.commit()
        flash(f'Class "{class_data["name"]}" deleted.', 'success')
    else:
        flash('Class not found.', 'error')

    return redirect(url_for('classes.list_classes'))


@classes.route('/<int:class_id>/syllabus/upload', methods=['POST'])
@login_required
def upload_syllabus(class_id):
    """Upload a syllabus for a class."""
    db = get_db()
    cursor = db.execute(
        'SELECT * FROM classes WHERE id = ? AND user_id = ?',
        (class_id, session['user_id'])
    )
    class_data = cursor.fetchone()

    if not class_data:
        flash('Class not found.', 'error')
        return redirect(url_for('classes.list_classes'))

    if 'syllabus' not in request.files:
        flash('No file selected.', 'error')
        return redirect(url_for('classes.view_class', class_id=class_id))

    file = request.files['syllabus']

    if file.filename == '':
        flash('No file selected.', 'error')
        return redirect(url_for('classes.view_class', class_id=class_id))

    if file and allowed_file(file.filename):
        # Delete old syllabus if exists
        if class_data.get('syllabus_filename'):
            try:
                old_filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], class_data['syllabus_filename'])
                if os.path.exists(old_filepath):
                    os.remove(old_filepath)
            except Exception:
                pass

        # Save new file with unique name
        filename = secure_filename(file.filename)
        unique_filename = f"{class_id}_{filename}"
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)

        # Update database
        db.execute(
            'UPDATE classes SET syllabus_filename = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (unique_filename, class_id)
        )
        db.commit()

        flash('Syllabus uploaded successfully!', 'success')

        # Analyze syllabus with Groq API
        api_key = os.environ.get('GROQ_API_KEY')
        if api_key:
            success, message = analyze_and_save(filepath, class_id, db, api_key)
            if success:
                flash(f'Syllabus analyzed: {message}', 'success')
            else:
                flash(f'Analysis note: {message}', 'warning')
        else:
            flash('Set GROQ_API_KEY in .env to enable syllabus analysis', 'warning')
    else:
        flash('Invalid file type. Allowed: PDF, DOC, DOCX, TXT', 'error')

    return redirect(url_for('classes.view_class', class_id=class_id))


@classes.route('/<int:class_id>/syllabus/view')
@login_required
def view_syllabus(class_id):
    """View/download the syllabus for a class."""
    db = get_db()
    cursor = db.execute(
        'SELECT syllabus_filename FROM classes WHERE id = ? AND user_id = ?',
        (class_id, session['user_id'])
    )
    class_data = cursor.fetchone()

    if not class_data or not class_data.get('syllabus_filename'):
        flash('No syllabus found.', 'error')
        return redirect(url_for('classes.view_class', class_id=class_id))

    return send_from_directory(
        current_app.config['UPLOAD_FOLDER'],
        class_data['syllabus_filename'],
        as_attachment=False
    )


@classes.route('/<int:class_id>/assignment/<int:assignment_id>/status', methods=['POST'])
@login_required
def update_assignment_status(class_id, assignment_id):
    """Update assignment status."""
    # Verify the class belongs to the user
    db = get_db()
    cursor = db.execute(
        'SELECT id FROM classes WHERE id = ? AND user_id = ?',
        (class_id, session['user_id'])
    )
    if not cursor.fetchone():
        flash('Class not found.', 'error')
        return redirect(url_for('classes.list_classes'))

    new_status = request.form.get('status', 'pending')
    if new_status not in ('pending', 'completed', 'reminder'):
        new_status = 'pending'

    db.execute(
        'UPDATE assignments SET status = ? WHERE id = ? AND class_id = ?',
        (new_status, assignment_id, class_id)
    )
    db.commit()

    return redirect(url_for('classes.view_class', class_id=class_id))


@classes.route('/<int:class_id>/syllabus/delete', methods=['POST'])
@login_required
def delete_syllabus(class_id):
    """Delete the syllabus for a class."""
    db = get_db()
    cursor = db.execute(
        'SELECT syllabus_filename FROM classes WHERE id = ? AND user_id = ?',
        (class_id, session['user_id'])
    )
    class_data = cursor.fetchone()

    if class_data and class_data.get('syllabus_filename'):
        try:
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], class_data['syllabus_filename'])
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception:
            pass

        db.execute(
            'UPDATE classes SET syllabus_filename = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?',
            (class_id, session['user_id'])
        )
        db.commit()
        flash('Syllabus deleted.', 'success')
    else:
        flash('No syllabus found.', 'error')

    return redirect(url_for('classes.view_class', class_id=class_id))
