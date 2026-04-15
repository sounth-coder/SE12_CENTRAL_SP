from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
from datetime import timedelta
import sqlite3
from flask_bcrypt import Bcrypt
import numpy as np
from sentence_transformers import SentenceTransformer

embed_model = SentenceTransformer("all-MiniLM-L6-v2")

### IMPORTANT DELETE THIS BEFORE UPLOADING TO GITHUB - SECURITY RISK - WILL REPLACE THIS LATER ###
import google.generativeai as genai

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")
### IMPORTANT DELETE THIS BEFORE UPLOADING TO GITHUB - SECURITY RISK - WILL REPLACE THIS LATER ###


app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')

bcrypt = Bcrypt(app)

def search_documents(question, top_k=4):

    conn = sqlite3.connect("knowledge.db")
    cur = conn.cursor()

    q_emb = embed_model.encode(question)

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

LEVEL_ORDER = {'7':7,'8':8,'9':9,'10':10,'11':11,'12':12,'T':99}

def can_access(user_level: str, min_level: str) -> bool:
    return LEVEL_ORDER.get(user_level, 0) >= LEVEL_ORDER.get(min_level, 0)

def log_resource_access(user_id: int, resource_id: int): 
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)          #LOGGING OF IP'S TO DETER RESOURCE DISTRIBUTION/ABUSE OF SERVICE
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

@app.route('/')
def index():
    """Landing page"""
    return render_template('index.html')

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
            session.permanent = bool(remember)
            session['logged_in'] = True
            session['user_id'] = user['id']
            session['email'] = user['email']
            session['access_level'] = user['access_level']
            session['name'] = user['first_name']

            return redirect(url_for('home'))  

        return render_template('login.html', error="Invalid email or password")

    return render_template('login.html')

@app.route('/home')
def home():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    return render_template(
        'home.html',
        username=session.get('name', 'Student')
    )


@app.route('/student-id')
def student_id():
    """Student ID page"""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    username = session.get('name', 'Student')
    return render_template('student_id.html', username=username)

@app.route('/resources')
def resources():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    user_level = session.get('access_level', '7')

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM resources ORDER BY subject, created_at DESC")
    rows = cur.fetchall()
    conn.close()

    allowed, locked = [], []
    for r in rows:
        (allowed if can_access(user_level, r['min_level']) else locked).append(dict(r))

    return render_template('resources.html', allowed=allowed, locked=locked, user_level=user_level)

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

    if not can_access(user_level, r['min_level']):
        return "Forbidden", 403

    # LOG ACCESS THROUGH IP  
    log_resource_access(session['user_id'], resource_id)

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
    if not can_access(user_level, r['min_level']):
        return "Forbidden", 403

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
    
    return render_template('announcements.html')

@app.route('/news')
def news():
    """Girra News page"""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    return render_template('news.html')

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
You are CENTRAL, the Girra Student Portal assistant.

Rules:
- Prioritise information from the provided school documents.
- If the information is not present in the documents, you may use general curriculum knowledge.
- You may evaluate student work (e.g., essays) and give estimated marks using HSC marking standards.
- When evaluating essays, give a mark out of 20 and brief feedback.
- Do not refuse to help with academic questions or essay feedback.
- Answer in under 150 words unless the student asks for detailed feedback.
                                          
HSC Marking Guidelines (simplified): 
17–20: Insightful analysis, strong textual conversation, sophisticated language.
13–16: Clear analysis with good textual support.
9–12: Basic understanding with limited analysis.
1–8: Limited understanding with minimal textual reference.
                                                                   
Be concise and helpful.

School Documents:
{context}

Student Question:
{msg}
""")

        return jsonify(reply=response.text)

    except Exception as e:
        return jsonify(error=str(e)), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

#LOCAL FLASK OPERATION SCRIPT
#if __name__ == "__main__":
#    app.run(debug=True)

### NEED TO FIX ROLE BASED ACCESS 

