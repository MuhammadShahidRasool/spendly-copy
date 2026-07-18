from database.db import get_db


def get_user_by_id(user_id):
    """Return a dict with name, email, member_since for the given user, or None."""
    db = get_db()
    try:
        row = db.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            return None

        # Format created_at as "Month YYYY" (e.g. "January 2026")
        member_since = db.execute(
            "SELECT strftime('%m', created_at) AS mm, strftime('%Y', created_at) AS yyyy FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

        month_names = [
            "", "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ]
        month_str = month_names[int(member_since["mm"])]
        year_str = member_since["yyyy"]

        return {
            "name": row["name"],
            "email": row["email"],
            "member_since": f"{month_str} {year_str}",
        }
    finally:
        db.close()


def get_summary_stats(user_id):
    """Return dict with total_spent, transaction_count, top_category for the user."""
    db = get_db()
    try:
        stats = db.execute(
            """
            SELECT
                COALESCE(SUM(amount), 0) AS total_spent,
                COUNT(*) AS transaction_count
            FROM expenses
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        top = db.execute(
            """
            SELECT category FROM expenses
            WHERE user_id = ?
            GROUP BY category
            ORDER BY SUM(amount) DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()

        return {
            "total_spent": stats["total_spent"],
            "transaction_count": stats["transaction_count"],
            "top_category": top["category"] if top else "—",
        }
    finally:
        db.close()


def get_recent_transactions(user_id, limit=10):
    """Return list of dicts (date, description, category, amount) ordered newest-first."""
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT date, description, category, amount
            FROM expenses
            WHERE user_id = ?
            ORDER BY date DESC, id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()

        return [
            {
                "date": row["date"],
                "description": row["description"],
                "category": row["category"],
                "amount": row["amount"],
            }
            for row in rows
        ]
    finally:
        db.close()


def get_category_breakdown(user_id):
    """Return list of dicts (name, amount, pct) ordered by amount descending.

    Percentages are integers rounding to 100; the largest category absorbs
    any rounding remainder.
    """
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT category AS name, SUM(amount) AS amount
            FROM expenses
            WHERE user_id = ?
            GROUP BY category
            ORDER BY amount DESC
            """,
            (user_id,),
        ).fetchall()

        if not rows:
            return []

        total = sum(r["amount"] for r in rows)

        # Compute integer percentages, track rounding remainder
        breakdown = []
        remainder = 0
        for r in rows:
            raw_pct = (r["amount"] / total) * 100
            int_pct = int(raw_pct)
            remainder += raw_pct - int_pct
            breakdown.append({"name": r["name"], "amount": r["amount"], "pct": int_pct})

        # Distribute the rounding remainder (add 1 to largest categories first)
        remainder_rounded = round(remainder)
        # Sort by amount descending to give extra 1% to the largest categories
        sorted_indices = sorted(
            range(len(breakdown)),
            key=lambda i: (-breakdown[i]["amount"], breakdown[i]["name"]),
        )
        for i in range(remainder_rounded):
            breakdown[sorted_indices[i]]["pct"] += 1

        return breakdown
    finally:
        db.close()
