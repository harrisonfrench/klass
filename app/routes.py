from flask import render_template, request, redirect, url_for, session, Response
from . import app
from .db_connect import get_db
from .blueprints.auth import login_required
from .services.streak_service import get_user_streak, get_today_stats, get_weekly_activity, has_studied_today
from .services.onboarding_service import get_onboarding_progress, check_onboarding_complete
from .services.insights_service import get_user_insights
from datetime import datetime, date
import calendar as cal


@app.route('/googlee23f5fa5f2501c4a.html')
def google_verification():
    """Google Search Console verification file."""
    return Response('google-site-verification: googlee23f5fa5f2501c4a.html', mimetype='text/html')


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

    # Get streak data
    streak = get_user_streak(user_id)
    today_stats = get_today_stats(user_id)
    weekly_activity = get_weekly_activity(user_id)
    studied_today = has_studied_today(user_id)

    # Get onboarding progress
    onboarding = get_onboarding_progress(user_id)
    show_onboarding = not onboarding['completed'] and onboarding['percentage'] < 100

    # Get performance insights
    insights = get_user_insights(user_id) if not show_onboarding else []

    return render_template('dashboard.html',
        classes=classes,
        class_count=class_count,
        upcoming_count=upcoming_count,
        notes_count=notes_count,
        flashcard_count=flashcard_count,
        study_guide_count=study_guide_count,
        recent_notes=recent_notes,
        streak=streak,
        today_stats=today_stats,
        weekly_activity=weekly_activity,
        studied_today=studied_today,
        onboarding=onboarding,
        show_onboarding=show_onboarding,
        insights=insights
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

    # Get streak data
    streak = get_user_streak(user_id)
    today_stats = get_today_stats(user_id)
    weekly_activity = get_weekly_activity(user_id)
    studied_today = has_studied_today(user_id)

    # Get onboarding progress
    onboarding = get_onboarding_progress(user_id)
    show_onboarding = not onboarding['completed'] and onboarding['percentage'] < 100

    # Get performance insights
    insights = get_user_insights(user_id) if not show_onboarding else []

    return render_template('dashboard.html',
        classes=classes,
        class_count=class_count,
        upcoming_count=upcoming_count,
        notes_count=notes_count,
        flashcard_count=flashcard_count,
        study_guide_count=study_guide_count,
        recent_notes=recent_notes,
        streak=streak,
        today_stats=today_stats,
        weekly_activity=weekly_activity,
        studied_today=studied_today,
        onboarding=onboarding,
        show_onboarding=show_onboarding,
        insights=insights
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
            due_date_val = assignment['due_date']
            # Handle both string (SQLite) and date object (MySQL)
            if isinstance(due_date_val, str):
                date_str = due_date_val
                due_date = datetime.strptime(due_date_val, '%Y-%m-%d').date()
            else:
                date_str = due_date_val.strftime('%Y-%m-%d')
                due_date = due_date_val

            if date_str not in events_by_date:
                events_by_date[date_str] = []

            # Auto-mark as completed if due date has passed
            status = assignment['status']
            if due_date < today and status != 'completed':
                status = 'completed'

            events_by_date[date_str].append({
                'title': assignment['title'],
                'type': 'assignment',
                'class_name': assignment['class_name'],
                'class_color': assignment['class_color'],
                'status': status
            })

    for event in events:
        if event['event_date']:
            event_date_val = event['event_date']
            # Handle both string (SQLite) and date object (MySQL)
            if isinstance(event_date_val, str):
                date_str = event_date_val
            else:
                date_str = event_date_val.strftime('%Y-%m-%d')

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


@app.route('/ai-assistant')
@login_required
def ai_assistant():
    """AI Study Assistant page."""
    db = get_db()
    user_id = session['user_id']

    # Get user's classes for the filter dropdown
    cursor = db.execute(
        'SELECT id, name, code, color FROM classes WHERE user_id = %s ORDER BY name',
        (user_id,)
    )
    classes = cursor.fetchall()

    return render_template('ai_assistant.html', classes=classes)


@app.route('/download')
def download():
    """Desktop app download page."""
    return render_template('download.html')
