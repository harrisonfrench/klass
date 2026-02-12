from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from app.db_connect import get_db
from app import limiter

auth = Blueprint('auth', __name__)


def login_required(f):
    """Decorator to require login for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    """Get the current logged-in user from the database."""
    if 'user_id' not in session:
        return None

    if not hasattr(g, 'current_user'):
        db = get_db()
        g.current_user = db.execute(
            'SELECT id, email, username, created_at FROM users WHERE id = ?',
            (session['user_id'],)
        ).fetchone()

    return g.current_user


@auth.before_app_request
def load_logged_in_user():
    """Load user info into g before each request."""
    g.user = get_current_user()


@auth.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")  # Prevent brute force attacks
def login():
    """Handle user login."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)

        error = None

        if not email:
            error = 'Email is required.'
        elif not password:
            error = 'Password is required.'

        if error is None:
            db = get_db()
            user = db.execute(
                'SELECT * FROM users WHERE email = ?',
                (email,)
            ).fetchone()

            if user is None:
                error = 'Invalid email or password.'
            elif not check_password_hash(user['password_hash'], password):
                error = 'Invalid email or password.'

        if error is None:
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']

            if remember:
                session.permanent = True

            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('dashboard'))

        flash(error, 'error')

    return render_template('auth/login.html')


@auth.route('/register', methods=['GET', 'POST'])
@limiter.limit("3 per minute")  # Prevent spam registrations
def register():
    """Handle user registration."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        error = None

        if not email:
            error = 'Email is required.'
        elif not username:
            error = 'Username is required.'
        elif len(username) < 3:
            error = 'Username must be at least 3 characters.'
        elif not password:
            error = 'Password is required.'
        elif len(password) < 6:
            error = 'Password must be at least 6 characters.'
        elif password != confirm_password:
            error = 'Passwords do not match.'

        if error is None:
            db = get_db()

            # Check if email already exists
            existing = db.execute(
                'SELECT id FROM users WHERE email = ?',
                (email,)
            ).fetchone()

            if existing:
                error = 'Email is already registered.'
            else:
                # Check if username already exists
                existing = db.execute(
                    'SELECT id FROM users WHERE username = ?',
                    (username,)
                ).fetchone()

                if existing:
                    error = 'Username is already taken.'

        if error is None:
            # Create the user
            db.execute(
                'INSERT INTO users (email, username, password_hash) VALUES (?, ?, ?)',
                (email, username, generate_password_hash(password))
            )
            db.commit()

            # Get the new user
            user = db.execute(
                'SELECT id, username FROM users WHERE email = ?',
                (email,)
            ).fetchone()

            # Create default settings for the user
            db.execute(
                'INSERT INTO user_settings (user_id) VALUES (?)',
                (user['id'],)
            )
            db.commit()

            # Log them in
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']

            flash('Welcome! Your account has been created.', 'success')
            return redirect(url_for('dashboard'))

        flash(error, 'error')

    return render_template('auth/register.html')


@auth.route('/logout')
def logout():
    """Handle user logout."""
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth.login'))


@auth.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit("3 per minute")  # Prevent abuse
def forgot_password():
    """Handle password reset request."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        if not email:
            flash('Please enter your email address.', 'error')
        else:
            db = get_db()
            user = db.execute(
                'SELECT id FROM users WHERE email = ?',
                (email,)
            ).fetchone()

            # Always show success message to prevent email enumeration
            flash('If an account exists with that email, you will receive password reset instructions.', 'success')
            # TODO: Implement actual email sending for password reset

    return render_template('auth/forgot_password.html')
