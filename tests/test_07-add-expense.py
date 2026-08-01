"""Tests for the Add Expense feature (Step 7).

Spec source: .claude/specs/07-add-expense.md

These tests validate what the spec says the feature SHOULD do:

Definition of done covered here:
- GET /expenses/add while logged out redirects to the login page
- POST /expenses/add while logged out redirects to the login page
- GET /expenses/add while logged in renders the add-expense form with
  amount, category, date, and optional description fields, and the select
  lists the 7 fixed categories (Food, Transport, Bills, Health,
  Entertainment, Shopping, Other)
- POSTing a valid expense inserts a row, redirects to the profile page,
  and flashes a success message
- The inserted row stores the correct user_id, amount, category, date,
  and description (NULL when omitted)
- A newly added expense appears on the profile page: in the recent
  transactions list and in the total-spent stat
- Empty / non-numeric / zero / negative amounts, missing or invalid
  categories, and missing or invalid dates (e.g. 2026-07-32) are rejected
  with an inline error (the register.html error pattern the spec
  references) and NO DB row is written
- The form action is not a hardcoded URL — it matches url_for('add_expense')

Assertions are written against the spec's contract, not implementation
details (no exact error-message strings, no route source). COUNT-delta
and dynamic-total assertions are used because the shared test DB is
mutated by earlier tests in the session.
"""

import re

import pytest
from flask import url_for

from database.db import get_db


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


def login_as_demo_user(client):
    """Set the Flask session to be logged in as the seed demo user."""
    user_id = get_seed_user_id()
    assert user_id is not None, "Seed user must exist"
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_name"] = "Demo User"
    return user_id


def get_csrf_token(client):
    """GET the add-expense form and return its CSRF token.

    The token is stored in the session when the form is rendered, so this
    mirrors what a real browser does before submitting.
    """
    resp = client.get("/expenses/add")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    match = re.search(r'name="csrf_token" value="([^"]+)"', body)
    assert match is not None, "CSRF token must be present in the form"
    return match.group(1)


# ------------------------------------------------------------------ #
# Shared valid payload                                                #
# ------------------------------------------------------------------ #

VALID_EXPENSE = {
    "amount": "99.99",
    "category": "Food",
    "date": "2026-08-01",
    "description": "Spec team lunch",
}


def valid_payload(client, **overrides):
    """Return VALID_EXPENSE plus a fresh CSRF token, with optional overrides."""
    data = dict(VALID_EXPENSE)
    data["csrf_token"] = get_csrf_token(client)
    data.update(overrides)
    return data


# ================================================================== #
# Auth guard — GET and POST while logged out                          #
# ================================================================== #


class TestAddExpenseAuthGuard:
    """Logged-out users must be redirected to /login for both GET and POST."""

    def test_get_redirects_to_login_when_logged_out(self, client):
        """GET /expenses/add while logged out redirects to the login page."""
        resp = client.get("/expenses/add", follow_redirects=False)
        assert resp.status_code == 302, "Logged-out GET must redirect"
        assert resp.location == "/login"

    def test_post_redirects_to_login_when_logged_out(self, client, db):
        """POST /expenses/add while logged out redirects and writes no row."""
        user_id = get_seed_user_id()
        assert user_id is not None, "Seed user must exist"
        before = db.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()[0]

        resp = client.post(
            "/expenses/add",
            data=dict(VALID_EXPENSE, csrf_token="any"),
            follow_redirects=False,
        )
        assert resp.status_code == 302, "Logged-out POST must redirect"
        assert resp.location == "/login"

        after = db.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        assert after == before, "Logged-out POST must not write an expense row"


# ================================================================== #
# GET /expenses/add — form rendering while logged in                  #
# ================================================================== #


class TestAddExpenseForm:
    """GET /expenses/add while logged in renders the add-expense form."""

    def test_get_renders_form_when_logged_in(self, client):
        """The form includes amount, category, date, and description fields."""
        login_as_demo_user(client)
        resp = client.get("/expenses/add")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")

        assert 'name="amount"' in body, "Amount field is missing"
        assert 'name="category"' in body, "Category select is missing"
        assert 'name="date"' in body, "Date field is missing"
        assert 'name="description"' in body, "Description field is missing"
        assert 'method="POST"' in body, "Form must submit via POST"

    def test_form_lists_all_seven_fixed_categories(self, client):
        """The category select contains the 7 fixed categories from Step 1."""
        login_as_demo_user(client)
        resp = client.get("/expenses/add")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")

        for cat in ["Food", "Transport", "Bills", "Health",
                    "Entertainment", "Shopping", "Other"]:
            assert f'value="{cat}"' in body, f"Missing category option: {cat}"

    def test_form_action_matches_url_for_add_expense(self, app, client):
        """The form action must be url_for('add_expense'), not a hardcoded URL."""
        login_as_demo_user(client)
        with app.app_context():
            expected_action = url_for("add_expense")

        resp = client.get("/expenses/add")
        assert resp.status_code == 200
        assert f'action="{expected_action}"' in resp.data.decode("utf-8"), (
            "Form action must resolve to url_for('add_expense')"
        )


# ================================================================== #
# POST /expenses/add — successful submission                          #
# ================================================================== #


class TestAddExpensePostSuccess:
    """POST with valid input inserts a row, redirects, and flashes success."""

    def test_valid_post_inserts_row_and_redirects_to_profile(self, client, db):
        """A valid expense adds exactly one row and redirects to /profile."""
        user_id = login_as_demo_user(client)
        before = db.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()[0]

        resp = client.post("/expenses/add", data=valid_payload(client))
        assert resp.status_code == 302, "Valid POST must redirect"
        assert resp.location == "/profile"

        after = db.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        assert after == before + 1, "Exactly one expense row must be inserted"

    def test_inserted_row_has_correct_columns(self, client, db):
        """The new row stores the correct user_id, amount, category, date, description."""
        user_id = login_as_demo_user(client)
        data = valid_payload(
            client,
            amount="42.42",
            category="Transport",
            date="2026-08-03",
            description="Cab fare",
        )
        client.post("/expenses/add", data=data)

        row = db.execute(
            "SELECT user_id, amount, category, date, description "
            "FROM expenses WHERE user_id = ? AND amount = ?",
            (user_id, 42.42),
        ).fetchone()
        assert row is not None, "Expense row must exist after a valid POST"
        assert row["user_id"] == user_id, "user_id must match the logged-in user"
        assert row["amount"] == 42.42, "amount must be stored correctly"
        assert row["category"] == "Transport", "category must be stored correctly"
        assert row["date"] == "2026-08-03", "date must be stored correctly"
        assert row["description"] == "Cab fare", "description must be stored"

    def test_description_is_null_when_omitted(self, client, db):
        """Omitting the optional description stores a NULL description."""
        user_id = login_as_demo_user(client)
        data = valid_payload(
            client,
            amount="55.55",
            category="Other",
            date="2026-08-04",
            # no description — description is optional per the spec
        )
        resp = client.post("/expenses/add", data=data)
        assert resp.status_code == 302
        assert resp.location == "/profile"

        row = db.execute(
            "SELECT description FROM expenses WHERE user_id = ? AND amount = ?",
            (user_id, 55.55),
        ).fetchone()
        assert row is not None, "Expense row must exist after a valid POST"
        assert row["description"] is None, (
            "Omitted description must be stored as NULL"
        )

    def test_success_post_flashes_message(self, client):
        """A successful add flashes a success message rendered on /profile."""
        login_as_demo_user(client)
        resp_post = client.post("/expenses/add", data=valid_payload(client))
        assert resp_post.status_code == 302

        resp = client.get("/profile")
        assert resp.status_code == 200
        # base.html renders flashed messages as divs with class flash-<category>
        assert 'class="flash-' in resp.data.decode("utf-8"), (
            "A flash message must be rendered after a successful add"
        )

    def test_new_expense_appears_on_profile(self, client, db):
        """The new expense shows in transactions and the total spent stat."""
        user_id = login_as_demo_user(client)
        total_before = float(db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0])

        amount = 77.77
        desc = "Spec profile check lunch"
        data = valid_payload(
            client, amount="77.77", category="Food", date="2026-08-05", description=desc
        )
        resp_post = client.post("/expenses/add", data=data)
        assert resp_post.status_code == 302

        resp = client.get("/profile")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")

        assert desc in body, (
            "New expense must appear in the profile's recent transactions"
        )
        assert f"Rs {total_before + amount:.2f}" in body, (
            "Total spent must reflect the newly added amount"
        )

    def test_unpadded_date_is_normalized(self, client, db):
        """An unpadded date is stored in canonical YYYY-MM-DD form."""
        user_id = login_as_demo_user(client)
        data = valid_payload(
            client,
            amount="12.34",
            category="Bills",
            date="2026-8-5",
            description="Unpadded date check",
        )
        resp = client.post("/expenses/add", data=data)
        assert resp.status_code == 302
        assert resp.location == "/profile"

        row = db.execute(
            "SELECT date FROM expenses WHERE user_id = ? AND amount = ?",
            (user_id, 12.34),
        ).fetchone()
        assert row is not None, "Expense row must exist after a valid POST"
        assert row["date"] == "2026-08-05", (
            "Unpadded dates must be stored in canonical YYYY-MM-DD form"
        )


# ================================================================== #
# POST /expenses/add — validation                                     #
# ================================================================== #


class TestAddExpenseValidation:
    """Invalid input is rejected inline with no DB row written."""

    @pytest.mark.parametrize("field,value", [
        # --- amount: empty / non-numeric / zero / negative ---
        ("amount", ""),          # empty amount
        ("amount", "abc"),       # non-numeric amount
        ("amount", "0"),         # zero amount
        ("amount", "-5"),        # negative amount
        # --- category: missing / not in the fixed 7-category list ---
        ("category", ""),        # missing category
        ("category", "Fake"),    # invalid category
        # --- date: missing / not a valid YYYY-MM-DD ---
        ("date", ""),            # missing date
        ("date", "2026-07-32"),  # invalid day (spec's example)
        ("date", "2026-13-01"),  # invalid month
        ("date", "not-a-date"),  # malformed date
    ])
    def test_invalid_submission_rejected_with_no_db_row(
        self, client, db, field, value
    ):
        """An invalid amount/category/date re-renders with an inline error
        and writes no DB row."""
        user_id = login_as_demo_user(client)
        before = db.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()[0]

        data = valid_payload(client, **{field: value})
        resp = client.post("/expenses/add", data=data)

        # The form is re-rendered (200), NOT a redirect to /profile
        assert resp.status_code == 200, (
            "Invalid input must re-render the form, not redirect"
        )
        body = resp.data.decode("utf-8")

        # Inline error uses the register.html error pattern the spec references
        assert 'class="auth-error"' in body, "An inline error must be shown"
        # The add-expense form must still be present on the re-render
        assert 'name="amount"' in body, "The add-expense form must be re-rendered"

        after = db.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        assert after == before, "No DB row may be written for invalid input"


# ================================================================== #
# CSRF protection                                                     #
# ================================================================== #


class TestAddExpenseCSRF:
    """POSTs without a valid CSRF token are rejected with a 400 and no row."""

    @pytest.mark.parametrize("missing_token", [
        {"csrf_token": ""},        # empty token
        {"csrf_token": "forged"},  # token that doesn't match the session's
    ])
    def test_post_without_valid_csrf_token_rejected(
        self, client, db, missing_token
    ):
        """A POST lacking the session's CSRF token is rejected (400)."""
        user_id = login_as_demo_user(client)
        before = db.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()[0]

        data = dict(VALID_EXPENSE)
        data.update(missing_token)
        resp = client.post("/expenses/add", data=data)
        assert resp.status_code == 400, "Missing/mismatched CSRF token must be rejected"

        after = db.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        assert after == before, "No DB row may be written without a valid token"

    def test_valid_csrf_token_allows_submit(self, client, db):
        """A POST with the session's CSRF token is accepted."""
        user_id = login_as_demo_user(client)
        before = db.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()[0]

        resp = client.post("/expenses/add", data=valid_payload(client))
        assert resp.status_code == 302
        assert resp.location == "/profile"

        after = db.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        assert after == before + 1, "Valid CSRF-token POST must insert a row"
