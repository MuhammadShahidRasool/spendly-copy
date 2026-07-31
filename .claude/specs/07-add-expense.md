# Spec: Add Expense

## Overview

The Add Expense feature turns the `GET /expenses/add` stub into a full GET/POST form page where a logged-in user records a new expense (amount, category, date, optional description). This is the first write path into the `expenses` table — up to now expenses only exist via `seed_db()` and the `seed_expenses.py` CLI script. It gives the tracker a primary input surface: a user signs up (Step 2), logs in (Step 3), sees their dashboard (Steps 4–6), and can now add a real expense that immediately appears in their profile's stats, transaction table, and category breakdown.

## Depends on

- **Step 1 (Database Setup)** — provides `get_db()`, `init_db()`, `seed_db()`, and the `expenses` table schema
- **Step 3 (Login and Logout)** — provides session-based auth (`session["user_id"]`) that this route guards on
- **Steps 4–6 (Profile Page)** — provides the profile page that new expenses must appear on

## Routes

- `GET /expenses/add` — render the add-expense form — **logged-in**
- `POST /expenses/add` — validate input, insert the expense, redirect to profile — **logged-in**

## Database changes

No new tables or columns. Add a new helper to `database/db.py`:

- `create_expense(user_id, amount, category, date, description)` — parameterized `INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)`, following the existing `create_user()` pattern (open `get_db()`, try/finally, commit, close, return `last_insert_rowid()`). `description` may be `None`.

## Templates

**Create:** `templates/add_expense.html` — extends `base.html`, overrides `title` and `content`; contains a POST form with fields for amount, category, date, and description, using the existing `.form-group` / `.form-input` / `.btn-submit` classes and the `{% if error %}` context-variable error pattern from `register.html`. Category is a `<select>` with the fixed 7-category list (Food, Transport, Bills, Health, Entertainment, Shopping, Other).

**Modify:** `templates/base.html` — optionally add an "Add expense" link/button in the logged-in navbar or on the profile page so the form is reachable (use `url_for('add_expense')`).

## Files to change

- `app.py` — replace the `add_expense` stub with a GET/POST route
- `database/db.py` — add `create_expense()` helper
- `templates/base.html` — optional nav link to the add-expense form

## Files to create

- `templates/add_expense.html`
- `static/css/add_expense.css` — page-specific styles (per CLAUDE.md: page-specific styles go in a new `.css` file, not inline `<style>`)
- `.claude/specs/07-add-expense.md` (this spec)

## New dependencies

No new dependencies.

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders) — never f-strings in SQL
- Passwords hashed with werkzeug (n/a for this feature, but keep the convention)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Never hardcode URLs in templates — always use `url_for('add_expense')`
- Never put DB logic in route functions — the INSERT belongs in `create_expense()` in `database/db.py`
- No new pip packages; vanilla JS only
- Category values must match the fixed list from Step 1: Food, Transport, Bills, Health, Entertainment, Shopping, Other

## Definition of done

- [ ] `GET /expenses/add` while logged out redirects to the login page
- [ ] `GET /expenses/add` while logged in renders `add_expense.html` with amount, category, date, and description fields (description optional)
- [ ] Submitting a valid expense (amount, category, valid YYYY-MM-DD date) redirects to the profile page and flashes a success message
- [ ] A newly added expense appears in the profile page's recent transactions and summary stats (total spent reflects the new amount)
- [ ] The submitted date is validated; an invalid date is rejected with an inline error and no DB row is written
- [ ] Empty/invalid amount and missing category are rejected with an inline error and no DB row is written
- [ ] The inserted row in `spendly.db` has the correct `user_id`, `amount`, `category`, `date`, and `description` (null when omitted)
- [ ] No hardcoded URLs in `add_expense.html` — the form action uses `url_for('add_expense')`
