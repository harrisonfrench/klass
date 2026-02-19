"""Flashcards Blueprint - Quizlet-style flashcard system."""

import re
import json
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from app.db_connect import get_db
from app.services.ai_service import generate_flashcards as ai_generate_flashcards
from app.blueprints.auth import login_required

flashcards = Blueprint('flashcards', __name__)


@flashcards.route('/')
@login_required
def list_decks():
    """List all flashcard decks for the current user."""
    db = get_db()

    cursor = db.execute('''
        SELECT d.*, c.name as class_name, c.code as class_code, c.color as class_color,
               (SELECT COUNT(*) FROM flashcards WHERE deck_id = d.id) as card_count
        FROM flashcard_decks d
        JOIN classes c ON d.class_id = c.id
        WHERE c.user_id = %s
        ORDER BY d.updated_at DESC
    ''', (session['user_id'],))
    decks = cursor.fetchall()

    # Get classes for creating new decks
    cursor = db.execute(
        'SELECT * FROM classes WHERE user_id = %s ORDER BY name ASC',
        (session['user_id'],)
    )
    classes = cursor.fetchall()

    return render_template('flashcards/list.html', decks=decks, classes=classes)


@flashcards.route('/deck/<int:deck_id>')
@login_required
def view_deck(deck_id):
    """View a flashcard deck."""
    db = get_db()

    cursor = db.execute('''
        SELECT d.*, c.name as class_name, c.code as class_code, c.color as class_color
        FROM flashcard_decks d
        JOIN classes c ON d.class_id = c.id
        WHERE d.id = %s AND c.user_id = %s
    ''', (deck_id, session['user_id']))
    deck = cursor.fetchone()

    if not deck:
        flash('Deck not found.', 'error')
        return redirect(url_for('flashcards.list_decks'))

    cursor = db.execute('''
        SELECT * FROM flashcards WHERE deck_id = %s ORDER BY created_at DESC
    ''', (deck_id,))
    cards = cursor.fetchall()

    return render_template('flashcards/deck.html', deck=deck, cards=cards)


@flashcards.route('/deck/create', methods=['POST'])
@login_required
def create_deck():
    """Create a new flashcard deck."""
    db = get_db()

    class_id = request.form.get('class_id')
    title = request.form.get('title', 'Untitled Deck')

    if not class_id:
        flash('Please select a class.', 'error')
        return redirect(url_for('flashcards.list_decks'))

    # Verify class belongs to user
    cursor = db.execute(
        'SELECT id FROM classes WHERE id = %s AND user_id = %s',
        (class_id, session['user_id'])
    )
    if not cursor.fetchone():
        flash('Class not found.', 'error')
        return redirect(url_for('flashcards.list_decks'))

    cursor = db.execute('''
        INSERT INTO flashcard_decks (user_id, class_id, title)
        VALUES (%s, %s, %s)
    ''', (session['user_id'], class_id, title))
    db.commit()

    deck_id = cursor.lastrowid
    return redirect(url_for('flashcards.view_deck', deck_id=deck_id))


@flashcards.route('/deck/<int:deck_id>/delete', methods=['POST'])
@login_required
def delete_deck(deck_id):
    """Delete a flashcard deck."""
    db = get_db()

    # Verify deck belongs to user
    cursor = db.execute('''
        SELECT d.id FROM flashcard_decks d
        JOIN classes c ON d.class_id = c.id
        WHERE d.id = %s AND c.user_id = %s
    ''', (deck_id, session['user_id']))
    if not cursor.fetchone():
        flash('Deck not found.', 'error')
        return redirect(url_for('flashcards.list_decks'))

    db.execute('DELETE FROM flashcards WHERE deck_id = %s', (deck_id,))
    db.execute('DELETE FROM flashcard_decks WHERE id = %s', (deck_id,))
    db.commit()

    flash('Deck deleted.', 'success')
    return redirect(url_for('flashcards.list_decks'))


@flashcards.route('/deck/<int:deck_id>/card/add', methods=['POST'])
@login_required
def add_card(deck_id):
    """Add a card to a deck."""
    db = get_db()

    # Verify deck belongs to user
    cursor = db.execute('''
        SELECT d.id FROM flashcard_decks d
        JOIN classes c ON d.class_id = c.id
        WHERE d.id = %s AND c.user_id = %s
    ''', (deck_id, session['user_id']))
    if not cursor.fetchone():
        if request.is_json:
            return jsonify({'success': False, 'error': 'Deck not found'}), 404
        flash('Deck not found.', 'error')
        return redirect(url_for('flashcards.list_decks'))

    front = request.form.get('front', '').strip()
    back = request.form.get('back', '').strip()

    if not front or not back:
        if request.is_json:
            return jsonify({'success': False, 'error': 'Front and back are required'}), 400
        flash('Both front and back are required.', 'error')
        return redirect(url_for('flashcards.view_deck', deck_id=deck_id))

    cursor = db.execute('''
        INSERT INTO flashcards (deck_id, front, back)
        VALUES (%s, %s, %s)
    ''', (deck_id, front, back))
    db.commit()

    # Update deck timestamp
    db.execute('UPDATE flashcard_decks SET updated_at = CURRENT_TIMESTAMP WHERE id = %s', (deck_id,))
    db.commit()

    if request.is_json:
        return jsonify({'success': True, 'card_id': cursor.lastrowid})

    flash('Card added.', 'success')
    return redirect(url_for('flashcards.view_deck', deck_id=deck_id))


@flashcards.route('/card/<int:card_id>/edit', methods=['POST'])
@login_required
def edit_card(card_id):
    """Edit a flashcard."""
    db = get_db()

    # Verify card belongs to user
    cursor = db.execute('''
        SELECT f.id FROM flashcards f
        JOIN flashcard_decks d ON f.deck_id = d.id
        JOIN classes c ON d.class_id = c.id
        WHERE f.id = %s AND c.user_id = %s
    ''', (card_id, session['user_id']))
    if not cursor.fetchone():
        if request.is_json:
            return jsonify({'success': False, 'error': 'Card not found'}), 404
        flash('Card not found.', 'error')
        return redirect(url_for('flashcards.list_decks'))

    data = request.get_json() if request.is_json else request.form
    front = data.get('front', '').strip()
    back = data.get('back', '').strip()

    if not front or not back:
        if request.is_json:
            return jsonify({'success': False, 'error': 'Front and back are required'}), 400
        flash('Both front and back are required.', 'error')
        return redirect(request.referrer)

    db.execute('UPDATE flashcards SET front = %s, back = %s WHERE id = %s', (front, back, card_id))
    db.commit()

    if request.is_json:
        return jsonify({'success': True})

    flash('Card updated.', 'success')
    return redirect(request.referrer)


@flashcards.route('/card/<int:card_id>/delete', methods=['POST'])
@login_required
def delete_card(card_id):
    """Delete a flashcard."""
    db = get_db()

    # Verify card belongs to user
    cursor = db.execute('''
        SELECT f.deck_id FROM flashcards f
        JOIN flashcard_decks d ON f.deck_id = d.id
        JOIN classes c ON d.class_id = c.id
        WHERE f.id = %s AND c.user_id = %s
    ''', (card_id, session['user_id']))
    card = cursor.fetchone()

    if card:
        db.execute('DELETE FROM flashcards WHERE id = %s', (card_id,))
        db.commit()

    if request.is_json:
        return jsonify({'success': True})

    flash('Card deleted.', 'success')
    return redirect(request.referrer or url_for('flashcards.list_decks'))


@flashcards.route('/deck/<int:deck_id>/study')
@login_required
def study_deck(deck_id):
    """Study mode for a flashcard deck."""
    db = get_db()

    cursor = db.execute('''
        SELECT d.*, c.name as class_name, c.code as class_code, c.color as class_color
        FROM flashcard_decks d
        JOIN classes c ON d.class_id = c.id
        WHERE d.id = %s AND c.user_id = %s
    ''', (deck_id, session['user_id']))
    deck = cursor.fetchone()

    if not deck:
        flash('Deck not found.', 'error')
        return redirect(url_for('flashcards.list_decks'))

    # Get cards for study (prioritize cards due for review)
    cursor = db.execute('''
        SELECT * FROM flashcards
        WHERE deck_id = %s
        ORDER BY
            CASE WHEN next_review IS NULL THEN 0 ELSE 1 END,
            next_review ASC,
            times_reviewed ASC
    ''', (deck_id,))
    cards = cursor.fetchall()

    if not cards:
        flash('No cards in this deck. Add some cards first!', 'warning')
        return redirect(url_for('flashcards.view_deck', deck_id=deck_id))

    return render_template('flashcards/study.html', deck=deck, cards=cards)


def calculate_sm2(card, quality):
    """
    SM-2 Spaced Repetition Algorithm.
    quality: 0-5 (0=complete blackout, 5=perfect response)
    Returns updated card values: ease_factor, interval, repetitions, next_review
    """
    ease_factor = card.get('ease_factor') or 2.5
    interval = card.get('interval') or 0
    repetitions = card.get('repetitions') or 0

    if quality < 3:
        # Failed - reset
        repetitions = 0
        interval = 1
    else:
        # Passed
        if repetitions == 0:
            interval = 1
        elif repetitions == 1:
            interval = 6
        else:
            interval = round(interval * ease_factor)

        # Update ease factor
        ease_factor = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        ease_factor = max(1.3, ease_factor)  # Minimum ease factor
        repetitions += 1

    # Cap interval at 365 days
    interval = min(interval, 365)
    next_review = datetime.now() + timedelta(days=interval)

    return {
        'ease_factor': ease_factor,
        'interval': interval,
        'repetitions': repetitions,
        'next_review': next_review
    }


@flashcards.route('/card/<int:card_id>/review', methods=['POST'])
@login_required
def review_card(card_id):
    """Record a review for a card using SM-2 spaced repetition algorithm."""
    db = get_db()

    data = request.get_json()
    # quality: 0=Again, 2=Hard, 4=Good, 5=Easy
    quality = data.get('quality', 4)

    # Verify card belongs to user
    cursor = db.execute('''
        SELECT f.* FROM flashcards f
        JOIN flashcard_decks d ON f.deck_id = d.id
        JOIN classes c ON d.class_id = c.id
        WHERE f.id = %s AND c.user_id = %s
    ''', (card_id, session['user_id']))
    card = cursor.fetchone()

    if not card:
        return jsonify({'success': False, 'error': 'Card not found'}), 404

    # Calculate SM-2 values
    sm2_result = calculate_sm2(card, quality)

    # Update review stats
    times_reviewed = card['times_reviewed'] + 1
    times_correct = card['times_correct'] + (1 if quality >= 3 else 0)

    # Map quality to difficulty for backward compatibility
    difficulty = quality

    db.execute('''
        UPDATE flashcards
        SET times_reviewed = %s, times_correct = %s, difficulty = %s,
            ease_factor = %s, `interval` = %s, repetitions = %s,
            last_reviewed = CURRENT_TIMESTAMP, next_review = %s
        WHERE id = %s
    ''', (times_reviewed, times_correct, difficulty,
          sm2_result['ease_factor'], sm2_result['interval'], sm2_result['repetitions'],
          sm2_result['next_review'], card_id))
    db.commit()

    # Record study session for streak tracking
    cursor = db.execute('''
        SELECT d.class_id FROM flashcard_decks d WHERE d.id = %s
    ''', (card['deck_id'],))
    deck = cursor.fetchone()
    if deck:
        db.execute('''
            INSERT INTO study_sessions (user_id, class_id, activity_type, duration)
            VALUES (%s, %s, 'flashcards', 1)
        ''', (session['user_id'], deck['class_id']))
        db.commit()

    return jsonify({
        'success': True,
        'times_reviewed': times_reviewed,
        'times_correct': times_correct,
        'ease_factor': round(sm2_result['ease_factor'], 2),
        'interval': sm2_result['interval'],
        'next_review': sm2_result['next_review'].isoformat()
    })


@flashcards.route('/deck/<int:deck_id>/due-count')
@login_required
def get_due_count(deck_id):
    """Get count of cards due for review."""
    db = get_db()

    cursor = db.execute('''
        SELECT COUNT(*) as count FROM flashcards
        WHERE deck_id = %s AND (next_review IS NULL OR next_review <= NOW())
    ''', (deck_id,))
    result = cursor.fetchone()

    return jsonify({'success': True, 'due_count': result['count'] if result else 0})


@flashcards.route('/deck/<int:deck_id>/import-note', methods=['POST'])
@login_required
def import_note_to_deck(deck_id):
    """Generate flashcards from a note and add them to a deck."""
    db = get_db()

    # Check deck exists and belongs to user
    cursor = db.execute('''
        SELECT d.* FROM flashcard_decks d
        JOIN classes c ON d.class_id = c.id
        WHERE d.id = %s AND c.user_id = %s
    ''', (deck_id, session['user_id']))
    deck = cursor.fetchone()
    if not deck:
        return jsonify({'success': False, 'error': 'Deck not found'}), 404

    data = request.get_json()
    note_id = data.get('note_id')
    num_cards = data.get('num_cards', 10)

    if not note_id:
        return jsonify({'success': False, 'error': 'No note specified'}), 400

    # Get note content (verify it belongs to user)
    cursor = db.execute('''
        SELECT n.* FROM notes n
        JOIN classes c ON n.class_id = c.id
        WHERE n.id = %s AND c.user_id = %s
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
        # Generate flashcards
        cards = ai_generate_flashcards(clean_content, num_cards)

        # Add cards to deck
        for card in cards:
            db.execute('''
                INSERT INTO flashcards (deck_id, front, back)
                VALUES (%s, %s, %s)
            ''', (deck_id, card['front'], card['back']))

        db.execute('UPDATE flashcard_decks SET updated_at = CURRENT_TIMESTAMP WHERE id = %s', (deck_id,))
        db.commit()

        return jsonify({
            'success': True,
            'cards_added': len(cards),
            'note_title': note['title']
        })
    except Exception as e:
        return jsonify({'success': False, 'error': f'AI service error: {str(e)}'}), 500


@flashcards.route('/deck/<int:deck_id>/notes')
@login_required
def get_deck_notes(deck_id):
    """Get notes for the class associated with a deck."""
    db = get_db()

    cursor = db.execute('''
        SELECT d.class_id FROM flashcard_decks d
        JOIN classes c ON d.class_id = c.id
        WHERE d.id = %s AND c.user_id = %s
    ''', (deck_id, session['user_id']))
    deck = cursor.fetchone()

    if not deck:
        return jsonify({'success': False, 'error': 'Deck not found'}), 404

    cursor = db.execute('''
        SELECT id, title FROM notes WHERE class_id = %s ORDER BY updated_at DESC
    ''', (deck['class_id'],))
    notes = cursor.fetchall()

    return jsonify({'success': True, 'notes': notes})


@flashcards.route('/class/<int:class_id>/generate-all', methods=['POST'])
@login_required
def generate_from_all_notes(class_id):
    """Generate flashcards from all notes in a class."""
    db = get_db()

    # Check class exists and belongs to user
    cursor = db.execute(
        'SELECT * FROM classes WHERE id = %s AND user_id = %s',
        (class_id, session['user_id'])
    )
    class_data = cursor.fetchone()
    if not class_data:
        return jsonify({'success': False, 'error': 'Class not found'}), 404

    data = request.get_json()
    title = data.get('title', f"{class_data['name']} Flashcards")
    num_cards = data.get('num_cards', 15)

    # Get all notes for this class
    cursor = db.execute('''
        SELECT id, title, content FROM notes WHERE class_id = %s ORDER BY updated_at DESC
    ''', (class_id,))
    notes = cursor.fetchall()

    if not notes:
        return jsonify({'success': False, 'error': 'No notes in this class'}), 400

    # Combine all notes content
    combined_content = ""
    for note in notes:
        content = note['content'] or ''
        clean_content = re.sub(r'<[^>]+>', '', content).strip()
        if clean_content:
            combined_content += f"\n\n## {note['title']}\n{clean_content}"

    if not combined_content.strip():
        return jsonify({'success': False, 'error': 'All notes are empty'}), 400

    try:
        # Create deck first
        cursor = db.execute('''
            INSERT INTO flashcard_decks (user_id, class_id, title)
            VALUES (%s, %s, %s)
        ''', (session['user_id'], class_id, title))
        db.commit()
        deck_id = cursor.lastrowid

        # Generate flashcards
        cards = ai_generate_flashcards(combined_content, num_cards)

        # Add cards to deck
        for card in cards:
            db.execute('''
                INSERT INTO flashcards (deck_id, front, back)
                VALUES (%s, %s, %s)
            ''', (deck_id, card['front'], card['back']))

        db.execute('UPDATE flashcard_decks SET updated_at = CURRENT_TIMESTAMP WHERE id = %s', (deck_id,))
        db.commit()

        return jsonify({
            'success': True,
            'deck_id': deck_id,
            'cards_added': len(cards)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': f'AI service error: {str(e)}'}), 500
