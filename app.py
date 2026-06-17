from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import hmac
import os
import re
import secrets
import stat
import time
from datetime import date, timedelta
import sqlite3
from flask_bcrypt import Bcrypt
import numpy as np
from sentence_transformers import SentenceTransformer
from urllib.parse import urlparse


#Faster loading times -- used to take ~ at least a minute to load. Very concerning. 
embed_model = None

def get_model():
    global embed_model
    if embed_model is None:
        embed_model = SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
    return embed_model

import os
from dotenv import load_dotenv
import google.generativeai as genai

from flask import Flask, render_template, Response
from barcode import Code39
from barcode.writer import SVGWriter
import io

load_dotenv(override=True) # LOADS ENV FILE THAT IS HIDDEN FROM GITHUB.  -- OVERIDE NOT OPTIMAL - WILL FIND OUT WHAT'S WRONG SOON. 

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")


app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')

bcrypt = Bcrypt(app)

ALLOWED_EMAIL_DOMAIN = "education.nsw.gov.au"
STUDENT_NUMBER_RE = re.compile(r"^\d{9}$")
EMAIL_RE = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.IGNORECASE)
PASSWORD_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$")

LOGIN_RATE_LIMIT_WINDOW_SECONDS = 15 * 60
LOGIN_RATE_LIMIT_MAX_FAILURES = 5
LOGIN_LOCKOUT_SECONDS = 15 * 60
login_failures = {}

app.secret_key = (
    os.getenv("SECRET_KEY")
    or os.getenv("FLASK_SECRET_KEY")
    or secrets.token_hex(32)
)
app.permanent_session_lifetime = timedelta(hours=1)

if not os.getenv("SECRET_KEY") and not os.getenv("FLASK_SECRET_KEY"):
    print("WARNING: SECRET_KEY is not set. Using a temporary development secret for this run.")


### CSRF PROTECTION 
def csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


app.jinja_env.globals["csrf_token"] = csrf_token


def valid_csrf() -> bool:
    return valid_csrf_token_value(request.form.get("_csrf_token", ""))


def valid_json_csrf() -> bool:
    return valid_csrf_token_value(request.headers.get("X-CSRFToken", ""))


def valid_csrf_token_value(submitted: str) -> bool:
    token = session.get("_csrf_token")
    return bool(token and submitted and hmac.compare_digest(token, submitted))


def is_valid_school_email(email: str) -> bool:
    return bool(email and EMAIL_RE.match(email) and email.endswith(f"@{ALLOWED_EMAIL_DOMAIN}"))


def is_strong_password(password: str) -> bool:
    return bool(PASSWORD_RE.match(password or ""))


def normalize_security_answer(answer: str) -> str:
    return re.sub(r"\s+", " ", (answer or "").strip().lower())


def is_valid_student_number(student_number) -> bool:
    return student_number is None or bool(STUDENT_NUMBER_RE.match(student_number))


def clean_old_login_failures(now=None):
    now = now or time.time()
    expired_before = now - max(LOGIN_RATE_LIMIT_WINDOW_SECONDS, LOGIN_LOCKOUT_SECONDS)
    for key, entry in list(login_failures.items()):
        if entry["updated_at"] < expired_before and entry.get("locked_until", 0) < now:
            login_failures.pop(key, None)


def login_rate_key(email: str):
    return ((email or "").strip().lower(), request_ip())


def login_is_locked(email: str) -> bool:
    now = time.time()
    clean_old_login_failures(now)
    entry = login_failures.get(login_rate_key(email))
    return bool(entry and entry.get("locked_until", 0) > now)


def record_failed_login(email: str):
    now = time.time()
    clean_old_login_failures(now)
    key = login_rate_key(email)
    entry = login_failures.setdefault(key, {"count": 0, "first_at": now, "updated_at": now, "locked_until": 0})

    if now - entry["first_at"] > LOGIN_RATE_LIMIT_WINDOW_SECONDS:
        entry.update({"count": 0, "first_at": now, "locked_until": 0})

    entry["count"] += 1
    entry["updated_at"] = now
    if entry["count"] >= LOGIN_RATE_LIMIT_MAX_FAILURES:
        entry["locked_until"] = now + LOGIN_LOCKOUT_SECONDS


def clear_failed_logins(email: str):
    login_failures.pop(login_rate_key(email), None)


def harden_sqlite_permissions(db_path: str):
    if os.name == "posix" and os.path.exists(db_path):
        os.chmod(db_path, stat.S_IRUSR | stat.S_IWUSR)


def harden_project_databases():
    harden_sqlite_permissions("girra_portal.db")
    harden_sqlite_permissions("knowledge.db")

AI_UNAVAILABLE_REPLY = (
    "CENTRAL's AI features are not available on this computer right now. "
    "The main portal is still usable. Check that GEMINI_API_KEY is set, "
    "dependencies are installed, and knowledge.db has been built with ingest_documents.py."
)

def search_documents(question, top_k=4):
    if not os.path.exists("knowledge.db"):
        return []

    conn = sqlite3.connect("knowledge.db")
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'documents'")
    if not cur.fetchone():
        conn.close()
        return []

    cur.execute("SELECT filename, content, embedding FROM documents")
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return []

    q_emb = get_model().encode(question)

    scored = []

    for filename, content, emb_blob in rows:
        emb = np.frombuffer(emb_blob, dtype=np.float32)

        similarity = np.dot(q_emb, emb) / (
            np.linalg.norm(q_emb) * np.linalg.norm(emb)
        )

        scored.append((similarity, filename, content))

    scored.sort(reverse=True)

    return scored[:top_k]

def get_db():
    conn = sqlite3.connect("girra_portal.db") 
    conn.row_factory = sqlite3.Row
    return conn

def ensure_portal_tables():               ### REDUNDANCY ONE - TO PREVENT SQL ERRORS WHEN TABLES ARE UPDATED/ADDED. THIS FUNCTION CHECKS FOR EXISTENCE OF TABLES AND COLUMNS AND CREATES/UPDATES AS NEEDED.
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            student_number TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            access_level TEXT NOT NULL CHECK(access_level IN ('7','8','9','10','11','12','T')),
            role TEXT NOT NULL DEFAULT 'student' CHECK(role IN ('student','teacher','admin')),
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_student_number
        ON users(student_number)
        WHERE student_number IS NOT NULL;
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            drive_url TEXT NOT NULL,
            subject TEXT NOT NULL,
            min_level TEXT NOT NULL CHECK(min_level IN ('7','8','9','10','11','12','T')),
            created_by INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)

    cur.execute("PRAGMA table_info(users)")
    user_columns = {column["name"] for column in cur.fetchall()}
    if "role" not in user_columns:
        cur.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'student'")
    if "student_number" not in user_columns:
        cur.execute("ALTER TABLE users ADD COLUMN student_number TEXT")

    cur.execute("PRAGMA table_info(resources)")
    resource_columns = {column["name"] for column in cur.fetchall()}
    if "created_by" not in resource_columns:
        cur.execute("ALTER TABLE resources ADD COLUMN created_by INTEGER")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_security_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            question_key TEXT NOT NULL,
            question_text TEXT NOT NULL,
            answer_hash TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, question_key)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS content_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_type TEXT NOT NULL CHECK(content_type IN ('announcement','news')),
            title TEXT NOT NULL,
            category TEXT,
            body TEXT NOT NULL,
            created_by INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (created_by) REFERENCES users(id)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_id INTEGER,
            action TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id INTEGER,
            details TEXT,
            ip_address TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (actor_id) REFERENCES users(id)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS teacher_conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            teacher_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','answered','closed')),
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES users(id),
            FOREIGN KEY (teacher_id) REFERENCES users(id)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS teacher_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (conversation_id) REFERENCES teacher_conversations(id),
            FOREIGN KEY (sender_id) REFERENCES users(id)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_read_state (
            user_id INTEGER NOT NULL,
            item_type TEXT NOT NULL,
            item_id INTEGER NOT NULL DEFAULT 0,
            last_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (user_id, item_type, item_id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS login_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_activity_daily (
            user_id INTEGER NOT NULL,
            activity_date TEXT NOT NULL,
            active_minutes INTEGER NOT NULL DEFAULT 0,
            login_count INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (user_id, activity_date),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_teacher_conversations_student
        ON teacher_conversations(student_id, updated_at);
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_teacher_conversations_teacher
        ON teacher_conversations(teacher_id, updated_at);
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_login_events_user_created
        ON login_events(user_id, created_at);
    """)
    conn.commit()
    conn.close()
    harden_project_databases()

def ensure_security_questions_table():
    ensure_portal_tables()

SECURITY_QUESTIONS = [
    {
        "key": "previous_school",
        "text": "What was the first school you attended before Girraween?"
    },
    {
        "key": "high_school_street",
        "text": "What was the name of the street you lived on when you started high school?"
    },
    {
        "key": "childhood_item",
        "text": "What was the name of your first pet or favourite childhood item?"
    },
]

LEVEL_ORDER = {'7':7,'8':8,'9':9,'10':10,'11':11,'12':12,'T':99}

## DYNAMIC SCHOOL WEEK DISPLAYER! 
NSW_SCHOOL_TERMS = {
    2026: [
        (1, date(2026, 2, 2), date(2026, 4, 2)),
        (2, date(2026, 4, 22), date(2026, 7, 3)),
        (3, date(2026, 7, 21), date(2026, 9, 25)),
        (4, date(2026, 10, 13), date(2026, 12, 17)),
    ],
}

def get_school_term_label(today=None):
    today = today or date.today()
    terms = NSW_SCHOOL_TERMS.get(today.year, [])

    for term_number, start_date, end_date in terms:
        if start_date <= today <= end_date:
            week_number = ((today - start_date).days // 7) + 1
            return f"Term {term_number}, Week {week_number}, {today.year}"

    return f"School Holidays, {today.year}"

def can_access(user_level: str, min_level: str) -> bool:
    return LEVEL_ORDER.get(user_level, 0) >= LEVEL_ORDER.get(min_level, 0)

def current_role() -> str:
    return session.get("role", "teacher" if session.get("access_level") == "T" else "student")

def is_teacher() -> bool:
    return current_role() == "teacher" and session.get("access_level") == "T"

def is_admin() -> bool:
    return current_role() == "admin"

def can_publish_posts() -> bool:
    return is_teacher() or is_admin()

def can_manage_resources() -> bool:
    return is_teacher() or is_admin()

# TEACHERS AND ADMINS CAN HANDLE STUDENT MESSAGE THREADS.
def can_answer_teacher_messages() -> bool:
    return is_teacher() or is_admin()

def is_google_drive_url(value: str) -> bool:
    parsed = urlparse(value)
    hostname = (parsed.hostname or "").lower()
    return parsed.scheme in ("http", "https") and hostname in ("drive.google.com", "docs.google.com")

def require_login():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return None

def require_teacher():
    login_redirect = require_login()
    if login_redirect:
        return login_redirect
    if not is_teacher():
        return "Forbidden", 403
    return None

def require_publisher():
    login_redirect = require_login()
    if login_redirect:
        return login_redirect
    if not can_publish_posts():
        return "Forbidden", 403
    return None

def require_resource_manager():
    login_redirect = require_login()
    if login_redirect:
        return login_redirect
    if not can_manage_resources():
        return "Forbidden", 403
    return None

def require_admin():
    login_redirect = require_login()
    if login_redirect:
        return login_redirect
    if not is_admin():
        return "Forbidden", 403
    return None

def request_ip() -> str:
    if os.getenv("TRUST_PROXY_HEADERS", "").lower() == "true":
        forwarded_for = request.headers.get("X-Forwarded-For", "")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
    return request.remote_addr or ""

def audit(action: str, target_type: str, target_id=None, details: str = ""):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO audit_log (actor_id, action, target_type, target_id, details, ip_address)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (session.get("user_id"), action, target_type, target_id, details, request_ip()))
    conn.commit()
    conn.close()

def record_login_event(user_id: int):                   ### USED FOR ANALYTICS AND SECURITY MONITORING - STORES LOGIN TIME, IP, AND USER AGENT. ALSO UPDATES DAILY ACTIVITY SUMMARY.
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO login_events (user_id, ip_address, user_agent)
        VALUES (?, ?, ?)
    """, (user_id, request_ip(), request.headers.get("User-Agent", "")))
    cur.execute("""
        INSERT INTO user_activity_daily (user_id, activity_date, active_minutes, login_count, updated_at)
        VALUES (?, date('now', 'localtime'), 0, 1, datetime('now'))
        ON CONFLICT(user_id, activity_date)
        DO UPDATE SET
            login_count = login_count + 1,
            updated_at = excluded.updated_at
    """, (user_id,))
    conn.commit()
    conn.close()


def record_activity_minute(user_id: int, minutes: int = 1):
    minutes = max(1, min(int(minutes), 5))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO user_activity_daily (user_id, activity_date, active_minutes, login_count, updated_at)
        VALUES (?, date('now', 'localtime'), ?, 0, datetime('now'))
        ON CONFLICT(user_id, activity_date)
        DO UPDATE SET
            active_minutes = active_minutes + excluded.active_minutes,
            updated_at = excluded.updated_at
    """, (user_id, minutes))
    conn.commit()
    conn.close()


def get_user_activity_summary(user_id: int):           ### SUMMARISES DATA ON A VERY NEAT HEATMAP 
    today_date = date.today()
    start_date = date(today_date.year, 1, 1)
    end_date = date(today_date.year, 12, 31)
    days = (end_date - start_date).days + 1

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT activity_date, active_minutes, login_count
        FROM user_activity_daily
        WHERE user_id = ? AND activity_date BETWEEN ? AND ?
    """, (user_id, start_date.isoformat(), end_date.isoformat()))
    activity_by_date = {
        row["activity_date"]: {
            "minutes": row["active_minutes"],
            "logins": row["login_count"],
        }
        for row in cur.fetchall()
    }
    cur.execute("SELECT COUNT(*) AS count FROM login_events WHERE user_id = ?", (user_id,))
    total_logins = cur.fetchone()["count"]
    conn.close()

    days_data = []
    total_minutes = 0
    active_days = 0
    for offset in range(days):
        current_date = start_date + timedelta(days=offset)
        key = current_date.isoformat()
        values = activity_by_date.get(key, {"minutes": 0, "logins": 0})
        minutes = values["minutes"]
        logins = values["logins"]
        is_future = current_date > today_date
        if not is_future:
            total_minutes += minutes
        if not is_future and (minutes > 0 or logins > 0):
            active_days += 1
        days_data.append({
            "date": key,
            "label": current_date.strftime("%d %b %Y"),
            "minutes": minutes,
            "logins": logins,
            "future": is_future,
            "level": activity_level(minutes),
        })

    current_streak = 0
    past_days = [item for item in days_data if not item["future"]]
    for item in reversed(past_days):
        if item["minutes"] > 0 or item["logins"] > 0:
            current_streak += 1
        else:
            break

    padded_days = [{"empty": True} for _ in range(start_date.weekday())] + days_data
    weeks = [padded_days[i:i + 7] for i in range(0, len(padded_days), 7)]
    today = past_days[-1] if past_days else {"minutes": 0, "logins": 0}

    return {
        "weeks": weeks,
        "year": today_date.year,
        "total_minutes": total_minutes,
        "hours": total_minutes // 60,
        "remaining_minutes": total_minutes % 60,
        "today_minutes": today["minutes"],
        "today_logins": today["logins"],
        "total_logins": total_logins,
        "active_days": active_days,
        "current_streak": current_streak,
    }


def activity_level(minutes: int) -> int:
    if minutes <= 0:
        return 0
    if minutes < 5:
        return 1
    if minutes < 15:
        return 2
    if minutes < 30:
        return 3
    return 4

def log_resource_access(user_id: int, resource_id: int): 
    ip = request_ip()          #LOGGING OF IP'S TO DETER RESOURCE DISTRIBUTION/ABUSE OF SERVICE
    ua = request.headers.get("User-Agent", "")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO resource_access (user_id, resource_id, ip_address, user_agent)
        VALUES (?, ?, ?, ?)
    """, (user_id, resource_id, ip, ua))
    conn.commit()
    conn.close()


def mark_read(item_type: str, item_id: int = 0):
    user_id = session.get("user_id")
    if not user_id:
        return

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO user_read_state (user_id, item_type, item_id, last_seen_at)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(user_id, item_type, item_id)
        DO UPDATE SET last_seen_at = excluded.last_seen_at
    """, (user_id, item_type, item_id))
    conn.commit()
    conn.close()


def get_last_seen(cur, user_id: int, item_type: str, item_id: int = 0):
    cur.execute("""
        SELECT last_seen_at
        FROM user_read_state
        WHERE user_id = ? AND item_type = ? AND item_id = ?
    """, (user_id, item_type, item_id))
    row = cur.fetchone()
    return row["last_seen_at"] if row else "1970-01-01 00:00:00"


def get_notification_counts():
    if not session.get("logged_in"):
        return {"announcements": 0, "news": 0, "resources": 0, "teacher_chat": 0, "total": 0}

    user_id = session.get("user_id")
    user_level = session.get("access_level", "7")
    conn = get_db()
    cur = conn.cursor()

    announcement_seen = get_last_seen(cur, user_id, "announcements")
    news_seen = get_last_seen(cur, user_id, "news")
    resources_seen = get_last_seen(cur, user_id, "resources")

    cur.execute("""
        SELECT COUNT(*) AS count
        FROM content_items
        WHERE content_type = 'announcement' AND created_at > ?
    """, (announcement_seen,))
    announcements_count = cur.fetchone()["count"]

    cur.execute("""
        SELECT COUNT(*) AS count
        FROM content_items
        WHERE content_type = 'news' AND created_at > ?
    """, (news_seen,))
    news_count = cur.fetchone()["count"]

    if is_admin():
        cur.execute("SELECT COUNT(*) AS count FROM resources WHERE created_at > ?", (resources_seen,))
    else:
        allowed_levels = [level for level in LEVEL_ORDER if can_access(user_level, level)]
        if allowed_levels:
            placeholders = ",".join("?" for _ in allowed_levels)
            cur.execute(
                f"SELECT COUNT(*) AS count FROM resources WHERE created_at > ? AND min_level IN ({placeholders})",
                [resources_seen, *allowed_levels]
            )
        else:
            cur.execute("SELECT 0 AS count")
    resources_count = cur.fetchone()["count"]

    cur.execute("""
        SELECT COUNT(*) AS count
        FROM teacher_conversations AS c
        JOIN teacher_messages AS latest ON latest.id = (
            SELECT id
            FROM teacher_messages
            WHERE conversation_id = c.id
            ORDER BY created_at DESC, id DESC
            LIMIT 1
        )
        LEFT JOIN user_read_state AS rs
            ON rs.user_id = ?
           AND rs.item_type = 'teacher_chat'
           AND rs.item_id = c.id
        WHERE (c.student_id = ? OR c.teacher_id = ?)
          AND latest.sender_id <> ?
          AND latest.created_at > COALESCE(rs.last_seen_at, '1970-01-01 00:00:00')
    """, (user_id, user_id, user_id, user_id))
    teacher_chat_count = cur.fetchone()["count"]
    conn.close()

    total = announcements_count + news_count + resources_count + teacher_chat_count
    return {
        "announcements": announcements_count,
        "news": news_count,
        "resources": resources_count,
        "teacher_chat": teacher_chat_count,
        "total": total,
    }


@app.context_processor
def inject_notifications():
    return {
        "notifications": get_notification_counts(),
        "is_teacher": is_teacher(),
        "is_admin": is_admin(),
    }


ensure_portal_tables()

@app.route('/')
def index():
    """Landing page"""
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/girra-countdown')
def girra_countdown():
    return render_template('girra_countdown.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if not valid_csrf():
            return render_template('login.html', error="Your session expired. Please try again."), 400

        email = (request.form.get('username') or '').strip().lower()
        password = request.form.get('password') or ''
        remember = request.form.get('remember')

        if login_is_locked(email):
            return render_template('login.html', error="Too many failed attempts. Please wait 15 minutes and try again."), 429

        if not is_valid_school_email(email):
            record_failed_login(email)
            return render_template('login.html', error="Invalid email or password")

        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cur.fetchone()
        conn.close()

        if user and bcrypt.check_password_hash(user['password_hash'], password):
            clear_failed_logins(email)
            role = user['role'] if 'role' in user.keys() else ('teacher' if user['access_level'] == 'T' else 'student')
            session.permanent = bool(remember)
            session['logged_in'] = True
            session['user_id'] = user['id']
            session['email'] = user['email']
            session['student_number'] = user['student_number']
            session['access_level'] = user['access_level']
            session['role'] = role
            session['name'] = user['first_name']
            session['full_name'] = f"{user['first_name']} {user['last_name']}"
            record_login_event(user['id'])

            return redirect(url_for('home'))  

        record_failed_login(email)
        return render_template('login.html', error="Invalid email or password")

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    ensure_security_questions_table()

    if request.method == 'POST':
        if not valid_csrf():
            return render_template(
                'register.html',
                error="Your session expired. Please try again.",
                questions=SECURITY_QUESTIONS,
                form=request.form
            ), 400

        first_name = (request.form.get('first_name') or '').strip()
        last_name = (request.form.get('last_name') or '').strip()
        student_number = (request.form.get('student_number') or '').strip() or None
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        confirm_password = request.form.get('confirm_password') or ''
        terms_ack = request.form.get('terms_ack')
        answers = {
            question["key"]: (request.form.get(f"security_{question['key']}") or '').strip()
            for question in SECURITY_QUESTIONS
        }

        if not all([first_name, last_name, email, password, confirm_password]) or not all(answers.values()):
            return render_template(
                'register.html',
                error="Please complete all registration fields.",
                questions=SECURITY_QUESTIONS,
                form=request.form
            )

        if not terms_ack:
            return render_template(
                'register.html',
                error="You must agree to the Terms & Conditions to create an account.",
                questions=SECURITY_QUESTIONS,
                form=request.form
            )

        if not is_valid_school_email(email):
            return render_template(
                'register.html',
                error=f"Please use your @{ALLOWED_EMAIL_DOMAIN} school email address.",
                questions=SECURITY_QUESTIONS,
                form=request.form
            )

        if not is_valid_student_number(student_number):
            return render_template(
                'register.html',
                error="Barcode number must be exactly 9 digits.",
                questions=SECURITY_QUESTIONS,
                form=request.form
            )

        if password != confirm_password:
            return render_template(
                'register.html',
                error="Passwords do not match.",
                questions=SECURITY_QUESTIONS,
                form=request.form
            )

        if not is_strong_password(password):
            return render_template(
                'register.html',
                error="Password must be at least 8 characters and include uppercase, lowercase, and a number.",
                questions=SECURITY_QUESTIONS,
                form=request.form
            )

        password_hash = bcrypt.generate_password_hash(password).decode()

        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO users
                (first_name, last_name, email, student_number, password_hash, access_level)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (first_name, last_name, email, student_number, password_hash, '7'))
            user_id = cur.lastrowid

            for question in SECURITY_QUESTIONS:
                answer_hash = bcrypt.generate_password_hash(normalize_security_answer(answers[question["key"]])).decode()
                cur.execute("""
                    INSERT INTO user_security_questions
                    (user_id, question_key, question_text, answer_hash)
                    VALUES (?, ?, ?, ?)
                """, (user_id, question["key"], question["text"], answer_hash))

            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            return render_template(
                'register.html',
                error="That email address or barcode number is already registered.",
                questions=SECURITY_QUESTIONS,
                form=request.form
            )
        finally:
            conn.close()

        return redirect(url_for('login'))

    return render_template('register.html', questions=SECURITY_QUESTIONS)

@app.route('/home')
def home():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT content_items.*, users.first_name, users.last_name
        FROM content_items
        LEFT JOIN users ON users.id = content_items.created_by
        WHERE content_type = 'announcement'
        ORDER BY created_at DESC
        LIMIT 3
    """)
    announcements = cur.fetchall()
    conn.close()

    return render_template(
        'home.html',
        username=session.get('name', 'Student'),
        school_term=get_school_term_label(),
        announcements=announcements,
        is_teacher=is_teacher(),
        is_admin=is_admin(),
        can_publish=can_publish_posts()
    )


@app.route('/analytics')
def analytics():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    activity = get_user_activity_summary(session['user_id'])
    return render_template('analytics.html', activity=activity)


@app.post('/api/activity/heartbeat')
def activity_heartbeat():
    if not session.get('logged_in'):
        return jsonify({"success": False}), 401
    if not valid_json_csrf():
        return jsonify({"success": False, "message": "Invalid CSRF token"}), 400

    now = time.time()
    last_ping = session.get("last_activity_heartbeat_at", 0)
    if now - float(last_ping or 0) < 50:
        return jsonify({"success": True, "recorded": False})

    session["last_activity_heartbeat_at"] = now
    record_activity_minute(session['user_id'], 1)
    return jsonify({"success": True, "recorded": True})


@app.route('/student-id')
def student_id():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if is_teacher():
        return redirect(url_for('home'))
    
    username = session.get('full_name', session.get('name', 'Student'))
    student_number = session.get('student_number') or str(session.get('user_id'))
    year_level = session.get('access_level', '7')
    role_label = current_role().title()

    return render_template(
        'student_id.html',
        username=username,
        student_id=student_number,
        email=session.get('email', ''),
        year_level=year_level,
        role_label=role_label
    )

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    ensure_security_questions_table()
    user_id = session.get('user_id')
    message = None
    error = None

    if request.method == 'POST':
        if not valid_csrf():
            error = "Your session expired. Please try again."
        else:
            action = request.form.get('action')
            conn = get_db()
            cur = conn.cursor()

            if action == 'profile':
                student_number = (request.form.get('student_number') or '').strip() or None
                if is_valid_student_number(student_number):
                    try:
                        cur.execute("UPDATE users SET student_number = ? WHERE id = ?", (student_number, user_id))
                        conn.commit()
                        session['student_number'] = student_number
                        audit("updated", "profile", user_id, "Updated Girra ID")
                        message = "Profile updated."
                    except sqlite3.IntegrityError:
                        conn.rollback()
                        error = "That Girra ID is already registered."
                else:
                    error = "Girra ID must be exactly 9 digits."

            elif action == 'password':
                current_password = request.form.get('current_password') or ''
                new_password = request.form.get('new_password') or ''
                confirm_password = request.form.get('confirm_password') or ''
                cur.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
                user = cur.fetchone()

                if not user or not bcrypt.check_password_hash(user['password_hash'], current_password):
                    error = "Current password is incorrect."
                elif new_password != confirm_password:
                    error = "New passwords do not match."
                elif not is_strong_password(new_password):
                    error = "Password must be at least 8 characters and include uppercase, lowercase, and a number."
                else:
                    password_hash = bcrypt.generate_password_hash(new_password).decode()
                    cur.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
                    conn.commit()
                    audit("updated", "profile", user_id, "Changed password")
                    message = "Password changed."

            elif action == 'security':
                answers = {
                    question["key"]: (request.form.get(f"security_{question['key']}") or '').strip()
                    for question in SECURITY_QUESTIONS
                }
                if not all(answers.values()):
                    error = "Please answer every security question."
                else:
                    for question in SECURITY_QUESTIONS:
                        answer_hash = bcrypt.generate_password_hash(normalize_security_answer(answers[question["key"]])).decode()
                        cur.execute("""
                            INSERT INTO user_security_questions
                            (user_id, question_key, question_text, answer_hash)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(user_id, question_key)
                            DO UPDATE SET question_text = excluded.question_text,
                                          answer_hash = excluded.answer_hash
                        """, (user_id, question["key"], question["text"], answer_hash))
                    conn.commit()
                    audit("updated", "profile", user_id, "Updated security questions")
                    message = "Security questions updated."

            conn.close()

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT first_name, last_name, email, student_number, access_level, role FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()
    conn.close()

    return render_template(
        'profile.html',
        user=user,
        questions=SECURITY_QUESTIONS,
        message=message,
        error=error
    )

@app.route('/resources')
def resources():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    user_level = session.get('access_level', '7')
    search = (request.args.get('q') or '').strip()
    subject_filter = (request.args.get('subject') or '').strip()
    level_filter = (request.args.get('level') or '').strip()

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT resources.*, users.first_name, users.last_name
        FROM resources
        LEFT JOIN users ON users.id = resources.created_by
        ORDER BY subject, created_at DESC
    """)
    rows = cur.fetchall()
    conn.close()

    allowed, locked = [], []
    subjects = sorted({r['subject'] for r in rows if r['subject']})
    for r in rows:
        resource = dict(r)
        haystack = f"{resource['title']} {resource.get('description') or ''} {resource['subject']}".lower()
        if search and search.lower() not in haystack:
            continue
        if subject_filter and resource['subject'] != subject_filter:
            continue
        if level_filter and resource['min_level'] != level_filter:
            continue
        (allowed if is_admin() or can_access(user_level, resource['min_level']) else locked).append(resource)

    mark_read("resources")

    return render_template(
        'resources.html',
        allowed=allowed,
        locked=locked,
        subjects=subjects,
        search=search,
        subject_filter=subject_filter,
        level_filter=level_filter,
        user_level=user_level,
        can_manage_resources=can_manage_resources(),
        is_admin=is_admin()
    )

@app.post('/teacher/resources')
def teacher_add_resource():
    blocked = require_resource_manager()
    if blocked:
        return blocked

    title = (request.form.get('title') or '').strip()
    description = (request.form.get('description') or '').strip()
    drive_url = (request.form.get('drive_url') or '').strip()
    subject = (request.form.get('subject') or '').strip()
    min_level = (request.form.get('min_level') or '7').strip()

    if not title or not drive_url or not subject or min_level not in LEVEL_ORDER:
        return redirect(url_for('resources'))

    if not is_google_drive_url(drive_url):
        return redirect(url_for('resources'))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO resources (title, description, drive_url, subject, min_level, created_by)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (title, description, drive_url, subject, min_level, session.get('user_id')))
    resource_id = cur.lastrowid
    conn.commit()
    conn.close()
    audit("created", "resource", resource_id, title)
    return redirect(url_for('resources'))

@app.post('/teacher/resources/<int:resource_id>/edit')
def teacher_edit_resource(resource_id):
    blocked = require_resource_manager()
    if blocked:
        return blocked

    title = (request.form.get('title') or '').strip()
    description = (request.form.get('description') or '').strip()
    drive_url = (request.form.get('drive_url') or '').strip()
    subject = (request.form.get('subject') or '').strip()
    min_level = (request.form.get('min_level') or '7').strip()

    if not title or not drive_url or not subject or min_level not in LEVEL_ORDER:
        return redirect(url_for('resources'))
    if not is_google_drive_url(drive_url):
        return redirect(url_for('resources'))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE resources
        SET title = ?, description = ?, drive_url = ?, subject = ?, min_level = ?
        WHERE id = ?
    """, (title, description, drive_url, subject, min_level, resource_id))
    conn.commit()
    conn.close()
    audit("updated", "resource", resource_id, title)
    return redirect(url_for('resources'))

@app.post('/admin/resources/<int:resource_id>/delete')
def admin_delete_resource(resource_id):
    blocked = require_admin()
    if blocked:
        return blocked

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT title FROM resources WHERE id = ?", (resource_id,))
    resource = cur.fetchone()

    if not resource:
        conn.close()
        return redirect(url_for('resources'))

    title = resource['title']
    cur.execute("DELETE FROM resource_access WHERE resource_id = ?", (resource_id,))
    cur.execute("DELETE FROM resources WHERE id = ?", (resource_id,))
    conn.commit()
    conn.close()

    audit("deleted", "resource", resource_id, title)
    return redirect(url_for('resources'))

@app.route('/resource/<int:resource_id>')
def resource_gate(resource_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    user_level = session.get('access_level', '7')

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM resources WHERE id = ?", (resource_id,))
    r = cur.fetchone()
    conn.close()

    if not r:
        return "Not found", 404

    if not is_admin() and not can_access(user_level, r['min_level']):
        return "Forbidden", 403

    # SHOW A WARNING PAGE BEFORE PROCEEDING 
    return render_template('resource_gate.html', r=dict(r))

@app.route('/resource/<int:resource_id>/open')
def resource_open(resource_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    user_level = session.get('access_level', '7')

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT drive_url, min_level FROM resources WHERE id = ?", (resource_id,))
    r = cur.fetchone()
    conn.close()

    if not r:
        return "Not found", 404
    if not is_admin() and not can_access(user_level, r['min_level']):
        return "Forbidden", 403

    log_resource_access(session['user_id'], resource_id)
    return redirect(r['drive_url'])


@app.route('/help')
def help_centre():
    """Help Centre page"""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    return render_template('help.html')

@app.route('/teacher-chat')
def teacher_chat():
    """Student-to-teacher messaging."""
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    # LOAD THE TEACHER LIST FIRST SO STUDENTS CAN START A NEW THREAD.
    user_id = session.get('user_id')
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, first_name, last_name
        FROM users
        WHERE role IN ('teacher', 'admin')
        ORDER BY last_name, first_name
    """)
    teachers = cur.fetchall()

    if can_answer_teacher_messages():
        # TEACHERS SEE ONLY THE THREADS ADDRESSED TO THEM.
        cur.execute("""
            SELECT
                teacher_conversations.*,
                students.first_name AS student_first_name,
                students.last_name AS student_last_name,
                teachers.first_name AS teacher_first_name,
                teachers.last_name AS teacher_last_name,
                latest.body AS latest_body,
                latest.created_at AS latest_at
            FROM teacher_conversations
            JOIN users AS students ON students.id = teacher_conversations.student_id
            JOIN users AS teachers ON teachers.id = teacher_conversations.teacher_id
            LEFT JOIN teacher_messages AS latest
                ON latest.id = (
                    SELECT id
                    FROM teacher_messages
                    WHERE conversation_id = teacher_conversations.id
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                )
            WHERE teacher_conversations.teacher_id = ?
            ORDER BY teacher_conversations.updated_at DESC
        """, (user_id,))
    else:
        # STUDENTS SEE THEIR OWN THREADS ACROSS ALL TEACHERS.
        cur.execute("""
            SELECT
                teacher_conversations.*,
                students.first_name AS student_first_name,
                students.last_name AS student_last_name,
                teachers.first_name AS teacher_first_name,
                teachers.last_name AS teacher_last_name,
                latest.body AS latest_body,
                latest.created_at AS latest_at
            FROM teacher_conversations
            JOIN users AS students ON students.id = teacher_conversations.student_id
            JOIN users AS teachers ON teachers.id = teacher_conversations.teacher_id
            LEFT JOIN teacher_messages AS latest
                ON latest.id = (
                    SELECT id
                    FROM teacher_messages
                    WHERE conversation_id = teacher_conversations.id
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                )
            WHERE teacher_conversations.student_id = ?
            ORDER BY teacher_conversations.updated_at DESC
        """, (user_id,))

    conversations = cur.fetchall()
    active_id = request.args.get('conversation_id', type=int)
    if not active_id and conversations:
        active_id = conversations[0]['id']

    active_conversation = None
    messages = []
    if active_id:
        # THE ACTIVE THREAD MUST BELONG TO THE CURRENT USER ON EITHER SIDE.
        cur.execute("""
            SELECT
                teacher_conversations.*,
                students.first_name AS student_first_name,
                students.last_name AS student_last_name,
                teachers.first_name AS teacher_first_name,
                teachers.last_name AS teacher_last_name
            FROM teacher_conversations
            JOIN users AS students ON students.id = teacher_conversations.student_id
            JOIN users AS teachers ON teachers.id = teacher_conversations.teacher_id
            WHERE teacher_conversations.id = ?
              AND (teacher_conversations.student_id = ? OR teacher_conversations.teacher_id = ?)
        """, (active_id, user_id, user_id))
        active_conversation = cur.fetchone()

    if active_conversation:
        cur.execute("""
            SELECT teacher_messages.*, users.first_name, users.last_name, users.role
            FROM teacher_messages
            JOIN users ON users.id = teacher_messages.sender_id
            WHERE teacher_messages.conversation_id = ?
            ORDER BY teacher_messages.created_at, teacher_messages.id
        """, (active_conversation['id'],))
        messages = cur.fetchall()

    conn.close()
    if active_conversation:
        mark_read("teacher_chat", active_conversation['id'])
    return render_template(
        'teacher_chat.html',
        teachers=teachers,
        conversations=conversations,
        active_conversation=active_conversation,
        messages=messages,
        can_answer=can_answer_teacher_messages()
    )

@app.post('/teacher-chat/new')
def teacher_chat_new():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if can_answer_teacher_messages():
        return redirect(url_for('teacher_chat'))
    if not valid_csrf():
        return "Your session expired. Please try again.", 400

    teacher_id = request.form.get('teacher_id', type=int)
    subject = (request.form.get('subject') or '').strip()
    body = (request.form.get('body') or '').strip()

    if not teacher_id or not subject or not body:
        return redirect(url_for('teacher_chat'))

    # ONLY REAL TEACHER OR ADMIN ACCOUNTS CAN BE SELECTED AS RECIPIENTS.
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE id = ? AND role IN ('teacher', 'admin')", (teacher_id,))
    teacher = cur.fetchone()
    if not teacher:
        conn.close()
        return redirect(url_for('teacher_chat'))

    cur.execute("""
        INSERT INTO teacher_conversations (student_id, teacher_id, subject)
        VALUES (?, ?, ?)
    """, (session.get('user_id'), teacher_id, subject))
    conversation_id = cur.lastrowid
    cur.execute("""
        INSERT INTO teacher_messages (conversation_id, sender_id, body)
        VALUES (?, ?, ?)
    """, (conversation_id, session.get('user_id'), body))
    conn.commit()
    conn.close()
    audit("created", "teacher_conversation", conversation_id, subject)
    return redirect(url_for('teacher_chat', conversation_id=conversation_id))

@app.post('/teacher-chat/<int:conversation_id>/reply')
def teacher_chat_reply(conversation_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if not valid_csrf():
        return "Your session expired. Please try again.", 400

    body = (request.form.get('body') or '').strip()
    if not body:
        return redirect(url_for('teacher_chat', conversation_id=conversation_id))

    user_id = session.get('user_id')
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT *
        FROM teacher_conversations
        WHERE id = ? AND (student_id = ? OR teacher_id = ?)
    """, (conversation_id, user_id, user_id))
    conversation = cur.fetchone()

    if not conversation or conversation['status'] == 'closed':
        conn.close()
        return redirect(url_for('teacher_chat'))

    # A STUDENT REPLY REOPENS THE THREAD; A TEACHER REPLY MARKS IT ANSWERED.
    next_status = 'answered' if can_answer_teacher_messages() else 'open'
    cur.execute("""
        INSERT INTO teacher_messages (conversation_id, sender_id, body)
        VALUES (?, ?, ?)
    """, (conversation_id, user_id, body))
    cur.execute("""
        UPDATE teacher_conversations
        SET status = ?, updated_at = datetime('now')
        WHERE id = ?
    """, (next_status, conversation_id))
    conn.commit()
    conn.close()
    return redirect(url_for('teacher_chat', conversation_id=conversation_id))

@app.post('/teacher-chat/<int:conversation_id>/messages/<int:message_id>/delete')                ### DELETING MESSAGES - ONLY THE SENDER OR A TEACHER CAN DELETE MESSAGES, AND DELETING A MESSAGE DOES NOT DELETE THE CONVERSATION.
def teacher_chat_delete_message(conversation_id, message_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if not valid_csrf():
        return "Your session expired. Please try again.", 400

    user_id = session.get('user_id')
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT teacher_messages.*, teacher_conversations.student_id, teacher_conversations.teacher_id
        FROM teacher_messages
        JOIN teacher_conversations ON teacher_conversations.id = teacher_messages.conversation_id
        WHERE teacher_messages.id = ?
          AND teacher_messages.conversation_id = ?
          AND (teacher_conversations.student_id = ? OR teacher_conversations.teacher_id = ?)
    """, (message_id, conversation_id, user_id, user_id))
    message = cur.fetchone()

    if not message:
        conn.close()
        return redirect(url_for('teacher_chat'))

    can_delete_message = message['sender_id'] == user_id or (
        can_answer_teacher_messages() and message['teacher_id'] == user_id
    )
    if not can_delete_message:
        conn.close()
        return "Forbidden", 403

    cur.execute("DELETE FROM teacher_messages WHERE id = ?", (message_id,))
    cur.execute("""
        UPDATE teacher_conversations
        SET updated_at = COALESCE(
            (
                SELECT MAX(created_at)
                FROM teacher_messages
                WHERE conversation_id = ?
            ),
            datetime('now')
        )
        WHERE id = ?
    """, (conversation_id, conversation_id))
    conn.commit()
    conn.close()
    audit("deleted", "teacher_message", message_id, f"Conversation {conversation_id}")
    return redirect(url_for('teacher_chat', conversation_id=conversation_id))

@app.post('/teacher-chat/<int:conversation_id>/close')
def teacher_chat_close(conversation_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if not can_answer_teacher_messages():
        return "Forbidden", 403
    if not valid_csrf():
        return "Your session expired. Please try again.", 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE teacher_conversations
        SET status = 'closed', updated_at = datetime('now')
        WHERE id = ? AND teacher_id = ?
    """, (conversation_id, session.get('user_id')))
    conn.commit()
    conn.close()
    return redirect(url_for('teacher_chat', conversation_id=conversation_id))

@app.post('/teacher-chat/<int:conversation_id>/delete')
def teacher_chat_delete(conversation_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if not valid_csrf():
        return "Your session expired. Please try again.", 400

    user_id = session.get('user_id')
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT *
        FROM teacher_conversations
        WHERE id = ? AND (student_id = ? OR teacher_id = ?)
    """, (conversation_id, user_id, user_id))
    conversation = cur.fetchone()

    if not conversation:
        conn.close()
        return redirect(url_for('teacher_chat'))

    cur.execute("DELETE FROM teacher_messages WHERE conversation_id = ?", (conversation_id,))
    cur.execute("""
        DELETE FROM user_read_state
        WHERE item_type = 'teacher_chat' AND item_id = ?
    """, (conversation_id,))
    cur.execute("DELETE FROM teacher_conversations WHERE id = ?", (conversation_id,))
    conn.commit()
    conn.close()
    audit("deleted", "teacher_conversation", conversation_id, conversation['subject'])
    return redirect(url_for('teacher_chat'))

@app.route('/announcements')
def announcements():
    """Announcements page"""
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT content_items.*, users.first_name, users.last_name
        FROM content_items
        LEFT JOIN users ON users.id = content_items.created_by
        WHERE content_type = 'announcement'
        ORDER BY created_at DESC
    """)
    items = cur.fetchall()
    conn.close()
    mark_read("announcements")
    return render_template(
        'announcements.html',
        items=items,
        can_publish=can_publish_posts(),
        is_admin=is_admin()
    )

@app.route('/news')
def news():
    """Girra News page"""
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT content_items.*, users.first_name, users.last_name
        FROM content_items
        LEFT JOIN users ON users.id = content_items.created_by
        WHERE content_type = 'news'
        ORDER BY created_at DESC
    """)
    items = cur.fetchall()
    conn.close()
    mark_read("news")
    return render_template(
        'news.html',
        items=items,
        can_publish=can_publish_posts(),
        is_admin=is_admin()
    )

@app.post('/teacher/content')
def teacher_add_content():
    blocked = require_publisher()
    if blocked:
        return blocked

    content_type = (request.form.get('content_type') or '').strip()
    title = (request.form.get('title') or '').strip()
    category = (request.form.get('category') or '').strip()
    body = (request.form.get('body') or '').strip()

    if content_type not in ('announcement', 'news') or not title or not body:
        return redirect(url_for('announcements' if content_type == 'announcement' else 'news'))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO content_items (content_type, title, category, body, created_by)
        VALUES (?, ?, ?, ?, ?)
    """, (content_type, title, category, body, session.get('user_id')))
    content_id = cur.lastrowid
    conn.commit()
    conn.close()
    audit("created", content_type, content_id, title)
    return redirect(url_for('announcements' if content_type == 'announcement' else 'news'))

@app.post('/teacher/content/<int:content_id>/edit')
def teacher_edit_content(content_id):
    blocked = require_publisher()
    if blocked:
        return blocked

    title = (request.form.get('title') or '').strip()
    category = (request.form.get('category') or '').strip()
    body = (request.form.get('body') or '').strip()

    if not title or not body:
        return redirect(url_for('announcements'))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT content_type FROM content_items WHERE id = ?", (content_id,))
    item = cur.fetchone()
    if not item:
        conn.close()
        return redirect(url_for('announcements'))

    cur.execute("""
        UPDATE content_items
        SET title = ?, category = ?, body = ?
        WHERE id = ?
    """, (title, category, body, content_id))
    conn.commit()
    conn.close()
    audit("updated", item["content_type"], content_id, title)
    return redirect(url_for('announcements' if item["content_type"] == 'announcement' else 'news'))

@app.post('/admin/content/<int:content_id>/delete')
def admin_delete_content(content_id):
    blocked = require_admin()
    if blocked:
        return blocked

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT title, content_type FROM content_items WHERE id = ?", (content_id,))
    item = cur.fetchone()

    if not item:
        conn.close()
        return redirect(url_for('announcements'))

    title = item['title']
    content_type = item['content_type']
    cur.execute("DELETE FROM content_items WHERE id = ?", (content_id,))
    conn.commit()
    conn.close()

    audit("deleted", content_type, content_id, title)
    return redirect(url_for('announcements' if content_type == 'announcement' else 'news'))

@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    blocked = require_admin()
    if blocked:
        return blocked

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_member':
            first_name = (request.form.get('first_name') or '').strip()
            last_name = (request.form.get('last_name') or '').strip()
            email = (request.form.get('email') or '').strip().lower()
            student_number = (request.form.get('student_number') or '').strip() or None
            access_level = (request.form.get('access_level') or '7').strip()
            role = (request.form.get('role') or 'student').strip()
            password = request.form.get('password') or 'Password123!'

            if first_name and last_name and email and access_level in LEVEL_ORDER and role in ('student', 'teacher', 'admin'):
                password_hash = bcrypt.generate_password_hash(password).decode()
                conn = get_db()
                cur = conn.cursor()
                try:
                    cur.execute("""
                        INSERT INTO users (first_name, last_name, email, student_number, password_hash, access_level, role)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (first_name, last_name, email, student_number, password_hash, access_level, role))
                    member_id = cur.lastrowid
                    conn.commit()
                    audit("created", "member", member_id, email)
                except sqlite3.IntegrityError:
                    conn.rollback()
                finally:
                    conn.close()

        elif action == 'update_member':
            member_id = request.form.get('member_id')
            student_number = (request.form.get('student_number') or '').strip() or None
            access_level = (request.form.get('access_level') or '').strip()
            role = (request.form.get('role') or '').strip()

            if member_id and access_level in LEVEL_ORDER and role in ('student', 'teacher', 'admin'):
                conn = get_db()
                cur = conn.cursor()
                try:
                    cur.execute("""
                        UPDATE users
                        SET student_number = ?, access_level = ?, role = ?
                        WHERE id = ?
                    """, (student_number, access_level, role, member_id))
                    conn.commit()
                    audit("updated", "member", member_id, f"role={role}, access_level={access_level}, girra_id={student_number}")
                except sqlite3.IntegrityError:
                    conn.rollback()
                finally:
                    conn.close()

        elif action == 'remove_member':
            member_id = request.form.get('member_id')
            if member_id and str(member_id) != str(session.get('user_id')):
                conn = get_db()
                cur = conn.cursor()
                cur.execute("DELETE FROM users WHERE id = ?", (member_id,))
                conn.commit()
                conn.close()
                audit("deleted", "member", member_id, "Member removed")

        return redirect(url_for('admin_dashboard'))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, first_name, last_name, email, student_number, access_level, role, created_at FROM users ORDER BY last_name, first_name")
    members = cur.fetchall()
    cur.execute("""
        SELECT resource_access.*, users.first_name, users.last_name, users.email, resources.title
        FROM resource_access
        JOIN users ON users.id = resource_access.user_id
        JOIN resources ON resources.id = resource_access.resource_id
        ORDER BY accessed_at DESC
        LIMIT 100
    """)
    access_logs = cur.fetchall()
    cur.execute("""
        SELECT audit_log.*, users.first_name, users.last_name, users.email
        FROM audit_log
        LEFT JOIN users ON users.id = audit_log.actor_id
        ORDER BY audit_log.created_at DESC
        LIMIT 100
    """)
    audit_logs = cur.fetchall()
    cur.execute("SELECT COUNT(*) AS count FROM users")
    total_members = cur.fetchone()["count"]
    cur.execute("SELECT COUNT(*) AS count FROM resources")
    total_resources = cur.fetchone()["count"]
    cur.execute("SELECT COUNT(*) AS count FROM content_items WHERE content_type = 'announcement'")
    total_announcements = cur.fetchone()["count"]
    cur.execute("SELECT COUNT(*) AS count FROM teacher_conversations WHERE status != 'closed'")
    open_conversations = cur.fetchone()["count"]
    cur.execute("""
        SELECT resources.title, COUNT(resource_access.id) AS open_count
        FROM resource_access
        JOIN resources ON resources.id = resource_access.resource_id
        GROUP BY resources.id
        ORDER BY open_count DESC, resources.title
        LIMIT 5
    """)
    top_resources = cur.fetchall()
    cur.execute("""
        SELECT users.first_name, users.last_name, users.email, COUNT(resource_access.id) AS open_count
        FROM resource_access
        JOIN users ON users.id = resource_access.user_id
        GROUP BY users.id
        ORDER BY open_count DESC, users.last_name
        LIMIT 5
    """)
    active_users = cur.fetchall()
    cur.execute("""
        SELECT status, COUNT(*) AS count
        FROM teacher_conversations
        GROUP BY status
        ORDER BY status
    """)
    conversation_stats = cur.fetchall()
    conn.close()

    return render_template(
        'admin.html',
        members=members,
        access_logs=access_logs,
        audit_logs=audit_logs,
        total_members=total_members,
        total_resources=total_resources,
        total_announcements=total_announcements,
        open_conversations=open_conversations,
        top_resources=top_resources,
        active_users=active_users,
        conversation_stats=conversation_stats,
        levels=LEVEL_ORDER.keys()
    )

@app.route('/prefects')
def prefects():
    """Prefects page"""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    return render_template('prefects.html')

@app.route('/humans')
def humans():
    """Humans of Girra page"""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    return render_template('humans.html')

@app.route('/logout')
def logout():
    """Logout"""
    session.clear()
    return redirect(url_for('index'))

@app.route('/terms')
def terms():
    """Terms & Conditions page"""
    return render_template('terms.html')

@app.route('/api/forgot-password', methods=['POST'])
def forgot_password():
    """Reset a password using saved security questions."""
    if not valid_json_csrf():
        return jsonify({'success': False, 'message': 'Your session expired. Please refresh and try again.'}), 400

    ensure_security_questions_table()
    data = request.get_json(silent=True) or {}
    action = data.get('action', 'questions')
    email = (data.get('email') or '').strip().lower()

    if login_is_locked(email):
        return jsonify({'success': False, 'message': 'Too many attempts. Please wait 15 minutes and try again.'}), 429

    if not is_valid_school_email(email):
        record_failed_login(email)
        return jsonify({'success': False, 'message': 'Enter a valid school email address.'}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE email = ?", (email,))
    user = cur.fetchone()

    if not user:
        conn.close()
        record_failed_login(email)
        return jsonify({'success': False, 'message': 'No account was found for that email address.'}), 404

    cur.execute("""
        SELECT question_key, question_text, answer_hash
        FROM user_security_questions
        WHERE user_id = ?
        ORDER BY id
    """, (user['id'],))
    questions = cur.fetchall()

    if not questions:
        conn.close()
        return jsonify({
            'success': False,
            'message': 'This account does not have security questions set. Please contact an admin.'
        }), 400

    if action == 'questions':
        conn.close()
        return jsonify({
            'success': True,
            'questions': [
                {'key': question['question_key'], 'text': question['question_text']}
                for question in questions
            ]
        })

    if action != 'reset':
        conn.close()
        return jsonify({'success': False, 'message': 'Invalid reset request.'}), 400

    answers = data.get('answers') or {}
    new_password = data.get('new_password') or ''
    confirm_password = data.get('confirm_password') or ''

    if new_password != confirm_password:
        conn.close()
        return jsonify({'success': False, 'message': 'New passwords do not match.'}), 400

    if not is_strong_password(new_password):
        conn.close()
        return jsonify({
            'success': False,
            'message': 'Password must be at least 8 characters and include uppercase, lowercase, and a number.'
        }), 400

    for question in questions:
        answer = normalize_security_answer(answers.get(question['question_key']))
        if not answer or not bcrypt.check_password_hash(question['answer_hash'], answer):
            conn.close()
            record_failed_login(email)
            return jsonify({'success': False, 'message': 'One or more security answers were incorrect.'}), 400

    password_hash = bcrypt.generate_password_hash(new_password).decode()
    cur.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user['id']))
    conn.commit()
    conn.close()
    clear_failed_logins(email)
    audit("updated", "user", user['id'], "Reset password using security questions")
    return jsonify({'success': True, 'message': 'Password reset. You can now sign in.'})

@app.post("/api/chat")
def api_chat():

    data = request.get_json(silent=True) or {}
    msg = (data.get("message") or "").strip()

    if not msg:
        return jsonify(error="Message required"), 400

    try:
        if not GEMINI_API_KEY:
            return jsonify(reply=AI_UNAVAILABLE_REPLY, ai_available=False), 200

        try:
            results = search_documents(msg)
        except Exception:
            results = []

        context = "\n\n".join(
            f"[{file}]\n{content}"
            for _, file, content in results
        )
        if not context:
            context = "No local school document context is available on this computer."

        response = model.generate_content(f"""
You are CENTRAL, the AI academic assistant for Girra Student Portal.

ROLE
Provide accurate, concise academic support to students using the supplied school documents as your primary source.

PRIORITY ORDER
1. FIRST use information from the School Documents.
2. If the answer is not in the documents, use reliable general HSC/NESA curriculum knowledge.
3. If uncertain, say what is unclear rather than inventing information.

RULES
- Never ignore relevant information in the School Documents.
- Do not hallucinate policies, dates, assessment details, or school-specific procedures.
- Answer directly and concisely (under 150 words unless detailed feedback is requested).
- If asked about essays, short answers, or student work:
  • Evaluate using HSC marking standards.
  • Give a mark out of 20.
  • Give 3 brief strengths.
  • Give 3 specific improvements.
  • State the likely band (Band 4/5/6).

MARKING GUIDE
17–20:
Insightful analysis, strong textual conversation, sophisticated expression.

13–16:
Clear analysis, relevant evidence, good control of language.

9–12:
Basic understanding, limited analysis, inconsistent evidence.

1–8:
Minimal understanding, weak textual support.

RESPONSE FORMAT
For normal questions:
Answer:
[response]

For essay marking:
Mark: __/20
Band: __
Strengths:
- ...
- ...
- ...

Improvements:
- ...
- ...
- ...

School Documents:
{context}

Student Question:
{msg}
""")

        return jsonify(reply=response.text)

    except Exception:
        return jsonify(reply=AI_UNAVAILABLE_REPLY, ai_available=False), 200


### STUDENT BAR_CODE GENERATOR 
@app.route("/barcode/<student_id>")
def barcode(student_id):
    buffer = io.BytesIO()

    code = Code39(
        student_id,
        writer=SVGWriter(),
        add_checksum=False
    )

    code.write(buffer, options={
        "write_text": True
    })

    svg = buffer.getvalue()
    return Response(svg, mimetype="image/svg+xml")

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5000)




#LOCAL FLASK OPERATION SCRIPT
#if __name__ == "__main__":
#    app.run(debug=True)

### NEED TO FIX ROLE BASED ACCESS --> DONE! 

