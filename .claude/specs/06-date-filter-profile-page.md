# Spec: Date Filter for Profile Page

## Overview
Step 6 adds date-range filtering to the profile page so users can view expenses within a specific period. Currently, the profile page shows all transactions, summary stats, and category breakdown for the user's entire history. This step adds a date filter bar above the transaction history table that lets users pick a start and end date. When a filter is applied, the summary stats, transaction list, and category breakdown all update to reflect only expenses within the selected range.

## Depends on
- Step 1: Database setup (expenses table with `date` column)
- Step 2: Registration (user accounts exist)
- Step 3: Login / Logout (session management)
- Step 4: Profile page UI (template structure exists)
- Step 5: Backend routes (live DB queries in `database/queries.py`)

## Routes
- **GET /profile** — modified to accept optional `start_date` and `end_date` query parameters — logged-in only

No new routes.

## Database changes
No database changes. The `expenses` table already has a `date` column (TEXT). All filtering is done via SQL `WHERE` clauses with date comparisons.

## Templates
- **Modify**: `templates/profile.html`
  - Add a date filter form/bar above the transaction history section
  - Form fields: start date (input type="date"), end date (input type="date"), Apply button, Reset link
  - The form must use GET method (not POST) so the filter state is reflected in the URL
  - Pre-fill the inputs with the currently applied values from the URL
  - When no filter is active, show a hint like "Showing all expenses" instead of the date range
  - The filter should visually fit within the existing profile page design (use CSS variables, no inline styles)
  - Category breakdown and summary stats must also reflect the filtered date range

## Files to change
- `app.py` — extract `start_date`/`end_date` from `request.args` in the `profile()` view and pass them to all three query functions
- `database/queries.py` — add optional `start_date` and `end_date` parameters to `get_summary_stats()`, `get_recent_transactions()`, and `get_category_breakdown()`; add `WHERE` clause filtering when dates are provided
- `templates/profile.html` — add the date filter bar UI above the transaction history table

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format values into SQL
- Foreign keys PRAGMA must be enabled on every connection (already done in `get_db()`)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- The date filter form must use GET method so filters appear as URL query params
- When `start_date` and `end_date` are both empty/missing, show all expenses (no date filtering)
- If only one of the two dates is provided, treat it as an open-ended range (e.g. only `start_date` means "from that date onwards")
- Validate date format — if invalid dates are provided, ignore the filter silently (don't crash)
- The `WHERE` clause must compare `date >= ?` and `date <= ?` with parameterised placeholders
- The filter inputs should use `<input type="date">` for native browser date pickers
- Summary stats, transactions, and category breakdown must all respect the same date filter — they must use the same filtered queries
- No JavaScript required — this must work with pure HTML form submission
- After applying a filter, the URL should be something like `/profile?start_date=2026-01-01&end_date=2026-12-31`

## Definition of done
- [ ] Visiting `/profile` without any filter shows all expenses (existing behaviour preserved)
- [ ] Visiting `/profile?start_date=2026-07-01&end_date=2026-07-31` shows only July 2026 expenses in all sections
- [ ] The date filter form has date inputs and an "Apply" button
- [ ] The date filter form has a "Reset" link that clears the filter and returns to `/profile`
- [ ] Summary stats (total spent, transaction count, top category) update to reflect the filtered date range
- [ ] Transaction history table shows only filtered transactions
- [ ] Category breakdown shows only filtered categories with percentages summing to 100%
- [ ] No errors or crashes when invalid/empty date strings are provided
- [ ] All amounts display the ₹ symbol
