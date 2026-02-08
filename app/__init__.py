import os
from flask import Flask, g
from .app_factory import create_app
from .db_connect import close_db, get_db, init_db

app = create_app()
app.secret_key = 'your-secret'  # Replace with an environment variable

# Configure uploads
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads', 'syllabi')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

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

app.register_blueprint(auth, url_prefix='/auth')
app.register_blueprint(ai_chat, url_prefix='/ai-tutor')
app.register_blueprint(settings, url_prefix='/settings')
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


# Context processor to inject sidebar classes into all templates
@app.context_processor
def inject_sidebar_classes():
    from flask import session
    try:
        if 'user_id' not in session:
            return {'sidebar_classes': []}
        db = get_db()
        cursor = db.execute(
            'SELECT id, name, code, color FROM classes WHERE user_id = ? ORDER BY name',
            (session['user_id'],)
        )
        sidebar_classes = cursor.fetchall()
        return {'sidebar_classes': sidebar_classes}
    except Exception:
        return {'sidebar_classes': []}
