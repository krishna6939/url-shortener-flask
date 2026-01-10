from flask import Flask, request, redirect, render_template, session, url_for
import sqlite3
import string
import random
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "super-secret-key"

# ---------- ADMIN CREDENTIALS ----------
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = generate_password_hash("admin123")

# ---------- DATABASE ----------
def init_db():
    conn = sqlite3.connect("urls.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            short_code TEXT UNIQUE NOT NULL,
            original_url TEXT NOT NULL,
            clicks INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    return sqlite3.connect("urls.db")

# ---------- HELPERS ----------
def generate_short_code(length=6):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))

def login_required():
    return session.get("admin_logged_in")

# ---------- ROUTES ----------
@app.route("/", methods=["GET", "POST"])
def home():
    short_url = None
    error = None

    if request.method == "POST":
        original_url = request.form["url"]
        custom_code = request.form.get("custom_code")

        short_code = custom_code if custom_code else generate_short_code()

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO urls (short_code, original_url) VALUES (?, ?)",
                (short_code, original_url)
            )
            conn.commit()
            conn.close()

            short_url = request.host_url + short_code

        except sqlite3.IntegrityError:
            error = "Short code already exists. Try another."

    return render_template("index.html", short_url=short_url, error=error)

@app.route("/<short_code>")
def redirect_url(short_code):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT original_url FROM urls WHERE short_code = ?",
        (short_code,)
    )
    row = cursor.fetchone()

    if row:
        cursor.execute(
            "UPDATE urls SET clicks = clicks + 1 WHERE short_code = ?",
            (short_code,)
        )
        conn.commit()
        conn.close()
        return redirect(row[0])

    conn.close()
    return "URL not found", 404

# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == ADMIN_USERNAME and check_password_hash(
            ADMIN_PASSWORD_HASH, password
        ):
            session["admin_logged_in"] = True
            return redirect(url_for("admin"))
        else:
            error = "Invalid credentials"

    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------- ADMIN ----------
@app.route("/admin")
def admin():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT short_code, original_url, clicks FROM urls")
    urls = cursor.fetchall()
    conn.close()

    return render_template("admin.html", urls=urls)

# ---------- RUN ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
