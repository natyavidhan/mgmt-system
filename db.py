"""
Database helpers.

Every SQL query in the app lives in this file. The routes in app.py call
these small functions instead of writing SQL themselves.
"""
import sqlite3

from flask import current_app, g


# --- Connection ---------------------------------------------------------------

def get_db():
    """Return this request's database connection, opening it if needed."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row  # lets us write row["name"] instead of row[1]
    return g.db


def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app(app):
    """Create the tables (if they're missing) and close connections after each request."""
    app.teardown_appcontext(close_db)
    with app.app_context():
        with app.open_resource("schema.sql") as f:
            get_db().executescript(f.read().decode("utf-8"))


# --- Users --------------------------------------------------------------------

def count_users():
    return get_db().execute("SELECT COUNT(*) FROM users").fetchone()[0]


def get_user(user_id):
    return get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_user_by_name(username):
    return get_db().execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()


def add_user(username, password_hash):
    """Save a new user and return their id."""
    db = get_db()
    cursor = db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, password_hash),
    )
    db.commit()
    return cursor.lastrowid


# --- Items --------------------------------------------------------------------

def get_items():
    """All items, sorted A to Z."""
    return get_db().execute(
        "SELECT * FROM items ORDER BY name COLLATE NOCASE"
    ).fetchall()


def get_item(item_id):
    return get_db().execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()


def get_categories():
    """Categories already in use. The item form suggests these as you type."""
    rows = get_db().execute(
        "SELECT DISTINCT category FROM items WHERE category != '' "
        "ORDER BY category COLLATE NOCASE"
    ).fetchall()
    return [row["category"] for row in rows]


def sku_in_use(sku, ignore_id=None):
    """True if a *different* item already has this SKU."""
    row = get_db().execute("SELECT id FROM items WHERE sku = ?", (sku,)).fetchone()
    return row is not None and row["id"] != ignore_id


def add_item(item):
    db = get_db()
    db.execute(
        """
        INSERT INTO items (name, sku, category, price, quantity, low_stock_at)
        VALUES (:name, :sku, :category, :price, :quantity, :low_stock_at)
        """,
        item,
    )
    db.commit()


def update_item(item_id, item):
    db = get_db()
    db.execute(
        """
        UPDATE items
        SET name = :name, sku = :sku, category = :category,
            price = :price, quantity = :quantity, low_stock_at = :low_stock_at
        WHERE id = :id
        """,
        {**item, "id": item_id},
    )
    db.commit()


def delete_item(item_id):
    db = get_db()
    db.execute("DELETE FROM items WHERE id = ?", (item_id,))
    db.commit()


def change_quantity(item_id, amount):
    """Add stock, or take it away if amount is negative. Never goes below zero."""
    db = get_db()
    db.execute(
        "UPDATE items SET quantity = MAX(quantity + ?, 0) WHERE id = ?",
        (amount, item_id),
    )
    db.commit()


def get_stats():
    """The totals shown in the cards at the top of the inventory page."""
    return get_db().execute(
        """
        SELECT
            COUNT(*)                                             AS products,
            COALESCE(SUM(quantity), 0)                           AS units,
            COALESCE(SUM(quantity * price), 0)                   AS stock_value,
            COUNT(CASE WHEN quantity <= low_stock_at THEN 1 END) AS restock
        FROM items
        """
    ).fetchone()
