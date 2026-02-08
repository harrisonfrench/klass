import os
import json
from datetime import datetime
from groq import Groq
from PyPDF2 import PdfReader
from docx import Document


def extract_text_from_file(filepath):
    """Extract text content from PDF, DOCX, or TXT files."""
    ext = filepath.rsplit('.', 1)[1].lower() if '.' in filepath else ''

    if ext == 'pdf':
        return extract_text_from_pdf(filepath)
    elif ext == 'docx':
        return extract_text_from_docx(filepath)
    elif ext in ('txt', 'doc'):
        return extract_text_from_txt(filepath)
    else:
        return None


def extract_text_from_pdf(filepath):
    """Extract text from PDF file."""
    try:
        reader = PdfReader(filepath)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text
    except Exception as e:
        print(f"Error extracting PDF text: {e}")
        return None


def extract_text_from_docx(filepath):
    """Extract text from DOCX file."""
    try:
        doc = Document(filepath)
        text = "\n".join([para.text for para in doc.paragraphs])
        return text
    except Exception as e:
        print(f"Error extracting DOCX text: {e}")
        return None


def extract_text_from_txt(filepath):
    """Extract text from TXT file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading TXT file: {e}")
        return None


def analyze_syllabus_with_groq(text, api_key):
    """Use Groq API to analyze syllabus text and extract assignments/events."""
    if not api_key:
        return None, "No API key provided"

    if not text or len(text.strip()) < 50:
        return None, "Syllabus text is too short to analyze"

    # Truncate if too long (Groq has context limits)
    max_chars = 15000
    if len(text) > max_chars:
        text = text[:max_chars]

    client = Groq(api_key=api_key)

    current_year = datetime.now().year

    prompt = f"""Analyze this course syllabus and extract all assignments, exams, quizzes, and important dates.

Return a JSON object with two arrays:
1. "assignments" - for homework, projects, papers, quizzes, exams
2. "calendar_events" - for class sessions, office hours, holidays, other important dates

For each assignment, include:
- "title": name of the assignment
- "description": brief description (optional)
- "due_date": date in YYYY-MM-DD format (use {current_year} or {current_year + 1} for reasonable dates, null if not specified)
- "points": point value if mentioned (null if not specified)
- "type": one of "homework", "quiz", "exam", "project", "paper", "other"

For each calendar event, include:
- "title": name of the event
- "description": brief description (optional)
- "event_date": date in YYYY-MM-DD format (use {current_year} or {current_year + 1}, null if not specified)
- "event_type": one of "exam", "holiday", "deadline", "class", "other"

Only include items you can clearly identify from the syllabus. If no dates are found, still include the items with null dates.

SYLLABUS TEXT:
{text}

Respond with ONLY valid JSON, no other text or markdown."""

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            max_tokens=4096
        )

        response_text = chat_completion.choices[0].message.content.strip()

        # Handle potential markdown code blocks
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            # Remove first and last lines (```json and ```)
            response_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        data = json.loads(response_text)
        return data, None

    except json.JSONDecodeError as e:
        return None, f"Failed to parse response as JSON: {e}"
    except Exception as e:
        return None, f"Groq API error: {e}"


def save_analysis_to_db(db, class_id, analysis_data):
    """Save extracted assignments and events to database."""
    assignments_added = 0
    events_added = 0

    # Save assignments
    for assignment in analysis_data.get('assignments', []):
        try:
            db.execute(
                '''INSERT INTO assignments (class_id, title, description, due_date, points, status)
                   VALUES (?, ?, ?, ?, ?, 'pending')''',
                (
                    class_id,
                    assignment.get('title', 'Untitled'),
                    assignment.get('description'),
                    assignment.get('due_date'),
                    assignment.get('points')
                )
            )
            assignments_added += 1
        except Exception as e:
            print(f"Error saving assignment: {e}")

    # Save calendar events
    for event in analysis_data.get('calendar_events', []):
        try:
            db.execute(
                '''INSERT INTO calendar_events (class_id, title, description, event_date, event_type)
                   VALUES (?, ?, ?, ?, ?)''',
                (
                    class_id,
                    event.get('title', 'Untitled'),
                    event.get('description'),
                    event.get('event_date'),
                    event.get('event_type', 'other')
                )
            )
            events_added += 1
        except Exception as e:
            print(f"Error saving event: {e}")

    db.commit()
    return assignments_added, events_added


def analyze_and_save(filepath, class_id, db, api_key):
    """Main function to extract, analyze, and save syllabus data."""
    # Extract text
    text = extract_text_from_file(filepath)
    if not text:
        return False, "Could not extract text from file"

    # Analyze with Groq
    analysis_data, error = analyze_syllabus_with_groq(text, api_key)
    if error:
        return False, error

    # Clear existing assignments/events for this class (re-analysis)
    db.execute('DELETE FROM assignments WHERE class_id = ?', (class_id,))
    db.execute('DELETE FROM calendar_events WHERE class_id = ?', (class_id,))

    # Save to database
    assignments_added, events_added = save_analysis_to_db(db, class_id, analysis_data)

    return True, f"Found {assignments_added} assignments and {events_added} calendar events"
