"""Onboarding Service - Handles new user onboarding flow."""

from datetime import datetime
from app.db_connect import get_db


# Demo class content
DEMO_CLASS = {
    'name': 'Getting Started with Klass',
    'code': 'KLASS-101',
    'instructor': 'Klass AI',
    'semester': 'Welcome',
    'color': '#6366f1',
    'description': 'Learn how to use Klass to supercharge your studying!'
}

DEMO_NOTE_CONTENT = """<h2>Welcome to Klass! 🎓</h2>
<p>This is your first note. Here's what you can do:</p>

<h3>📝 Smart Notes</h3>
<ul>
<li>Type or paste your lecture notes here</li>
<li>Use the AI toolbar to <strong>summarize</strong>, <strong>expand</strong>, or <strong>simplify</strong> text</li>
<li>Auto-save keeps your work safe</li>
</ul>

<h3>🃏 AI Flashcards</h3>
<ul>
<li>Generate flashcards from your notes with one click</li>
<li>Our SM-2 algorithm optimizes your study schedule</li>
<li>Track your mastery over time</li>
</ul>

<h3>📊 Quizzes & Study Guides</h3>
<ul>
<li>Create practice quizzes from any content</li>
<li>Generate comprehensive study guides before exams</li>
</ul>

<h3>🤖 AI Tutor</h3>
<ul>
<li>Ask questions about your notes or any subject</li>
<li>Get explanations tailored to your learning style</li>
</ul>

<p><em>Try selecting this text and using the AI tools in the toolbar above!</em></p>
"""

DEMO_FLASHCARDS = [
    {
        'front': 'What is spaced repetition?',
        'back': 'A learning technique that increases intervals between review sessions for better long-term retention. Klass uses the SM-2 algorithm to optimize your study schedule.'
    },
    {
        'front': 'How can AI help with note-taking?',
        'back': 'AI can summarize long passages, expand on key points, simplify complex concepts, and generate study materials like flashcards and quizzes.'
    },
    {
        'front': 'What are the benefits of active recall?',
        'back': 'Active recall (testing yourself) strengthens neural pathways better than passive re-reading. Flashcards are a great way to practice active recall!'
    },
    {
        'front': 'How do streaks help with studying?',
        'back': 'Daily streaks create accountability and build study habits. Even 10 minutes of flashcard review counts toward your streak!'
    }
]


def create_demo_content(user_id):
    """Create demo class, note, and flashcards for a new user."""
    db = get_db()

    # Create demo class
    db.execute('''
        INSERT INTO classes (user_id, name, code, instructor, semester, color, description)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    ''', (user_id, DEMO_CLASS['name'], DEMO_CLASS['code'], DEMO_CLASS['instructor'],
          DEMO_CLASS['semester'], DEMO_CLASS['color'], DEMO_CLASS['description']))
    db.commit()

    # Get class ID
    cursor = db.execute('SELECT id FROM classes WHERE user_id = %s ORDER BY id DESC LIMIT 1', (user_id,))
    class_result = cursor.fetchone()
    class_id = class_result['id']

    # Create demo note
    db.execute('''
        INSERT INTO notes (class_id, title, content, is_pinned)
        VALUES (%s, %s, %s, 1)
    ''', (class_id, 'Welcome to Klass! Start Here', DEMO_NOTE_CONTENT))
    db.commit()

    # Create demo flashcard deck
    db.execute('''
        INSERT INTO flashcard_decks (user_id, class_id, title, description, card_count)
        VALUES (%s, %s, %s, %s, %s)
    ''', (user_id, class_id, 'Study Tips & Techniques',
          'Learn the basics of effective studying with Klass', len(DEMO_FLASHCARDS)))
    db.commit()

    # Get deck ID
    cursor = db.execute('SELECT id FROM flashcard_decks WHERE user_id = %s ORDER BY id DESC LIMIT 1', (user_id,))
    deck_result = cursor.fetchone()
    deck_id = deck_result['id']

    # Create demo flashcards
    for card in DEMO_FLASHCARDS:
        db.execute('''
            INSERT INTO flashcards (deck_id, front, back)
            VALUES (%s, %s, %s)
        ''', (deck_id, card['front'], card['back']))
    db.commit()

    return class_id


def check_onboarding_complete(user_id):
    """Check if user has completed onboarding."""
    db = get_db()
    cursor = db.execute(
        'SELECT onboarding_completed FROM user_settings WHERE user_id = %s',
        (user_id,)
    )
    settings = cursor.fetchone()

    if not settings:
        return False

    return bool(settings.get('onboarding_completed', 0))


def complete_onboarding(user_id):
    """Mark onboarding as complete for a user."""
    db = get_db()
    db.execute(
        'UPDATE user_settings SET onboarding_completed = 1 WHERE user_id = %s',
        (user_id,)
    )
    db.commit()


def get_onboarding_progress(user_id):
    """Get the current onboarding progress for a user."""
    db = get_db()

    progress = {
        'has_class': False,
        'has_note': False,
        'has_flashcards': False,
        'has_studied': False,
        'completed': False
    }

    # Check for classes
    cursor = db.execute('SELECT COUNT(*) as count FROM classes WHERE user_id = %s', (user_id,))
    progress['has_class'] = cursor.fetchone()['count'] > 0

    # Check for notes
    cursor = db.execute('''
        SELECT COUNT(*) as count FROM notes n
        JOIN classes c ON n.class_id = c.id
        WHERE c.user_id = %s
    ''', (user_id,))
    progress['has_note'] = cursor.fetchone()['count'] > 0

    # Check for flashcard decks
    cursor = db.execute('SELECT COUNT(*) as count FROM flashcard_decks WHERE user_id = %s', (user_id,))
    progress['has_flashcards'] = cursor.fetchone()['count'] > 0

    # Check for study activity
    cursor = db.execute('''
        SELECT COUNT(*) as count FROM flashcards f
        JOIN flashcard_decks d ON f.deck_id = d.id
        WHERE d.user_id = %s AND f.times_reviewed > 0
    ''', (user_id,))
    progress['has_studied'] = cursor.fetchone()['count'] > 0

    # Check if onboarding is complete
    progress['completed'] = check_onboarding_complete(user_id)

    # Calculate completion percentage
    steps_done = sum([
        progress['has_class'],
        progress['has_note'],
        progress['has_flashcards'],
        progress['has_studied']
    ])
    progress['percentage'] = int((steps_done / 4) * 100)

    return progress


def get_next_onboarding_step(user_id):
    """Get the next recommended onboarding step."""
    progress = get_onboarding_progress(user_id)

    if not progress['has_class']:
        return {
            'step': 'create_class',
            'title': 'Create Your First Class',
            'description': 'Add a class to organize your notes and study materials',
            'action_url': '/classes/create',
            'action_text': 'Create Class'
        }
    elif not progress['has_note']:
        return {
            'step': 'create_note',
            'title': 'Take Some Notes',
            'description': 'Add notes to your class - try the AI tools!',
            'action_url': '/notes',
            'action_text': 'Go to Notes'
        }
    elif not progress['has_flashcards']:
        return {
            'step': 'create_flashcards',
            'title': 'Generate Flashcards',
            'description': 'Create flashcards from your notes with AI',
            'action_url': '/flashcards',
            'action_text': 'Create Flashcards'
        }
    elif not progress['has_studied']:
        return {
            'step': 'study',
            'title': 'Start Studying',
            'description': 'Review your flashcards to build your streak',
            'action_url': '/flashcards',
            'action_text': 'Study Now'
        }
    else:
        return None
