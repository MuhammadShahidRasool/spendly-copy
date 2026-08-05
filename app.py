import math
import os
import secrets
import sqlite3
from datetime import datetime

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    abort,
)
from werkzeug.security import check_password_hash

from database.db import get_db, init_db, seed_db, create_user, create_expense
from database.queries import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
    get_expense_by_id,
    update_expense,
)

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()

with app.app_context():
    init_db()
    seed_db()

def _validate_date(date_str):
    """Return a canonical YYYY-MM-DD string if date_str is a valid date, else None.

    Callers decide how to treat None: the profile filter silently ignores it,
    the add-expense form rejects it with an inline error. Unpadded input such
    as "2026-1-5" is normalized to "2026-01-05" so stored dates always sort
    lexicographically for date-range filtering.
    """
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def _get_csrf_token():
    """Return a per-session CSRF token, generating one on first use.

    The token lives in the session so a logged-in user's browser must
    include it to mutate data. Prevents cross-site request forgery on the
    expense POST — a malicious page can't forge a valid token.
    """
    token = session.get("csrf_token")
    if token is None:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def _csrf_protect():
    """Reject a POST whose CSRF token doesn't match the session's.

    Called by write routes; renders 400 for missing/mismatched tokens.
    """
    submitted = request.form.get("csrf_token", "")
    expected = session.get("csrf_token", "")
    if not submitted or not expected or not secrets.compare_digest(submitted, expected):
        abort(400)


EXPENSE_CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not email or not password or not confirm_password:
            return render_template(
                "register.html", error="All fields are required."
            )

        if password != confirm_password:
            return render_template(
                "register.html", error="Passwords do not match."
            )

        if len(password) < 8:
            return render_template(
                "register.html",
                error="Password must be at least 8 characters.",
            )

        try:
            create_user(name, email, password)
            flash("Account created successfully! Please sign in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            return render_template(
                "register.html",
                error="An account with this email already exists.",
            )

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            return render_template("login.html", error="Please fill in all fields.")

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
        db.close()

        if user is None or not check_password_hash(user["password_hash"], password):
            return render_template(
                "login.html", error="Invalid email or password."
            )

        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        return redirect(url_for("profile"))

    return render_template("login.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.")
    return redirect(url_for("landing"))

@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user_id = session["user_id"]
    user = get_user_by_id(user_id)

    if user is None:
        session.clear()
        flash("User not found. Please sign in again.")
        return redirect(url_for("login"))

    user["initials"] = user["name"][0] if user["name"] else "?"

    # --- Date filter ---
    raw_start = request.args.get("start_date")
    raw_end = request.args.get("end_date")
    start_date = _validate_date(raw_start)
    end_date = _validate_date(raw_end)

    stats = get_summary_stats(user_id, start_date, end_date)
    transactions = get_recent_transactions(user_id, start_date=start_date, end_date=end_date)
    raw_categories = get_category_breakdown(user_id, start_date, end_date)
    categories = [
        {"name": c["name"], "total": c["amount"], "percentage": c["pct"]}
        for c in raw_categories
    ]

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
        filter_start=raw_start if start_date else "",
        filter_end=raw_end if end_date else "",
    )

@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    return render_template("analytics.html")


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    if request.method == "POST":
        _csrf_protect()

        amount_raw = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        date_raw = request.form.get("date", "").strip()
        description = request.form.get("description", "").strip()

        error = None
        amount = None
        try:
            amount = float(amount_raw)
        except (ValueError, TypeError):
            error = "Please enter a valid amount."

        if error is None and (amount <= 0 or not math.isfinite(amount)):
            error = "Amount must be greater than zero."

        if not category:
            error = "Please select a category."
        elif category not in EXPENSE_CATEGORIES:
            error = "Please select a valid category."

        if not date_raw:
            error = "Please enter a date."
        elif _validate_date(date_raw) is None:
            error = "Please enter a valid date (YYYY-MM-DD)."

        if error is None:
            create_expense(
                session["user_id"],
                amount,
                category,
                _validate_date(date_raw),
                description or None,
            )
            flash("Expense added successfully!", "success")
            return redirect(url_for("profile"))

        return render_template(
            "add_expense.html",
            error=error,
            categories=EXPENSE_CATEGORIES,
            csrf_token=_get_csrf_token(),
            form_amount=amount_raw,
            form_category=category,
            form_date=date_raw,
            form_description=description,
        )

    return render_template(
        "add_expense.html", categories=EXPENSE_CATEGORIES, csrf_token=_get_csrf_token()
    )

@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    expense = get_expense_by_id(id, session["user_id"])
    if expense is None:
        abort(404)

    error = None
    if request.method == "POST":
        _csrf_protect()

        amount_raw = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        date_raw = request.form.get("date", "").strip()
        description = request.form.get("description", "").strip()

        amount = None
        try:
            amount = float(amount_raw)
        except (ValueError, TypeError):
            error = "Please enter a valid amount."

        if error is None and (amount <= 0 or not math.isfinite(amount)):
            error = "Amount must be greater than zero."

        if not category:
            error = "Please select a category."
        elif category not in EXPENSE_CATEGORIES:
            error = "Please select a valid category."

        if not date_raw:
            error = "Please enter a date."
        elif _validate_date(date_raw) is None:
            error = "Please enter a valid date (YYYY-MM-DD)."

        if error is None:
            update_expense(
                id,
                session["user_id"],
                amount,
                category,
                _validate_date(date_raw),
                description or None,
            )
            flash("Expense updated successfully!", "success")
            return redirect(url_for("profile"))

    if request.method == "GET":
        form_amount = f"{expense['amount']:.2f}"
        form_category = expense["category"]
        form_date = expense["date"]
        form_description = expense["description"] or ""
    else:
        form_amount = amount_raw
        form_category = category
        form_date = date_raw
        form_description = description

    return render_template(
        "edit_expense.html",
        expense=expense,
        error=error,
        categories=EXPENSE_CATEGORIES,
        csrf_token=_get_csrf_token(),
        form_amount=form_amount,
        form_category=form_category,
        form_date=form_date,
        form_description=form_description,
    )

@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"

if __name__ == "__main__":
    app.run(debug=True, port=5001)
