"""Export Service - Data export functionality."""

import json
import csv
import io
import re
from datetime import datetime


def export_notes_markdown(db, user_id, class_id=None):
    """Export notes as Markdown.

    Args:
        db: Database connection
        user_id: User ID
        class_id: Optional class ID to filter by

    Returns:
        tuple: (markdown_content, filename)
    """
    if class_id:
        cursor = db.execute('''
            SELECT n.*, c.name as class_name, c.code as class_code
            FROM notes n
            JOIN classes c ON n.class_id = c.id
            WHERE c.user_id = %s AND n.class_id = %s
            ORDER BY c.name, n.updated_at DESC
        ''', (user_id, class_id))
    else:
        cursor = db.execute('''
            SELECT n.*, c.name as class_name, c.code as class_code
            FROM notes n
            JOIN classes c ON n.class_id = c.id
            WHERE c.user_id = %s
            ORDER BY c.name, n.updated_at DESC
        ''', (user_id,))

    notes = cursor.fetchall()

    markdown = "# My Notes\n\n"
    markdown += f"Exported on {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    markdown += "---\n\n"

    current_class = None
    for note in notes:
        if note['class_name'] != current_class:
            current_class = note['class_name']
            markdown += f"## {note['class_code'] or note['class_name']}\n\n"

        markdown += f"### {note['title'] or 'Untitled'}\n\n"

        # Convert HTML to plain text (basic conversion)
        content = note['content'] or ''
        content = html_to_markdown(content)
        markdown += content + "\n\n"

        markdown += f"*Last updated: {note['updated_at'][:16] if note['updated_at'] else 'Unknown'}*\n\n"
        markdown += "---\n\n"

    filename = f"notes_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    return markdown, filename


def export_flashcards_csv(db, user_id, deck_id=None):
    """Export flashcards as CSV (compatible with Anki).

    Args:
        db: Database connection
        user_id: User ID
        deck_id: Optional deck ID to filter by

    Returns:
        tuple: (csv_content, filename)
    """
    if deck_id:
        cursor = db.execute('''
            SELECT f.*, d.title as deck_title, c.name as class_name
            FROM flashcards f
            JOIN flashcard_decks d ON f.deck_id = d.id
            JOIN classes c ON d.class_id = c.id
            WHERE d.user_id = %s AND d.id = %s
            ORDER BY d.title, f.id
        ''', (user_id, deck_id))
    else:
        cursor = db.execute('''
            SELECT f.*, d.title as deck_title, c.name as class_name
            FROM flashcards f
            JOIN flashcard_decks d ON f.deck_id = d.id
            JOIN classes c ON d.class_id = c.id
            WHERE d.user_id = %s
            ORDER BY d.title, f.id
        ''', (user_id,))

    cards = cursor.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow(['Front', 'Back', 'Deck', 'Class', 'Tags'])

    for card in cards:
        front = html_to_text(card['front'])
        back = html_to_text(card['back'])
        writer.writerow([
            front,
            back,
            card['deck_title'],
            card['class_name'],
            ''  # Tags placeholder
        ])

    filename = f"flashcards_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return output.getvalue(), filename


def export_full_backup(db, user_id):
    """Export all user data as JSON backup.

    Args:
        db: Database connection
        user_id: User ID

    Returns:
        tuple: (json_content, filename)
    """
    backup = {
        'export_date': datetime.now().isoformat(),
        'version': '1.0',
        'classes': [],
        'notes': [],
        'flashcard_decks': [],
        'flashcards': [],
        'study_guides': [],
        'quizzes': [],
        'quiz_attempts': []
    }

    # Export classes
    cursor = db.execute(
        'SELECT * FROM classes WHERE user_id = %s',
        (user_id,)
    )
    backup['classes'] = [dict(row) for row in cursor.fetchall()]

    # Export notes
    cursor = db.execute('''
        SELECT n.* FROM notes n
        JOIN classes c ON n.class_id = c.id
        WHERE c.user_id = %s
    ''', (user_id,))
    backup['notes'] = [dict(row) for row in cursor.fetchall()]

    # Export flashcard decks
    cursor = db.execute(
        'SELECT * FROM flashcard_decks WHERE user_id = %s',
        (user_id,)
    )
    backup['flashcard_decks'] = [dict(row) for row in cursor.fetchall()]

    # Export flashcards
    cursor = db.execute('''
        SELECT f.* FROM flashcards f
        JOIN flashcard_decks d ON f.deck_id = d.id
        WHERE d.user_id = %s
    ''', (user_id,))
    backup['flashcards'] = [dict(row) for row in cursor.fetchall()]

    # Export study guides
    cursor = db.execute(
        'SELECT * FROM study_guides WHERE user_id = %s',
        (user_id,)
    )
    backup['study_guides'] = [dict(row) for row in cursor.fetchall()]

    # Export quizzes
    cursor = db.execute(
        'SELECT * FROM quizzes WHERE user_id = %s',
        (user_id,)
    )
    backup['quizzes'] = [dict(row) for row in cursor.fetchall()]

    # Export quiz attempts
    cursor = db.execute(
        'SELECT * FROM quiz_attempts WHERE user_id = %s',
        (user_id,)
    )
    backup['quiz_attempts'] = [dict(row) for row in cursor.fetchall()]

    json_content = json.dumps(backup, indent=2, default=str)
    filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    return json_content, filename


def html_to_markdown(html):
    """Convert HTML to basic Markdown."""
    if not html:
        return ''

    text = html

    # Convert common HTML tags to Markdown
    text = re.sub(r'<h1[^>]*>(.*?)</h1>', r'# \1\n', text, flags=re.DOTALL)
    text = re.sub(r'<h2[^>]*>(.*?)</h2>', r'## \1\n', text, flags=re.DOTALL)
    text = re.sub(r'<h3[^>]*>(.*?)</h3>', r'### \1\n', text, flags=re.DOTALL)
    text = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', text, flags=re.DOTALL)
    text = re.sub(r'<b[^>]*>(.*?)</b>', r'**\1**', text, flags=re.DOTALL)
    text = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', text, flags=re.DOTALL)
    text = re.sub(r'<i[^>]*>(.*?)</i>', r'*\1*', text, flags=re.DOTALL)
    text = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', text, flags=re.DOTALL)
    text = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1\n', text, flags=re.DOTALL)
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', text, flags=re.DOTALL)

    # Remove remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    # Clean up whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()

    return text


def html_to_text(html):
    """Convert HTML to plain text."""
    if not html:
        return ''

    # Remove all HTML tags
    text = re.sub(r'<br\s*/?>', '\n', html)
    text = re.sub(r'<[^>]+>', '', text)

    # Decode HTML entities
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')

    return text.strip()
