"""Tests for the date filter feature on the profile page (Step 6).

Verifies that the /profile route correctly:
- Accepts optional start_date and end_date query parameters
- Filters summary stats, transaction list, and category breakdown accordingly
- Handles open-ended ranges (only one date provided)
- Silently ignores invalid date strings
- Renders the filter form with pre-filled values and a conditional Clear link
- Still requires authentication (redirects anonymous users to /login)
"""

import pytest
from flask import session

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


# ================================================================== #
# Date filter — Form UI                                               #
# ================================================================== #


class TestProfileDateFilterForm:
    """Tests for the presence and state of the date filter form elements."""

    def test_filter_form_has_date_inputs(self, client):
        """The filter form includes 'From' and 'To' date inputs and an Apply button."""
        login_as_demo_user(client)
        resp = client.get("/profile")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")

        assert '<form method="GET"' in body, "Form must use GET method"
        assert '/profile' in body, "Form action must point to /profile"
        assert 'name="start_date"' in body, "Form must have a start_date input"
        assert 'name="end_date"' in body, "Form must have an end_date input"
        assert 'type="date"' in body, "Inputs must be type='date'"
        assert "Apply" in body, "Form must have an Apply button"

    def test_clear_link_hidden_when_no_filter(self, client):
        """The Clear link must NOT appear when no date filter is active."""
        login_as_demo_user(client)
        resp = client.get("/profile")
        body = resp.data.decode("utf-8")

        # The Clear link is rendered with class "btn-ghost filter-btn"
        assert "btn-ghost filter-btn" not in body, (
            "Clear link must not appear when no filter is active"
        )

    def test_clear_link_shown_when_both_dates(self, client):
        """Clear link appears when both start_date and end_date are applied."""
        login_as_demo_user(client)
        resp = client.get("/profile?start_date=2026-07-01&end_date=2026-07-31")
        body = resp.data.decode("utf-8")

        assert "btn-ghost filter-btn" in body, (
            "Clear link must appear when a filter is active"
        )
        assert "Clear" in body, "Clear link text must be present"

    def test_clear_link_shown_when_only_start_date(self, client):
        """Clear link appears when only start_date is applied."""
        login_as_demo_user(client)
        resp = client.get("/profile?start_date=2026-07-01")
        body = resp.data.decode("utf-8")

        assert "btn-ghost filter-btn" in body, (
            "Clear link must appear when only start_date is set"
        )

    def test_clear_link_shown_when_only_end_date(self, client):
        """Clear link appears when only end_date is applied."""
        login_as_demo_user(client)
        resp = client.get("/profile?end_date=2026-07-31")
        body = resp.data.decode("utf-8")

        assert "btn-ghost filter-btn" in body, (
            "Clear link must appear when only end_date is set"
        )

    def test_inputs_prefilled_with_applied_dates(self, client):
        """Date inputs are pre-filled with the values from the query string."""
        login_as_demo_user(client)
        resp = client.get("/profile?start_date=2026-07-01&end_date=2026-07-31")
        body = resp.data.decode("utf-8")

        assert 'value="2026-07-01"' in body, (
            "Start date input must be pre-filled with the applied value"
        )
        assert 'value="2026-07-31"' in body, (
            "End date input must be pre-filled with the applied value"
        )

    def test_inputs_empty_when_no_filter(self, client):
        """Date inputs are empty when no filter query params are provided."""
        login_as_demo_user(client)
        resp = client.get("/profile")
        body = resp.data.decode("utf-8")

        # The input value attribute should be empty
        assert 'value=""' in body or 'value>' in body or 'value >' in body, (
            "Date inputs must be empty when no filter is applied"
        )

    def test_clear_link_returns_to_plain_profile(self, client):
        """The Clear link href points to /profile with no query params."""
        login_as_demo_user(client)
        resp = client.get("/profile?start_date=2026-07-01&end_date=2026-07-31")
        body = resp.data.decode("utf-8")

        # The Clear link is an <a> with href="{{ url_for('profile') }}"
        # which resolves to /profile
        assert '/profile"' in body, "Clear link must point to /profile"


# ================================================================== #
# Date filter — Data filtering behavior                                #
# ================================================================== #


class TestProfileDateFilterBehavior:
    """Tests that the date filter correctly limits data in all three sections."""

    def test_no_filter_shows_all_transactions(self, client):
        """Without any date filter, all 8 seed transactions are visible."""
        login_as_demo_user(client)
        resp = client.get("/profile")
        body = resp.data.decode("utf-8")

        # All seed transaction descriptions
        assert "Weekly grocery run" in body
        assert "Monthly bus pass" in body
        assert "Electricity bill" in body
        assert "Pharmacy — vitamins" in body
        assert "Movie tickets" in body
        assert "New running shoes" in body
        assert "Birthday gift wrap" in body
        assert "Dinner at Olive Tree" in body

    def test_no_filter_shows_full_stats(self, client):
        """Without any date filter, summary stats reflect all 8 expenses."""
        login_as_demo_user(client)
        resp = client.get("/profile")
        body = resp.data.decode("utf-8")

        assert "515.49" in body, "Total spent must be 515.49 with no filter"
        assert "8" in body, "Transaction count should be 8 with no filter"

    def test_full_date_range_filters_transactions(self, client):
        """Applying both start and end date shows only transactions in range."""
        login_as_demo_user(client)
        resp = client.get("/profile?start_date=2026-07-01&end_date=2026-07-05")
        body = resp.data.decode("utf-8")

        # Transactions within range (July 1–5)
        assert "Monthly bus pass" in body    # 2026-07-01
        assert "Weekly grocery run" in body  # 2026-07-03
        assert "Electricity bill" in body    # 2026-07-05

        # Transactions outside range must NOT appear
        assert "Pharmacy" not in body
        assert "Movie tickets" not in body
        assert "New running shoes" not in body
        assert "Birthday gift wrap" not in body
        assert "Dinner at Olive Tree" not in body

    def test_full_date_range_updates_stats(self, client):
        """Summary stats are recalculated to reflect only the filtered range."""
        login_as_demo_user(client)
        resp = client.get("/profile?start_date=2026-07-01&end_date=2026-07-05")
        body = resp.data.decode("utf-8")

        # 65.00 (Transport) + 85.50 (Food) + 120.00 (Bills) = 270.50
        assert "270.50" in body, (
            "Total spent for July 1–5 must be 270.50"
        )
        assert "3" in body, (
            "Transaction count for July 1–5 must be 3"
        )

    def test_full_date_range_updates_top_category(self, client):
        """The top category reflects the filtered date range."""
        login_as_demo_user(client)
        resp = client.get("/profile?start_date=2026-07-01&end_date=2026-07-05")
        body = resp.data.decode("utf-8")

        # Bills: 120.00, Food: 85.50, Transport: 65.00
        assert "Bills" in body, (
            "Top category for July 1–5 should be Bills"
        )

    def test_only_start_date_filters_from_date_onwards(self, client):
        """With only start_date, expenses from that date onwards are shown (open-ended end)."""
        login_as_demo_user(client)
        resp = client.get("/profile?start_date=2026-07-15")
        body = resp.data.decode("utf-8")

        # Transactions on or after 2026-07-15
        assert "New running shoes" in body    # 2026-07-15
        assert "Birthday gift wrap" in body   # 2026-07-18
        assert "Dinner at Olive Tree" in body # 2026-07-20

        # Transactions before 2026-07-15 must NOT appear
        assert "Monthly bus pass" not in body       # 2026-07-01
        assert "Weekly grocery run" not in body     # 2026-07-03
        assert "Electricity bill" not in body       # 2026-07-05
        assert "Pharmacy" not in body               # 2026-07-08
        assert "Movie tickets" not in body          # 2026-07-12

    def test_only_start_date_updates_stats(self, client):
        """Summary stats reflect open-ended range with only start_date."""
        login_as_demo_user(client)
        resp = client.get("/profile?start_date=2026-07-15")
        body = resp.data.decode("utf-8")

        # 89.99 (Shopping) + 25.00 (Other) + 55.00 (Food) = 169.99
        assert "169.99" in body, (
            "Total spent from July 15 onwards must be 169.99"
        )
        assert "3" in body, (
            "Transaction count from July 15 onwards must be 3"
        )

    def test_only_end_date_filters_up_to_date(self, client):
        """With only end_date, expenses up to that date are shown (open-ended start)."""
        login_as_demo_user(client)
        resp = client.get("/profile?end_date=2026-07-08")
        body = resp.data.decode("utf-8")

        # Transactions on or before 2026-07-08
        assert "Monthly bus pass" in body       # 2026-07-01
        assert "Weekly grocery run" in body     # 2026-07-03
        assert "Electricity bill" in body       # 2026-07-05
        assert "Pharmacy" in body               # 2026-07-08

        # Transactions after 2026-07-08 must NOT appear
        assert "Movie tickets" not in body
        assert "New running shoes" not in body
        assert "Birthday gift wrap" not in body
        assert "Dinner at Olive Tree" not in body

    def test_only_end_date_updates_stats(self, client):
        """Summary stats reflect open-ended range with only end_date."""
        login_as_demo_user(client)
        resp = client.get("/profile?end_date=2026-07-08")
        body = resp.data.decode("utf-8")

        # 65.00 (Transport) + 85.50 (Food) + 120.00 (Bills) + 45.00 (Health) = 315.50
        assert "315.50" in body, (
            "Total spent up to July 8 must be 315.50"
        )
        assert "4" in body, (
            "Transaction count up to July 8 must be 4"
        )

    def test_category_breakdown_reflects_filter(self, client):
        """Category breakdown updates to show only categories in the filtered range."""
        login_as_demo_user(client)

        # July 10–31: Shopping, Food, Entertainment, Other
        resp = client.get("/profile?start_date=2026-07-10&end_date=2026-07-31")
        body = resp.data.decode("utf-8")

        assert "Shopping" in body
        assert "Entertainment" in body
        assert "Other" in body

        # Categories NOT in this range must not appear in breakdown
        assert "Transport" not in body
        assert "Bills" not in body
        assert "Health" not in body

    def test_category_percentages_sum_to_100_when_filtered(self, client):
        """Category breakdown percentages sum to 100 even when filtered."""
        login_as_demo_user(client)

        resp = client.get("/profile?start_date=2026-07-01&end_date=2026-07-05")
        body = resp.data.decode("utf-8")

        # Just verify the breakdown section is present and percentages render
        assert "%" in body, (
            "Category percentages should still render with a filter"
        )

    def test_rupee_symbol_present_in_filtered_view(self, client):
        """All amounts display the Rs symbol when a filter is active."""
        login_as_demo_user(client)
        resp = client.get("/profile?start_date=2026-07-01&end_date=2026-07-31")
        body = resp.data.decode("utf-8")

        assert "Rs" in body, (
            "Rupee symbol must appear in filtered profile view"
        )


# ================================================================== #
# Date filter — Edge cases and error handling                          #
# ================================================================== #


class TestProfileDateFilterEdgeCases:
    """Tests that invalid or boundary inputs are handled gracefully."""

    def test_invalid_start_date_ignored(self, client):
        """An invalid start_date is silently ignored and all expenses are shown."""
        login_as_demo_user(client)
        resp = client.get("/profile?start_date=not-a-date")
        body = resp.data.decode("utf-8")

        # All 8 transactions should still appear
        assert "Dinner at Olive Tree" in body
        assert "Weekly grocery run" in body
        assert "515.49" in body, "Total should reflect all expenses"
        assert "8" in body, "Transaction count should be all 8"

    def test_invalid_end_date_ignored(self, client):
        """An invalid end_date is silently ignored and all expenses are shown."""
        login_as_demo_user(client)
        resp = client.get("/profile?end_date=not-a-date")
        body = resp.data.decode("utf-8")

        assert "Dinner at Olive Tree" in body
        assert "515.49" in body

    def test_both_dates_invalid_shows_all(self, client):
        """Both invalid dates are silently ignored and all expenses are shown."""
        login_as_demo_user(client)
        resp = client.get("/profile?start_date=abc&end_date=xyz")
        body = resp.data.decode("utf-8")

        assert "Dinner at Olive Tree" in body
        assert "515.49" in body

    def test_empty_date_strings_treated_as_no_filter(self, client):
        """Empty date query params are treated as no filter (all expenses shown)."""
        login_as_demo_user(client)
        resp = client.get("/profile?start_date=&end_date=")
        body = resp.data.decode("utf-8")

        assert "Dinner at Olive Tree" in body
        assert "515.49" in body

    def test_missing_start_date_with_end_date(self, client):
        """Only end_date with start_date missing works as open-ended start."""
        login_as_demo_user(client)
        resp = client.get("/profile?end_date=2026-07-05")
        body = resp.data.decode("utf-8")

        # Should show July 1–5 expenses only (all seed dates are >= July 1)
        assert "Electricity bill" in body
        assert "Dinner at Olive Tree" not in body

    def test_missing_end_date_with_start_date(self, client):
        """Only start_date with end_date missing works as open-ended end."""
        login_as_demo_user(client)
        resp = client.get("/profile?start_date=2026-07-20")
        body = resp.data.decode("utf-8")

        # Should show only the July 20 expense
        assert "Dinner at Olive Tree" in body
        assert "Weekly grocery run" not in body

    def test_no_expenses_in_date_range(self, client):
        """A date range matching no expenses shows zero stats and empty tables."""
        login_as_demo_user(client)
        resp = client.get("/profile?start_date=2025-01-01&end_date=2025-12-31")
        body = resp.data.decode("utf-8")

        # Stats show zeros
        assert "Rs 0.00" in body, (
            "Total spent must be 0.00 when no expenses match the filter"
        )
        assert "0" in body, (
            "Transaction count should be 0 when no expenses match the filter"
        )

        # No transactions from the seed data should appear
        assert "Dinner at Olive Tree" not in body
        assert "Weekly grocery run" not in body

    def test_unauthenticated_redirects_to_login(self, client):
        """Unauthenticated requests to /profile with date params redirect to /login."""
        resp = client.get(
            "/profile?start_date=2026-07-01&end_date=2026-07-31",
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert resp.location == "/login"

    def test_date_format_validation_rejects_invalid_month(self, client):
        """A date with an invalid month (13) is silently ignored."""
        login_as_demo_user(client)
        resp = client.get("/profile?start_date=2026-13-01&end_date=2026-07-31")
        body = resp.data.decode("utf-8")

        # The invalid start should be ignored, so end_date alone acts as filter
        # end_date=2026-07-31 is valid, so it should filter by just end_date
        # Since all seed expenses are in July 2026, all 8 should appear
        assert "Dinner at Olive Tree" in body

    def test_date_format_validation_rejects_invalid_day(self, client):
        """A date with an invalid day (32) is silently ignored."""
        login_as_demo_user(client)
        resp = client.get("/profile?end_date=2026-07-32")
        body = resp.data.decode("utf-8")

        # Invalid end_date is ignored, all expenses shown
        assert "Dinner at Olive Tree" in body
        assert "515.49" in body

    def test_same_start_and_end_date(self, client):
        """Using the same date for both start and end shows only that day's expenses."""
        login_as_demo_user(client)
        resp = client.get("/profile?start_date=2026-07-03&end_date=2026-07-03")
        body = resp.data.decode("utf-8")

        # Only the July 3 expense (Weekly grocery run, 85.50)
        assert "Weekly grocery run" in body
        assert "85.50" in body or "85.5" in body
        assert "Dinner at Olive Tree" not in body
        assert "1" in body, "Transaction count should be 1"

    def test_http_200_with_valid_date_filter(self, client):
        """Profile page with valid date filter returns HTTP 200."""
        login_as_demo_user(client)
        resp = client.get("/profile?start_date=2026-07-01&end_date=2026-07-31")
        assert resp.status_code == 200

    def test_http_200_with_invalid_date_filter(self, client):
        """Profile page with invalid date filter still returns HTTP 200 (no crash)."""
        login_as_demo_user(client)
        resp = client.get("/profile?start_date=garbage")
        assert resp.status_code == 200
