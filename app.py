from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
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
        embed_model = SentenceTransformer("all-MiniLM-L6-v2")
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

def search_documents(question, top_k=4):

    conn = sqlite3.connect("knowledge.db")
    cur = conn.cursor()

    q_emb = get_model().encode(question)

    cur.execute("SELECT filename, content, embedding FROM documents")
    rows = cur.fetchall()

    scored = []

    for filename, content, emb_blob in rows:
        emb = np.frombuffer(emb_blob, dtype=np.float32)

        similarity = np.dot(q_emb, emb) / (
            np.linalg.norm(q_emb) * np.linalg.norm(emb)
        )

        scored.append((similarity, filename, content))

    conn.close()

    scored.sort(reverse=True)

    return scored[:top_k]

def get_db():
    conn = sqlite3.connect("girra_portal.db")
    conn.row_factory = sqlite3.Row
    return conn

def ensure_portal_tables():
    conn = get_db()
    cur = conn.cursor()

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
    conn.commit()
    conn.close()

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
    return request.headers.get("X-Forwarded-For", request.remote_addr)

def audit(action: str, target_type: str, target_id=None, details: str = ""):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO audit_log (actor_id, action, target_type, target_id, details, ip_address)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (session.get("user_id"), action, target_type, target_id, details, request_ip()))
    conn.commit()
    conn.close()

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


# SECRET KEY FOR SESSIONS
app.secret_key = 'girraween-student-portal-2026-secret-key'
app.permanent_session_lifetime = timedelta(hours=1)
ensure_portal_tables()

@app.route('/')
def index():
    """Landing page"""
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember')

        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cur.fetchone()
        conn.close()

        if user and bcrypt.check_password_hash(user['password_hash'], password):
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

            return redirect(url_for('home'))  

        return render_template('login.html', error="Invalid email or password")

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    ensure_security_questions_table()

    if request.method == 'POST':
        first_name = (request.form.get('first_name') or '').strip()
        last_name = (request.form.get('last_name') or '').strip()
        student_number = (request.form.get('student_number') or '').strip() or None
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        confirm_password = request.form.get('confirm_password') or ''
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

        if password != confirm_password:
            return render_template(
                'register.html',
                error="Passwords do not match.",
                questions=SECURITY_QUESTIONS,
                form=request.form
            )

        if len(password) < 8:
            return render_template(
                'register.html',
                error="Password must be at least 8 characters long.",
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
                answer_hash = bcrypt.generate_password_hash(answers[question["key"]].lower()).decode()
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


@app.route('/student-id')
def student_id():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
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

@app.route('/resources')
def resources():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    user_level = session.get('access_level', '7')

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
    for r in rows:
        (allowed if is_admin() or can_access(user_level, r['min_level']) else locked).append(dict(r))

    return render_template(
        'resources.html',
        allowed=allowed,
        locked=locked,
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
    conn.close()

    return render_template(
        'admin.html',
        members=members,
        access_logs=access_logs,
        audit_logs=audit_logs,
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
    """Handle forgot password request"""
    email = request.json.get('email')
    # MOCK FOR NOW - WILL UPDATE THIS WITH A REAL API SERVICE LATER - WILL NEED TO DO 2FA API IN NEXT COMMIT
    return jsonify({'success': True, 'message': 'Password reset link sent to your school email!'})

@app.post("/api/chat")
def api_chat():

    data = request.get_json(silent=True) or {}
    msg = (data.get("message") or "").strip()

    if not msg:
        return jsonify(error="Message required"), 400

    try:

        results = search_documents(msg)

        context = "\n\n".join(
            f"[{file}]\n{content}"
            for _, file, content in results
        )

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

    except Exception as e:
        return jsonify(error=str(e)), 500


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

