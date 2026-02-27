import os
from datetime import timedelta
from flask import Flask, g
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from cachetools import TTLCache
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
from .app_factory import create_app
from .db_connect import close_db, get_db, init_db

# Initialize Sentry error monitoring (if DSN is configured)
sentry_dsn = os.environ.get('SENTRY_DSN')
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=[FlaskIntegration()],
        traces_sample_rate=0.1,  # 10% of requests for performance monitoring
        profiles_sample_rate=0.1,
        environment=os.environ.get('FLASK_ENV', 'development'),
        send_default_pii=False,  # Don't send PII to Sentry
    )

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
from app.blueprints.admin import admin
from app.blueprints.friends import friends
from app.blueprints.notifications import notifications

app.register_blueprint(auth, url_prefix='/auth')
app.register_blueprint(admin)
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
app.register_blueprint(friends, url_prefix='/friends')
app.register_blueprint(notifications, url_prefix='/notifications')

# Exempt beacon-save endpoint from CSRF (used by navigator.sendBeacon on page unload)
# This is safe because the endpoint still validates user session and note ownership
csrf.exempt(notes.name + '.beacon_save_note')

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

    # HSTS - Forces HTTPS, prevents downgrade attacks
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

    # Permissions Policy - Declares browser features used
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(self), camera=()'

    # Content Security Policy - Whitelists allowed resources
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' code.jquery.com cdn.jsdelivr.net cdnjs.cloudflare.com cdn.quilljs.com; "
        "style-src 'self' 'unsafe-inline' fonts.googleapis.com cdnjs.cloudflare.com cdn.jsdelivr.net cdn.quilljs.com; "
        "font-src 'self' fonts.gstatic.com cdnjs.cloudflare.com; "
        "img-src 'self' data: blob:; "
        "connect-src 'self' api.groq.com; "
        "media-src 'self' blob:; "
        "frame-ancestors 'self'"
    )

    return response


# Context processor to inject admin check into all templates
@app.context_processor
def inject_admin_check():
    from app.blueprints.admin import is_admin
    return {'is_admin': is_admin()}


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
            'SELECT id, name, code, color FROM classes WHERE user_id = %s ORDER BY name',
            (user_id,)
        )
        sidebar_classes = cursor.fetchall()

        # Cache the result
        sidebar_cache[cache_key] = sidebar_classes
        return {'sidebar_classes': sidebar_classes}
    except Exception:
        return {'sidebar_classes': []}


# Context processor to inject user theme and profile picture into all templates
@app.context_processor
def inject_user_settings():
    from flask import session
    try:
        if 'user_id' not in session:
            return {'user_theme': 'light', 'user_profile_picture': None}

        db = get_db()
        cursor = db.execute(
            'SELECT theme, profile_picture FROM user_settings WHERE user_id = %s',
            (session['user_id'],)
        )
        settings = cursor.fetchone()
        theme = settings['theme'] if settings and settings.get('theme') else 'light'
        profile_picture = settings.get('profile_picture') if settings else None
        return {'user_theme': theme, 'user_profile_picture': profile_picture}
    except Exception:
        return {'user_theme': 'light', 'user_profile_picture': None}
