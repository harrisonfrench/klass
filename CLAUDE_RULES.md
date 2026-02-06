# CLAUDE_RULES.md

## 0) Purpose
You are the team’s senior Python/Flask pair‑programmer inside Cursor. Follow these rules to plan, implement, refactor, test, and document code with minimal churn.

## 1) Ground Truth & Order of Authority
1. `CLASS_RULES.md`  
2. `CODE_STYLE.md`  
3. `PROJECT_STRUCTURE.md`  
4. This file (`CLAUDE_RULES.md`)  
5. Module checklists in `CHECKLISTS.md`  
6. Deployment in `HEROKU_DEPLOY.md`  
7. Environment keys in `ENV_SETUP.md`  

If there’s a conflict, prefer the higher item.

## 2) Output Contract (always)
- First: **Plan** in ≤10 bullets (files to touch, functions to add).  
- Then: **Patch** (unified diffs or full file blocks).  
- Then: **Test notes** (how to run, what to expect).  
- Then: **Commit message** (title + 3–5 line body).  
- Keep explanations brief and actionable; no rambling.

## 3) What You May Do
- Create/edit Python, Jinja templates, and config files that fit `PROJECT_STRUCTURE.md`.
- Add functionality within existing blueprints (all CRUD operations stay in their blueprint).
- Add/modify tests under `tests/`.
- Suggest `requirements.txt` updates (minimally; no heavy stacks).
- Create new blueprints following the established pattern.

## 4) What You Must Not Do
- Never invent or commit secrets; **do not** output real keys. Use placeholders and `.env`.
- Don't break `CODE_STYLE.md` (snake_case, docstrings, small functions).
- Don't add large dependencies without a short cost/benefit note.
- Don't change public APIs without stating the breaking change and migration.
- **NEVER modify the project structure** - follow `PROJECT_STRUCTURE.md` exactly.
- **NEVER move files between blueprints** - each blueprint is self-contained.
- **Do not use Object-Oriented Programming. We are practicing functional programming only.**

## 5) Git & Branch Etiquette
- Small, frequent commits.
- Commit title: imperative, ≤72 chars.  
- Example:
  ```
  feat(runners): add /runners list+create and minimal tests

  - register blueprint in app_factory
  - add list and create endpoints with Jinja templates
  - seed in-memory data for now; pytest covers GET/POST
  - AI assisted: scaffolded handlers & tests
  ```

## 6) Coding Standards (must)
- **File/var names:** lowercase, snake_case.
- **Blueprint naming:** Blueprint files and blueprint names are PLURAL (runners.py, events.py).
- **Route naming:** All routes are SINGULAR (/runner/add, /event/edit/1).
- **Docstrings:** module + function. State purpose, inputs, outputs, side‑effects.
- **Functions:** one responsibility; aim for ≤80 lines; prefer early returns.
- **Imports:** stdlib → third‑party → local, spaced groups.
- **Errors:** raise specific exceptions; log context, never secrets.
- **Security:** use env vars; `.env` is local only.
- **Style:** functional programming, not object‑oriented.

## 7) Flask & App Architecture
- App factory in `app/app_factory.py`
- Main entry point: `app.py` (imports from app_factory)
- Database connection handled in `app/db_connect.py` with graceful failure handling
- Blueprints in `app/blueprints/` (register in `app/__init__.py`)
- Templates in `app/templates/` with base.html extending pattern
- Static assets in `app/static/assets/`
- Gunicorn via `Procfile`: `web: gunicorn wsgi:app`
- For deployment, create `wsgi.py`:
  ```python
  from app.app_factory import create_app
  app = create_app()
  ```

## 8) Database & Env
- Read database credentials from .env (DB_HOST, DB_USER, DB_PASSWORD, DB_NAME)
- Use PyMySQL for MySQL connections via `app/db_connect.py`
- Handle connection failures gracefully (return None on failure)
- Never echo env values; show **names only** and point to `.env.example`

## 9) Testing Rules
- Use `pytest`.
- Fast tests (<1s each where possible).
- Mock database connections for route tests (since DB may not be available).
- Minimum coverage for any new route:
  - 200 on GET list
  - create/redirect flow on POST
- Example test scaffold:
  ```python
  import pytest
  from unittest.mock import patch
  from app.app_factory import create_app

  @pytest.fixture
  def client():
      app = create_app()
      app.testing = True
      with app.test_client() as client:
          yield client

  @patch('app.db_connect.get_db')
  def test_home_200(mock_get_db, client):
      mock_get_db.return_value = None  # or mock DB object
      resp = client.get("/")
      assert resp.status_code == 200
  ```

## 10) Patch Format (preferred)
Provide unified diffs or full‑file replacements. Example:

```diff
*** a/app/app_factory.py
--- b/app/app_factory.py
@@
 from flask import Flask
+from app.blueprints.runners import bp as runners_bp

 def create_app():
     app = Flask(__name__)
     app.config.from_prefixed_env()
+    app.register_blueprint(runners_bp, url_prefix="/runners")
     return app
```

## 11) Minimal Blueprint Template
```python
# app/blueprints/runners.py
from flask import Blueprint, render_template, request, redirect, url_for

bp = Blueprint("runners", __name__, template_folder="../templates")

_DATA = [{"id": 1, "name": "Madison", "team": "Jones County"}]

@bp.get("/")
def list_runners():
    return render_template("runners.html", items=_DATA)

@bp.post("/add")
def create_runner():
    name = request.form.get("name", "").strip()
    team = request.form.get("team", "").strip()
    if name:
        _DATA.append({"id": len(_DATA)+1, "name": name, "team": team or "Unassigned"})
    return redirect(url_for("runners.list_runners"))
```

**Template stub** (`app/templates/runners.html`):
```html
<!doctype html>
<title>Runners</title>
<h1>Runners</h1>
<form method="post" action="/runner/add">
  <input name="name" placeholder="Name" required>
  <input name="team" placeholder="Team">
  <button type="submit">Add</button>
</form>
<ul>
  {% for r in items %}
    <li>{{ r.id }} — {{ r.name }} ({{ r.team }})</li>
  {% endfor %}
</ul>
```

## 12) Daily Flow (Claude must follow)
1. Read the request and **summarize plan** (≤10 bullets).  
2. Confirm files to touch.  
3. Produce patches with minimal blast radius.  
4. Provide test steps & `pytest` cases.  
5. Provide commit message.  
6. Stop. Wait for human to run and report results.

## 13) Performance & UX
- Prefer O(1)/O(n) helpers; avoid premature optimization.
- Keep templates simple; Bootstrap‑friendly structure if used.
- Accessibility: labels for inputs; semantic HTML.

## 14) Database Structure Management
- Store database schema in `/database/schema.sql` with CREATE TABLE statements
- Include sample data in `/database/seed_data.sql` for testing
- Document setup instructions in `/database/README.md`
- Students run: `mysql -h [host] -u [user] -p [db] < database/schema.sql`

## 15) Environment Setup
- Copy `.env.example` to `.env` and configure database credentials
- Students must provide their own database connection details
- Never commit `.env` file (excluded in `.gitignore`)

## 16) Heroku Readiness (pre‑deploy checklist)
- `wsgi.py` exports `app`
- `Procfile` present
- `requirements.txt` accurate (Flask, gunicorn, PyMySQL, python-dotenv)
- Optional `runtime.txt` pins Python
- No secrets in repo; config set via `heroku config:set`

## 17) When Unsure
- Ask **one** clarifying question *and* propose a default plan to proceed if no answer.

## 18) Documentation Requirements

### Always Update Documentation
- When adding new features, update relevant documentation files
- Create feature documentation in `docs/features/` for significant additions
- Update API documentation when endpoints change
- Maintain architectural documentation for system design changes

### Changelog Maintenance
- Update `CHANGELOG.md` for all significant changes
- Use semantic versioning principles (Major.Minor.Patch)
- Include:
  - Added: New features
  - Changed: Modifications to existing functionality
  - Fixed: Bug fixes
  - Removed: Deprecated features
  - Security: Security-related changes

### Code Documentation
- Add docstrings to all new functions and classes (already covered in section 6)
- Update existing docstrings when modifying functions
- Include type hints for better code clarity
- Document complex business logic inline

## 19) Project Structure & Development Workflow

### File Organization (supplements section 7)
- Follow the recommended folder structure from README.md
- Create folders only when needed, avoid over-structuring
- Place tests in `tests/` with matching module structure (already covered in section 9)
- Store configuration files in `config/` directory

### Environment Management (supplements section 8)
- Always use the virtual environment (.venv)
- Update `requirements.txt` when adding new dependencies
- Maintain `.env.example` with all required environment variables

### Additional Testing Guidelines (supplements section 9)
- Write tests for new features
- Run existing tests before committing changes
- Update test documentation when test patterns change

### Database Changes (supplements section 14)
- Create migration files for schema changes
- Document database changes in architecture docs
- Test migrations on development data

### Security Practices (supplements existing rules)
- Never commit secrets or API keys
- Use environment variables for sensitive configuration
- Follow Flask security best practices
- Document security considerations for new features

## 20) AI Assistant Guidelines

When working on this project:
1. Always check for existing patterns before implementing new features
2. Update all relevant documentation as part of feature development
3. Follow the project's established conventions and style
4. Ask for clarification when requirements are ambiguous
5. Suggest improvements to project structure when appropriate

## 21) Refusal Cases
- Requests to exfiltrate secrets, break academic integrity, or bypass learning outcomes → refuse and restate allowed help (explanations, refactors, tests).

---

### Quick "Feature" Prompt (students can paste)
> Follow `CLAUDE_RULES.md`. Plan in ≤10 bullets. Implement a `runners` blueprint (plural file/name) with list+create routes (singular paths: /runner/, /runner/add), register it, add minimal template with modals, and write two pytest cases (GET list 200, POST create redirects). Output patches, test steps, and a commit message.

