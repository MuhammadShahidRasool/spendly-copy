"""Tests for database queries and /profile route."""

import time

import pytest
from flask import session

from database.db import get_db
from database.queries import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #


def get_seed_user_id():
    """Return the ID of the demo user inserted by seed_db()."""
    db = get_db()
    try:
        row = db.execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()
        return row["id"] if row else None
    finally:
        db.close()


def create_user(name, email=None):
    """Insert a user with no expenses and return their ID.

    If email is omitted, a unique one is generated automatically.
    """
    if email is None:
        email = f"{name.lower().replace(' ', '_')}_{int(time.time() * 1e6)}@test.com"

    db = get_db()
    try:
        db.execute(
            "INSERT INTO users (name, email, password_hash, created_at) "
            "VALUES (?, ?, ?, ?)",
            (name, email, "dummyhash", "2026-06-01 08:00:00"),
        )
        db.commit()
        return db.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        db.close()


# ------------------------------------------------------------------ #
# Unit tests — get_user_by_id                                         #
# ------------------------------------------------------------------ #


class TestGetUserById:
    def test_valid_user(self):
        user_id = get_seed_user_id()
        assert user_id is not None, "Seed user must exist"
        result = get_user_by_id(user_id)

        assert result is not None
        assert result["name"] == "Demo User"
        assert result["email"] == "demo@spendly.com"
        assert result["member_since"] == "July 2026"

    def test_nonexistent_user(self):
        result = get_user_by_id(99999)
        assert result is None


# ------------------------------------------------------------------ #
# Unit tests — get_summary_stats                                       #
# ------------------------------------------------------------------ #


class TestGetSummaryStats:
    def test_with_expenses(self):
        user_id = get_seed_user_id()
        assert user_id is not None
        result = get_summary_stats(user_id)

        assert result["total_spent"] == 515.49
        assert result["transaction_count"] == 8
        assert result["top_category"] == "Food"

    def test_no_expenses(self):
        user_id = create_user("Empty User")
        result = get_summary_stats(user_id)

        assert result["total_spent"] == 0
        assert result["transaction_count"] == 0
        assert result["top_category"] == "—"


# ------------------------------------------------------------------ #
# Unit tests — get_recent_transactions                                  #
# ------------------------------------------------------------------ #


class TestGetRecentTransactions:
    def test_with_expenses(self):
        user_id = get_seed_user_id()
        assert user_id is not None
        result = get_recent_transactions(user_id)

        assert len(result) == 8

        # Verify newest-first order
        dates = [r["date"] for r in result]
        assert dates == sorted(dates, reverse=True)

        # Check shape of each item
        for item in result:
            assert "date" in item
            assert "description" in item
            assert "category" in item
            assert "amount" in item

        # Spot-check a known row
        assert result[0]["description"] == "Dinner at Olive Tree"
        assert result[0]["amount"] == 55.00

    def test_no_expenses(self):
        user_id = create_user("Empty User 2")
        result = get_recent_transactions(user_id)
        assert result == []


# ------------------------------------------------------------------ #
# Unit tests — get_category_breakdown                                   #
# ------------------------------------------------------------------ #


class TestGetCategoryBreakdown:
    def test_with_expenses(self):
        user_id = get_seed_user_id()
        assert user_id is not None
        result = get_category_breakdown(user_id)

        assert len(result) == 7

        # Ordered by amount descending
        amounts = [c["amount"] for c in result]
        assert amounts == sorted(amounts, reverse=True)

        # All percentages sum to 100
        total_pct = sum(c["pct"] for c in result)
        assert total_pct == 100

        # Spot-check first (largest) category
        assert result[0]["name"] == "Food"
        assert result[0]["amount"] == 140.50

    def test_no_expenses(self):
        user_id = create_user("Empty User 3")
        result = get_category_breakdown(user_id)
        assert result == []


# ------------------------------------------------------------------ #
# Route tests — GET /profile                                           #
# ------------------------------------------------------------------ #


class TestProfileRoute:
    def test_unauthenticated_redirect(self, client):
        """Visiting /profile while logged out redirects to /login."""
        resp = client.get("/profile", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.location == "/login"

    def test_authenticated_as_seed_user(self, client):
        """Visiting /profile as seed user shows correct data."""
        user_id = get_seed_user_id()
        assert user_id is not None

        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["user_name"] = "Demo User"

        resp = client.get("/profile")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")

        # User info
        assert "Demo User" in body
        assert "demo@spendly.com" in body

        # ₹ symbol (template uses "Rs")
        assert "Rs" in body

        # Stats
        assert "515.49" in body
        assert "8" in body
        assert "Food" in body

        # Transaction amounts visible
        assert "120.00" in body
        assert "55.00" in body

        # Category breakdown — all 7 categories present
        for cat in ("Food", "Bills", "Shopping", "Transport", "Health",
                    "Entertainment", "Other"):
            assert cat in body

    def test_new_user_no_expenses(self, client):
        """A newly registered user with no expenses sees zeros."""
        uid = create_user("Fresh User")
        with client.session_transaction() as sess:
            sess["user_id"] = uid
            sess["user_name"] = "Fresh User"

        resp = client.get("/profile")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")

        assert "Rs 0.00" in body
        # Template shows "0" for transaction_count
        # Top category is em dash: —
        assert "—" in body
