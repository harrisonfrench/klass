# PROJECT_STRUCTURE.md

## File Organization Principles

### 1) Blueprint-Centric Organization
- **All functionality for a feature area goes in its blueprint**
- Example: `runners` blueprint contains add, edit, delete, list operations
- No cross-blueprint functionality mixing

### 2) Required Directory Structure
```
starter-kit-f25/
├── app/
│   ├── __init__.py
│   ├── app_factory.py
│   ├── db_connect.py
│   ├── functions.py
│   ├── routes.py
│   ├── blueprints/
│   │   ├── example.py
│   │   ├── runners.py
│   │   └── events.py
│   ├── static/
│   │   └── assets/
│   └── templates/
│       ├── base.html
│       ├── index.html
│       ├── about.html
│       └── [feature].html
├── database/
│   ├── schema.sql
│   ├── seed_data.sql
│   └── README.md
├── docs/
│   ├── code_review.md
│   ├── create_brief.md
│   ├── plan_feature.md
│   └── write_docs.md
├── .env.example
├── .gitignore
├── app.py
├── Procfile
├── CLAUDE_RULES.md
├── PROJECT_STRUCTURE.md
└── requirements.txt
```

### 3) Blueprint Structure Rules
- Each blueprint = one `.py` file named after the feature (e.g., `runners.py`, `events.py`)
- All CRUD operations for that area stay within the single blueprint file
- Each blueprint gets one main template file (e.g., `runners.html`) with modals for forms
- Blueprint static files (if any) go in `app/static/[blueprint_name]/`

### 4) Documentation & Prompts
- `/docs/` folder contains reusable Claude Code prompts for common tasks
- `code_review.md` - prompt for reviewing code quality
- `create_brief.md` - prompt for creating project briefs  
- `plan_feature.md` - prompt for planning new features
- `write_docs.md` - prompt for generating documentation

### 5) What NOT to Change
- **Never** move files between blueprints
- **Never** create cross-blueprint dependencies
- **Never** reorganize the core app structure
- **Never** change the database/ or docs/ directory structures
- **Never** modify the root-level file organization

### 6) Template Organization
```
app/templates/
├── base.html (shared layout)
├── index.html (homepage)
├── about.html (general pages)
├── runners.html (single template with modals for add/edit)
├── events.html (single template with modals)
└── examples.html (existing example)
```

**Note: Prefer using modals for add/edit forms rather than separate pages/templates. This keeps the UI streamlined and reduces template file count.**

### 7) Adding New Features
- Create new blueprint file `app/blueprints/[feature].py`
- Register blueprint in `app/__init__.py`
- Create single template file `app/templates/[feature].html` with modals
- All feature functionality stays within its single blueprint file

## Enforcement
- This structure is **mandatory** and should never be changed
- Focus on functionality within existing structure
- Ask before suggesting any structural modifications