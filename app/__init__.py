import os
from datetime import timedelta
from flask import Flask, g
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from cachetools import TTLCache
from .app_factory import create_app
from .db_connect import close_db, get_db, init_db

app = create_app()

# Security: Secret key from environment variable
app.secret_key = os.environ.get('SECRET_KEY')
if not app.secret_key:
    raise RuntimeError("SECRET_KEY environment variable is required. Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\"")

# Security: CSRF protection
csrf = CSRFProtect(app)

# Security: Rate limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

# Security: Secure session configuration
app.config.update(
    SESSION_COOKIE_SECURE=os.environ.get('FLASK_ENV') == 'production',  # HTTPS only in production
    SESSION_COOKIE_HTTPONLY=True,  # Prevent JavaScript access
    SESSION_COOKIE_SAMESITE='Lax',  # CSRF protection
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
)

# Configure uploads
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads', 'syllabi')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Performance: Simple in-memory cache for sidebar classes (5-minute TTL)
sidebar_cache = TTLCache(maxsize=1000, ttl=300)

# Initialize database
init_db()

# Register Blueprints
from app.blueprints.examples import examples
from app.blueprints.classes import classes
from app.blueprints.notes import notes
from app.blueprints.flashcards import flashcards
from app.blueprints.study_guides import study_guides
from app.blueprints.quizzes import quizzes
from app.blueprints.auth import auth
from app.blueprints.ai_chat import ai_chat
from app.blueprints.settings import settings
from app.blueprints.analytics import analytics
from app.blueprints.pomodoro import pomodoro

app.register_blueprint(auth, url_prefix='/auth')
app.register_blueprint(pomodoro, url_prefix='/pomodoro')
app.register_blueprint(ai_chat, url_prefix='/ai-tutor')
app.register_blueprint(settings, url_prefix='/settings')
app.register_blueprint(analytics, url_prefix='/analytics')
app.register_blueprint(examples, url_prefix='/example')
app.register_blueprint(classes, url_prefix='/classes')
app.register_blueprint(notes, url_prefix='/notes')
app.register_blueprint(flashcards, url_prefix='/flashcards')
app.register_blueprint(study_guides, url_prefix='/study-guides')
app.register_blueprint(quizzes, url_prefix='/quizzes')

from . import routes

# Setup database connection teardown
@app.teardown_appcontext
def teardown_db(exception=None):
    close_db(exception)


# Security: Add security headers to all responses
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response


# Context processor to inject sidebar classes into all templates (with caching)
@app.context_processor
def inject_sidebar_classes():
    from flask import session
    try:
        if 'user_id' not in session:
            return {'sidebar_classes': []}

        user_id = session['user_id']
        cache_key = f"sidebar_{user_id}"

        # Check cache first
        if cache_key in sidebar_cache:
            return {'sidebar_classes': sidebar_cache[cache_key]}

        db = get_db()
        cursor = db.execute(
            'SELECT id, name, code, color FROM classes WHERE user_id = ? ORDER BY name',
            (user_id,)
        )
        sidebar_classes = cursor.fetchall()

        # Cache the result
        sidebar_cache[cache_key] = sidebar_classes
        return {'sidebar_classes': sidebar_classes}
    except Exception:
        return {'sidebar_classes': []}
