import os
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

import pymysql

# ---------------- PROJECT SETTINGS ----------------

app = Flask(__name__)

app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "local-development-key-change-before-deployment"
)

# ---------------- AIVEN MYSQL CONNECTION ----------------
# Password ko code me mat likhna, neeche wali jagah se lena hai

def get_db():
    connection = pymysql.connect(
        host=os.getenv("MYSQL_HOST", "mysql-2f07378e-hoorab-finance.l.aivencloud.com"),
        port=int(os.getenv("MYSQL_PORT", "16301")),
        user=os.getenv("MYSQL_USER", "avnadmin"),
        password=os.getenv("MYSQL_PASSWORD", "APNA_PASSWORD_YAHAN LIKHAN"),
        database=os.getenv("MYSQL_DB", "defaultdb"),
        cursorclass=pymysql.cursors.Cursor,
        autocommit=False
    )
    return connection

def to_number(value):
    if isinstance(value, Decimal):
        return float(value)
    return float(value or 0)

def close_db(connection=None, cursor=None):
    if cursor is not None:
        try:
            cursor.close()
        except:
            pass
    if connection is not None:
        try:
            connection.close()
        except:
            pass

# ---------------- DATABASE CONNECTION TEST ----------------

def test_database():
    connection = None
    try:
        connection = get_db()
        cursor = connection.cursor()
        cursor.execute("SELECT DATABASE()")
        result = cursor.fetchone()
        print("DATABASE CONNECTED SUCCESSFULLY!")
        print("DATABASE NAME:", result[0])
        cursor.close()
    except Exception as e:
        print("MySQL connection failed:", e)
        raise
    finally:
        if connection:
            connection.close()

test_database()

# ---------------- LOGIN PROTECTION ----------------

def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Please log in first."}), 401
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
            cursor.execute(
                "SELECT UserID FROM Users WHERE Email = %s",
                (email,)
            )
            existing_user = cursor.fetchone()
            if existing_user:
                flash("This email is already registered. Please log in.", "error")
                return render_template("register.html")

            password_hash = generate_password_hash(password)

            cursor.execute(
                """
                INSERT INTO Users
                    (FullName, Email, PasswordHash, CreatedAt)
                VALUES (%s, %s, %s, NOW())
                """,
                (username, email, password_hash)
            )
            cursor.execute("SELECT LAST_INSERT_ID()")
            new_user_id = cursor.fetchone()[0]
            connection.commit()

            session.clear()
            session["user_id"] = new_user_id
            session["username"] = username
            session.permanent = True
            return redirect(url_for("dashboard"))

        except Exception as e:
            if connection:
                connection.rollback()
            app.logger.exception("Registration database error: %s", e)
            flash("Database error. Check the Terminal.", "error")
        finally:
            close_db(connection, cursor)
    return render_template("register.html")

# ---------------- LOGIN - YE WALA HISSA AAP KE CODE ME NAHI THA, IS LIYE ADD KIYA HAI ----------------
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
            cursor.execute("SELECT UserID, FullName, PasswordHash FROM Users WHERE Email = %s", (email,))
            user = cursor.fetchone()
            if user and check_password_hash(user[2], password):
                session.clear()
                session["user_id"] = user[0]
                session["username"] = user[1]
                session.permanent = True
                return redirect(url_for("dashboard"))
            flash("Invalid email or password.", "error")
        except Exception as e:
            app.logger.exception("Login error: %s", e)
            flash("Database error.", "error")
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
    today = date.today()
    month_start = today.replace(day=1)
    if today.month == 12:
        next_month = date(today.year + 1, 1, 1)
    else:
        next_month = date(today.year, today.month + 1, 1)
    connection = None
    cursor = None
    try:
        connection = get_db()
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN TransactionType = 'income' THEN Amount ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN TransactionType = 'expense' THEN Amount ELSE 0 END), 0)
            FROM Transactions
            WHERE UserID = %s
            AND TransactionDate >= %s
            AND TransactionDate < %s
            """,
            (user_id, month_start, next_month)
        )
        result = cursor.fetchone()
        income = to_number(result[0])
        expenses = to_number(result[1])
        cursor.execute(
            """
            SELECT MonthlyBudget FROM Budgets
            WHERE UserID = %s AND `Month` = %s AND `Year` = %s
            """,
            (user_id, today.month, today.year)
        )
        budget_record = cursor.fetchone()
        monthly_budget = to_number(budget_record[0]) if budget_record else 0
        return jsonify({
            "username": session.get("username", ""),
            "income": income,
            "expenses": expenses,
            "budget": monthly_budget,
            "savings": income - expenses,
            "remaining": monthly_budget - expenses,
            "month": month_start.isoformat()
        })
    except Exception:
        app.logger.exception("Dashboard summary error")
        return jsonify({"error": "Could not load dashboard data."}), 500
    finally:
        close_db(connection, cursor)

# ---------------- MONTHLY BUDGET ----------------

@app.route("/api/monthly-budget", methods=["GET", "POST"])
@login_required
def monthly_budget():
    user_id = session["user_id"]
    connection = None
    cursor = None
    try:
        if request.method == "POST":
            data = request.get_json(silent=True) or {}
            budget_value = data.get("monthly_budget", data.get("budget", data.get("income", 0)))
            try:
                budget_amount = float(budget_value)
            except (TypeError, ValueError):
                return jsonify({"error": "Enter a valid budget."}), 400
            if budget_amount < 0:
                return jsonify({"error": "Budget cannot be negative."}), 400
            month_value = data.get("month", date.today().strftime("%Y-%m"))
        else:
            month_value = request.args.get("month", date.today().strftime("%Y-%m"))
        try:
            selected_month = date.fromisoformat(month_value[:7] + "-01")
        except ValueError:
            return jsonify({"error": "Invalid month."}), 400

        connection = get_db()
        cursor = connection.cursor()
        month = selected_month.month
        year = selected_month.year
        if request.method == "POST":
            cursor.execute(
                "SELECT BudgetID FROM Budgets WHERE UserID = %s AND `Month` = %s AND `Year` = %s",
                (user_id, month, year)
            )
            existing = cursor.fetchone()
            if existing:
                cursor.execute("UPDATE Budgets SET MonthlyBudget = %s WHERE BudgetID = %s", (budget_amount, existing[0]))
            else:
                cursor.execute(
                    "INSERT INTO Budgets (UserID, MonthlyBudget, `Month`, `Year`, CreatedAt) VALUES (%s, %s, %s, %s, NOW())",
                    (user_id, budget_amount, month, year)
                )
            connection.commit()
        if month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month + 1, 1)
        cursor.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN TransactionType = 'income' THEN Amount ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN TransactionType = 'expense' THEN Amount ELSE 0 END), 0)
            FROM Transactions
            WHERE UserID = %s AND TransactionDate >= %s AND TransactionDate < %s
            """,
            (user_id, selected_month, next_month)
        )
        totals = cursor.fetchone()
        income = to_number(totals[0])
        expenses = to_number(totals[1])
        cursor.execute("SELECT MonthlyBudget FROM Budgets WHERE UserID = %s AND `Month` = %s AND `Year` = %s", (user_id, month, year))
        record = cursor.fetchone()
        budget_amount = to_number(record[0]) if record else 0
        return jsonify({
            "month": selected_month.isoformat(),
            "budget": budget_amount,
            "income": income,
            "expenses": expenses,
            "remaining": budget_amount - expenses
        }), 201 if request.method == "POST" else 200
    except Exception:
        if connection:
            connection.rollback()
        app.logger.exception("Monthly budget error")
        return jsonify({"error": "Could not process monthly budget."}), 500
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
            SELECT
                b.`Month`, b.`Year`, b.MonthlyBudget,
                COALESCE(SUM(CASE WHEN t.TransactionType = 'income' THEN t.Amount ELSE 0 END), 0) AS Income,
                COALESCE(SUM(CASE WHEN t.TransactionType = 'expense' THEN t.Amount ELSE 0 END), 0) AS Expenses
            FROM Budgets b
            LEFT JOIN Transactions t
                ON b.UserID = t.UserID
                AND MONTH(t.TransactionDate) = b.`Month`
                AND YEAR(t.TransactionDate) = b.`Year`
            WHERE b.UserID = %s
            GROUP BY b.`Month`, b.`Year`, b.MonthlyBudget
            ORDER BY b.`Year` DESC, b.`Month` DESC
            """,
            (session["user_id"],)
        )
        rows = cursor.fetchall()
        history = []
        for row in rows:
            income = to_number(row[3])
            expenses = to_number(row[4])
            budget_amount = to_number(row[2])
            history.append({
                "month": f"{row[1]}-{row[0]:02d}",
                "income": income,
                "expenses": expenses,
                "budget": budget_amount,
                "remaining": budget_amount - expenses
            })
        return jsonify({"history": history})
    except Exception:
        app.logger.exception("Monthly history error")
        return jsonify({"error": "Could not load monthly history."}), 500
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
        return jsonify({"error": "Invalid amount."}), 400
    category = str(data.get("category", "")).strip()
    transaction_type = str(data.get("transaction_type", "")).strip().lower()
    transaction_date = str(data.get("transaction_date", date.today().isoformat())).strip()
    description = str(data.get("description", "")).strip()
    if amount <= 0:
        return jsonify({"error": "Amount must be positive."}), 400
    if not category:
        return jsonify({"error": "Category is required."}), 400
    if transaction_type not in ("income", "expense"):
        return jsonify({"error": "Type must be income or expense."}), 400
    try:
        transaction_date = date.fromisoformat(transaction_date)
    except ValueError:
        return jsonify({"error": "Invalid date."}), 400
    connection = None
    cursor = None
    try:
        connection = get_db()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO Transactions (UserID, TransactionType, Amount, Category, Description, TransactionDate)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (session["user_id"], transaction_type, amount, category, description, transaction_date)
        )
        connection.commit()
        return jsonify({"message": "Transaction saved successfully."}), 201
    except Exception:
        if connection:
            connection.rollback()
        app.logger.exception("Transaction save error")
        return jsonify({"error": "Could not save transaction."}), 500
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
            SELECT TransactionID, Amount, Category, TransactionType, TransactionDate, Description
            FROM Transactions WHERE UserID = %s ORDER BY TransactionDate DESC, TransactionID DESC
            """,
            (session["user_id"],)
        )
        rows = cursor.fetchall()
        transactions = []
        for row in rows:
            transactions.append({
                "transaction_id": row[0],
                "amount": to_number(row[1]),
                "category": row[2],
                "transaction_type": row[3],
                "transaction_date": row[4].isoformat() if row[4] else None,
                "description": row[5]
            })
        return jsonify({"transactions": transactions})
    except Exception:
        app.logger.exception("Transaction history error")
        return jsonify({"error": "Could not load transaction history."}), 500
    finally:
        close_db(connection, cursor)

# ---------------- FINANCE ASSISTANT ----------------

@app.route("/api/chat", methods=["POST"])
@login_required
def ai_chat():
    data = request.get_json(silent=True) or {}
    question = str(data.get("message", "")).strip().lower()
    if not question:
        return jsonify({"error": "Please type a question."}), 400
    if len(question) > 4000:
        return jsonify({"error": "Question is too long."}), 400
    if any(word in question for word in ["hello", "hi", "salam", "assalam"]):
        reply = "Hello! Welcome to Hoorab Finance Assistant. I can help with budgeting, saving and expenses."
    elif any(word in question for word in ["budget", "monthly plan", "manage money"]):
        reply = "Calculate your monthly income, list essential expenses, set a savings target and track your spending."
    elif any(word in question for word in ["save", "saving", "savings"]):
        reply = "Set a realistic savings goal, record your expenses and save a manageable amount regularly."
    elif any(word in question for word in ["business", "profit", "sales"]):
        reply = "Business profit is calculated by subtracting total costs from total revenue."
    else:
        reply = "I can help with budgeting, income, savings, expenses and business planning."
    return jsonify({"reply": reply})

# ---------------- RUN APPLICATION ----------------

if __name__ == "__main__":
    app.run(debug=True)