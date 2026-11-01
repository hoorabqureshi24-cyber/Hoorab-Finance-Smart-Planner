import os
import sqlite3
from pathlib import Path
from functools import wraps
from datetime import date
from decimal import Decimal

from flask import (
    Flask, render_template, request, jsonify,
    redirect, url_for, session, flash
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)


# ---------------- PROJECT SETTINGS ----------------

app = Flask(__name__)

app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "local-development-key-change-before-deployment"
)
import os

# Vercel par writable folder sirf /tmp hai
if os.environ.get("VERCEL"):
    DATABASE = Path("/tmp/finance.db")
else:
    DATABASE = Path(__file__).resolve().parent / "finance.db"


# ---------------- DATABASE CONNECTION ----------------

def get_db():
    connection = sqlite3.connect(str(DATABASE))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def close_db(connection=None, cursor=None):
    if cursor is not None:
        cursor.close()

    if connection is not None:
        connection.close()


# ---------------- DATABASE INITIALIZATION ----------------

def initialize_database():

    DATABASE.parent.mkdir(parents=True, exist_ok=True)

    connection = None

    try:
        connection = get_db()

        connection.executescript("""

            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                user_password TEXT NOT NULL,
                user_created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS monthly_budgets (
                budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                budget_month TEXT NOT NULL,
                total_budget REAL DEFAULT 0,
                used_amount REAL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (user_id)
                REFERENCES users(user_id)
                ON DELETE CASCADE,

                UNIQUE(user_id, budget_month)
            );

            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                transaction_type TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                transaction_date TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (user_id)
                REFERENCES users(user_id)
                ON DELETE CASCADE
            );

        """)

        connection.commit()

        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()

        print("DATABASE PATH:", DATABASE)
        print("DATABASE EXISTS:", DATABASE.exists())
        print(
            "DATABASE TABLES:",
            [row["name"] for row in tables]
        )

    except sqlite3.Error:
        app.logger.exception("Database initialization failed")
        raise

    finally:
        if connection is not None:
            connection.close()


def to_number(value):
    if isinstance(value, Decimal):
        return float(value)

    return float(value or 0)


# Create database tables when Flask starts.
initialize_database()


# ---------------- LOGIN PROTECTION ----------------

def login_required(view):

    @wraps(view)
    def wrapped_view(*args, **kwargs):

        if "user_id" not in session:

            if request.path.startswith("/api/"):
                return jsonify({
                    "error": "Please log in first."
                }), 401

            return redirect(url_for("login"))

        return view(*args, **kwargs)

    return wrapped_view


# ---------------- HOME ----------------

@app.route("/")
def home():
    return render_template("index.html")


# ---------------- REGISTER ----------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("Please fill in all fields.", "error")
            return render_template("register.html")

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("register.html")

        connection = None
        cursor = None

        try:
            connection = get_db()
            cursor = connection.cursor()

            password_hash = generate_password_hash(password)

            cursor.execute(
                """
                INSERT INTO users (username, email, password_hash)
                VALUES (?, ?, ?)
                """,
                (username, email, password_hash)
            )

            new_user_id = cursor.lastrowid
            connection.commit()

            session.clear()
            session["user_id"] = new_user_id
            session["username"] = username

            return redirect(url_for("dashboard"))

        except sqlite3.IntegrityError:
            if connection:
                connection.rollback()
            flash("This email is already registered. Please log in.", "error")

        except sqlite3.Error:
            if connection:
                connection.rollback()
            app.logger.exception("Registration database error")
            flash("Registration failed. Check the Terminal.", "error")

        finally:
            close_db(connection, cursor)

    return render_template("register.html")


# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        connection = None
        cursor = None

        try:
            connection = get_db()
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT id, username, email, password_hash
                FROM users
                WHERE LOWER(TRIM(email)) = ?
                """,
                (email,)
            )

            user = cursor.fetchone()

            password_ok = False

            if user:
                password_ok = check_password_hash(
                    user["password_hash"], password
                )

            if user and password_ok:
                session.clear()
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                session.permanent = True

                return redirect(url_for("dashboard"))

            flash("Invalid email or password.", "error")

        except sqlite3.Error:
            app.logger.exception("Login database error")
            flash("Database error. Check the Terminal.", "error")

        finally:
            close_db(connection, cursor)

    return render_template("login.html")

# ---------------- LOGOUT ----------------

@app.route("/logout")
@login_required
def logout():

    session.clear()

    return redirect(url_for("home"))


# ---------------- PROTECTED PAGES ----------------

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/budget")
@login_required
def budget():
    return render_template("budget.html")


@app.route("/business")
@login_required
def business():
    return render_template("business.html")


@app.route("/simulator")
@login_required
def simulator():
    return render_template("simulator.html")


@app.route("/voice")
@login_required
def voice():
    return render_template("voice.html")


# ---------------- DASHBOARD SUMMARY ----------------

@app.route("/api/dashboard-summary")
@login_required
def dashboard_summary():

    user_id = session["user_id"]
    month = date.today().replace(day=1).isoformat()

    connection = None
    cursor = None

    try:
        connection = get_db()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                COALESCE(SUM(
                    CASE WHEN transaction_type = 'income'
                    THEN amount ELSE 0 END
                ), 0) AS income,

                COALESCE(SUM(
                    CASE WHEN transaction_type = 'expense'
                    THEN amount ELSE 0 END
                ), 0) AS expenses

            FROM transactions
            WHERE user_id = ?
            AND transaction_date >= ?
            """,
            (user_id, month)
        )

        result = cursor.fetchone()

        income = to_number(result["income"])
        expenses = to_number(result["expenses"])

        cursor.execute(
            """
            SELECT total_budget, used_amount
            FROM monthly_budgets
            WHERE user_id = ?
            AND budget_month = ?
            """,
            (user_id, month)
        )

        budget_record = cursor.fetchone()

        if budget_record:
            income = to_number(budget_record["total_budget"])
            expenses = to_number(budget_record["used_amount"])

        return jsonify({
            "username": session.get("username", ""),
            "income": income,
            "expenses": expenses,
            "savings": max(0, income - expenses),
            "remaining": income - expenses,
            "month": month
        })

    except sqlite3.Error:
        app.logger.exception("Dashboard summary error")

        return jsonify({
            "error": "Could not load dashboard data."
        }), 500

    finally:
        close_db(connection, cursor)


# ---------------- MONTHLY BUDGET ----------------

@app.route("/api/monthly-budget", methods=["GET", "POST"])
@login_required
def monthly_budget():

    user_id = session["user_id"]

    month_value = request.values.get(
        "month",
        date.today().replace(day=1).isoformat()
    )

    try:
        month = date.fromisoformat(
            month_value
        ).replace(day=1).isoformat()

    except ValueError:
        return jsonify({
            "error": "Invalid month."
        }), 400

    connection = None
    cursor = None

    try:
        connection = get_db()
        cursor = connection.cursor()

        if request.method == "POST":

            data = request.get_json(silent=True) or {}

            try:
                income = float(data.get("income", 0))
                expenses = float(data.get("expenses", 0))

            except (TypeError, ValueError):
                return jsonify({
                    "error": "Enter valid amounts."
                }), 400

            if income < 0 or expenses < 0:
                return jsonify({
                    "error": "Amounts cannot be negative."
                }), 400

            cursor.execute(
                """
                INSERT INTO monthly_budgets
                (user_id, budget_month, total_budget, used_amount)
                VALUES (?, ?, ?, ?)

                ON CONFLICT(user_id, budget_month)
                DO UPDATE SET
                    total_budget = excluded.total_budget,
                    used_amount = excluded.used_amount
                """,
                (user_id, month, income, expenses)
            )

            connection.commit()

            return jsonify({
                "message": "Monthly record saved.",
                "income": income,
                "expenses": expenses,
                "remaining": income - expenses,
                "month": month
            }), 201

        cursor.execute(
            """
            SELECT total_budget, used_amount
            FROM monthly_budgets
            WHERE user_id = ? AND budget_month = ?
            """,
            (user_id, month)
        )

        record = cursor.fetchone()

        if not record:
            return jsonify({
                "month": month,
                "income": 0,
                "expenses": 0,
                "remaining": 0
            })

        income = to_number(record["total_budget"])
        expenses = to_number(record["used_amount"])

        return jsonify({
            "month": month,
            "income": income,
            "expenses": expenses,
            "remaining": income - expenses
        })

    except sqlite3.Error:
        if connection:
            connection.rollback()

        app.logger.exception("Monthly budget error")

        return jsonify({
            "error": "Could not process monthly budget."
        }), 500

    finally:
        close_db(connection, cursor)


# ---------------- MONTHLY HISTORY ----------------

@app.route("/api/monthly-history")
@login_required
def monthly_history():

    connection = None
    cursor = None

    try:
        connection = get_db()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT budget_month, total_budget, used_amount
            FROM monthly_budgets
            WHERE user_id = ?
            ORDER BY budget_month DESC
            """,
            (session["user_id"],)
        )

        rows = cursor.fetchall()
        history = []

        for row in rows:
            income = to_number(row["total_budget"])
            expenses = to_number(row["used_amount"])

            history.append({
                "month": row["budget_month"],
                "income": income,
                "expenses": expenses,
                "remaining": income - expenses
            })

        return jsonify({
            "history": history
        })

    except sqlite3.Error:
        app.logger.exception("Monthly history error")

        return jsonify({
            "error": "Could not load monthly history."
        }), 500

    finally:
        close_db(connection, cursor)


# ---------------- ADD TRANSACTION ----------------

@app.route("/api/transactions", methods=["POST"])
@login_required
def add_transaction():

    data = request.get_json(silent=True) or {}

    try:
        amount = float(data.get("amount", 0))

    except (TypeError, ValueError):
        return jsonify({
            "error": "Invalid amount."
        }), 400

    category = str(data.get("category", "")).strip()

    transaction_type = str(
        data.get("transaction_type", "")
    ).strip().lower()

    transaction_date = str(
        data.get("transaction_date", date.today().isoformat())
    ).strip()

    description = str(data.get("description", "")).strip()

    if amount <= 0:
        return jsonify({
            "error": "Amount must be positive."
        }), 400

    if not category:
        return jsonify({
            "error": "Category is required."
        }), 400

    if transaction_type not in ("income", "expense"):
        return jsonify({
            "error": "Type must be income or expense."
        }), 400

    try:
        date.fromisoformat(transaction_date)

    except ValueError:
        return jsonify({
            "error": "Invalid date."
        }), 400

    connection = None
    cursor = None

    try:
        connection = get_db()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO transactions
            (user_id, transaction_type, amount, category,
             description, transaction_date)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                transaction_type,
                amount,
                category,
                description,
                transaction_date
            )
        )

        connection.commit()

        return jsonify({
            "message": "Transaction saved successfully."
        }), 201

    except sqlite3.Error:
        if connection:
            connection.rollback()

        app.logger.exception("Transaction save error")

        return jsonify({
            "error": "Could not save transaction."
        }), 500

    finally:
        close_db(connection, cursor)


# ---------------- PRIVATE TRANSACTION HISTORY ----------------

@app.route("/api/history")
@login_required
def financial_history():

    connection = None
    cursor = None

    try:
        connection = get_db()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT transaction_id, amount, category,
                   transaction_type, transaction_date, description
            FROM transactions
            WHERE user_id = ?
            ORDER BY transaction_date DESC, transaction_id DESC
            """,
            (session["user_id"],)
        )

        rows = cursor.fetchall()

        transactions = [
            dict(row) for row in rows
        ]

        return jsonify({
            "transactions": transactions
        })

    except sqlite3.Error:
        app.logger.exception("Transaction history error")

        return jsonify({
            "error": "Could not load transaction history."
        }), 500

    finally:
        close_db(connection, cursor)


# ---------------- FINANCE ASSISTANT ----------------

@app.route("/api/chat", methods=["POST"])
@login_required
def ai_chat():

    data = request.get_json(silent=True) or {}

    question = str(
        data.get("message", "")
    ).strip().lower()

    if not question:
        return jsonify({
            "error": "Please type a question."
        }), 400

    if len(question) > 4000:
        return jsonify({
            "error": "Question is too long."
        }), 400

    if any(word in question for word in [
        "hello", "hi", "salam", "assalam"
    ]):
        reply = (
            "Hello! Welcome to Hoorab Finance Assistant. "
            "I can help with budgeting, saving and expenses."
        )

    elif any(word in question for word in [
        "budget", "monthly plan", "manage money"
    ]):
        reply = (
            "Calculate your monthly income, list essential expenses, "
            "set a savings target and track your spending regularly."
        )

    elif any(word in question for word in [
        "save", "saving", "savings"
    ]):
        reply = (
            "Set a realistic savings goal, record your expenses "
            "and save a manageable amount regularly."
        )

    elif any(word in question for word in [
        "expense", "spending", "spent"
    ]):
        reply = (
            "Record expenses by date and category. Compare your "
            "spending with your monthly budget."
        )

    elif any(word in question for word in [
        "income", "salary", "earning"
    ]):
        reply = (
            "Record your income, plan essential expenses first "
            "and then decide your savings target."
        )

    elif any(word in question for word in [
        "business", "profit", "sales"
    ]):
        reply = (
            "Business profit is calculated by subtracting total "
            "costs from total revenue."
        )

    else:
        reply = (
            "I can help with budgeting, income, savings, expenses "
            "and business planning."
        )

    return jsonify({
        "reply": reply
    })


# ---------------- RUN APPLICATION ----------------
if __name__ == "__main__":
    app.run(debug=True)
