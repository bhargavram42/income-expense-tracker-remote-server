from fastmcp import FastMCP
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "expenses.db")
CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")

mcp = FastMCP("ExpenseTracker")

def init_db():
    with sqlite3.connect(DB_PATH) as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS expenses(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT DEFAULT '',
                note TEXT DEFAULT ''
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS income(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                source TEXT NOT NULL,
                note TEXT DEFAULT ''
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS budgets(
                category TEXT PRIMARY KEY,
                monthly_limit REAL NOT NULL
            )
        """)


init_db()

@mcp.tool()
def add_expense(date, amount, category, subcategory="", note=""):
    '''Add a new expense entry to the database.'''
    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(
            "INSERT INTO expenses(date, amount, category, subcategory, note) VALUES (?,?,?,?,?)",
            (date, amount, category, subcategory, note)
        )
        return {"status": "ok", "id": cur.lastrowid}
    
@mcp.tool()
def list_expenses(start_date, end_date):
    '''List expense entries within an inclusive date range.'''
    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(
            """
            SELECT id, date, amount, category, subcategory, note
            FROM expenses
            WHERE date BETWEEN ? AND ?
            ORDER BY id ASC
            """,
            (start_date, end_date)
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

@mcp.tool()
def summarize(start_date, end_date, category=None):
    '''Summarize expenses by category within an inclusive date range.'''
    with sqlite3.connect(DB_PATH) as c:
        query = (
            """
            SELECT category, SUM(amount) AS total_amount
            FROM expenses
            WHERE date BETWEEN ? AND ?
            """
        )
        params = [start_date, end_date]

        if category:
            query += " AND category = ?"
            params.append(category)

        query += " GROUP BY category ORDER BY category ASC"

        cur = c.execute(query, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    
@mcp.tool()
def update_expense(expense_id, date=None, amount=None, category=None, subcategory=None, note=None):
    """Update an existing expense."""
    fields, params = [], []

    for k, v in {
        "date": date,
        "amount": amount,
        "category": category,
        "subcategory": subcategory,
        "note": note,
    }.items():
        if v is not None:
            fields.append(f"{k} = ?")
            params.append(v)

    if not fields:
        return {"status": "no_changes"}

    params.append(expense_id)

    with sqlite3.connect(DB_PATH) as c:
        c.execute(
            f"UPDATE expenses SET {', '.join(fields)} WHERE id = ?",
            params,
        )
    return {"status": "ok"}

@mcp.tool()
def delete_expense(expense_id):
    """Delete an expense by ID."""
    with sqlite3.connect(DB_PATH) as c:
        c.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    return {"status": "deleted"}

@mcp.tool()
def add_income(date, amount, source, note=""):
    """Add an income entry."""
    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(
            "INSERT INTO income(date, amount, source, note) VALUES (?,?,?,?)",
            (date, amount, source, note)
        )
    return {"status": "ok", "id": cur.lastrowid}
@mcp.tool()
def list_income(start_date, end_date):
    """List income entries in a date range."""
    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(
            """
            SELECT id, date, amount, source, note
            FROM income
            WHERE date BETWEEN ? AND ?
            ORDER BY date
            """,
            (start_date, end_date)
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
@mcp.tool()
def set_budget(category, monthly_limit):
    """Set monthly budget for a category."""
    with sqlite3.connect(DB_PATH) as c:
        c.execute(
            """
            INSERT INTO budgets(category, monthly_limit)
            VALUES (?, ?)
            ON CONFLICT(category)
            DO UPDATE SET monthly_limit = excluded.monthly_limit
            """,
            (category, monthly_limit)
        )
    return {"status": "ok"}

@mcp.tool()
def budget_status(month):
    """
    month: YYYY-MM
    """
    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(
            """
            SELECT
                b.category,
                b.monthly_limit,
                IFNULL(SUM(e.amount), 0) AS spent,
                (b.monthly_limit - IFNULL(SUM(e.amount), 0)) AS remaining
            FROM budgets b
            LEFT JOIN expenses e
                ON b.category = e.category
               AND substr(e.date, 1, 7) = ?
            GROUP BY b.category
            ORDER BY b.category
            """,
            (month,)
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


@mcp.resource("expense://categories", mime_type="application/json")
def categories():
    # Read fresh each time so you can edit the file without restarting
    print("DEBUG: categories resource requested")
    with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
        return f.read()
    
@mcp.prompt(
    name="expense_summary_prompt",
    description="Summarize expenses and highlight key spending patterns."
)
def expense_summary_prompt(start_date: str, end_date: str):
    return f"""
You are a personal finance assistant.

Summarize the user's expenses between {start_date} and {end_date}.

Tasks:
- Identify top spending categories
- Mention unusually high expenses
- Suggest 1–2 optimization ideas

Use data returned from the expense summary tool.
"""
@mcp.prompt(
    name="budget_health_prompt",
    description="Analyze budget usage and warn about overspending."
)
def budget_health_prompt(month: str):
    return f"""
You are a budget advisor.

Analyze the user's budget status for {month}.

Tasks:
- Identify categories exceeding budget
- Flag categories above 80% usage
- Give concise, actionable advice

Base your reasoning strictly on the budget_status tool output.
"""


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)