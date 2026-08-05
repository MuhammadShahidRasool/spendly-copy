# Spec: Delete Expense

## Overview
Step 9 lets a logged-in user permanently remove one of their own expenses
from the profile transaction history. Deleting is a destructive, stateful
mutation, so the feature guards it the same way the add/edit expense writes
are guarded: the route is scoped to both `id` and `user_id` (a user can never
delete another user's row), requires login, and **only accepts CSRF-protected
`POST` requests** so a malicious third-party page cannot forge a deletion. The
existing placeholder route `/expenses/<int:id>/delete` (currently a raw-string
stub) is replaced with this secure handler. One new query helper,
`delete_expense`, is added to `database/queries.py`, and each row in the
profile transaction table gains a "Delete" action next to the existing "Edit"
link from Step 8.

## Depends on
- Step 1: Database setup (`expenses` table exists with `id` and `user_id`)
- Step 3: Login / Logout (`session["user_id"]` is set and enforced)
- Step 5: Profile page renders transactions (the delete control lives there)
- Step 7: Add Expense (establishes the `_csrf_protect()` / `_get_csrf_token()`
  mutation pattern this step follows)
- Step 8: Edit Expense (`get_recent_transactions` already returns the expense
  `id`, and the table already has an "Actions" column with an "Edit" link)

## Routes
- `POST /expenses/<int:id>/delete` — delete the caller's own expense with the
  given `id`, then redirect to `/profile` — logged-in only, CSRF-protected

> The previous `GET` method is deliberately dropped. Deletion is irreversible
> and side-effectful, so it must not be triggerable by a plain `GET` (which
> would open a CSRF deletion vector). The client invokes this as a tiny `POST`
> form carrying a fresh `csrf_token`, exactly like add/edit.

## Database changes
No new tables, columns, or constraints. The `expenses` table already has `id`
and `user_id` with the FK to `users(id)` from Step 1.

## Templates
- **Modify**: `templates/profile.html`
  - In the existing `Actions` column of the transaction table `<tbody>`, next to
    the "Edit" link added in Step 8, add a "Delete" control per row. This must
    be a small inline `<form method="POST">` with:
    - `action` of `url_for('delete_expense', id=t['id'])`
    - a hidden `<input type="hidden" name="csrf_token" value="{{ csrf_token }}">`
    - a "Delete" submit button (destructive styling, distinct from the Edit link)
  - No new template file is required.
  - Pass `csrf_token` into the profile render so the delete forms are valid.
    The `_get_csrf_token()` helper already exists in `app.py`.

## Files to change
- `database/queries.py`
  - Add `delete_expense(expense_id, user_id)` — issues a parameterised `DELETE
    scoped to both `id` and `user_id` (`WHERE id = ? AND user_id = ?`), returns
    the number of rows deleted (0 if it doesn't exist or belongs to another
    user). Follows the `get_expense_by_id` / `update_expense` ownership pattern.
- `app.py`
  - Import `delete_expense` from `database.queries`.
  - Replace the placeholder at `/expenses/<int:id>/delete` (currently a GET-only
    raw string) with a proper handler declared as
    `@app.route("/expenses/<int:id>/delete", methods=["POST"])`:
    - Redirect to `/login` (302) if not logged in.
    - Call `_csrf_protect()` to reject forged/missing CSRF tokens (400).
    - Call `delete_expense(id, session["user_id"])`.
    - Flash a success message and `redirect(url_for("profile"))`.
    - Do not abort 404 on a non-existent/other-user id: deletion is idempotent
      and the redirect is the same outcome either way (mirrors real "delete"
      UX; the ownership-scoped query simply deletes nothing for a foreign row).
- `templates/profile.html`
  - Add the per-row delete form+button in the existing Actions column.
  - Render the hidden CSRF token (see above).
- `app.py` route for `profile()` must pass `csrf_token=_get_csrf_token()` in
  the `render_template` call so `profile.html` can render the delete form.

## Files to create
- No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format values into SQL
- `delete_expense` must scope its `WHERE` clause to `id = ? AND user_id = ?` so
  a user can never delete another user's row
- The delete route must be **POST-only** with a login guard and `_csrf_protect()`;
  a GET to `/expenses/<id>/delete` should be rejected (say `405 Method Not
  Allowed` from Flask's method scoping) rather than deleting
- Fake a success flash and redirect to `/profile` after delete — do not render a
  template for the delete action
- Shared page uses CSS variables — never hardcode hex values; the delete
  control should reuse design-token-based classes (e.g. a danger-styled
  button), not inline styles
- All templates extend `base.html`; no inline styles
- Currency must always display as ₹ (this page currently uses `Rs` — match
  whatever `/profile` already uses; for delete no new currency formatting is
  introduced, so no change beyond what Step 8 established)
- Do NOT change the DB schema or indexes
- CSRF token must come from `_get_csrf_token()` and be compared with
  `secrets.compare_digest` via the existing `_csrf_protect()` helper

## Tests to write
File: `tests/test_delete_expense.py` (following the test_edit_expense.py pattern:
dedicated delete-test users, never touching the seed demo user's rows)

### Unit tests
| Function | Input | Expected output |
|---|---|---|
| `delete_expense` | valid `expense_id`, owning `user_id` | returns `1`; row no longer exists |
| `delete_expense` | valid `expense_id`, wrong `user_id` | returns `0`; row still exists untouched |
| `delete_expense` | non-existent `expense_id` (any user) | returns `0`; no error raised |

### Route tests
- `POST /expenses/<id>/delete` — logged out: returns 302 redirect to `/login`;
  the expense row is NOT deleted
- `POST /expenses/<id>/delete` — logged in, owning user, valid CSRF:
  returns 302 redirect to `/profile`; the expense row no longer exists; it no
  longer appears on `/profile` afterwards
- `POST /expenses/<id>/delete` — logged in as another user targeting the
  owner's expense, valid CSRF: returns 302 to `/profile` (idempotent); the
  target expense still exists untouched
- `POST /expenses/<id>/delete` — logged in, missing CSRF token: returns 400 and
  does NOT delete the row
- `POST /expenses/<id>/delete` — logged in, forged CSRF token: returns 400 and
  does NOT delete the row
- `GET /expenses/<id>/delete` — logged in: must NOT delete the row (returns a
  non-2xx method error, e.g. 405)

## Definition of done
- [ ] The profile transaction list shows a "Delete" control next to each row's
  "Edit" link, within the same Actions column
- [ ] Updating a delete while logged out redirects to `/login` and does not
  remove the expense
- [ ] Updating a delete for the logged-in user's own expense removes that row
  from both the database and the profile transaction list, then redirects to
  `/profile`
- [ ] Updating a delete targeting another user's expense leaves that expense
  intact (idempotent, no error)
- [ ] A delete POST without a valid CSRF token is rejected and removes nothing
- [ ] A plain GET to `/expenses/<id>/delete` does not delete anything
- [ ] The page renders with no server error and the nav still works — the
  delete control is CSRF-protected, POST only, with no new schema or packages