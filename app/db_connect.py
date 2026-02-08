import sqlite3
from flask import g
import os

DATABASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database', 'app.db')


def dict_factory(cursor, row):
    """Convert SQLite rows to dictionaries."""
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}


def get_db():
    """Get database connection, creating one if needed."""
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = dict_factory
    return g.db


def close_db(exception=None):
    """Close database connection."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """Initialize the database with schema."""
    db = sqlite3.connect(DATABASE)
    db.row_factory = dict_factory

    # Create users table first (for authentication)
    db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    db.execute('''
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            code TEXT,
            instructor TEXT,
            semester TEXT,
            color TEXT DEFAULT '#0d6efd',
            description TEXT,
            syllabus_filename TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    # Add syllabus_filename column if it doesn't exist
    try:
        db.execute('ALTER TABLE classes ADD COLUMN syllabus_filename TEXT')
    except Exception:
        pass  # Column already exists

    # Add user_id column to classes if it doesn't exist
    try:
        db.execute('ALTER TABLE classes ADD COLUMN user_id INTEGER REFERENCES users(id)')
    except Exception:
        pass  # Column already exists

    # Create assignments table
    db.execute('''
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            due_date DATE,
            points INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE CASCADE
        )
    ''')

    # Create calendar_events table
    db.execute('''
        CREATE TABLE IF NOT EXISTS calendar_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            event_date DATE,
            event_type TEXT DEFAULT 'other',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE CASCADE
        )
    ''')

    # Create notes table
    db.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER NOT NULL,
            title TEXT NOT NULL DEFAULT 'Untitled',
            content TEXT DEFAULT '',
            is_pinned INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE CASCADE
        )
    ''')

    # Create flashcard decks table
    db.execute('''
        CREATE TABLE IF NOT EXISTS flashcard_decks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            class_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            card_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE CASCADE
        )
    ''')

    # Add user_id to flashcard_decks if it doesn't exist
    try:
        db.execute('ALTER TABLE flashcard_decks ADD COLUMN user_id INTEGER REFERENCES users(id)')
    except Exception:
        pass

    # Create flashcards table
    db.execute('''
        CREATE TABLE IF NOT EXISTS flashcards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deck_id INTEGER NOT NULL,
            front TEXT NOT NULL,
            back TEXT NOT NULL,
            difficulty INTEGER DEFAULT 0,
            times_reviewed INTEGER DEFAULT 0,
            times_correct INTEGER DEFAULT 0,
            last_reviewed TIMESTAMP,
            next_review TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (deck_id) REFERENCES flashcard_decks (id) ON DELETE CASCADE
        )
    ''')

    # Create study guides table
    db.execute('''
        CREATE TABLE IF NOT EXISTS study_guides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            class_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            source_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE CASCADE
        )
    ''')

    # Add user_id to study_guides if it doesn't exist
    try:
        db.execute('ALTER TABLE study_guides ADD COLUMN user_id INTEGER REFERENCES users(id)')
    except Exception:
        pass

    # Create quizzes table
    db.execute('''
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            class_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            questions TEXT,
            time_limit INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE CASCADE
        )
    ''')

    # Add user_id to quizzes if it doesn't exist
    try:
        db.execute('ALTER TABLE quizzes ADD COLUMN user_id INTEGER REFERENCES users(id)')
    except Exception:
        pass

    # Create quiz attempts table
    db.execute('''
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            quiz_id INTEGER NOT NULL,
            score INTEGER,
            total INTEGER,
            answers TEXT,
            time_taken INTEGER,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (quiz_id) REFERENCES quizzes (id) ON DELETE CASCADE
        )
    ''')

    # Add user_id to quiz_attempts if it doesn't exist
    try:
        db.execute('ALTER TABLE quiz_attempts ADD COLUMN user_id INTEGER REFERENCES users(id)')
    except Exception:
        pass

    # Create chat sessions table for AI tutor
    db.execute('''
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            class_id INTEGER,
            title TEXT DEFAULT 'New Chat',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE SET NULL
        )
    ''')

    # Create chat messages table
    db.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE
        )
    ''')

    # Create study sessions table for analytics
    db.execute('''
        CREATE TABLE IF NOT EXISTS study_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            class_id INTEGER,
            activity_type TEXT NOT NULL,
            duration INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE SET NULL
        )
    ''')

    # Create user settings table
    db.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            theme TEXT DEFAULT 'light',
            default_class_color TEXT DEFAULT '#6366f1',
            ai_features_enabled INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    db.commit()
    db.close()
    print(f"Database initialized at {DATABASE}")
