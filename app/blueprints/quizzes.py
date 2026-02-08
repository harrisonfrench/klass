"""Quizzes Blueprint - AI-generated quizzes from notes."""

import re
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from app.db_connect import get_db
from app.services.ai_service import generate_quiz, grade_short_answer
from app.blueprints.auth import login_required

quizzes = Blueprint('quizzes', __name__)


@quizzes.route('/')
@login_required
def list_quizzes():
    """List all quizzes for the current user."""
    db = get_db()

    cursor = db.execute('''
        SELECT q.*, c.name as class_name, c.code as class_code, c.color as class_color,
               (SELECT COUNT(*) FROM quiz_attempts WHERE quiz_id = q.id) as attempt_count,
               (SELECT MAX(score) FROM quiz_attempts WHERE quiz_id = q.id) as best_score,
               (SELECT total FROM quiz_attempts WHERE quiz_id = q.id ORDER BY completed_at DESC LIMIT 1) as total_questions
        FROM quizzes q
        JOIN classes c ON q.class_id = c.id
        WHERE c.user_id = ?
        ORDER BY q.created_at DESC
    ''', (session['user_id'],))
    quizzes_list = cursor.fetchall()

    # Get classes for creating new quizzes
    cursor = db.execute(
        'SELECT * FROM classes WHERE user_id = ? ORDER BY name ASC',
        (session['user_id'],)
    )
    classes = cursor.fetchall()

    return render_template('quizzes/list.html', quizzes=quizzes_list, classes=classes)


@quizzes.route('/<int:quiz_id>')
@login_required
def view_quiz(quiz_id):
    """View quiz details and history."""
    db = get_db()

    cursor = db.execute('''
        SELECT q.*, c.name as class_name, c.code as class_code, c.color as class_color
        FROM quizzes q
        JOIN classes c ON q.class_id = c.id
        WHERE q.id = ? AND c.user_id = ?
    ''', (quiz_id, session['user_id']))
    quiz = cursor.fetchone()

    if not quiz:
        flash('Quiz not found.', 'error')
        return redirect(url_for('quizzes.list_quizzes'))

    # Get quiz attempts
    cursor = db.execute('''
        SELECT * FROM quiz_attempts WHERE quiz_id = ? ORDER BY completed_at DESC
    ''', (quiz_id,))
    attempts = cursor.fetchall()

    # Parse questions count
    questions = []
    if quiz.get('questions'):
        try:
            questions = json.loads(quiz['questions'])
        except json.JSONDecodeError:
            pass

    return render_template('quizzes/view.html', quiz=quiz, attempts=attempts, question_count=len(questions))


@quizzes.route('/<int:quiz_id>/take')
@login_required
def take_quiz(quiz_id):
    """Take a quiz."""
    db = get_db()

    cursor = db.execute('''
        SELECT q.*, c.name as class_name, c.code as class_code, c.color as class_color
        FROM quizzes q
        JOIN classes c ON q.class_id = c.id
        WHERE q.id = ? AND c.user_id = ?
    ''', (quiz_id, session['user_id']))
    quiz = cursor.fetchone()

    if not quiz:
        flash('Quiz not found.', 'error')
        return redirect(url_for('quizzes.list_quizzes'))

    questions = []
    if quiz.get('questions'):
        try:
            questions = json.loads(quiz['questions'])
        except json.JSONDecodeError:
            flash('Error loading quiz questions.', 'error')
            return redirect(url_for('quizzes.view_quiz', quiz_id=quiz_id))

    if not questions:
        flash('This quiz has no questions.', 'error')
        return redirect(url_for('quizzes.view_quiz', quiz_id=quiz_id))

    return render_template('quizzes/take.html', quiz=quiz, questions=questions)


@quizzes.route('/<int:quiz_id>/submit', methods=['POST'])
@login_required
def submit_quiz(quiz_id):
    """Submit quiz answers."""
    db = get_db()

    # Verify quiz belongs to user
    cursor = db.execute('''
        SELECT q.* FROM quizzes q
        JOIN classes c ON q.class_id = c.id
        WHERE q.id = ? AND c.user_id = ?
    ''', (quiz_id, session['user_id']))
    quiz = cursor.fetchone()

    if not quiz:
        return jsonify({'success': False, 'error': 'Quiz not found'}), 404

    questions = []
    if quiz.get('questions'):
        try:
            questions = json.loads(quiz['questions'])
        except json.JSONDecodeError:
            return jsonify({'success': False, 'error': 'Invalid quiz data'}), 400

    data = request.get_json()
    answers = data.get('answers', {})
    time_taken = data.get('time_taken', 0)

    # Server-side time limit validation
    time_limit = quiz.get('time_limit')
    if time_limit and time_limit > 0:
        # Allow 10 second grace period for network latency
        max_time = (time_limit * 60) + 10
        if time_taken > max_time:
            # Still accept the submission but note it was over time
            time_taken = time_limit * 60  # Cap at the limit

    # Grade the quiz
    score = 0
    results = []

    for i, question in enumerate(questions):
        q_id = str(i)
        user_answer = answers.get(q_id)
        correct_answer = question.get('correct_answer')
        is_correct = False
        ai_feedback = None
        ai_score = None

        if question['type'] == 'multiple_choice':
            is_correct = user_answer == correct_answer
        elif question['type'] == 'true_false':
            is_correct = user_answer == correct_answer
        elif question['type'] == 'short_answer':
            # Use AI grading for short answer questions
            try:
                grading_result = grade_short_answer(
                    question['question'],
                    correct_answer,
                    user_answer
                )
                ai_score = grading_result.get('score', 0)
                ai_feedback = grading_result.get('feedback', '')
                is_correct = grading_result.get('is_correct', False)
            except Exception:
                # Fallback to basic matching if AI fails
                if user_answer and correct_answer:
                    is_correct = user_answer.lower().strip() in correct_answer.lower()

        if is_correct:
            score += 1

        result_entry = {
            'question': question['question'],
            'type': question['type'],
            'user_answer': user_answer,
            'correct_answer': correct_answer,
            'is_correct': is_correct,
            'explanation': question.get('explanation', ''),
            'options': question.get('options', [])
        }

        # Add AI feedback for short answer questions
        if ai_feedback:
            result_entry['ai_feedback'] = ai_feedback
        if ai_score is not None:
            result_entry['ai_score'] = ai_score

        results.append(result_entry)

    # Save attempt
    cursor = db.execute('''
        INSERT INTO quiz_attempts (user_id, quiz_id, score, total, answers, time_taken)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (session['user_id'], quiz_id, score, len(questions), json.dumps(answers), time_taken))
    db.commit()

    return jsonify({
        'success': True,
        'score': score,
        'total': len(questions),
        'percentage': round(score / len(questions) * 100) if questions else 0,
        'results': results,
        'attempt_id': cursor.lastrowid
    })


@quizzes.route('/generate/<int:class_id>', methods=['GET', 'POST'])
@login_required
def generate_quiz_page(class_id):
    """Generate a new quiz for a class."""
    db = get_db()

    cursor = db.execute(
        'SELECT * FROM classes WHERE id = ? AND user_id = ?',
        (class_id, session['user_id'])
    )
    class_data = cursor.fetchone()

    if not class_data:
        flash('Class not found.', 'error')
        return redirect(url_for('quizzes.list_quizzes'))

    cursor = db.execute('''
        SELECT * FROM notes WHERE class_id = ? ORDER BY updated_at DESC
    ''', (class_id,))
    notes = cursor.fetchall()

    if request.method == 'POST':
        title = request.form.get('title', f"Quiz - {class_data['name']}")
        selected_notes = request.form.getlist('notes')
        num_questions = int(request.form.get('num_questions', 10))
        question_types = request.form.getlist('question_types')
        time_limit = int(request.form.get('time_limit', 0))

        if not selected_notes:
            flash('Please select at least one note.', 'error')
            return redirect(url_for('quizzes.generate_quiz_page', class_id=class_id))

        if not question_types:
            question_types = ['multiple_choice', 'true_false']

        # Combine selected notes content
        placeholders = ','.join(['?' for _ in selected_notes])
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
            return redirect(url_for('quizzes.generate_quiz_page', class_id=class_id))

        try:
            questions = generate_quiz(combined_content, num_questions, question_types)

            cursor = db.execute('''
                INSERT INTO quizzes (user_id, class_id, title, questions, time_limit)
                VALUES (?, ?, ?, ?, ?)
            ''', (session['user_id'], class_id, title, json.dumps(questions), time_limit if time_limit > 0 else None))
            db.commit()

            quiz_id = cursor.lastrowid
            flash(f'Quiz generated with {len(questions)} questions!', 'success')
            return redirect(url_for('quizzes.view_quiz', quiz_id=quiz_id))

        except Exception as e:
            flash(f'Error generating quiz: {str(e)}', 'error')
            return redirect(url_for('quizzes.generate_quiz_page', class_id=class_id))

    return render_template('quizzes/generate.html', class_data=class_data, notes=notes)


@quizzes.route('/<int:quiz_id>/delete', methods=['POST'])
@login_required
def delete_quiz(quiz_id):
    """Delete a quiz."""
    db = get_db()

    # Verify quiz belongs to user
    cursor = db.execute('''
        SELECT q.id FROM quizzes q
        JOIN classes c ON q.class_id = c.id
        WHERE q.id = ? AND c.user_id = ?
    ''', (quiz_id, session['user_id']))
    if not cursor.fetchone():
        flash('Quiz not found.', 'error')
        return redirect(url_for('quizzes.list_quizzes'))

    db.execute('DELETE FROM quiz_attempts WHERE quiz_id = ?', (quiz_id,))
    db.execute('DELETE FROM quizzes WHERE id = ?', (quiz_id,))
    db.commit()

    flash('Quiz deleted.', 'success')
    return redirect(url_for('quizzes.list_quizzes'))


@quizzes.route('/attempt/<int:attempt_id>/review')
@login_required
def review_attempt(attempt_id):
    """Review a quiz attempt."""
    db = get_db()

    cursor = db.execute('''
        SELECT a.*, q.title as quiz_title, q.questions, c.name as class_name, c.color as class_color
        FROM quiz_attempts a
        JOIN quizzes q ON a.quiz_id = q.id
        JOIN classes c ON q.class_id = c.id
        WHERE a.id = ? AND c.user_id = ?
    ''', (attempt_id, session['user_id']))
    attempt = cursor.fetchone()

    if not attempt:
        flash('Attempt not found.', 'error')
        return redirect(url_for('quizzes.list_quizzes'))

    questions = json.loads(attempt['questions']) if attempt.get('questions') else []
    answers = json.loads(attempt['answers']) if attempt.get('answers') else {}

    # Build results
    results = []
    for i, question in enumerate(questions):
        q_id = str(i)
        user_answer = answers.get(q_id)
        correct_answer = question.get('correct_answer')
        is_correct = False

        if question['type'] == 'multiple_choice':
            is_correct = user_answer == correct_answer
        elif question['type'] == 'true_false':
            is_correct = user_answer == correct_answer
        elif question['type'] == 'short_answer':
            if user_answer and correct_answer:
                is_correct = user_answer.lower().strip() in correct_answer.lower()

        results.append({
            'question': question['question'],
            'type': question['type'],
            'user_answer': user_answer,
            'correct_answer': correct_answer,
            'is_correct': is_correct,
            'explanation': question.get('explanation', ''),
            'options': question.get('options', [])
        })

    return render_template('quizzes/review.html', attempt=attempt, results=results)
