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
    password_hash TEXT NOT NULL,
    access_level TEXT NOT NULL CHECK(access_level IN ('7','8','9','10','11','12','T')),
    created_at TEXT DEFAULT (datetime('now'))
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
    ('Abby','Johnson','abby.johnson@girraween.nsw.edu.au', password,'10'),
    ('Bob','Smith','skibidi', password,'11'),
    ('Catherine','Davis','catherine.davis@girraween.nsw.edu.au', password,'12'),
    ('Daniel','Brown','daniel.brown@girraween.nsw.edu.au', password,'9'),
    ('Eva','Martinez','eva.martinez@girraween.nsw.edu.au', password,'10'),
    ('Frank','Wilson','frank.wilson@girraween.nsw.edu.au', password,'11'),
    ('Grace','Lee','grace.lee@girraween.nsw.edu.au', password,'12'),
    ('Henry','Taylor','henry.taylor@girraween.nsw.edu.au', password,'8'),
    ('Olivia','Adams','olivia.adams@girraween.nsw.edu.au', password,'9'),
    ('Mr','Patel','r.patel@girraween.nsw.edu.au', password,'T'),
]

cur.executemany("""
INSERT OR IGNORE INTO users
(first_name,last_name,email,password_hash,access_level)
VALUES (?,?,?,?,?)
""", users)


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
