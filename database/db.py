import sqlite3
import os

from werkzeug.security import generate_password_hash


DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "spendly.db")


def get_db():
    """Open a connection to spendly.db with dict-like row access and FK enforcement."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables using CREATE TABLE IF NOT EXISTS. Safe to call repeatedly."""
    conn = get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                date TEXT NOT NULL,
                description TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
    finally:
        conn.close()


def create_user(name, email, password):
    """Hash password with werkzeug, insert user row, return new user id.

    Raises sqlite3.IntegrityError if the email is already taken (UNIQUE constraint).
    """
    password_hash = generate_password_hash(password)
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, password_hash),
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()


def seed_db():
    """Insert demo user and sample expenses if the users table is empty.

    Safe to call multiple times — checks for existing data first.
    """
    conn = get_db()
    try:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()
        if row["cnt"] > 0:
            return  # already seeded

        password_hash = generate_password_hash("demo123")
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Demo User", "demo@spendly.com", password_hash),
        )
        user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        expenses = [
            (user_id, 85.50, "Food", "2026-07-03", "Weekly grocery run"),
            (user_id, 65.00, "Transport", "2026-07-01", "Monthly bus pass"),
            (user_id, 120.00, "Bills", "2026-07-05", "Electricity bill"),
            (user_id, 45.00, "Health", "2026-07-08", "Pharmacy — vitamins"),
            (user_id, 30.00, "Entertainment", "2026-07-12", "Movie tickets"),
            (user_id, 89.99, "Shopping", "2026-07-15", "New running shoes"),
            (user_id, 25.00, "Other", "2026-07-18", "Birthday gift wrap"),
            (user_id, 55.00, "Food", "2026-07-20", "Dinner at Olive Tree"),
        ]
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            expenses,
        )
        conn.commit()
    finally:
        conn.close()
