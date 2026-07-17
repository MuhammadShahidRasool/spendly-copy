Spec: Login and Logout
## Overview
This feature implements user authentication — the ability to sign in with registered credentials and sign out. After users can create an account (Step 2), they need a way to authenticate and start an application session. Login validates email/password against the users table, creates a Flask session cookie, and redirects to the dashboard. Logout clears the session and returns the user to the landing page. The navbar updates to show the logged-in user's name and a logout link instead of "Sign in" and "Get started".

## Depends on
- Step 1 (Database Setup) — users table with email and password_hash columns
- Step 2 (Registration) — users can create accounts

## Routes
- `POST /login` — validate credentials, start session — public
- `GET /logout` — clear session, redirect to landing — logged-in

The existing `GET /login` route (already implemented) renders the login form.

## Database changes
No database changes needed. The `users` table already has `email`, `password_hash`, and `name` columns — sufficient for authentication.

## Templates
Create: none
Modify:
- `base.html` — conditionally show logged-in nav (user name + logout link) or logged-out nav (Sign in + Get started)

## Files to change
- `app.py` — add POST handler for `/login`; implement `/logout`; add SECRET_KEY and session imports
- `templates/base.html` — conditional navbar based on login state

## Files to create
None

## New dependencies
No new dependencies. Uses:
- `flask.session` (built-in)
- `flask.request` (built-in)
- `werkzeug.security.check_password_hash` (already installed)

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed/checked with werkzeug
- Use CSS variables — never hardcode hex values
- All templates extend base.html
- Use `url_for()` for every internal link — never hardcode URLs
- DB queries belong in route handlers or `database/db.py` — prefer inline parameterised queries in route for auth logic
- Session keys must use a strong SECRET_KEY (use `os.urandom(24)` or a fixed dev key)

## Definition of done
1. `GET /login` renders the login form (already works)
2. `POST /login` with valid demo credentials (`demo@spendly.com` / `demo123`) redirects to the dashboard (or profile page)
3. `POST /login` with invalid credentials shows an error message on the login page
4. After login, the navbar shows the user's name and a "Sign out" link instead of "Sign in" / "Get started"
5. Clicking "Sign out" clears the session and redirects to landing
6. After logout, the navbar reverts to the logged-out state
7. `GET /dashboard` does not exist yet (will be Step 5) — login redirects to `/` landing for now
8. No raw string returns — all routes render templates or redirect
