from flask import render_template, request, redirect, url_for, session
from . import app
from .db_connect import get_db
from .blueprints.auth import login_required
from datetime import datetime, date
import calendar as cal


@app.route('/')
@login_required
def index():
    db = get_db()
    user_id = session['user_id']

    cursor = db.execute(
        'SELECT * FROM classes WHERE user_id = %s ORDER BY created_at DESC LIMIT 5',
        (user_id,)
    )
    classes = cursor.fetchall()

    cursor = db.execute('SELECT COUNT(*) as count FROM classes WHERE user_id = %s', (user_id,))
    class_count = cursor.fetchone()['count']

    # Count upcoming assignments (pending with future due dates)
    cursor = db.execute('''
        SELECT COUNT(*) as count FROM assignments a
        JOIN classes c ON a.class_id = c.id
        WHERE c.user_id = %s
        AND a.status != 'completed'
        AND a.due_date >= CURDATE()
    ''', (user_id,))
    upcoming_count = cursor.fetchone()['count']

    # Count notes
    cursor = db.execute('''
        SELECT COUNT(*) as count FROM notes n
        JOIN classes c ON n.class_id = c.id
        WHERE c.user_id = %s
    ''', (user_id,))
    notes_count = cursor.fetchone()['count']

    # Count flashcard decks
    cursor = db.execute('''
        SELECT COUNT(*) as count FROM flashcard_decks d
        JOIN classes c ON d.class_id = c.id
        WHERE c.user_id = %s
    ''', (user_id,))
    flashcard_count = cursor.fetchone()['count']

    # Count study guides
    cursor = db.execute('''
        SELECT COUNT(*) as count FROM study_guides sg
        JOIN classes c ON sg.class_id = c.id
        WHERE c.user_id = %s
    ''', (user_id,))
    study_guide_count = cursor.fetchone()['count']

    # Get recent notes with class info
    cursor = db.execute('''
        SELECT n.*, c.name as class_name, c.code as class_code, c.color as class_color
        FROM notes n
        JOIN classes c ON n.class_id = c.id
        WHERE c.user_id = %s
        ORDER BY n.updated_at DESC
        LIMIT 5
    ''', (user_id,))
    recent_notes = cursor.fetchall()

    return render_template('dashboard.html',
        classes=classes,
        class_count=class_count,
        upcoming_count=upcoming_count,
        notes_count=notes_count,
        flashcard_count=flashcard_count,
        study_guide_count=study_guide_count,
        recent_notes=recent_notes
    )


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    user_id = session['user_id']

    cursor = db.execute(
        'SELECT * FROM classes WHERE user_id = %s ORDER BY created_at DESC LIMIT 5',
        (user_id,)
    )
    classes = cursor.fetchall()

    cursor = db.execute('SELECT COUNT(*) as count FROM classes WHERE user_id = %s', (user_id,))
    class_count = cursor.fetchone()['count']

    # Count upcoming assignments (pending with future due dates)
    cursor = db.execute('''
        SELECT COUNT(*) as count FROM assignments a
        JOIN classes c ON a.class_id = c.id
        WHERE c.user_id = %s
        AND a.status != 'completed'
        AND a.due_date >= CURDATE()
    ''', (user_id,))
    upcoming_count = cursor.fetchone()['count']

    # Count notes
    cursor = db.execute('''
        SELECT COUNT(*) as count FROM notes n
        JOIN classes c ON n.class_id = c.id
        WHERE c.user_id = %s
    ''', (user_id,))
    notes_count = cursor.fetchone()['count']

    # Count flashcard decks
    cursor = db.execute('''
        SELECT COUNT(*) as count FROM flashcard_decks d
        JOIN classes c ON d.class_id = c.id
        WHERE c.user_id = %s
    ''', (user_id,))
    flashcard_count = cursor.fetchone()['count']

    # Count study guides
    cursor = db.execute('''
        SELECT COUNT(*) as count FROM study_guides sg
        JOIN classes c ON sg.class_id = c.id
        WHERE c.user_id = %s
    ''', (user_id,))
    study_guide_count = cursor.fetchone()['count']

    # Get recent notes with class info
    cursor = db.execute('''
        SELECT n.*, c.name as class_name, c.code as class_code, c.color as class_color
        FROM notes n
        JOIN classes c ON n.class_id = c.id
        WHERE c.user_id = %s
        ORDER BY n.updated_at DESC
        LIMIT 5
    ''', (user_id,))
    recent_notes = cursor.fetchall()

    return render_template('dashboard.html',
        classes=classes,
        class_count=class_count,
        upcoming_count=upcoming_count,
        notes_count=notes_count,
        flashcard_count=flashcard_count,
        study_guide_count=study_guide_count,
        recent_notes=recent_notes
    )


@app.route('/search')
@login_required
def search():
    query = request.args.get('q', '').strip()
    if not query:
        return redirect(url_for('dashboard'))

    db = get_db()
    user_id = session['user_id']

    # Search classes
    classes = db.execute('''
        SELECT * FROM classes
        WHERE user_id = %s AND (name LIKE %s OR code LIKE %s OR instructor LIKE %s)
    ''', (user_id, f'%{query}%', f'%{query}%', f'%{query}%')).fetchall()

    # Search assignments with class info
    assignments = db.execute('''
        SELECT a.*, c.name as class_name, c.color as class_color
        FROM assignments a
        JOIN classes c ON a.class_id = c.id
        WHERE c.user_id = %s AND (a.title LIKE %s OR a.description LIKE %s)
    ''', (user_id, f'%{query}%', f'%{query}%')).fetchall()

    # Search calendar events with class info
    events = db.execute('''
        SELECT e.*, c.name as class_name, c.color as class_color
        FROM calendar_events e
        JOIN classes c ON e.class_id = c.id
        WHERE c.user_id = %s AND (e.title LIKE %s OR e.description LIKE %s)
    ''', (user_id, f'%{query}%', f'%{query}%')).fetchall()

    # Search notes with class info
    notes = db.execute('''
        SELECT n.*, c.name as class_name, c.color as class_color
        FROM notes n
        JOIN classes c ON n.class_id = c.id
        WHERE c.user_id = %s AND (n.title LIKE %s OR n.content LIKE %s)
    ''', (user_id, f'%{query}%', f'%{query}%')).fetchall()

    return render_template('search_results.html',
        query=query, classes=classes, assignments=assignments, events=events, notes=notes)


@app.route('/calendar')
@login_required
def calendar():
    db = get_db()
    user_id = session['user_id']

    # Get year and month from query params or use current
    today = date.today()
    year = request.args.get('year', today.year, type=int)
    month = request.args.get('month', today.month, type=int)

    # Handle month overflow
    if month < 1:
        month = 12
        year -= 1
    elif month > 12:
        month = 1
        year += 1

    # Get all assignments with class info
    cursor = db.execute('''
        SELECT a.*, c.name as class_name, c.code as class_code, c.color as class_color
        FROM assignments a
        JOIN classes c ON a.class_id = c.id
        WHERE c.user_id = %s
        ORDER BY a.due_date ASC
    ''', (user_id,))
    assignments = cursor.fetchall()

    # Get all calendar events with class info
    cursor = db.execute('''
        SELECT e.*, c.name as class_name, c.code as class_code, c.color as class_color
        FROM calendar_events e
        JOIN classes c ON e.class_id = c.id
        WHERE c.user_id = %s
        ORDER BY e.event_date ASC
    ''', (user_id,))
    events = cursor.fetchall()

    # Build events by date lookup
    events_by_date = {}
    for assignment in assignments:
        if assignment['due_date']:
            date_str = assignment['due_date']
            if date_str not in events_by_date:
                events_by_date[date_str] = []

            # Auto-mark as completed if due date has passed
            status = assignment['status']
            try:
                due_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                if due_date < today and status != 'completed':
                    status = 'completed'
            except ValueError:
                pass

            events_by_date[date_str].append({
                'title': assignment['title'],
                'type': 'assignment',
                'class_name': assignment['class_name'],
                'class_color': assignment['class_color'],
                'status': status
            })

    for event in events:
        if event['event_date']:
            date_str = event['event_date']
            if date_str not in events_by_date:
                events_by_date[date_str] = []
            events_by_date[date_str].append({
                'title': event['title'],
                'type': event['event_type'] or 'other',
                'class_name': event['class_name'],
                'class_color': event['class_color']
            })

    # Build calendar days
    calendar_days = []
    month_calendar = cal.Calendar(firstweekday=6)  # Sunday first

    for day_date in month_calendar.itermonthdates(year, month):
        date_str = day_date.strftime('%Y-%m-%d')
        day_events = events_by_date.get(date_str, [])

        calendar_days.append({
            'day': day_date.day,
            'date': date_str,
            'current_month': day_date.month == month,
            'is_today': day_date == today,
            'events': day_events
        })

    # Month navigation
    prev_month = month - 1
    prev_year = year
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1

    next_month = month + 1
    next_year = year
    if next_month > 12:
        next_month = 1
        next_year += 1

    month_name = cal.month_name[month]

    return render_template(
        'calendar.html',
        calendar_days=calendar_days,
        year=year,
        month_name=month_name,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month
    )
