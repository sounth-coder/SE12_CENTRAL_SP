import sqlite3
from flask_bcrypt import Bcrypt
from flask import Flask

app = Flask(__name__)
bcrypt = Bcrypt(app)

DB_NAME = "girra_portal.db"

conn = sqlite3.connect(DB_NAME)
cur = conn.cursor()


# USERS TABLE
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

cur.execute("PRAGMA table_info(users)")
user_columns = {column[1] for column in cur.fetchall()}
if "student_number" not in user_columns:
    cur.execute("ALTER TABLE users ADD COLUMN student_number TEXT")
if "role" not in user_columns:
    cur.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'student'")

cur.execute("""
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_student_number
ON users(student_number)
WHERE student_number IS NOT NULL;
""")

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


# RESOURCES TABLE
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

cur.execute("PRAGMA table_info(resources)")
resource_columns = {column[1] for column in cur.fetchall()}
if "created_by" not in resource_columns:
    cur.execute("ALTER TABLE resources ADD COLUMN created_by INTEGER")

# RESOURCE ACCESS LOGS
cur.execute("""
CREATE TABLE IF NOT EXISTS resource_access (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    resource_id INTEGER NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    accessed_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (resource_id) REFERENCES resources(id)
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
CREATE INDEX IF NOT EXISTS idx_teacher_conversations_student
ON teacher_conversations(student_id, updated_at);
""")

cur.execute("""
CREATE INDEX IF NOT EXISTS idx_teacher_conversations_teacher
ON teacher_conversations(teacher_id, updated_at);
""")


# ADD USERS TO DB
password = bcrypt.generate_password_hash("Password123!").decode()

users = [
    ('Aarav','S','aarav.s@education.nsw.gov.au','444456345', password,'12','student'),
    ('Raguram','P','raguram.ps@education.nsw.gov.au','443547291', password,'12','student'),
    ('Sountharikan','Thirukkumaran','sountharikan.thirukkumaran@education.nsw.gov.au','444628464', password,'12','admin'),
    ('Mr','Patel','mr.patel@education.nsw.gov.au', None, password,'T','teacher'),
]

for user in users:
    first_name, last_name, email, student_number, password_hash, access_level, role = user
    cur.execute("""
        SELECT id FROM users
        WHERE lower(first_name) = lower(?) AND lower(last_name) = lower(?)
    """, (first_name, last_name))
    existing_user = cur.fetchone()

    if existing_user:
        cur.execute("""
            UPDATE users
            SET email = ?,
                student_number = ?,
                password_hash = ?,
                access_level = ?,
                role = ?
            WHERE id = ?
        """, (email, student_number, password_hash, access_level, role, existing_user[0]))
    else:
        cur.execute("""
            INSERT INTO users
            (first_name,last_name,email,student_number,password_hash,access_level,role)
            VALUES (?,?,?,?,?,?,?)
        """, user)

for first_name, last_name, email, student_number, _, _, _ in users:
    cur.execute("""
        DELETE FROM users
        WHERE lower(first_name) = lower(?)
          AND lower(last_name) = lower(?)
          AND email <> ?
          AND (student_number IS NULL OR student_number <> ?)
    """, (first_name, last_name, email, student_number))


# ADD RESOURCES TO DB (PLACE HOLDER DRIVE LINKS FOR NOW)
resources = [
    ('Year 7 Maths – BODMAS Pack',
     'BODMAS drills + worked examples',
     'https://go.clueylearning.com.au/en/maths-worksheets/free-printable-pdfs/year-7/Year-7-BODMAS-Maths-Using-order-of-operations-to-solve-expressions-1-clueylearning.com.au-1300182000.pdf',
     'Math', '7'),

    ('Year 11 Physics – Kinematics Pack',
     'SUVAT drills + worked examples',
     'https://artofsmart.com.au/physics/year-11-hsc-physics-kinematics/',
     'Physics', '11'),

    ('Year 12 GHS Shared HSC Google Drive',
     'The ultimate mega-drive.',
     'https://drive.google.com/drive/folders/1YyBVNd76Ps28ngT-mz1c1tsgCwsAvB2X',
     'All', '12'),

    ('Teacher Assessment Templates',
     'Internal use only',
     'https://www.nsw.gov.au/education-and-training/nesa/teacher-accreditation/resources/effective-documentary-evidence/assessment-task-example',
     'Admin', 'T'),
]

cur.executemany("""
INSERT OR IGNORE INTO resources
(title, description, drive_url, subject, min_level)
VALUES (?,?,?,?,?)
""", resources)

conn.commit()
conn.close()

print("Database initialised successfully")

