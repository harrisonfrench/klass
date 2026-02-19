import pymysql
from pymysql.cursors import DictCursor
from contextlib import contextmanager
from flask import g
import os


def get_db_config():
    """Get database configuration from environment variables."""
    return {
        'host': os.environ.get('DB_HOST', 'localhost'),
        'user': os.environ.get('DB_USER', 'root'),
        'password': os.environ.get('DB_PASSWORD', ''),
        'database': os.environ.get('DB_NAME', 'personalapp'),
        'port': int(os.environ.get('DB_PORT', 3306)),
        'charset': 'utf8mb4',
        'cursorclass': DictCursor,
        'autocommit': False
    }


class MySQLConnectionWrapper:
    """
    Wrapper around PyMySQL connection to provide sqlite3-like interface.
    This allows db.execute() to work directly like sqlite3.
    """
    def __init__(self, connection):
        self._conn = connection

    def execute(self, query, params=None):
        """Execute a query and return the cursor (like sqlite3)."""
        cursor = self._conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        # Store lastrowid on cursor for INSERT operations
        cursor.lastrowid = cursor.lastrowid
        return cursor

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()

    def cursor(self):
        return self._conn.cursor()


@contextmanager
def transaction(db):
    """
    Context manager for database transactions with automatic rollback on error.

    Usage:
        with transaction(db):
            db.execute('INSERT INTO ...')
            db.execute('UPDATE ...')
        # Commits automatically on success, rolls back on exception
    """
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        raise e


def get_db():
    """Get database connection, creating one if needed."""
    if 'db' not in g:
        config = get_db_config()
        conn = pymysql.connect(**config)
        g.db = MySQLConnectionWrapper(conn)
    return g.db


def close_db(exception=None):
    """Close database connection."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """Initialize the database with schema."""
    config = get_db_config()
    db = pymysql.connect(**config)
    cursor = db.cursor()

    # Create users table first (for authentication)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INT PRIMARY KEY AUTO_INCREMENT,
            email VARCHAR(255) UNIQUE NOT NULL,
            username VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS classes (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT,
            name VARCHAR(255) NOT NULL,
            code VARCHAR(50),
            instructor VARCHAR(255),
            semester VARCHAR(50),
            color VARCHAR(20) DEFAULT '#0d6efd',
            description TEXT,
            syllabus_filename VARCHAR(255),
            d2l_course_url VARCHAR(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    # Create assignments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS assignments (
            id INT PRIMARY KEY AUTO_INCREMENT,
            class_id INT NOT NULL,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            due_date DATE,
            points INT,
            status VARCHAR(50) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE CASCADE
        )
    ''')

    # Create calendar_events table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS calendar_events (
            id INT PRIMARY KEY AUTO_INCREMENT,
            class_id INT NOT NULL,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            event_date DATE,
            event_type VARCHAR(50) DEFAULT 'other',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE CASCADE
        )
    ''')

    # Create notes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INT PRIMARY KEY AUTO_INCREMENT,
            class_id INT NOT NULL,
            title VARCHAR(255) NOT NULL DEFAULT 'Untitled',
            content LONGTEXT DEFAULT '',
            is_pinned TINYINT(1) DEFAULT 0,
            note_type VARCHAR(20) DEFAULT 'general',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE CASCADE
        )
    ''')

    # Add note_type column if it doesn't exist (for existing databases)
    try:
        cursor.execute('ALTER TABLE notes ADD COLUMN note_type VARCHAR(20) DEFAULT \'general\'')
        db.commit()
    except pymysql.err.OperationalError:
        pass  # Column already exists

    # Create flashcard decks table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS flashcard_decks (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT,
            class_id INT NOT NULL,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            card_count INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE CASCADE
        )
    ''')

    # Create flashcards table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS flashcards (
            id INT PRIMARY KEY AUTO_INCREMENT,
            deck_id INT NOT NULL,
            front TEXT NOT NULL,
            back TEXT NOT NULL,
            difficulty INT DEFAULT 0,
            times_reviewed INT DEFAULT 0,
            times_correct INT DEFAULT 0,
            last_reviewed TIMESTAMP NULL,
            next_review TIMESTAMP NULL,
            ease_factor DECIMAL(4,2) DEFAULT 2.5,
            `interval` INT DEFAULT 0,
            repetitions INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (deck_id) REFERENCES flashcard_decks (id) ON DELETE CASCADE
        )
    ''')

    # Create study guides table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS study_guides (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT,
            class_id INT NOT NULL,
            title VARCHAR(255) NOT NULL,
            content LONGTEXT,
            source_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE CASCADE
        )
    ''')

    # Create quizzes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quizzes (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT,
            class_id INT NOT NULL,
            title VARCHAR(255) NOT NULL,
            questions JSON,
            time_limit INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE CASCADE
        )
    ''')

    # Create quiz attempts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT,
            quiz_id INT NOT NULL,
            score INT,
            total INT,
            answers JSON,
            time_taken INT,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (quiz_id) REFERENCES quizzes (id) ON DELETE CASCADE
        )
    ''')

    # Create chat sessions table for AI tutor
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT NOT NULL,
            class_id INT,
            title VARCHAR(255) DEFAULT 'New Chat',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE SET NULL
        )
    ''')

    # Create chat messages table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INT PRIMARY KEY AUTO_INCREMENT,
            session_id INT NOT NULL,
            role VARCHAR(50) NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE
        )
    ''')

    # Create study sessions table for analytics
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS study_sessions (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT NOT NULL,
            class_id INT,
            activity_type VARCHAR(50) NOT NULL,
            duration INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE SET NULL
        )
    ''')

    # Create user settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT UNIQUE NOT NULL,
            theme VARCHAR(20) DEFAULT 'light',
            default_class_color VARCHAR(20) DEFAULT '#6366f1',
            ai_features_enabled TINYINT(1) DEFAULT 1,
            pomodoro_work_duration INT DEFAULT 25,
            pomodoro_short_break INT DEFAULT 5,
            pomodoro_long_break INT DEFAULT 15,
            pomodoro_sessions_until_long INT DEFAULT 4,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    # Create pomodoro sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pomodoro_sessions (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT NOT NULL,
            class_id INT,
            session_type VARCHAR(50) NOT NULL,
            duration INT NOT NULL,
            completed TINYINT(1) DEFAULT 0,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE SET NULL
        )
    ''')

    # Create user streaks table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_streaks (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT UNIQUE NOT NULL,
            current_streak INT DEFAULT 0,
            longest_streak INT DEFAULT 0,
            last_study_date DATE,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    # Create study goals table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS study_goals (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT NOT NULL,
            goal_type VARCHAR(50) NOT NULL,
            target_value INT NOT NULL,
            current_value INT DEFAULT 0,
            period_start DATE,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    # Create achievements table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS achievements (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT NOT NULL,
            achievement_type VARCHAR(100) NOT NULL,
            earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    # Create shared resources table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shared_resources (
            id INT PRIMARY KEY AUTO_INCREMENT,
            resource_type VARCHAR(50) NOT NULL,
            resource_id INT NOT NULL,
            owner_id INT NOT NULL,
            share_code VARCHAR(100) UNIQUE NOT NULL,
            is_public TINYINT(1) DEFAULT 0,
            allow_copy TINYINT(1) DEFAULT 1,
            view_count INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    # Create shared access log table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shared_access (
            id INT PRIMARY KEY AUTO_INCREMENT,
            shared_resource_id INT NOT NULL,
            user_id INT,
            access_type VARCHAR(50) NOT NULL,
            accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (shared_resource_id) REFERENCES shared_resources (id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
        )
    ''')

    # Create indexes for frequently queried columns (Performance optimization)
    # Use try/except to handle if index already exists
    indexes = [
        'CREATE INDEX idx_classes_user_id ON classes(user_id)',
        'CREATE INDEX idx_notes_class_id ON notes(class_id)',
        'CREATE INDEX idx_notes_updated_at ON notes(updated_at)',
        'CREATE INDEX idx_flashcard_decks_class_id ON flashcard_decks(class_id)',
        'CREATE INDEX idx_flashcards_deck_id ON flashcards(deck_id)',
        'CREATE INDEX idx_flashcards_next_review ON flashcards(next_review)',
        'CREATE INDEX idx_quizzes_class_id ON quizzes(class_id)',
        'CREATE INDEX idx_quiz_attempts_quiz_id ON quiz_attempts(quiz_id)',
        'CREATE INDEX idx_quiz_attempts_user_id ON quiz_attempts(user_id)',
        'CREATE INDEX idx_assignments_class_id ON assignments(class_id)',
        'CREATE INDEX idx_study_sessions_user_id ON study_sessions(user_id)',
        'CREATE INDEX idx_study_sessions_created_at ON study_sessions(created_at)',
        'CREATE INDEX idx_chat_sessions_user_id ON chat_sessions(user_id)',
        'CREATE INDEX idx_chat_messages_session_id ON chat_messages(session_id)',
    ]

    for index_sql in indexes:
        try:
            cursor.execute(index_sql)
        except pymysql.err.OperationalError:
            pass  # Index already exists

    db.commit()
    cursor.close()
    db.close()
    print(f"Database initialized on MySQL: {config['host']}/{config['database']}")
