"""
Stockroom - a small, friendly inventory manager for small shops.

Start it with:

    python app.py

then open http://127.0.0.1:5000 in your browser.

    app.py       the pages and actions (this file)
    db.py        every database query
    schema.sql   the database tables
    templates/   the HTML pages
    static/      CSS, JavaScript, the logo and Pico.css
"""
import math
import secrets
from functools import wraps
from pathlib import Path

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import db

# Change these to make it yours.
SHOP_NAME = "Stockroom"
CURRENCY = "$"


# --- Setup ---------------------------------------------------------------------

app = Flask(__name__)

# The database and the secret key live in the "instance" folder next to this
# file. It's created on the first run and kept out of git.
instance_folder = Path(app.instance_path)
instance_folder.mkdir(exist_ok=True)

# Flask signs the login cookie with this key. We make a random one on the first
# run and keep reusing it, so restarting the app doesn't log everyone out.
secret_key_file = instance_folder / "secret_key"
if not secret_key_file.exists():
    secret_key_file.write_text(secrets.token_hex(32))

app.config.update(
    SECRET_KEY=secret_key_file.read_text(),
    DATABASE=instance_folder / "inventory.db",
    # Don't send the login cookie along with forms that other websites submit.
    SESSION_COOKIE_SAMESITE="Lax",
)

db.init_app(app)


# --- Small helpers -------------------------------------------------------------

STATUS_LABELS = {"ok": "In stock", "low": "Low stock", "out": "Out of stock"}


def stock_status(item):
    """'ok', 'low' or 'out'. Decides the colour of an item's badge."""
    if item["quantity"] == 0:
        return "out"
    if item["quantity"] <= item["low_stock_at"]:
        return "low"
    return "ok"


def money(amount):
    """1234.5 -> '$1,234.50'"""
    return f"{CURRENCY}{amount:,.2f}"


def display_stats():
    """The four totals at the top of the inventory page, formatted for display."""
    stats = db.get_stats()
    return {
        "products": f"{stats['products']:,}",
        "units": f"{stats['units']:,}",
        "stock_value": money(stats["stock_value"]),
        "restock": f"{stats['restock']:,}",
    }


def find_item_or_404(item_id):
    item = db.get_item(item_id)
    if item is None:
        abort(404)
    return item


def to_number(text, kind):
    """Turn form text into an int or float. Returns None if it isn't a usable number."""
    try:
        number = kind(text)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def read_item_form(form, item_id=None):
    """Read and check the add/edit item form.

    Returns (item, errors). `errors` maps a field name to what's wrong with it,
    so an empty dict means the form is good to save.
    """
    item = {
        "name": form.get("name", "").strip(),
        # Items without a SKU store NULL rather than "", because the database
        # only allows each SKU once, and "" would count as a SKU.
        "sku": form.get("sku", "").strip() or None,
        "category": form.get("category", "").strip(),
        "price": to_number(form.get("price"), float),
        "quantity": to_number(form.get("quantity"), int),
        "low_stock_at": to_number(form.get("low_stock_at"), int),
    }
    errors = {}

    if not item["name"]:
        errors["name"] = "Give the item a name."
    if item["sku"] and db.sku_in_use(item["sku"], ignore_id=item_id):
        errors["sku"] = "Another item already uses this SKU."
    if item["price"] is None or item["price"] < 0:
        errors["price"] = "Enter a price of 0 or more."
    if item["quantity"] is None or item["quantity"] < 0:
        errors["quantity"] = "Enter a whole number, 0 or more."
    if item["low_stock_at"] is None or item["low_stock_at"] < 0:
        errors["low_stock_at"] = "Enter a whole number, 0 or more."

    if not errors:
        item["price"] = round(item["price"], 2)
    return item, errors


# Let the templates use these too.
app.jinja_env.globals.update(
    shop_name=SHOP_NAME,
    currency=CURRENCY,
    stock_status=stock_status,
    status_labels=STATUS_LABELS,
)
app.jinja_env.filters["money"] = money


# --- Logging in and out --------------------------------------------------------

@app.before_request
def load_logged_in_user():
    """Before every request, look up who's logged in (g.user is None if nobody)."""
    user_id = session.get("user_id")
    g.user = db.get_user(user_id) if user_id else None


def login_required(view):
    """Put @login_required on a page to send logged-out visitors to the login page."""
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped_view


def log_in(user_id):
    session.clear()
    session["user_id"] = user_id


@app.route("/setup", methods=["GET", "POST"])
def setup():
    """Only shown on the very first run, to create the owner's account."""
    if db.count_users() > 0:
        return redirect(url_for("login"))

    error = None
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if not username:
            error = "Please choose a username."
        elif len(password) < 6:
            error = "Your password needs at least 6 characters."
        elif password != request.form["confirm_password"]:
            error = "Those two passwords don't match."
        else:
            user_id = db.add_user(username, generate_password_hash(password))
            log_in(user_id)
            flash("You're all set! Add your first item to get going.")
            return redirect(url_for("inventory"))

    return render_template("setup.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    if db.count_users() == 0:
        return redirect(url_for("setup"))  # first run: nobody to log in as yet
    if g.user:
        return redirect(url_for("inventory"))  # already logged in

    error = None
    if request.method == "POST":
        user = db.get_user_by_name(request.form["username"].strip())
        if user and check_password_hash(user["password_hash"], request.form["password"]):
            log_in(user["id"])
            return redirect(url_for("inventory"))
        error = "Wrong username or password."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# --- Inventory -----------------------------------------------------------------

@app.route("/")
@login_required
def inventory():
    return render_template("inventory.html", items=db.get_items(), stats=display_stats())


@app.route("/items/new", methods=["GET", "POST"])
@login_required
def new_item():
    values = {"quantity": 0, "low_stock_at": 5}  # what a blank form starts with
    errors = {}

    if request.method == "POST":
        values = request.form
        item, errors = read_item_form(request.form)
        if not errors:
            db.add_item(item)
            flash(f'Added "{item["name"]}".')
            return redirect(url_for("inventory"))

    return render_template("item_form.html", item=None, values=values, errors=errors,
                           categories=db.get_categories())


@app.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit_item(item_id):
    item = find_item_or_404(item_id)
    values = dict(item, price=f"{item['price']:.2f}")  # show 2.5 as 2.50
    errors = {}

    if request.method == "POST":
        values = request.form
        changes, errors = read_item_form(request.form, item_id=item_id)
        if not errors:
            db.update_item(item_id, changes)
            flash(f'Saved "{changes["name"]}".')
            return redirect(url_for("inventory"))

    return render_template("item_form.html", item=item, values=values, errors=errors,
                           categories=db.get_categories())


@app.post("/items/<int:item_id>/delete")
@login_required
def delete_item(item_id):
    item = find_item_or_404(item_id)
    db.delete_item(item_id)
    flash(f'Deleted "{item["name"]}".')
    return redirect(url_for("inventory"))


@app.post("/items/<int:item_id>/stock")
@login_required
def change_stock(item_id):
    """The − and + buttons call this in the background and get the new numbers back."""
    find_item_or_404(item_id)
    amount = request.form.get("amount", type=int)
    if amount is None:
        abort(400)

    db.change_quantity(item_id, amount)

    item = db.get_item(item_id)
    status = stock_status(item)
    return jsonify(
        quantity=item["quantity"],
        status=status,
        status_label=STATUS_LABELS[status],
        stats=display_stats(),
    )


if __name__ == "__main__":
    app.run(debug=True)
