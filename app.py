from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
import string, random
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "secret-key-change-this"

DB = "urls.db"

# ---------- ADMIN CREDENTIALS ----------
ADMIN_USER = "admin"
ADMIN_PASS_HASH = generate_password_hash("admin123")

# ---------- RESERVED ROUTES ----------
RESERVED_ROUTES = ["admin", "login", "logout", "stats", "toggle"]

# ---------- DATABASE ----------
def get_db():
    return sqlite3.connect(DB)

def init_db():
    with get_db() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            short_code TEXT UNIQUE,
            original_url TEXT,
            clicks INTEGER DEFAULT 0,
            expires_at TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT
        )
        """)

init_db()

# ---------- HELPERS ----------
def generate_code(length=6):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def is_expired(row):
    if row[4]:
        return datetime.now() > datetime.fromisoformat(row[4])
    return False

# ---------- ROUTES ----------
@app.route("/", methods=["GET", "POST"])
def index():
    short_url = None
    message = None

    if request.method == "POST":
        original = request.form["url"]
        custom = request.form["custom"].strip()
        expiry = request.form["expiry"]

        code = custom if custom else generate_code()

        if code in RESERVED_ROUTES:
            message = "This short code is reserved. Choose another."
        else:
            with get_db() as con:
                try:
                    con.execute(
                        "INSERT INTO urls (short_code, original_url, expires_at, created_at) VALUES (?, ?, ?, ?)",
                        (code, original, expiry or None, datetime.now().isoformat())
                    )
                    short_url = request.host_url + code
                except sqlite3.IntegrityError:
                    message = "Short code already exists. Try another."

    return render_template("index.html", short_url=short_url, message=message)

@app.route("/<code>")
def redirect_url(code):
    if code in RESERVED_ROUTES:
        return redirect(url_for(code))

    with get_db() as con:
        row = con.execute(
            "SELECT * FROM urls WHERE short_code=? AND is_active=1",
            (code,)
        ).fetchone()

        if not row or is_expired(row):
            return render_template("expired.html")

        con.execute(
            "UPDATE urls SET clicks = clicks + 1 WHERE short_code=?",
            (code,)
        )

        return redirect(row[2])

@app.route("/stats/<code>")
def stats(code):
    with get_db() as con:
        row = con.execute(
            "SELECT * FROM urls WHERE short_code=?",
            (code,)
        ).fetchone()

    if not row:
        return render_template("expired.html")

    return render_template("stats.html", row=row)

# ---------- ADMIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        user = request.form["username"]
        pwd = request.form["password"]

        if user == ADMIN_USER and check_password_hash(ADMIN_PASS_HASH, pwd):
            session["admin"] = True
            return redirect("/admin")
        else:
            error = "Invalid username or password"

    return render_template("login.html", error=error)

@app.route("/admin")
def admin():
    if not session.get("admin"):
        return redirect("/login")

    with get_db() as con:
        data = con.execute("SELECT * FROM urls").fetchall()

    return render_template("admin.html", data=data)

@app.route("/toggle/<code>")
def toggle(code):
    if not session.get("admin"):
        return redirect("/login")

    with get_db() as con:
        con.execute(
            "UPDATE urls SET is_active = NOT is_active WHERE short_code=?",
            (code,)
        )

    return redirect("/admin")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

if __name__ == "__main__":
    app.run(debug=True)
