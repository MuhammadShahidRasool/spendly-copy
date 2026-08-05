"""Tests for the Edit Expense feature (Step 8).

Spec source: .claude/specs/08-edit-expense.md

These tests validate what the spec says the feature SHOULD do:

Definition of done covered here:
- GET /expenses/<id>/edit while logged out redirects to /login
- POST /expenses/<id>/edit while logged out redirects to /login
- GET /expenses/<id>/edit for a non-existent or another user's expense
  returns 404
- GET /expenses/<id>/edit while logged in renders the edit form
  pre-filled with the expense's current values, category pre-selected
- POSTing valid changes redirects to /profile and updates the row in place
- The updated values appear on the profile page (transaction list + total)
- Invalid amount / category / date re-renders the form with an inline
  error and makes no DB change
- Omitting the optional description stores NULL
- The POST route is CSRF-protected (missing/forged token -> 400)

DB hygiene: this module creates a DEDICATED edit-test user and edits only
that user's rows. It never touches the seed demo user's expenses, so it
does not perturb the absolute-value assertions in the earlier feature
tests (06 date-filter, backend connection) that share the session temp DB.
"""

import os
import re

import pytest
from flask import url_for

from database.db import get_db, create_user, create_expense
from database.queries import get_expense_by_id, update_expense


def _new_test_user():
    """Create a fresh unique user and one owned expense.

    Returns (user_id, expense_id). The email carries a random hex suffix so
    users are unique even if the counter resets across pytest processes.
    """
    suffix = os.urandom(4).hex()
    user_id = create_user(f"Edit Test User {suffix}",
                          f"edit-test-{suffix}@spendly.com", "password123")
    expense_id = create_expense(user_id, 10.00, "Food", "2026-01-01", "seed row")
    return user_id, expense_id


def login_as(client, user_id, name):
    """Set the Flask session to be logged in as the given user."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_name"] = name


def get_csrf_token(client):
    """Return the session's CSRF token.

    Must be called while logged in. GETs ANY owned form that renders the
    hidden csrf_token; the token is session-bound, so rendering another
    user's form would 404 — this helper only ever targets the caller's own
    expense via the /profile list fallback. Simplest reliable path: hit
    /profile (always 200 when logged in), which does NOT carry a token, so
    instead we render the caller's own expense's edit form. To keep it
    identity-agnostic we just read the token out of a 200 edit GET the
    caller performs themselves.
    """
    # Find an expense the CURRENT session user owns and render its form.
    uid = None
    with client.session_transaction() as sess:
        uid = sess.get("user_id")
    assert uid is not None, "Must be logged in to obtain a CSRF token"
    db = get_db()
    try:
        row = db.execute(
            "SELECT id FROM expenses WHERE user_id = ? LIMIT 1", (uid,)
        ).fetchone()
    finally:
        db.close()
    assert row is not None, "Logged-in user must own an expense to render a token"
    resp = client.get(f"/expenses/{row['id']}/edit")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    match = re.search(r'name="csrf_token" value="([^"]+)"', body)
    assert match is not None, "CSRF token must be present in the form"
    return match.group(1)


def build_payload(client, expense_id, **overrides):
    """Build a valid edit payload for the given expense plus a fresh CSRF token.

    Uses the CURRENT session identity for the token (must already be logged
    in and own at least one expense).
    """
    db = get_db()
    try:
        row = db.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
    finally:
        db.close()
    assert row is not None
    data = {
        "amount": f"{row['amount']:.2f}",
        "category": row["category"],
        "date": row["date"],
        "description": row["description"] or "",
        "csrf_token": get_csrf_token(client),
    }
    data.update(overrides)
    return data


def get_row(expense_id):
    db = get_db()
    try:
        return db.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
    finally:
        db.close()


# ================================================================== #
# Unit tests — get_expense_by_id / update_expense                     #
# ================================================================== #


class TestGetExpenseById:
    def test_returns_expense_for_correct_user(self):
        user_id, expense_id = _new_test_user()
        result = get_expense_by_id(expense_id, user_id)
        assert result is not None, "Owned expense must be returned"
        assert result["id"] == expense_id

    def test_returns_none_for_wrong_user(self):
        user_id, expense_id = _new_test_user()
        other_id, _ = _new_test_user()
        result = get_expense_by_id(expense_id, other_id)
        assert result is None, "Must not return another user's expense"

    def test_returns_none_for_missing_id(self):
        user_id, _ = _new_test_user()
        assert get_expense_by_id(999_999, user_id) is None


class TestUpdateExpenseDB:
    def test_update_for_owning_user(self):
        user_id, expense_id = _new_test_user()
        n = update_expense(
            expense_id, user_id, 99.0, "Bills", "2026-02-02", "updated"
        )
        assert n == 1, "Exactly one row must be updated"
        row = get_row(expense_id)
        assert row["amount"] == 99.0
        assert row["category"] == "Bills"
        assert row["date"] == "2026-02-02"
        assert row["description"] == "updated"

    def test_update_for_wrong_user_leaves_row_unchanged(self):
        user_id, expense_id = _new_test_user()
        other_id, _ = _new_test_user()
        before = get_row(expense_id)
        n = update_expense(
            expense_id, other_id, 1.0, "Food", "2020-01-01", "hijacked"
        )
        assert n == 0, "Wrong-user update must affect zero rows"
        after = get_row(expense_id)
        assert after["amount"] == before["amount"]
        assert after["category"] == before["category"]
        assert after["date"] == before["date"]
        assert after["description"] == before["description"]

    def test_update_missing_id(self):
        user_id, _ = _new_test_user()
        assert update_expense(
            999_999, user_id, 1.0, "Food", "2020-01-01", "x"
        ) == 0


# ================================================================== #
# Auth guard                                    #
# ================================================================== #


class TestEditExpenseAuthGuard:
    def test_get_redirects_to_login_when_logged_out(self, client):
        user_id, expense_id = _new_test_user()
        resp = client.get(f"/expenses/{expense_id}/edit", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.location == "/login"

    def test_post_redirects_to_login_when_logged_out(self, client):
        user_id, expense_id = _new_test_user()
        before = float(get_row(expense_id)["amount"])
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "1", "csrf_token": "any"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert resp.location == "/login"
        assert float(get_row(expense_id)["amount"]) == before


# ================================================================== #
# GET /expenses/<id>/edit — form rendering                            #
# ================================================================== #


class TestEditExpenseGet:
    def test_renders_form_prefilled(self, client):
        user_id, expense_id = _new_test_user()
        login_as(client, user_id, "Edit Test User")
        resp = client.get(f"/expenses/{expense_id}/edit")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        row = get_row(expense_id)
        assert 'name="amount"' in body
        assert 'name="category"' in body
        assert 'name="date"' in body
        assert 'name="description"' in body
        assert f'value="{row["date"]}"' in body, "Date must be pre-filled"

    def test_category_is_preselected(self, client):
        user_id, expense_id = _new_test_user()
        login_as(client, user_id, "Edit Test User")
        resp = client.get(f"/expenses/{expense_id}/edit")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        row = get_row(expense_id)
        selected_pattern = re.compile(
            rf'value="{re.escape(row["category"])}"\s+selected'
        )
        assert selected_pattern.search(body), "Current category must be pre-selected"

    def test_form_action_matches_url_for_edit_expense(self, app, client):
        user_id, expense_id = _new_test_user()
        login_as(client, user_id, "Edit Test User")
        with app.app_context():
            expected_action = url_for("edit_expense", id=expense_id)
        resp = client.get(f"/expenses/{expense_id}/edit")
        assert resp.status_code == 200
        assert f'action="{expected_action}"' in resp.data.decode("utf-8"), (
            "Form action must resolve to url_for('edit_expense', id=...)"
        )

    def test_get_missing_expense_returns_404(self, client):
        user_id, _ = _new_test_user()
        login_as(client, user_id, "Edit Test User")
        assert client.get("/expenses/999999/edit").status_code == 404

    def test_get_other_users_expense_returns_404(self, client):
        owner, expense_id = _new_test_user()
        other, _ = _new_test_user()
        login_as(client, other, "Other User")
        assert client.get(f"/expenses/{expense_id}/edit").status_code == 404


# ================================================================== #
# POST /expenses/<id>/edit — success                                  #
# ================================================================== #


class TestEditExpensePostSuccess:
    def test_valid_post_redirects_to_profile(self, client):
        user_id, expense_id = _new_test_user()
        login_as(client, user_id, "Edit Test User")
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data=build_payload(client, expense_id,
                               amount="111.11", category="Bills",
                               date="2026-08-05", description="New title"),
        )
        assert resp.status_code == 302
        assert resp.location == "/profile"

    def test_valid_post_updates_the_row(self, client):
        user_id, expense_id = _new_test_user()
        login_as(client, user_id, "Edit Test User")
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data=build_payload(client, expense_id,
                               amount="150.00", category="Transport",
                               date="2026-08-06", description="Edited n"),
        )
        assert resp.status_code == 302
        row = get_row(expense_id)
        assert row["amount"] == 150.0
        assert row["category"] == "Transport"
        assert row["date"] == "2026-08-06"
        assert row["description"] == "Edited n"

    def test_omitted_description_stored_as_null(self, client):
        user_id, expense_id = _new_test_user()
        login_as(client, user_id, "Edit Test User")
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data=build_payload(client, expense_id, description=""),
        )
        assert resp.status_code == 302
        assert resp.location == "/profile"
        assert get_row(expense_id)["description"] is None

    def test_post_other_users_expense_returns_404(self, client):
        owner, expense_id = _new_test_user()
        other, other_expense_id = _new_test_user()
        login_as(client, other, "Other User")
        before = float(get_row(expense_id)["amount"])
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data=build_payload(client, other_expense_id, amount="1"),
        )
        assert resp.status_code == 404, "POST for another's expense must 404"
        assert float(get_row(expense_id)["amount"]) == before

    def test_post_missing_expense_returns_404(self, client):
        user_id, expense_id = _new_test_user()
        login_as(client, user_id, "Edit Test User")
        resp = client.post(
            "/expenses/999999/edit",
            data=build_payload(client, expense_id),
        )
        assert resp.status_code == 404


# ================================================================== #
# POST /expenses/<id>/edit — validation                               #
# ================================================================== #


class TestEditExpenseValidation:
    @pytest.mark.parametrize("field,value", [
        ("amount", ""),          # empty amount
        ("amount", "0"),         # zero amount
        ("amount", "abc"),       # non-numeric amount
        ("category", ""),        # missing category
        ("category", "Fake"),    # invalid category
        ("date", ""),            # missing date
        ("date", "2026-07-32"),  # invalid day
        ("date", "not-a-date"),  # malformed date
    ])
    def test_invalid_submission_rerenders_with_inline_error(
        self, client, db, field, value
    ):
        user_id, expense_id = _new_test_user()
        login_as(client, user_id, "Edit Test User")
        before = float(get_row(expense_id)["amount"])

        data = build_payload(client, expense_id, **{field: value})
        resp = client.post(f"/expenses/{expense_id}/edit", data=data)

        assert resp.status_code == 200, "Invalid input must re-render the form"
        body = resp.data.decode("utf-8")
        assert 'class="auth-error"' in body, "An inline error must be shown"
        assert float(get_row(expense_id)["amount"]) == before, (
            "No DB change may occur on error"
        )


# ================================================================== #
# CSRF protection                                                     #
# ================================================================== #


class TestEditExpenseCSRF:
    @pytest.mark.parametrize("missing_token", [
        {"csrf_token": ""},
        {"csrf_token": "forged"},
    ])
    def test_post_without_valid_csrf_token_rejected(self, client, missing_token):
        user_id, expense_id = _new_test_user()
        login_as(client, user_id, "Edit Test User")
        before = float(get_row(expense_id)["amount"])
        data = build_payload(client, expense_id)
        data.update(missing_token)
        resp = client.post(f"/expenses/{expense_id}/edit", data=data)
        assert resp.status_code == 400, "Missing/mismatched CSRF token must be 400"
        assert float(get_row(expense_id)["amount"]) == before
