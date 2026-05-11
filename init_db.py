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
    created_at TEXT DEFAULT (datetime('now'))
);
""")

cur.execute("PRAGMA table_info(users)")
user_columns = {column[1] for column in cur.fetchall()}
if "student_number" not in user_columns:
    cur.execute("ALTER TABLE users ADD COLUMN student_number TEXT")

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
    created_at TEXT DEFAULT (datetime('now'))
);
""")      

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


# ADD USERS TO DB
password = bcrypt.generate_password_hash("Password123!").decode()

users = [
    ('Abby','Johnson','abby.johnson@education.nsw.gov.au','444628401', password,'10'),                              #CHANGE - NOT REAL DATA
    ('Bob','Smith','bob.smith@education.nsw.gov.au','444628402', password,'11'),                                    #CHANGE - NOT REAL DATA
    ('Catherine','Davis','catherine.davis@education.nsw.gov.au','444628403', password,'12'),                        #CHANGE - NOT REAL DATA
    ('Daniel','Brown','daniel.brown@education.nsw.gov.au','444628404', password,'9'),                               #CHANGE - NOT REAL DATA
    ('Eva','Martinez','eva.martinez@education.nsw.gov.au','444628405', password,'10'),                              #CHANGE - NOT REAL DATA
    ('Frank','Wilson','frank.wilson@education.nsw.gov.au','444628406', password,'11'),                              #CHANGE - NOT REAL DATA
    ('Grace','Lee','grace.lee@education.nsw.gov.au','444628407', password,'12'),                                    #CHANGE - NOT REAL DATA
    ('Aarav','S','aarav.s@education.nsw.gov.au','444456345', password,'12'),
    ('Raguram','P','raguram.ps@education.nsw.gov.au','443547291', password,'12'),
    ('Sountharikan','Thirukkumaran','sountharikan.thirukkumaran@education.nsw.gov.au','444628464', password,'12'),
    ('Mr','Patel','mr.patel@education.nsw.gov.au', None, password,'T'),
]

for user in users:
    first_name, last_name, email, student_number, password_hash, access_level = user
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
                access_level = ?
            WHERE id = ?
        """, (email, student_number, password_hash, access_level, existing_user[0]))
    else:
        cur.execute("""
            INSERT INTO users
            (first_name,last_name,email,student_number,password_hash,access_level)
            VALUES (?,?,?,?,?,?)
        """, user)

for first_name, last_name, email, student_number, _, _ in users:
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
     'https://drive.google.com/file/d/AAA/view',
     'Math', '7'),

    ('Year 11 Physics – Kinematics Pack',
     'SUVAT drills + worked examples',
     'https://drive.google.com/file/d/AAA/view',
     'Physics', '11'),

    ('Year 12 Maths – Integration Drill',
     'Hard HSC-style integrals',
     'https://drive.google.com/file/d/BBB/view',
     'Math', '12'),

    ('Teacher Assessment Templates',
     'Internal use only',
     'https://drive.google.com/file/d/CCC/view',
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
