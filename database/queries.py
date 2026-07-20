from database.db import get_db


def _apply_date_filter(sql, params, start_date, end_date):
    """Append date-filter WHERE clause and extend params.

    Handles all four combinations: neither, both, only start, only end.
    Mutates params in-place and returns the (sql, params) pair.
    """
    if start_date and end_date:
        sql += " AND date BETWEEN ? AND ?"
        params.extend([start_date, end_date])
    elif start_date:
        sql += " AND date >= ?"
        params.append(start_date)
    elif end_date:
        sql += " AND date <= ?"
        params.append(end_date)
    return sql, params


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


def get_summary_stats(user_id, start_date=None, end_date=None):
    """Return dict with total_spent, transaction_count, top_category for the user.

    Optional start_date / end_date (YYYY-MM-DD strings) limit the range.
    """
    db = get_db()
    try:
        sql1 = """
            SELECT
                COALESCE(SUM(amount), 0) AS total_spent,
                COUNT(*) AS transaction_count
            FROM expenses
            WHERE user_id = ?
        """
        params1 = [user_id]
        sql1, params1 = _apply_date_filter(sql1, params1, start_date, end_date)
        stats = db.execute(sql1, params1).fetchone()

        sql2 = """
            SELECT category FROM expenses
            WHERE user_id = ?
        """
        params2 = [user_id]
        sql2, params2 = _apply_date_filter(sql2, params2, start_date, end_date)
        sql2 += " GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1"
        top = db.execute(sql2, params2).fetchone()

        return {
            "total_spent": stats["total_spent"],
            "transaction_count": stats["transaction_count"],
            "top_category": top["category"] if top else "—",
        }
    finally:
        db.close()


def get_recent_transactions(user_id, limit=10, start_date=None, end_date=None):
    """Return list of dicts (date, description, category, amount) ordered newest-first.

    Optional start_date / end_date (YYYY-MM-DD strings) limit the range.
    """
    db = get_db()
    try:
        sql = """
            SELECT date, description, category, amount
            FROM expenses
            WHERE user_id = ?
        """
        params = [user_id]
        sql, params = _apply_date_filter(sql, params, start_date, end_date)
        sql += " ORDER BY date DESC, id DESC LIMIT ?"
        params.append(limit)

        rows = db.execute(sql, params).fetchall()

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


def get_category_breakdown(user_id, start_date=None, end_date=None):
    """Return list of dicts (name, amount, pct) ordered by amount descending.

    Optional start_date / end_date (YYYY-MM-DD strings) limit the range.
    Percentages are integers rounding to 100; the largest category absorbs
    any rounding remainder.
    """
    db = get_db()
    try:
        sql = """
            SELECT category AS name, SUM(amount) AS amount
            FROM expenses
            WHERE user_id = ?
        """
        params = [user_id]
        sql, params = _apply_date_filter(sql, params, start_date, end_date)
        sql += " GROUP BY category ORDER BY amount DESC"

        rows = db.execute(sql, params).fetchall()

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
