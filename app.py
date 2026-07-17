import sqlite3

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
import os

from database.db import get_db, init_db, seed_db, create_user

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()

with app.app_context():
    init_db()
    seed_db()


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

    user = {
        "name": "Demo User",
        "email": "demo@spendly.com",
        "initials": "D",
        "member_since": "July 2026",
    }

    stats = {
        "total_spent": 515.49,
        "transaction_count": 8,
        "top_category": "Food",
    }

    transactions = [
        {"date": "2026-07-20", "description": "Dinner at Olive Tree", "category": "Food", "amount": 55.00},
        {"date": "2026-07-18", "description": "Birthday gift wrap", "category": "Other", "amount": 25.00},
        {"date": "2026-07-15", "description": "New running shoes", "category": "Shopping", "amount": 89.99},
        {"date": "2026-07-12", "description": "Movie tickets", "category": "Entertainment", "amount": 30.00},
        {"date": "2026-07-08", "description": "Pharmacy — vitamins", "category": "Health", "amount": 45.00},
        {"date": "2026-07-05", "description": "Electricity bill", "category": "Bills", "amount": 120.00},
        {"date": "2026-07-03", "description": "Weekly grocery run", "category": "Food", "amount": 85.50},
        {"date": "2026-07-01", "description": "Monthly bus pass", "category": "Transport", "amount": 65.00},
    ]

    categories = [
        {"name": "Food", "total": 140.50, "percentage": 27},
        {"name": "Bills", "total": 120.00, "percentage": 23},
        {"name": "Shopping", "total": 89.99, "percentage": 17},
        {"name": "Transport", "total": 65.00, "percentage": 13},
        {"name": "Health", "total": 45.00, "percentage": 9},
        {"name": "Entertainment", "total": 30.00, "percentage": 6},
        {"name": "Other", "total": 25.00, "percentage": 5},
    ]

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
