from models import db, Student, Event, Certificate, EventParticipant
from dotenv import load_dotenv
from pathlib import Path
import os
import sqlite3
import re
import secrets
import json
import time
import math
from functools import wraps
from datetime import timedelta, datetime
from flask import (Flask, render_template, request, redirect, url_for, flash, jsonify, g, session)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image, ImageOps
import io
import hmac
import logging
from datetime import date
from urllib.parse import urlparse

# =========================================
# 1. APP CONFIGURATION
# =========================================
load_dotenv(Path(__file__).resolve().with_name(".env"))

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get('SCHOOL_DB_PATH', BASE_DIR / 'school.db'))
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
secret_key = os.environ.get("SECRET_KEY")

if not secret_key or len(secret_key) < 32:
    raise RuntimeError(
        "SECRET_KEY missing or too short. Check your .env file."
    )

IS_PRODUCTION = os.environ.get('FLASK_ENV', '').lower() == 'production'
app.config.update(
    SECRET_KEY=secret_key,
    MAX_CONTENT_LENGTH=20 * 1024 * 1024,  # request-wide hard limit
    MAX_FORM_MEMORY_SIZE=2 * 1024 * 1024,
    SESSION_COOKIE_SECURE=IS_PRODUCTION,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    SESSION_REFRESH_EACH_REQUEST=True,
    TEMPLATES_AUTO_RELOAD=not IS_PRODUCTION,
    SEND_FILE_MAX_AGE_DEFAULT=0 if not IS_PRODUCTION else 3600,
    JSON_SORT_KEYS=False,
)

# Never use a shared default password. Each new/reset account receives its own
# one-time temporary password generated at the point of account creation/reset.

# UPGRADE: Upload folder for QR codes
UPLOAD_FOLDER = BASE_DIR / 'static' / 'uploads'
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    if not filename or not isinstance(filename, str) or len(filename) > 255:
        return False
    clean = secure_filename(filename)
    return bool(clean and '.' in clean and clean.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS)

# === Jinja filter to format YYYY-MM-DD → "OCT" ===
@app.template_filter('month_abbr')
def month_abbr(date_str):
    months = ['JAN','FEB','MAR','APR','MAY','JUN',
              'JUL','AUG','SEP','OCT','NOV','DEC']
    try:
        return months[int(str(date_str)[5:7]) - 1]
    except (ValueError, IndexError, TypeError):
        return ''

# Legacy hard-coded default password removed.

# =========================================
# 1.5. USER TABLE — EXTRA COLUMNS (MIGRATION)
# =========================================
USER_EXTRA_COLUMNS = {
    # Common / personal
    'blood_group': 'TEXT', 'marital_status': 'TEXT', 'aadhar': 'TEXT', 'pan': 'TEXT',
    'nationality': 'TEXT', 'mother_tongue': 'TEXT',
    # Contact
    'alternate_mobile': 'TEXT', 'whatsapp': 'TEXT',
    'city': 'TEXT', 'state': 'TEXT', 'pincode': 'TEXT',
    'photo_url': 'TEXT',
    # Teacher
    'specialization': 'TEXT', 'classes_assigned': 'TEXT', 'languages': 'TEXT',
    'employee_id': 'TEXT', 'joining_date': 'TEXT', 'employment_type': 'TEXT',
    'total_experience': 'TEXT', 'previous_school': 'TEXT',
    'salary': 'TEXT', 'bank_name': 'TEXT', 'account_number': 'TEXT', 'ifsc': 'TEXT',
    'emergency_name': 'TEXT', 'emergency_contact': 'TEXT', 'notes': 'TEXT',
    # Admin
    'reporting_to': 'TEXT',
    # Parent
    'occupation': 'TEXT', 'education': 'TEXT', 'annual_income': 'TEXT',
    'spouse_name': 'TEXT', 'spouse_occupation': 'TEXT', 'spouse_mobile': 'TEXT',
    'office_phone': 'TEXT', 'office_address': 'TEXT',
    'child_admission_no': 'TEXT', 'child_section': 'TEXT', 'child_dob': 'TEXT',
    # Student - academic
    'admission_no': 'TEXT', 'roll_no': 'TEXT', 'admission_date': 'TEXT',
    'class_name': 'TEXT', 'section': 'TEXT',
    'previous_class': 'TEXT', 'previous_percentage': 'TEXT',
    'category': 'TEXT', 'religion': 'TEXT',
    # Student - father / mother / guardian
    'father_name': 'TEXT', 'father_occupation': 'TEXT', 'father_mobile': 'TEXT',
    'father_email': 'TEXT', 'father_education': 'TEXT',
    'mother_name': 'TEXT', 'mother_occupation': 'TEXT', 'mother_mobile': 'TEXT',
    'mother_email': 'TEXT', 'mother_education': 'TEXT',
    'guardian_name': 'TEXT', 'guardian_relation': 'TEXT', 'guardian_mobile': 'TEXT',
    # Student - medical / transport / misc
    'allergies': 'TEXT', 'medical_conditions': 'TEXT', 'disability': 'TEXT',
    'transport_route': 'TEXT', 'pickup_point': 'TEXT', 'vehicle_no': 'TEXT',
    'sibling_name': 'TEXT', 'sibling_class': 'TEXT', 'hobbies': 'TEXT',
}

# ---------- Allowlisted field names per role ----------
COMMON_FIELDS = [
    'dob', 'gender', 'blood_group', 'marital_status', 'aadhar', 'pan',
    'nationality', 'mother_tongue',
    'email', 'phone', 'alternate_mobile', 'whatsapp',
    'address', 'city', 'state', 'pincode',
]
TEACHER_FIELDS = [
    'qualification', 'specialization', 'experience', 'subject',
    'classes_assigned', 'languages', 'employee_id', 'designation',
    'joining_date', 'employment_type', 'total_experience', 'previous_school',
    'salary', 'bank_name', 'account_number', 'ifsc',
    'emergency_name', 'emergency_contact', 'notes',
]
ADMIN_FIELDS = [
    'designation', 'department', 'employee_id', 'joining_date',
    'employment_type', 'reporting_to',
    'salary', 'bank_name', 'account_number', 'ifsc',
    'emergency_name', 'emergency_contact',
]
PARENT_FIELDS = [
    'relation', 'occupation', 'education', 'annual_income',
    'spouse_name', 'spouse_occupation', 'spouse_mobile',
    'office_phone', 'office_address',
    'child_name', 'child_admission_no', 'child_class', 'child_section', 'child_dob',
    'emergency_name', 'emergency_contact',
]
STUDENT_FIELDS = [
    'admission_no', 'roll_no', 'admission_date', 'class_name', 'section',
    'previous_school', 'previous_class', 'previous_percentage', 'category', 'religion',
    'father_name', 'father_occupation', 'father_mobile', 'father_email', 'father_education',
    'mother_name', 'mother_occupation', 'mother_mobile', 'mother_email', 'mother_education',
    'guardian_name', 'guardian_relation', 'guardian_mobile', 'emergency_contact',
    'allergies', 'medical_conditions', 'disability',
    'transport_route', 'pickup_point', 'vehicle_no',
    'account_number', 'bank_name', 'ifsc',
    'sibling_name', 'sibling_class', 'hobbies',
]
ROLE_FIELDS = {
    'teacher': TEACHER_FIELDS,
    'admin': ADMIN_FIELDS,
    'administrator': ADMIN_FIELDS,
    'parent': PARENT_FIELDS,
    'student': STUDENT_FIELDS,
}

# =========================================
# 2. DATABASE HELPERS
# =========================================
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH, timeout=15)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
        g.db.execute('PRAGMA busy_timeout = 15000')
    return g.db

@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def migrate_users_table(db):
    """Idempotent: existing users table me missing columns add karta hai."""
    existing = {row[1] for row in db.execute("PRAGMA table_info(users)").fetchall()}
    for col, coltype in USER_EXTRA_COLUMNS.items():
        if col not in existing:
            db.execute(f'ALTER TABLE users ADD COLUMN {col} {coltype}')

def migrate_attendance_table(db):
    """Add subject column to attendance if it doesn't exist."""
    existing = {row[1] for row in db.execute("PRAGMA table_info(attendance)").fetchall()}
    if 'subject' not in existing:
        db.execute("ALTER TABLE attendance ADD COLUMN subject TEXT DEFAULT 'General'")

def migrate_faculty_table(db):
    """Sync users table teachers to faculty table."""
    existing = {row[1] for row in db.execute("PRAGMA table_info(faculty)").fetchall()}
    if 'user_id' not in existing:
        db.execute('ALTER TABLE faculty ADD COLUMN user_id INTEGER')

    teachers = db.execute("SELECT id, name, subject, qualification, experience, photo_url FROM users WHERE role='teacher'").fetchall()
    for t in teachers:
        if not db.execute("SELECT 1 FROM faculty WHERE user_id = ? OR name = ?", (t['id'], t['name'])).fetchone():
            db.execute('''INSERT INTO faculty (user_id, name, subject, qualification, experience, photo_url) 
                          VALUES (?, ?, ?, ?, ?, ?)''',
                       (t['id'], t['name'], t['subject'] or 'General', t['qualification'] or '', t['experience'] or '', t['photo_url']))

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row

        db.execute('''CREATE TABLE IF NOT EXISTS enquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, name TEXT NOT NULL,
            phone TEXT NOT NULL, email TEXT, class_name TEXT, message TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')

        db.execute('''CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, title TEXT NOT NULL,
            tag TEXT NOT NULL, description TEXT, target_role TEXT DEFAULT 'all',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')

        db.execute('''CREATE TABLE IF NOT EXISTS login_attempts (
            attempt_key TEXT PRIMARY KEY,
            failures INTEGER NOT NULL DEFAULT 0,
            window_started REAL NOT NULL,
            blocked_until REAL NOT NULL DEFAULT 0
        )''')

        db.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, unique_id TEXT UNIQUE, role TEXT NOT NULL,
            name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, phone TEXT NOT NULL,
            password_hash TEXT NOT NULL, force_password_change INTEGER DEFAULT 1,
            dob TEXT, gender TEXT, qualification TEXT, experience TEXT, subject TEXT,
            designation TEXT, department TEXT, relation TEXT, child_name TEXT,
            child_class TEXT, address TEXT, is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')

        migrate_users_table(db)

        db.execute('''CREATE TABLE IF NOT EXISTS leave_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            leave_type TEXT NOT NULL, from_date TEXT NOT NULL, to_date TEXT NOT NULL,
            reason TEXT NOT NULL, status TEXT DEFAULT 'pending',
            admin_remarks TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')

        db.execute('''CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            date TEXT NOT NULL, status TEXT NOT NULL, subject TEXT DEFAULT 'General', 
            remarks TEXT, marked_by INTEGER, 
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')

        migrate_attendance_table(db)

        db.execute('''CREATE TABLE IF NOT EXISTS exam_marks (
            id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL,
            exam_type TEXT NOT NULL, subject TEXT NOT NULL, 
            marks_obtained REAL NOT NULL, total_marks REAL NOT NULL DEFAULT 100,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')

        db.execute('''CREATE TABLE IF NOT EXISTS fee_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL,
            amount REAL NOT NULL, payment_date TEXT NOT NULL,
            transaction_id TEXT, status TEXT DEFAULT 'pending',
            remarks TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')

        db.execute('''CREATE TABLE IF NOT EXISTS school_settings (
            key TEXT PRIMARY KEY, value TEXT)''')

        db.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, from_user_id INTEGER NOT NULL,
            to_user_id INTEGER, to_role TEXT, subject TEXT NOT NULL, body TEXT NOT NULL,
            is_read INTEGER DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        
        db.execute('''CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
            description TEXT, event_date TEXT NOT NULL, event_time TEXT,
            location TEXT, category TEXT DEFAULT 'general',
            is_featured INTEGER DEFAULT 0,
            cover_image_url TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        
        db.execute('''CREATE TABLE IF NOT EXISTS event_participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            role TEXT DEFAULT 'participant',
            added_on TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE CASCADE,
            FOREIGN KEY(student_id) REFERENCES users (id) ON DELETE CASCADE,
            UNIQUE(event_id, student_id)
        )''')

        # Migration: Add cover_image_url to events table if missing
        _event_cols = {row[1] for row in db.execute("PRAGMA table_info(events)").fetchall()}
        if 'cover_image_url' not in _event_cols:
            db.execute('ALTER TABLE events ADD COLUMN cover_image_url TEXT')

        # Event certificates — student-wise issued certificates
        db.execute('''CREATE TABLE IF NOT EXISTS event_certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            certificate_type TEXT DEFAULT 'participation',
            position TEXT,
            issued_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(event_id, student_id),
            FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
            FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE)''')

        db.execute('CREATE INDEX IF NOT EXISTS idx_event_cert_event ON event_certificates(event_id)')

        db.execute('''CREATE TABLE IF NOT EXISTS faculty (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT NOT NULL,
            subject TEXT NOT NULL, qualification TEXT, experience TEXT,
            photo_url TEXT, bio TEXT, display_order INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')

        migrate_faculty_table(db)

        db.execute('''CREATE TABLE IF NOT EXISTS testimonials (
            id INTEGER PRIMARY KEY AUTOINCREMENT, author_name TEXT NOT NULL,
            author_role TEXT DEFAULT 'Parent', message TEXT NOT NULL,
            rating INTEGER DEFAULT 5, is_approved INTEGER DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')

        db.execute('''CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT, student_name TEXT NOT NULL,
            class_name TEXT, achievement TEXT NOT NULL, year TEXT,
            category TEXT DEFAULT 'academic', photo_url TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')

        db.execute('''CREATE TABLE IF NOT EXISTS gallery (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
            image_url TEXT NOT NULL, category TEXT DEFAULT 'campus',
            display_order INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')

        db.execute('''CREATE TABLE IF NOT EXISTS faq (
            id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT NOT NULL,
            answer TEXT NOT NULL, display_order INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')

        db.execute('''CREATE TABLE IF NOT EXISTS homework (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name TEXT NOT NULL,
            subject TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            due_date TEXT,
            assigned_by INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')

        db.execute('''CREATE TABLE IF NOT EXISTS study_materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name TEXT NOT NULL,
            subject TEXT,
            title TEXT NOT NULL,
            description TEXT,
            file_url TEXT,
            external_link TEXT,
            material_type TEXT DEFAULT 'notes',
            uploaded_by INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')

        # NEW: Faculty subject assignments (class-wise + day-wise)
        db.execute('''CREATE TABLE IF NOT EXISTS faculty_subject_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            faculty_id INTEGER NOT NULL,
            class_name TEXT NOT NULL,
            day TEXT NOT NULL,
            subject TEXT NOT NULL,
            period TEXT,
            room TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE CASCADE)''')

        # =========================================
        # NEW: EXAM SYSTEM TABLES
        # =========================================
        db.execute('''CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name TEXT NOT NULL,
            subject_name TEXT NOT NULL,
            max_marks REAL NOT NULL DEFAULT 50,
            display_order INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')

        db.execute('''CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            academic_year TEXT,
            term_label TEXT DEFAULT '2nd TERM',
            notice_text TEXT,
            custom_message TEXT,
            status TEXT DEFAULT 'draft',
            created_by INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            published_at TEXT)''')

        # Subjects selected for each exam/class, with exam-specific max marks.
        db.execute('''CREATE TABLE IF NOT EXISTS exam_subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER NOT NULL,
            class_name TEXT NOT NULL,
            subject_id INTEGER NOT NULL,
            max_marks REAL NOT NULL DEFAULT 50,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(exam_id, class_name, subject_id),
            FOREIGN KEY(exam_id) REFERENCES exams(id) ON DELETE CASCADE,
            FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE
        )''')
        
        # Migration: add max_marks to existing exam_subjects table
        _exam_subjects_cols = {
            row[1]
            for row in db.execute(
                "PRAGMA table_info(exam_subjects)"
            ).fetchall()
        }

        if 'max_marks' not in _exam_subjects_cols:
            db.execute("""
                ALTER TABLE exam_subjects
                ADD COLUMN max_marks REAL NOT NULL DEFAULT 50
            """)
        
        db.execute('CREATE INDEX IF NOT EXISTS idx_exam_subjects_exam_class ON exam_subjects(exam_id, class_name)')

        db.execute('''CREATE TABLE IF NOT EXISTS exam_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER NOT NULL,
            class_name TEXT NOT NULL,
            teacher_id INTEGER,
            status TEXT DEFAULT 'pending',
            submitted_at TEXT,
            UNIQUE(exam_id, class_name))''')

        # NEW: EXAM FORM REGISTRATIONS TABLE
        db.execute('''CREATE TABLE IF NOT EXISTS exam_registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            student_name TEXT NOT NULL,
            father_name TEXT NOT NULL,
            mother_name TEXT,
            dob TEXT,
            gender TEXT,
            class_name TEXT,
            section TEXT,
            roll_no TEXT,
            admission_no TEXT,
            student_mobile TEXT,
            parent_mobile TEXT NOT NULL,
            address TEXT,
            exam_type TEXT,
            selected_subjects TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        
                # NEW: Question Paper Generator Tables
        db.execute('''CREATE TABLE IF NOT EXISTS exam_papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            class_name TEXT NOT NULL,
            subject TEXT NOT NULL,
            time_allowed TEXT,
            max_marks INTEGER,
            exam_year TEXT,
            teacher_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')

        db.execute('''CREATE TABLE IF NOT EXISTS exam_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id INTEGER NOT NULL,
            section_name TEXT NOT NULL,
            question_text TEXT NOT NULL,
            options TEXT,
            marks INTEGER NOT NULL DEFAULT 1,
            lines INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(paper_id) REFERENCES exam_papers(id) ON DELETE CASCADE)''')

        # Safe migration for databases created before answer-lines support.
        _question_cols = {
            row[1] for row in db.execute("PRAGMA table_info(exam_questions)").fetchall()
        }
        if 'lines' not in _question_cols:
            db.execute("ALTER TABLE exam_questions ADD COLUMN lines INTEGER NOT NULL DEFAULT 1")

        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_exam_questions_paper_id "
            "ON exam_questions(paper_id, id)"
        )

        # Migrate existing exam_marks table — add exam_id column if missing
        _mcols = {row[1] for row in db.execute("PRAGMA table_info(exam_marks)").fetchall()}
        if 'exam_id' not in _mcols:
            db.execute('ALTER TABLE exam_marks ADD COLUMN exam_id INTEGER')

        # Default school settings (required — not dummy data)
        db.execute("INSERT OR IGNORE INTO school_settings (key, value) VALUES ('fee_qr_url', '')")
        db.execute("INSERT OR IGNORE INTO school_settings (key, value) VALUES ('school_name', 'Residential Shanti Niketan')")
        db.execute("INSERT OR IGNORE INTO school_settings (key, value) VALUES ('upi_link', '')")

        db.commit()

COMMON_SUBJECTS = [
    ('HINDI', 100),
    ('ENGLISH', 100),
    ('MATH', 100),
    ('SCIENCE', 100),
    ('GRAMMAR', 100),
    ('GK/NETHIK SHIKSHA', 100),
    ('DRAWING', 100),
]


def ensure_common_subjects(db, class_name):
    """Insert any missing common subjects for the given class.

    - Per-subject existence check → only missing ones insert hote hain.
    - Never deletes or overwrites existing subjects.
    - Safe to call on every page load (idempotent).
    - Returns count of newly inserted rows.
    """
    if not class_name:
        return 0

    class_name = str(class_name).strip()
    if not class_name:
        return 0

    existing_names = {
        row['subject_name']
        for row in db.execute(
            'SELECT subject_name FROM subjects WHERE class_name = ?',
            (class_name,)
        ).fetchall()
    }

    added = 0
    for subject_name, default_max in COMMON_SUBJECTS:
        if subject_name in existing_names:
            continue
        db.execute(
            'INSERT INTO subjects (class_name, subject_name, max_marks) '
            'VALUES (?, ?, ?)',
            (class_name, subject_name, default_max)
        )
        added += 1

    if added:
        db.commit()
    return added

# =========================================
# 🚀 HELPER: Get All Standard + Dynamic Classes
# =========================================
def get_all_classes(db):
    """Hamesha standard classes (Pre-Nursery se 8th) dikhata hai, 
       aur agar database me koi custom class ho toh use bhi add karta hai."""
    standard_classes = [
        'Pre-Nursery', 'Nursery', 'LKG', 'UKG', 
        '1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th'
    ]
    
    class_rows = db.execute(
        '''SELECT class_name AS c FROM subjects
           UNION
           SELECT COALESCE(class_name, child_class) AS c FROM users
             WHERE role='student'
               AND COALESCE(class_name, child_class) IS NOT NULL
               AND COALESCE(class_name, child_class) != ''
        '''
    ).fetchall()
    
    dynamic_classes = {row['c'] for row in class_rows if row['c']}
    
    # Standard classes (case-insensitive) ko ignore karke sirf nayi classes nikalna
    standard_lower = {c.lower() for c in standard_classes}
    extra_classes = sorted([c for c in dynamic_classes if c.lower() not in standard_lower])
    
    return standard_classes + extra_classes

# =========================================
# 3. UTILITY HELPERS
# =========================================
def get_all_notices(target_role=None):
    db = get_db()
    if target_role and target_role != 'all':
        return db.execute("SELECT * FROM notices WHERE target_role IN ('all', ?) ORDER BY id DESC", (target_role,)).fetchall()
    return db.execute('SELECT * FROM notices ORDER BY id DESC').fetchall()

def get_user_by_id(uid):
    db = get_db()
    return db.execute('SELECT * FROM users WHERE id = ?', (uid,)).fetchone()

def get_user_by_unique_id(uid):
    db = get_db()
    return db.execute('SELECT * FROM users WHERE unique_id = ?', (uid,)).fetchone()

def generate_unique_id(role):
    """Generate unique ID like SNVT00001, SNVP00001, SNVST00001"""
    db = get_db()
    prefixes = {'admin': 'SNV', 'administrator': 'SNV', 'teacher': 'SNVT', 'parent': 'SNVP', 'student': 'SNVST'}
    prefix = prefixes.get(role, 'SNV')

    last = db.execute(
        "SELECT unique_id FROM users WHERE unique_id LIKE ? ORDER BY id DESC LIMIT 1",
        (prefix + '%',)
    ).fetchone()

    if last and last['unique_id']:
        try:
            num = int(last['unique_id'].replace(prefix, '')) + 1
        except:
            num = 1
    else:
        num = 1

    while True:
        new_id = f"{prefix}{str(num).zfill(5)}"
        exists = db.execute('SELECT 1 FROM users WHERE unique_id = ?', (new_id,)).fetchone()
        if not exists:
            return new_id
        num += 1

def get_setting(key, default=''):
    db = get_db()
    row = db.execute('SELECT value FROM school_settings WHERE key = ?', (key,)).fetchone()
    return row['value'] if row else default

def set_setting(key, value):
    db = get_db()
    db.execute('INSERT OR REPLACE INTO school_settings (key, value) VALUES (?, ?)', (key, value))
    db.commit()


def safe_redirect_url(default_url):
    """Accept only same-host referrers; otherwise use the supplied local URL."""
    referrer = request.referrer
    if not referrer:
        return default_url
    try:
        parsed = urlparse(referrer)
        host = request.host.split(':', 1)[0].lower()
        if parsed.scheme in {'http', 'https'} and parsed.hostname and parsed.hostname.lower() == host:
            return referrer
    except (TypeError, ValueError):
        pass
    return default_url

def get_combined_faculty():
    """Fetches faculty records. Ensures every active teacher has a faculty row
       so that faculty.id is always available for subject assignments."""
    db = get_db()

    teachers = db.execute(
        "SELECT id, name, subject, qualification, experience, photo_url FROM users "
        "WHERE role='teacher' AND is_active = 1"
    ).fetchall()
    for t in teachers:
        existing = db.execute(
            'SELECT id FROM faculty WHERE user_id = ?', (t['id'],)
        ).fetchone()
        if existing:
            continue
        existing = db.execute(
            'SELECT id FROM faculty WHERE name = ?', (t['name'],)
        ).fetchone()
        if existing:
            db.execute('UPDATE faculty SET user_id = ? WHERE id = ?',
                       (t['id'], existing['id']))
        else:
            db.execute(
                'INSERT INTO faculty '
                '(user_id, name, subject, qualification, experience, photo_url, bio) '
                'VALUES (?, ?, ?, ?, ?, ?, ?)',
                (t['id'], t['name'], t['subject'] or 'General',
                 t['qualification'] or '', t['experience'] or '', t['photo_url'],
                 'Dedicated teacher at Residential Shanti Niketan.')
            )
    db.commit()

    rows = db.execute(
        'SELECT id, user_id, name, subject, qualification, experience, '
        'photo_url, bio, display_order FROM faculty ORDER BY display_order, id'
    ).fetchall()
    return [dict(r) for r in rows]


# =========================================
# HELPER: Find a parent's child (student) record
# =========================================
def get_parent_child(db, parent_user):
    """
    Look up a parent's child (student) record.

    Tries in this order:
      1. child_admission_no → matches student.admission_no
      2. child_name + child_class → matches student.name + (class_name or child_class)

    Returns the student Row or None.
    """
    if not parent_user:
        return None

    if parent_user['child_admission_no']:
        row = db.execute(
            "SELECT * FROM users WHERE role='student' AND admission_no = ? LIMIT 1",
            (parent_user['child_admission_no'],)
        ).fetchone()
        if row:
            return row

    if parent_user['child_name'] and parent_user['child_class']:
        return db.execute(
            "SELECT * FROM users WHERE role='student' "
            "AND LOWER(name) = LOWER(?) "
            "AND (class_name = ? OR child_class = ?) "
            "LIMIT 1",
            (parent_user['child_name'],
             parent_user['child_class'],
             parent_user['child_class'])
        ).fetchone()

    return None


# =========================================
# 3.1. USER PHOTO + FIELD HELPERS
# =========================================
def save_user_photo(file_storage, max_kb=60):
    if not file_storage or not file_storage.filename or not allowed_file(file_storage.filename):
        return None
    compressed = compress_image(file_storage, target_kb=max_kb)
    if not compressed:
        return None
    photos_dir = UPLOAD_FOLDER / 'photos'
    photos_dir.mkdir(parents=True, exist_ok=True)
    filename = f"user_{secrets.token_hex(16)}.jpg"
    destination = photos_dir / filename
    # Exclusive create prevents accidental overwrite, even in the unlikely event of collision.
    with destination.open('xb') as output:
        output.write(compressed)
    return url_for('static', filename=f'uploads/photos/{filename}')


def _collect_form_fields(role):
    """Fetch allowlisted fields from request.form (empty -> None) + safe normalization."""
    data = {}
    for k in COMMON_FIELDS:
        v = request.form.get(k, '').strip()
        data[k] = v or None
    for k in ROLE_FIELDS.get(role, []):
        v = request.form.get(k, '').strip()
        data[k] = v or None
    if data.get('pan'):
        data['pan'] = data['pan'].upper()
    if data.get('ifsc'):
        data['ifsc'] = data['ifsc'].upper()
    if data.get('aadhar'):
        data['aadhar'] = re.sub(r'\D', '', data['aadhar']) or None
    return data


def compress_image(file_storage, target_kb=45, max_dim=1600,
                   quality_start=85, quality_min=20):
    """Decode and re-encode an uploaded image; never trust its extension/MIME."""
    try:
        file_storage.stream.seek(0)
        # Reject decompression bombs and malformed image payloads.
        Image.MAX_IMAGE_PIXELS = 25_000_000
        with Image.open(file_storage.stream) as source:
            if source.format not in {'JPEG', 'PNG', 'GIF', 'WEBP'}:
                return None
            source.verify()
        file_storage.stream.seek(0)
        with Image.open(file_storage.stream) as source:
            source.seek(0)  # first frame only for animated images
            img = ImageOps.exif_transpose(source.copy())

        if img.mode in ('RGBA', 'LA', 'P'):
            if img.mode == 'P':
                img = img.convert('RGBA')
            if img.mode == 'RGBA':
                bg = Image.new('RGB', img.size, (255, 255, 255))
                bg.paste(img, mask=img.getchannel('A'))
                img = bg
            else:
                img = img.convert('RGB')
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        quality = quality_start
        while quality >= quality_min:
            buf.seek(0)
            buf.truncate()
            img.save(buf, format='JPEG', quality=quality,
                     optimize=True, progressive=True)
            if buf.tell() <= target_kb * 1024:
                break
            quality -= 5

        while buf.tell() > target_kb * 1024 and max(img.size) > 400:
            new_size = (max(1, int(img.width * 0.85)), max(1, int(img.height * 0.85)))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            buf.seek(0)
            buf.truncate()
            img.save(buf, format='JPEG', quality=quality_min,
                     optimize=True, progressive=True)

        buf.seek(0)
        return buf.getvalue()
    except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        app.logger.warning('Rejected invalid or unsafe image upload')
        return None
    except Exception:
        app.logger.exception('Image processing failed')
        return None

# =========================================
# 4. DECORATORS
# =========================================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        uid = session.get('user_id')
        if not uid:
            flash('Please login to access this page.', 'error')
            return redirect(url_for('login_page'))
        user = get_user_by_id(uid)
        if not user or not user['is_active']:
            session.clear()
            flash('Your session is no longer valid. Please login again.', 'error')
            return redirect(url_for('login_page'))
        if user['force_password_change'] and request.endpoint not in ('change_password', 'logout', 'static'):
            flash('Please change your password to continue.', 'error')
            return redirect(url_for('change_password'))
        # Always trust the current database role, not a stale client session value.
        session['user_role'] = user['role']
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        uid = session.get('user_id')
        if not uid:
            flash('Please login to access admin panel.', 'error')
            return redirect(url_for('login_page'))
        user = get_user_by_id(uid)
        if not user or not user['is_active']:
            session.clear()
            flash('Your session is no longer valid. Please login again.', 'error')
            return redirect(url_for('login_page'))
        if user['role'] not in ('admin', 'administrator'):
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('user_dashboard'))
        session['user_role'] = user['role']
        if user['force_password_change']:
            flash('Please change your password to continue.', 'error')
            return redirect(url_for('change_password'))
        return f(*args, **kwargs)
    return decorated

def get_dashboard_url(role):
    return url_for('admin_dashboard') if role in ('admin', 'administrator') else url_for('user_dashboard')

# === Context processor for admin sidebar pending counts ===
@app.context_processor
def inject_admin_sidebar_counts():
    """Make pending counts available to all admin templates."""
    if not session.get('user_id') or session.get('user_role') not in ('admin', 'administrator'):
        return {}
    try:
        db = get_db()
        return {
            'pending_leaves': db.execute(
                "SELECT COUNT(*) FROM leave_requests WHERE status='pending'"
            ).fetchone()[0],
            'pending_fees': db.execute(
                "SELECT COUNT(*) FROM fee_payments WHERE status='pending'"
            ).fetchone()[0],
            'total_homework': db.execute(
                "SELECT COUNT(*) FROM homework"
            ).fetchone()[0],
            'total_study_materials': db.execute(
                "SELECT COUNT(*) FROM study_materials"
            ).fetchone()[0],
            'total_assignments': db.execute(
                "SELECT COUNT(*) FROM faculty_subject_assignments"
            ).fetchone()[0],
        }
    except Exception:
        return {}

# =========================================
# NEW: EXAM SYSTEM + QUESTION PAPERS — GLOBAL PENDING COUNTS
# =========================================
@app.context_processor
def inject_exam_pending_counts():
    """
    Provides pending_exam_submissions (admin) & pending_exam_marks (teacher)
    globally so every template can show live badges without per-route changes.
    
    NEW: Also provides question paper counts:
       - Admin/Administrator: total_question_papers (sabhi teachers ke)
       - Teacher: my_question_papers (apne banaye hue)
    """
    default = {
        'pending_exam_submissions': 0,
        'pending_exam_marks': 0,
        'total_question_papers': 0,
        'my_question_papers': 0,
    }

    if not session.get('user_id'):
        return default

    role = session.get('user_role')
    try:
        db = get_db()

        # ---------- ADMIN / ADMINISTRATOR ----------
        if role in ('admin', 'administrator'):
            pending = db.execute(
                "SELECT COUNT(*) FROM exam_submissions es "
                "JOIN exams e ON es.exam_id = e.id "
                "WHERE e.status='published' AND es.status IN ('pending', 'in_progress')"
            ).fetchone()[0] or 0

            # Total question papers created by all teachers
            total_qp = db.execute(
                "SELECT COUNT(*) FROM exam_papers"
            ).fetchone()[0] or 0

            return {
                'pending_exam_submissions': pending,
                'pending_exam_marks': 0,
                'total_question_papers': total_qp,
                'my_question_papers': 0,
            }

        # ---------- TEACHER ----------
        if role == 'teacher':
            user = db.execute(
                'SELECT classes_assigned FROM users WHERE id = ?',
                (session['user_id'],)
            ).fetchone()

            # Teacher ke apne banaye hue question papers ka count
            my_qp = db.execute(
                "SELECT COUNT(*) FROM exam_papers WHERE teacher_id = ?",
                (session['user_id'],)
            ).fetchone()[0] or 0

            if not user or not user['classes_assigned']:
                return {
                    'pending_exam_submissions': 0,
                    'pending_exam_marks': 0,
                    'total_question_papers': 0,
                    'my_question_papers': my_qp,
                }

            classes = [c.strip() for c in user['classes_assigned'].split(',') if c.strip()]
            if not classes:
                return {
                    'pending_exam_submissions': 0,
                    'pending_exam_marks': 0,
                    'total_question_papers': 0,
                    'my_question_papers': my_qp,
                }

            ph = ','.join(['?'] * len(classes))
            count = db.execute(
                f"SELECT COUNT(*) FROM exam_submissions es "
                f"JOIN exams e ON es.exam_id = e.id "
                f"WHERE e.status='published' "
                f"AND es.status IN ('pending', 'in_progress') "
                f"AND es.class_name IN ({ph})",
                tuple(classes)
            ).fetchone()[0] or 0

            return {
                'pending_exam_submissions': 0,
                'pending_exam_marks': count,
                'total_question_papers': 0,
                'my_question_papers': my_qp,
            }

    except Exception:
        pass

    return default
# =========================================
# SESSION SYNC — Ensures DB photo_url is always in session
# =========================================
@app.before_request
def sync_session_user_info():
    """Refresh identity from DB and reject deleted/deactivated accounts."""
    if session.get('user_id'):
        user = get_db().execute(
            'SELECT id, photo_url, name, role, is_active FROM users WHERE id = ?',
            (session['user_id'],)
        ).fetchone()
        if not user or not user['is_active']:
            session.clear()
            return None
        session['photo_url'] = user['photo_url']
        session['user_name'] = user['name']
        session['user_role'] = user['role']


def generate_csrf_token():
    """Return a session-bound CSRF token for HTML forms and AJAX requests."""
    token = session.get('_csrf_token')
    if not token:
        token = secrets.token_urlsafe(32)
        session['_csrf_token'] = token
    return token


@app.context_processor
def inject_csrf_token():
    return {'csrf_token': generate_csrf_token}


@app.before_request
def csrf_token_protection():
    """Require a valid session-bound token for every state-changing request."""
    if request.method not in {'POST', 'PUT', 'PATCH', 'DELETE'}:
        return None
    expected = session.get('_csrf_token')
    supplied = (request.form.get('csrf_token')
                or request.headers.get('X-CSRFToken')
                or request.headers.get('X-CSRF-Token'))
    if not expected or not supplied or not hmac.compare_digest(str(expected), str(supplied)):
        app.logger.warning('Rejected request with missing/invalid CSRF token: %s %s',
                           request.method, request.path)
        return ('Invalid or missing CSRF token. Refresh the page and try again.', 400)
    return None


@app.before_request
def basic_csrf_origin_guard():
    """Compatibility-safe browser CSRF mitigation for existing HTML forms.

    Rejects cross-origin unsafe browser requests. For complete token-based CSRF
    protection, templates must also include the session csrf_token in every form.
    """
    if request.method not in {'POST', 'PUT', 'PATCH', 'DELETE'}:
        return None
    fetch_site = request.headers.get('Sec-Fetch-Site', '').lower()
    if fetch_site == 'cross-site':
        return ('Cross-site request blocked.', 403)
    origin = request.headers.get('Origin')
    referer = request.headers.get('Referer')
    candidate = origin or referer
    if candidate:
        try:
            parsed = urlparse(candidate)
            expected_host = request.host.split(':', 1)[0].lower()
            if parsed.hostname and parsed.hostname.lower() != expected_host:
                return ('Cross-origin request blocked.', 403)
            if parsed.scheme and parsed.scheme not in {'http', 'https'}:
                return ('Invalid request origin.', 403)
        except (TypeError, ValueError):
            return ('Invalid request origin.', 403)
    return None

# =========================================
# 5. PUBLIC ROUTES
# =========================================
@app.route('/')
def home():
    notices = get_all_notices()
    db = get_db()

    upcoming_events = db.execute(
        "SELECT * FROM events WHERE event_date >= date('now') ORDER BY event_date ASC LIMIT 3"
    ).fetchall()
    testimonials = db.execute(
        'SELECT * FROM testimonials WHERE is_approved = 1 ORDER BY RANDOM() LIMIT 4'
    ).fetchall()
    achievements = db.execute(
        'SELECT * FROM achievements ORDER BY id DESC LIMIT 3'
    ).fetchall()

    gallery_images = db.execute('SELECT * FROM gallery ORDER BY display_order, id').fetchall()

    return render_template('index.html',
                          notices=notices,
                          upcoming_events=upcoming_events,
                          testimonials=testimonials,
                          achievements=achievements,
                          gallery_images=gallery_images)

@app.route('/notice')
def notices_page():
    notices = get_all_notices()
    return render_template('notice.html', notices=notices)

@app.route('/academics')
def academics_page():
    return render_template('academics.html')

@app.route('/gallery')
def gallery_page():
    db = get_db()
    images = db.execute('SELECT * FROM gallery ORDER BY display_order, id').fetchall()
    return render_template('gallery.html', images=images)

@app.route('/faculty')
def faculty_page():
    faculty_list = get_combined_faculty()
    return render_template('faculty.html', faculty=faculty_list)

@app.route('/events')
def events_page():
    db = get_db()
    events = db.execute('SELECT * FROM events ORDER BY event_date ASC').fetchall()
    return render_template('events.html', events=events)

@app.route('/faq')
def faq_page():
    db = get_db()
    faqs = db.execute('SELECT * FROM faq ORDER BY display_order, id').fetchall()
    return render_template('faq.html', faqs=faqs)

@app.route('/achievements')
def achievements_page():
    db = get_db()
    achievements = db.execute('SELECT * FROM achievements ORDER BY id DESC').fetchall()
    return render_template('achievements.html', achievements=achievements)


@app.route('/admin/edit-profile/<int:user_id>', methods=['POST'])
@admin_required
def admin_edit_profile(user_id):
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

    if not user:
        flash('User not found.', 'error')
        return redirect(safe_redirect_url(url_for('admin_users')))

    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    role = request.form.get('role', user['role'])

    if not name or not email or not phone or not role:
        flash('Name, Email, Phone and Role are required.', 'error')
        return redirect(safe_redirect_url(url_for('admin_users')))

    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        flash('Invalid email format.', 'error')
        return redirect(safe_redirect_url(url_for('admin_users')))

    if role not in ('teacher', 'admin', 'administrator', 'parent', 'student'):
        flash('Invalid role.', 'error')
        return redirect(safe_redirect_url(url_for('admin_users')))

    editable = set(COMMON_FIELDS) | set(ROLE_FIELDS.get(role, []))
    updates = {}
    for f in editable:
        if f in request.form:
            updates[f] = request.form.get(f, '').strip() or None

    if updates.get('pan'):
        updates['pan'] = updates['pan'].upper()
    if updates.get('ifsc'):
        updates['ifsc'] = updates['ifsc'].upper()
    if updates.get('aadhar'):
        updates['aadhar'] = re.sub(r'\D', '', updates['aadhar']) or None

    if role == 'student':
        if updates.get('class_name'):
            updates['child_class'] = updates['class_name']
        elif updates.get('child_class') and 'class_name' not in updates:
            updates['class_name'] = updates['child_class']

    new_photo = request.files.get('photo')
    if new_photo and new_photo.filename:
        saved_url = save_user_photo(new_photo)
        if saved_url:
            updates['photo_url'] = saved_url

    set_parts = ['name = ?', 'email = ?', 'phone = ?', 'role = ?']
    params = [name, email, phone, role]
    for k, v in updates.items():
        set_parts.append(f'{k} = ?')
        params.append(v)
    params.append(user_id)

    try:
        db.execute(f"UPDATE users SET {', '.join(set_parts)} WHERE id = ?", tuple(params))

        if role == 'teacher':
            fac = db.execute('SELECT id FROM faculty WHERE user_id = ?', (user_id,)).fetchone()
            if fac:
                db.execute('''UPDATE faculty SET name = ?, subject = COALESCE(?, subject), 
                              qualification = COALESCE(?, qualification), experience = COALESCE(?, experience), 
                              photo_url = COALESCE(?, photo_url) WHERE user_id = ?''',
                           (name, updates.get('subject'), updates.get('qualification'),
                            updates.get('experience'), updates.get('photo_url'), user_id))
            else:
                db.execute('''INSERT INTO faculty (user_id, name, subject, qualification, experience, photo_url) 
                              VALUES (?, ?, ?, ?, ?, ?)''',
                           (user_id, name, updates.get('subject') or 'General',
                            updates.get('qualification') or '', updates.get('experience') or '', updates.get('photo_url')))
        else:
            fac_row = db.execute('SELECT id FROM faculty WHERE user_id = ?', (user_id,)).fetchone()
            if fac_row:
                db.execute('DELETE FROM faculty_subject_assignments WHERE faculty_id = ?',
                           (fac_row['id'],))
            db.execute('DELETE FROM faculty WHERE user_id = ?', (user_id,))

        db.commit()

        if session['user_id'] == user_id:
            session['user_name'] = name
            session['user_role'] = role
            session['photo_url'] = updates.get('photo_url', user['photo_url'])

        flash('Profile updated successfully!', 'success')
    except sqlite3.IntegrityError:
        flash('Email already exists. Please use a different email.', 'error')
    except Exception:
        db.rollback()
        app.logger.exception('Admin profile update failed for user_id=%s', user_id)
        flash('Unable to update this profile right now. Please try again.', 'error')

    return redirect(safe_redirect_url(url_for('admin_users')))


# =========================================
# 6. AUTH ROUTES
# =========================================
LOGIN_FAILURE_LIMIT = 5
LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_LOCK_SECONDS = 15 * 60


def _login_attempt_key(unique_id):
    raw = f"{request.remote_addr or 'unknown'}|{unique_id.casefold()}"
    return hmac.new(app.config['SECRET_KEY'].encode('utf-8'), raw.encode('utf-8'), 'sha256').hexdigest()


def _login_is_blocked(db, attempt_key, now):
    row = db.execute('SELECT blocked_until FROM login_attempts WHERE attempt_key = ?',
                     (attempt_key,)).fetchone()
    return bool(row and float(row['blocked_until'] or 0) > now)


def _record_login_failure(db, attempt_key, now):
    # Periodically prune expired keys so repeated anonymous attempts cannot grow
    # this security table without bound.
    db.execute('DELETE FROM login_attempts WHERE window_started < ? AND blocked_until < ?',
               (now - 24 * 60 * 60, now))
    row = db.execute('SELECT failures, window_started FROM login_attempts WHERE attempt_key = ?',
                     (attempt_key,)).fetchone()
    if not row or now - float(row['window_started']) > LOGIN_WINDOW_SECONDS:
        failures, started = 1, now
    else:
        failures, started = int(row['failures']) + 1, float(row['window_started'])
    blocked_until = now + LOGIN_LOCK_SECONDS if failures >= LOGIN_FAILURE_LIMIT else 0
    db.execute('''INSERT INTO login_attempts (attempt_key, failures, window_started, blocked_until)
                  VALUES (?, ?, ?, ?)
                  ON CONFLICT(attempt_key) DO UPDATE SET
                    failures=excluded.failures,
                    window_started=excluded.window_started,
                    blocked_until=excluded.blocked_until''',
               (attempt_key, failures, started, blocked_until))
    db.commit()


@app.route('/login', methods=['GET'])
def login_page():
    if session.get('user_id'):
        return redirect(get_dashboard_url(session.get('user_role', 'student')))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    unique_id = request.form.get('unique_id', '').strip().upper()[:40]
    password = request.form.get('password', '')
    if not unique_id or not password or len(password) > 1024:
        flash('Invalid ID or password.', 'error')
        return redirect(url_for('login_page'))

    db = get_db()
    now = time.time()
    attempt_key = _login_attempt_key(unique_id)
    if _login_is_blocked(db, attempt_key, now):
        flash('Too many failed login attempts. Please wait 15 minutes and try again.', 'error')
        return redirect(url_for('login_page'))
    user = db.execute('SELECT * FROM users WHERE unique_id = ?', (unique_id,)).fetchone()

    if user and check_password_hash(user['password_hash'], password):
        if not user['is_active']:
            flash('Your account has been deactivated. Contact admin.', 'error')
            return redirect(url_for('login_page'))
        db.execute('DELETE FROM login_attempts WHERE attempt_key = ?', (attempt_key,))
        db.commit()
        session.clear()  # rotate session state after successful authentication
        session.permanent = True
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        session['user_role'] = user['role']
        session['unique_id'] = user['unique_id']
        session['photo_url'] = user['photo_url']

        if user['force_password_change']:
            flash('Welcome! Please set a new password.', 'success')
            return redirect(url_for('change_password'))

        flash(f'Welcome back, {user["name"]}!', 'success')
        return redirect(get_dashboard_url(user['role']))
    else:
        _record_login_failure(db, attempt_key, now)
        flash('Invalid ID or password.', 'error')
        return redirect(url_for('login_page'))

@app.route('/change-password', methods=['GET', 'POST'])
def change_password():
    if not session.get('user_id'):
        return redirect(url_for('login_page'))

    if request.method == 'POST':
        new_pw = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')

        if len(new_pw) < 10 or len(new_pw) > 128:
            flash('Password must be between 10 and 128 characters.', 'error')
            return redirect(url_for('change_password'))
        if new_pw != confirm:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('change_password'))

        db = get_db()
        db.execute('UPDATE users SET password_hash = ?, force_password_change = 0 WHERE id = ?',
                   (generate_password_hash(new_pw), session['user_id']))
        db.commit()
        flash('Password updated successfully!', 'success')
        return redirect(get_dashboard_url(session['user_role']))

    return render_template('change_password.html')

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('home'))

# =========================================
# 7. USER DASHBOARD
# =========================================
@app.route('/dashboard')
@login_required
def user_dashboard():
    user = get_user_by_id(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login_page'))

    notices = get_all_notices(user['role'])
    db    = get_db()
    role  = user['role']

    parent_child = get_parent_child(db, user) if role == 'parent' else None
    parent_child_id = parent_child['id'] if parent_child else None

    attendance_user_id = parent_child_id if role == 'parent' else user['id']

    if attendance_user_id:
        all_attendance = db.execute(
            'SELECT * FROM attendance WHERE user_id = ? ORDER BY date DESC',
            (attendance_user_id,)
        ).fetchall()
    else:
        all_attendance = []

    attendance = all_attendance[:30]

    messages = db.execute(
        'SELECT * FROM messages WHERE to_user_id = ? OR to_role = ? '
        'ORDER BY id DESC LIMIT 20',
        (user['id'], role)
    ).fetchall()

    upcoming_events = db.execute(
        "SELECT * FROM events WHERE event_date >= date('now') "
        "ORDER BY event_date ASC LIMIT 3"
    ).fetchall()

    # ---------- TEACHER ----------
    if role == 'teacher':
        leaves = db.execute(
            'SELECT * FROM leave_requests WHERE user_id = ? ORDER BY id DESC',
            (user['id'],)
        ).fetchall()
        return render_template('teacher_dashboard.html',
                              user=user, notices=notices, attendance=attendance,
                              leaves=leaves, messages=messages,
                              upcoming_events=upcoming_events)

    # ---------- STUDENT ----------
    elif role == 'student':
        fees = db.execute(
            'SELECT * FROM fee_payments WHERE student_id = ? ORDER BY id DESC',
            (user['id'],)
        ).fetchall()

        subject_stats = {}
        for a in all_attendance:
            sub = a['subject'] if 'subject' in a.keys() and a['subject'] else 'General'
            if sub not in subject_stats:
                subject_stats[sub] = {'present': 0, 'absent': 0, 'total': 0}
            subject_stats[sub]['total'] += 1
            if a['status'].lower() == 'present':
                subject_stats[sub]['present'] += 1
            else:
                subject_stats[sub]['absent'] += 1

        exam_marks = db.execute(
            'SELECT * FROM exam_marks WHERE student_id = ? '
            'ORDER BY exam_type, subject',
            (user['id'],)
        ).fetchall()

        pending_homework = 0
        homework_list = []
        target_class = user['class_name'] or user['child_class']
        if target_class:
            pending_homework = db.execute(
                "SELECT COUNT(*) FROM homework WHERE class_name = ? "
                "AND (due_date IS NULL OR due_date >= date('now'))",
                (target_class,)
            ).fetchone()[0] or 0
            homework_list = db.execute(
                "SELECT * FROM homework WHERE class_name = ? "
                "ORDER BY due_date DESC, id DESC LIMIT 10",
                (target_class,)
            ).fetchall()

        return render_template('student_dashboard.html',
                              user=user, notices=notices, attendance=attendance,
                              subject_stats=subject_stats, exam_marks=exam_marks,
                              fees=fees, messages=messages,
                              pending_homework=pending_homework,
                              homework_list=homework_list,
                              upcoming_events=upcoming_events,
                              fee_qr=get_setting('fee_qr_url'),
                              upi_link=get_setting('upi_link'))

    # ---------- PARENT ----------
    elif role == 'parent':
        if parent_child_id:
            fees = db.execute(
                'SELECT * FROM fee_payments WHERE student_id = ? ORDER BY id DESC',
                (parent_child_id,)
            ).fetchall()
        else:
            fees = []

        pending_homework = 0
        if user['child_class']:
            pending_homework = db.execute(
                "SELECT COUNT(*) FROM homework WHERE class_name = ? "
                "AND (due_date IS NULL OR due_date >= date('now'))",
                (user['child_class'],)
            ).fetchone()[0] or 0

        fee_paid    = sum(f['amount'] for f in fees if f['status'] == 'verified')
        fee_pending = sum(f['amount'] for f in fees if f['status'] == 'pending')
        fee_partial = sum(f['amount'] for f in fees if f['status'] == 'partial')
        fee_total   = fee_paid + fee_pending + fee_partial

        return render_template('parent_dashboard.html',
                              user=user, notices=notices, attendance=attendance,
                              fees=fees, messages=messages,
                              upcoming_events=upcoming_events,
                              pending_homework=pending_homework,
                              fee_total=fee_total,
                              fee_paid=fee_paid,
                              fee_pending=fee_pending,
                              child_linked=bool(parent_child_id),
                              fee_qr=get_setting('fee_qr_url'),
                              upi_link=get_setting('upi_link'))

    # ---------- FALLBACK ----------
    else:
        return render_template('user.html',
                              user=user, notices=notices, attendance=attendance,
                              leaves=[], fees=[], messages=messages,
                              upcoming_events=upcoming_events,
                              fee_qr=get_setting('fee_qr_url'),
                              upi_link=get_setting('upi_link'))

# =========================================
# 8. TEACHER LEAVE REQUEST
# =========================================
@app.route('/leave/request', methods=['POST'])
@login_required
def leave_request():
    leave_type = request.form.get('leave_type', '')
    from_date = request.form.get('from_date', '')
    to_date = request.form.get('to_date', '')
    reason = request.form.get('reason', '').strip()

    if not leave_type or not from_date or not to_date or not reason:
        flash('Please fill all leave fields.', 'error')
        return redirect(url_for('user_dashboard'))

    db = get_db()
    db.execute('INSERT INTO leave_requests (user_id, leave_type, from_date, to_date, reason) VALUES (?,?,?,?,?)',
               (session['user_id'], leave_type, from_date, to_date, reason))
    db.commit()
    flash('Leave request submitted. Awaiting admin approval.', 'success')
    return redirect(url_for('user_dashboard'))

# =========================================
# 9. FEE PAYMENT
# =========================================
@app.route('/fee/pay', methods=['POST'])
@login_required
def fee_pay():
    amount_raw = (request.form.get('amount') or '').strip()
    txn_id = (request.form.get('transaction_id') or '').strip()[:100]
    remarks = (request.form.get('remarks') or '').strip()[:500]

    try:
        amount = float(amount_raw)
        if not (0 < amount <= 1_000_000) or not amount_raw or not __import__('math').isfinite(amount):
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        flash('Invalid amount. Enter a valid amount between 0 and 10,00,000.', 'error')
        return redirect(url_for('user_dashboard'))

    db = get_db()

    payer = get_user_by_id(session['user_id'])
    student_id = session['user_id']

    if payer and payer['role'] == 'parent':
        child = get_parent_child(db, payer)
        if not child:
            flash('No linked child found for your account. Please contact the office.', 'error')
            return redirect(url_for('user_dashboard'))
        student_id = child['id']

    db.execute('INSERT INTO fee_payments (student_id, amount, payment_date, transaction_id, status, remarks) VALUES (?,?,?,?,?,?)',
               (student_id, amount, datetime.now().strftime('%Y-%m-%d'), txn_id, 'pending', remarks))
    db.commit()
    flash('Payment submitted. Admin will verify shortly.', 'success')
    return redirect(url_for('user_dashboard'))

# =========================================
# 10. ADMIN PANEL ROUTES
# =========================================
@app.route('/admin')
@admin_required
def admin_dashboard():
    db = get_db()
    stats = {
        'total_users':     db.execute('SELECT COUNT(*) FROM users').fetchone()[0],
        'total_teachers':  db.execute("SELECT COUNT(*) FROM users WHERE role='teacher'").fetchone()[0],
        'total_parents':   db.execute("SELECT COUNT(*) FROM users WHERE role='parent'").fetchone()[0],
        'total_students':  db.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0],
        'total_notices':   db.execute('SELECT COUNT(*) FROM notices').fetchone()[0],
        'total_enquiries': db.execute('SELECT COUNT(*) FROM enquiries').fetchone()[0],
        'pending_leaves':  db.execute("SELECT COUNT(*) FROM leave_requests WHERE status='pending'").fetchone()[0],
        'pending_fees':    db.execute("SELECT COUNT(*) FROM fee_payments WHERE status='pending'").fetchone()[0],
        'total_assignments': db.execute("SELECT COUNT(*) FROM faculty_subject_assignments").fetchone()[0],
    }

    stats['total_classes'] = db.execute(
        "SELECT COUNT(DISTINCT class_name) FROM users "
        "WHERE role='student' AND class_name IS NOT NULL AND class_name != ''"
    ).fetchone()[0] or 0

    fee_row = db.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN status='verified' THEN amount ELSE 0 END), 0) AS paid,
            COALESCE(SUM(CASE WHEN status='pending'  THEN amount ELSE 0 END), 0) AS pending,
            COALESCE(SUM(CASE WHEN status='partial'  THEN amount ELSE 0 END), 0) AS partial
        FROM fee_payments
    """).fetchone()

    paid    = float(fee_row['paid']    or 0)
    pending = float(fee_row['pending'] or 0)
    partial = float(fee_row['partial'] or 0)
    total   = paid + pending + partial

    def _pct(v):
        return round((v / total) * 100) if total > 0 else 0

    stats['expected_fees']  = total
    stats['collected_fees'] = paid + partial
    stats['pending_amount'] = pending
    stats['paid_pct']       = _pct(paid)
    stats['partial_pct']    = _pct(partial)
    stats['pending_pct']    = _pct(pending)
    stats['collected_pct']  = _pct(paid + partial)

    upcoming_events = db.execute(
        "SELECT * FROM events WHERE event_date >= date('now') "
        "ORDER BY event_date ASC LIMIT 4"
    ).fetchall()

    recent_students = db.execute(
        "SELECT * FROM users WHERE role='student' ORDER BY id DESC LIMIT 5"
    ).fetchall()

    admission_trend = []
    now = datetime.now()
    for i in range(6, -1, -1):
        target = (now.replace(day=1) - timedelta(days=i * 28)).replace(day=1)
        next_month = (target.replace(day=28) + timedelta(days=4)).replace(day=1)
        cnt = db.execute(
            "SELECT COUNT(*) FROM users WHERE role='student' "
            "AND created_at >= ? AND created_at < ?",
            (target.strftime('%Y-%m-%d'), next_month.strftime('%Y-%m-%d'))
        ).fetchone()[0]
        admission_trend.append({'label': target.strftime('%b'), 'count': cnt})

    max_trend = max((x['count'] for x in admission_trend), default=1) or 1

    recent_users  = db.execute('SELECT * FROM users ORDER BY id DESC LIMIT 6').fetchall()
    recent_leaves = db.execute('''SELECT lr.*, u.name as user_name, u.unique_id as user_uid, u.role as user_role
                                   FROM leave_requests lr JOIN users u ON lr.user_id = u.id
                                   ORDER BY lr.id DESC LIMIT 5''').fetchall()

    admin_inbox_messages = db.execute(
        "SELECT m.*, u.name as from_name "
        "FROM messages m LEFT JOIN users u ON m.from_user_id = u.id "
        "WHERE m.to_user_id = ? OR m.to_role = ? "
        "ORDER BY m.id DESC LIMIT 5",
        (session['user_id'], 'admin')
    ).fetchall()

    return render_template('admin.html',
                          stats=stats,
                          recent_users=recent_users,
                          recent_leaves=recent_leaves,
                          recent_students=recent_students,
                          upcoming_events=upcoming_events,
                          admission_trend=admission_trend,
                          max_trend=max_trend,
                          messages=admin_inbox_messages,
                          active_page='dashboard')

@app.route('/admin/users')
@admin_required
def admin_users():
    db = get_db()
    role_filter = request.args.get('role', 'all')
    q = (request.args.get('q') or '').strip()

    query = 'SELECT * FROM users WHERE 1=1'
    params = []

    if role_filter != 'all':
        query += ' AND role = ?'
        params.append(role_filter)

    if q:
        like = f'%{q}%'
        query += ' AND (name LIKE ? OR email LIKE ? OR phone LIKE ? OR unique_id LIKE ?)'
        params.extend([like, like, like, like])

    query += ' ORDER BY id DESC'
    users = db.execute(query, tuple(params)).fetchall()

    return render_template(
        'admin_users.html',
        users=users,
        role_filter=role_filter,
        q=q,
        active_page='users'
    )

# =========================================
# ADMIN DEDICATED PHOTO ROUTES
# =========================================
@app.route('/admin/users/<int:user_id>/update-photo', methods=['POST'])
@admin_required
def admin_update_user_photo(user_id):
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        flash('User not found.', 'error')
        return redirect(safe_redirect_url(url_for('admin_users')))

    photo_file = request.files.get('photo')
    if not photo_file or not photo_file.filename:
        flash('No file uploaded.', 'error')
        return redirect(safe_redirect_url(url_for('admin_users')))

    if not allowed_file(photo_file.filename):
        flash('Invalid file type.', 'error')
        return redirect(safe_redirect_url(url_for('admin_users')))

    photo_url = save_user_photo(photo_file)
    if not photo_url:
        flash('Image too large (max 2MB) or could not be saved.', 'error')
        return redirect(safe_redirect_url(url_for('admin_users')))

    db.execute('UPDATE users SET photo_url = ? WHERE id = ?', (photo_url, user_id))
    if user['role'] == 'teacher':
        db.execute('UPDATE faculty SET photo_url = ? WHERE user_id = ?', (photo_url, user_id))
    db.commit()

    if session['user_id'] == user_id:
        session['photo_url'] = photo_url

    flash('User photo updated successfully.', 'success')
    return redirect(safe_redirect_url(url_for('admin_users')))


@app.route('/admin/users/<int:user_id>/remove-photo', methods=['POST'])
@admin_required
def admin_remove_user_photo(user_id):
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        flash('User not found.', 'error')
        return redirect(safe_redirect_url(url_for('admin_users')))

    db.execute('UPDATE users SET photo_url = NULL WHERE id = ?', (user_id,))
    if user['role'] == 'teacher':
        db.execute('UPDATE faculty SET photo_url = NULL WHERE user_id = ?', (user_id,))
    db.commit()

    if session['user_id'] == user_id:
        session['photo_url'] = None

    flash('User photo removed.', 'success')
    return redirect(safe_redirect_url(url_for('admin_users')))

@app.route('/admin/create-user', methods=['GET', 'POST'])
@admin_required
def admin_create_user():
    if request.method == 'POST':
        form = request.form.to_dict()
        errors = {}
        db = get_db()

        role  = (form.get('role')  or '').strip()
        name  = (form.get('name')  or '').strip()
        email = (form.get('email') or '').strip()
        phone = (form.get('phone') or '').strip()

        if not role:
            errors['role'] = 'Please select a role'
        elif role not in ('teacher', 'admin', 'administrator', 'parent', 'student'):
            errors['role'] = 'Invalid role selected'

        if not name:
            errors['name'] = 'Full name is required'
        elif len(name) < 2:
            errors['name'] = 'Name must be at least 2 characters'
        elif len(name) > 100:
            errors['name'] = 'Name must be at most 100 characters'

        if not email:
            errors['email'] = 'Email is required'
        elif not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            errors['email'] = 'Invalid email format (e.g. user@example.com)'
        elif db.execute('SELECT 1 FROM users WHERE LOWER(email) = LOWER(?)',
                        (email,)).fetchone():
            errors['email'] = 'This email is already registered'

        if not phone:
            errors['phone'] = 'Mobile number is required'
        elif not re.match(r'^[0-9]{10}$', phone):
            errors['phone'] = 'Mobile number must be exactly 10 digits'
        elif db.execute('SELECT 1 FROM users WHERE phone = ?',
                        (phone,)).fetchone():
            errors['phone'] = 'This mobile number is already registered'

        pincode = (form.get('pincode') or '').strip()
        if pincode and not re.match(r'^[0-9]{6}$', pincode):
            errors['pincode'] = 'Pincode must be exactly 6 digits'

        aadhar = (form.get('aadhar') or '').strip()
        if aadhar and not re.match(r'^[0-9]{12}$', aadhar):
            errors['aadhar'] = 'Aadhaar must be exactly 12 digits'

        pan = (form.get('pan') or '').strip()
        if pan and not re.match(r'^[A-Za-z]{5}[0-9]{4}[A-Za-z]$', pan):
            errors['pan'] = 'Invalid PAN format (e.g. ABCDE1234F)'

        for mfield in ('alternate_mobile', 'whatsapp', 'emergency_contact',
                       'father_mobile', 'mother_mobile', 'guardian_mobile',
                       'spouse_mobile'):
            v = (form.get(mfield) or '').strip()
            if v and not re.match(r'^[0-9]{10}$', v):
                errors[mfield] = 'Must be exactly 10 digits'

        for efield in ('father_email', 'mother_email'):
            v = (form.get(efield) or '').strip()
            if v and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
                errors[efield] = 'Invalid email format'

        acct = (form.get('account_number') or '').strip()
        if acct and not re.match(r'^[0-9]{6,20}$', acct):
            errors['account_number'] = 'Account number must be 6-20 digits'

        ifsc = (form.get('ifsc') or '').strip()
        if ifsc and not re.match(r'^[A-Za-z]{4}0[A-Za-z0-9]{6}$', ifsc):
            errors['ifsc'] = 'Invalid IFSC code (e.g. SBIN0001234)'

        if role == 'teacher':
            if not (form.get('qualification') or '').strip():
                errors['qualification'] = 'Qualification is required'
            if not (form.get('subject') or '').strip():
                errors['subject'] = 'Primary Subject is required'

        elif role in ('admin', 'administrator'):
            if not (form.get('designation') or '').strip():
                errors['designation'] = 'Designation is required'
            if not (form.get('department') or '').strip():
                errors['department'] = 'Department is required'

        elif role == 'parent':
            if not (form.get('relation') or '').strip():
                errors['relation'] = 'Relation with child is required'
            if not (form.get('child_name') or '').strip():
                errors['child_name'] = "Child's name is required"
            if not (form.get('child_class') or '').strip():
                errors['child_class'] = "Child's class is required"

        elif role == 'student':
            student_required = {
                'class_name':    'Class is required',
                'section':       'Section is required',
                'father_name':   "Father's name is required",
                'mother_name':   "Mother's name is required",
                'father_mobile': "Father's mobile is required",
                'aadhar':        'Aadhaar is required for student',
            }
            for f, msg in student_required.items():
                if not (form.get(f) or '').strip():
                    errors[f] = msg

        photo_file = request.files.get('photo')
        has_photo = bool(photo_file and photo_file.filename)

        if has_photo and not allowed_file(photo_file.filename):
            errors['photo'] = 'Only JPG / PNG / WEBP / GIF allowed'

        if errors:
            flash(f'Please fix {len(errors)} error{"s" if len(errors)>1 else ""} below.', 'error')
            return render_template(
                'admin_create_user.html',
                form=form, errors=errors,
                active_page='create_user'
            )

        fields = _collect_form_fields(role)

        if role == 'student' and fields.get('class_name'):
            fields['child_class']   = fields['class_name']
            fields['child_section'] = fields.get('section')

        photo_url = save_user_photo(photo_file)
        if photo_url:
            fields['photo_url'] = photo_url

        unique_id = generate_unique_id(role)
        temporary_password = secrets.token_urlsafe(12)
        hashed    = generate_password_hash(temporary_password)

        if role == 'student' and not fields.get('admission_no'):
            fields['admission_no'] = unique_id

        base = {
            'unique_id': unique_id, 'role': role, 'name': name,
            'email': email, 'phone': phone, 'password_hash': hashed,
        }
        base.update(fields)

        cols         = ', '.join(base.keys())
        placeholders = ', '.join(['?'] * len(base))
        try:
            cursor = db.execute(f'INSERT INTO users ({cols}) VALUES ({placeholders})',
                       tuple(base.values()))
            new_user_id = cursor.lastrowid

            if role == 'teacher':
                db.execute('''INSERT INTO faculty (user_id, name, subject, qualification, experience, photo_url, bio) 
                              VALUES (?, ?, ?, ?, ?, ?, ?)''',
                           (new_user_id, name, fields.get('subject') or 'General',
                            fields.get('qualification') or '', fields.get('experience') or '',
                            fields.get('photo_url'), 'Teacher at Residential Shanti Niketan.'))

            db.commit()
        except sqlite3.IntegrityError:
            db.rollback()
            app.logger.exception('User creation failed due to a database constraint')
            flash('This email, phone, or identifier is already in use.', 'error')
            return render_template('admin_create_user.html', form=form,
                                   errors={'_': 'A unique field is already registered.'},
                                   active_page='create_user')
        except Exception:
            db.rollback()
            app.logger.exception('User creation failed')
            flash('Unable to create the user right now. Please try again.', 'error')
            return render_template('admin_create_user.html', form=form,
                                   errors={'_': 'A server error occurred. Please try again.'},
                                   active_page='create_user')

        flash(f'{role.capitalize()} created! ID: {unique_id} | '
              f'Temporary Password: {temporary_password} (share securely; change at first login)', 'success')
        
        # 🚀 NAYA LOGIC: Agar student add hua hai, toh direct Admission Form print page open ho
        if role == 'student':
            return redirect(url_for('admin_print_admission_form', student_id=new_user_id))
            
        return redirect(url_for('admin_users'))

    pre_role = request.args.get('role', '')
    if pre_role and pre_role in ('teacher', 'admin', 'administrator', 'parent', 'student'):
        initial_form = {'role': pre_role}
    else:
        initial_form = {}

    return render_template('admin_create_user.html',
                           form=initial_form, errors={},
                           active_page='create_user')

@app.route('/admin/students/<int:student_id>/print-admission-form')
@admin_required
def admin_print_admission_form(student_id):
    db = get_db()
    student = db.execute("SELECT * FROM users WHERE id=? AND role='student'", (student_id,)).fetchone()
    
    if not student:
        flash('Student not found.', 'error')
        return redirect(url_for('admin_users'))
        
    return render_template('admission_form_print.html', student=student)

# =========================================
# 10.1. API — LIVE EMAIL / PHONE AVAILABILITY
# =========================================
@app.route('/api/check-availability')
@admin_required
def api_check_availability():
    field = request.args.get('field', '')
    value = request.args.get('value', '').strip()
    db = get_db()

    if field == 'email':
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value):
            return jsonify({'available': False, 'error': 'Invalid email format'})
        exists = db.execute(
            'SELECT 1 FROM users WHERE LOWER(email) = LOWER(?)', (value,)
        ).fetchone()
        return jsonify({
            'available': not exists,
            'error': 'This email is already registered' if exists else ''
        })

    if field == 'phone':
        if not re.match(r'^[0-9]{10}$', value):
            return jsonify({'available': False, 'error': 'Must be exactly 10 digits'})
        exists = db.execute(
            'SELECT 1 FROM users WHERE phone = ?', (value,)
        ).fetchone()
        return jsonify({
            'available': not exists,
            'error': 'This mobile number is already registered' if exists else ''
        })

    return jsonify({'available': True, 'error': ''})

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    if user_id == session['user_id']:
        flash('You cannot delete your own account!', 'error')
        return redirect(url_for('admin_users'))
    db = get_db()

    fac_row = db.execute('SELECT id FROM faculty WHERE user_id = ?', (user_id,)).fetchone()
    if fac_row:
        db.execute('DELETE FROM faculty_subject_assignments WHERE faculty_id = ?',
                   (fac_row['id'],))

    db.execute('DELETE FROM users WHERE id = ?', (user_id,))
    db.execute('DELETE FROM faculty WHERE user_id = ?', (user_id,))
    db.commit()
    flash('User deleted.', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/change-role/<int:user_id>', methods=['POST'])
@admin_required
def admin_change_role(user_id):
    new_role = request.form.get('role', 'student')
    if new_role not in ['teacher', 'admin', 'administrator', 'parent', 'student']:
        flash('Invalid role.', 'error')
        return redirect(url_for('admin_users'))

    if user_id == session['user_id']:
        flash('You cannot change your own role!', 'error')
        return redirect(url_for('admin_users'))

    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    db.execute('UPDATE users SET role = ? WHERE id = ?', (new_role, user_id))

    if new_role == 'teacher':
        if not db.execute('SELECT 1 FROM faculty WHERE user_id = ?', (user_id,)).fetchone():
            db.execute('INSERT INTO faculty (user_id, name, subject) VALUES (?, ?, ?)',
                       (user_id, user['name'], user['subject'] or 'General'))
    else:
        fac_row = db.execute('SELECT id FROM faculty WHERE user_id = ?', (user_id,)).fetchone()
        if fac_row:
            db.execute('DELETE FROM faculty_subject_assignments WHERE faculty_id = ?',
                       (fac_row['id'],))
        db.execute('DELETE FROM faculty WHERE user_id = ?', (user_id,))

    db.commit()
    flash('User role updated successfully.', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/reset-password/<int:user_id>', methods=['POST'])
@admin_required
def admin_reset_password(user_id):
    db = get_db()
    user = db.execute('SELECT id FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('admin_users'))
    temporary_password = secrets.token_urlsafe(12)
    db.execute('UPDATE users SET password_hash = ?, force_password_change = 1 WHERE id = ?',
               (generate_password_hash(temporary_password), user_id))
    db.commit()
    flash(f'Password reset. One-time temporary password: {temporary_password}. Share it securely.', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/toggle/<int:user_id>', methods=['POST'])
@admin_required
def admin_toggle_user(user_id):
    if user_id == session['user_id']:
        flash('You cannot deactivate yourself!', 'error')
        return redirect(url_for('admin_users'))

    db = get_db()
    db.execute('UPDATE users SET is_active = CASE WHEN is_active=1 THEN 0 ELSE 1 END WHERE id = ?', (user_id,))
    db.commit()
    flash('User status toggled.', 'success')
    return redirect(url_for('admin_users'))

# === NOTICES ===
@app.route('/admin/notices')
@admin_required
def admin_notices():
    notices = get_all_notices()
    return render_template('admin_notices.html', notices=notices, active_page='notices')

@app.route('/admin/notices/print')
@admin_required
def admin_print_notices():
    db = get_db()

    raw_ids = (request.args.get('ids') or '').strip()
    ids = [int(p) for p in raw_ids.split(',') if p.strip().isdigit()]

    if ids:
        placeholders = ','.join('?' for _ in ids)
        notices = db.execute(
            f"SELECT * FROM notices WHERE id IN ({placeholders}) ORDER BY id DESC",
            tuple(ids)
        ).fetchall()
    else:
        notices = db.execute("SELECT * FROM notices ORDER BY id DESC").fetchall()

    if not notices:
        flash('No notices available to print.', 'error')
        return redirect(url_for('admin_notices'))

    cols = request.args.get('cols', '2')
    if cols not in ('1', '2', '3'):
        cols = '2'

    density = request.args.get('density', 'compact')
    if density not in ('tight', 'compact', 'normal', 'relaxed'):
        density = 'compact'

    cut = request.args.get('cut', 'on')
    if cut not in ('on', 'off'):
        cut = 'on'

    # ---- NEW: Name line toggle ----
    name_line = request.args.get('name_line', 'on')
    if name_line not in ('on', 'off'):
        name_line = 'on'

    repeat_raw = (request.args.get('repeat') or '').strip().lower()
    if repeat_raw == 'auto':
        repeat, initial_copies = 'auto', 1
    elif repeat_raw.isdigit() and 1 <= int(repeat_raw) <= 20:
        repeat, initial_copies = repeat_raw, int(repeat_raw)
    elif not repeat_raw:
        repeat = 'auto' if len(notices) == 1 else '1'
        initial_copies = 1
    else:
        repeat, initial_copies = '1', 1

    return render_template(
        'admin_notices_print.html',
        notices=notices,
        ids=[n['id'] for n in notices],
        cols=cols,
        density=density,
        cut=cut,
        name_line=name_line,
        repeat=repeat,
        initial_copies=initial_copies,
    )
    
@app.route('/admin/notices/edit/<int:nid>', methods=['GET', 'POST'])
@admin_required
def admin_edit_notice(nid):
    """Edit an existing notice — reuses admin_notices.html."""
    db = get_db()
    notice = db.execute('SELECT * FROM notices WHERE id = ?', (nid,)).fetchone()
    if not notice:
        flash('Notice not found.', 'error')
        return redirect(url_for('admin_notices'))

    if request.method == 'POST':
        date        = request.form.get('date', '').strip()
        title       = request.form.get('title', '').strip()
        tag         = request.form.get('tag', '').strip()
        description = request.form.get('description', '').strip()
        target_role = request.form.get('target_role', 'all')

        if not date or not title or not tag:
            flash('Please fill Date, Title, and Tag.', 'error')
            return redirect(url_for('admin_edit_notice', nid=nid))

        if target_role not in ('all', 'teacher', 'parent', 'student'):
            target_role = 'all'

        try:
            db.execute(
                '''UPDATE notices SET date = ?, title = ?, tag = ?,
                   description = ?, target_role = ? WHERE id = ?''',
                (date, title, tag, description, target_role, nid)
            )
            db.commit()
        except Exception:
            db.rollback()
            app.logger.exception('Notice update failed for id=%s', nid)
            flash('Could not update notice. Please try again.', 'error')
            return redirect(url_for('admin_edit_notice', nid=nid))

        flash(f'Notice #{nid} updated successfully!', 'success')
        return redirect(url_for('admin_notices'))

    notices = get_all_notices()
    return render_template(
        'admin_notices.html',
        notices=notices,
        edit_notice=notice,
        active_page='notices'
    )

@app.route('/admin/notices/add', methods=['POST'])
@admin_required
def admin_add_notice():
    date = request.form.get('date', '').strip()
    title = request.form.get('title', '').strip()
    tag = request.form.get('tag', '').strip()
    description = request.form.get('description', '').strip()
    target_role = request.form.get('target_role', 'all')

    if not date or not title or not tag:
        flash('Please fill Date, Title, and Tag.', 'error')
        return redirect(url_for('admin_notices'))

    db = get_db()
    db.execute('INSERT INTO notices (date, title, tag, description, target_role) VALUES (?,?,?,?,?)',
               (date, title, tag, description, target_role))
    db.commit()
    flash('Notice published! It will appear on home page and relevant user profiles.', 'success')
    return redirect(url_for('admin_notices'))

@app.route('/admin/notices/delete/<int:nid>', methods=['POST'])
@admin_required
def admin_delete_notice(nid):
    db = get_db()
    db.execute('DELETE FROM notices WHERE id = ?', (nid,))
    db.commit()
    flash('Notice deleted.', 'success')
    return redirect(url_for('admin_notices'))

# === ATTENDANCE ===
@app.route('/admin/attendance')
@admin_required
def admin_attendance():
    db = get_db()
    role         = request.args.get('role', 'student')
    date         = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    class_filter = request.args.get('class_filter', 'all')
    # If the admin opens Attendance without choosing a subject, automatically
    # show the subject that has the most student attendance records for this date.
    # Teacher student attendance is saved under the teacher's subject, while
    # teacher self-attendance is saved under 'General'. Defaulting to General
    # therefore hid student records on the admin page.
    requested_subject = (request.args.get('subject_filter') or '').strip()
    if requested_subject:
        subject_filter = requested_subject
    else:
        latest_student_subject = db.execute("""
            SELECT a.subject
            FROM attendance AS a
            JOIN users AS u ON u.id = a.user_id
            WHERE a.date = ?
              AND u.role = 'student'
              AND u.is_active = 1
              AND a.subject IS NOT NULL
              AND TRIM(a.subject) != ''
            GROUP BY a.subject
            ORDER BY COUNT(*) DESC, a.subject ASC
            LIMIT 1
        """, (date,)).fetchone()
        subject_filter = latest_student_subject['subject'] if latest_student_subject else 'General'

    query = "SELECT * FROM users WHERE role = ? AND is_active = 1"
    params = [role]
    if role == 'student' and class_filter != 'all':
        query += " AND (class_name = ? OR child_class = ?)"
        params.extend([class_filter, class_filter])
    query += " ORDER BY name"
    users = db.execute(query, tuple(params)).fetchall()

    class_list = []
    if role == 'student':
        rows = db.execute(
            "SELECT DISTINCT COALESCE(class_name, child_class) AS c FROM users "
            "WHERE role='student' AND COALESCE(class_name, child_class) IS NOT NULL "
            "AND COALESCE(class_name, child_class) != '' ORDER BY c"
        ).fetchall()
        class_list = [r['c'] for r in rows if r['c']]

    records = db.execute(
        "SELECT * FROM attendance WHERE date = ? AND subject = ?",
        (date, subject_filter)
    ).fetchall()
    attendance_map = {r['user_id']: r['status'] for r in records}

    user_ids = [u['id'] for u in users]
    present_count = absent_count = leave_count = halfday_count = 0
    for uid in user_ids:
        st = attendance_map.get(uid)
        if st == 'present':    present_count += 1
        elif st == 'absent':   absent_count  += 1
        elif st == 'leave':    leave_count   += 1
        elif st == 'half-day': halfday_count += 1
    marked     = present_count + absent_count + leave_count + halfday_count
    not_marked = len(user_ids) - marked

    overall = {}
    for r in ('student', 'teacher', 'parent'):
        role_ids = [row['id'] for row in db.execute(
            "SELECT id FROM users WHERE role=? AND is_active=1", (r,)
        ).fetchall()]
        if not role_ids:
            overall[r] = {'total': 0, 'present': 0, 'absent': 0,
                          'leave': 0, 'half-day': 0, 'not-marked': 0}
            continue
        ph = ','.join(['?'] * len(role_ids))
        rows = db.execute(
            f"SELECT user_id, status FROM attendance "
            f"WHERE date=? AND subject=? AND user_id IN ({ph})",
            (date, subject_filter, *role_ids)
        ).fetchall()
        m = {row['user_id']: row['status'] for row in rows}
        overall[r] = {
            'total':      len(role_ids),
            'present':    sum(1 for v in m.values() if v == 'present'),
            'absent':     sum(1 for v in m.values() if v == 'absent'),
            'leave':      sum(1 for v in m.values() if v == 'leave'),
            'half-day':   sum(1 for v in m.values() if v == 'half-day'),
            'not-marked': len(role_ids) - len(m),
        }

    subjects = [row['subject'] for row in db.execute(
        "SELECT DISTINCT subject FROM attendance "
        "WHERE subject IS NOT NULL AND subject != '' ORDER BY subject"
    ).fetchall()]
    if 'General' not in subjects:
        subjects.insert(0, 'General')
    if subject_filter not in subjects:
        subjects.insert(0, subject_filter)

    return render_template(
        'admin_attendance.html',
        users=users, role=role, date=date,
        attendance_map=attendance_map,
        class_filter=class_filter, class_list=class_list,
        subject_filter=subject_filter, subjects=subjects,
        present_count=present_count, absent_count=absent_count,
        leave_count=leave_count, halfday_count=halfday_count,
        marked=marked, not_marked=not_marked,
        overall=overall,
        active_page='attendance'
    )

@app.route('/admin/attendance/mark', methods=['POST'])
@admin_required
def admin_mark_attendance():
    date = (request.form.get('date') or datetime.now().strftime('%Y-%m-%d')).strip()
    subject = (request.form.get('subject') or 'General').strip()[:100] or 'General'
    role = (request.form.get('role') or 'student').strip().lower()
    class_filter = (request.form.get('class_filter') or 'all').strip()
    valid_roles = {'student', 'teacher', 'parent'}
    valid_statuses = {'present', 'absent', 'leave', 'half-day'}
    try:
        datetime.strptime(date, '%Y-%m-%d')
    except (TypeError, ValueError):
        flash('Invalid attendance date.', 'error')
        return redirect(url_for('admin_attendance'))
    if role not in valid_roles:
        flash('Invalid attendance role.', 'error')
        return redirect(url_for('admin_attendance', date=date))

    db = get_db()
    updates = []
    for key, raw_status in request.form.items():
        if not key.startswith('status_'):
            continue
        try:
            uid = int(key[len('status_'):])
        except (TypeError, ValueError):
            continue
        status = (raw_status or '').strip().lower()
        if status and status not in valid_statuses:
            flash('Invalid attendance status submitted; no changes were saved.', 'error')
            return redirect(url_for('admin_attendance', date=date, role=role,
                                    class_filter=class_filter, subject_filter=subject))
        target = db.execute(
            "SELECT id FROM users WHERE id=? AND role=? AND is_active=1", (uid, role)
        ).fetchone()
        if not target:
            continue
        if role == 'student' and class_filter != 'all':
            in_class = db.execute(
                "SELECT 1 FROM users WHERE id=? AND role='student' AND (class_name=? OR child_class=?)",
                (uid, class_filter, class_filter)
            ).fetchone()
            if not in_class:
                continue
        updates.append((uid, status))

    try:
        db.execute('BEGIN IMMEDIATE')
        for uid, status in updates:
            existing_rows = db.execute(
                'SELECT id FROM attendance WHERE user_id=? AND date=? AND subject=? ORDER BY id DESC',
                (uid, date, subject)
            ).fetchall()
            if not status:
                if existing_rows:
                    db.execute('DELETE FROM attendance WHERE id=?', (existing_rows[0]['id'],))
            elif existing_rows:
                db.execute('UPDATE attendance SET status=?, marked_by=? WHERE id=?',
                           (status, session['user_id'], existing_rows[0]['id']))
            else:
                db.execute('INSERT INTO attendance (user_id, date, status, subject, marked_by) VALUES (?,?,?,?,?)',
                           (uid, date, status, subject, session['user_id']))
        db.commit()
    except Exception:
        db.rollback()
        app.logger.exception('Admin attendance save failed')
        flash('Attendance could not be saved. Please try again.', 'error')
        return redirect(url_for('admin_attendance', date=date, role=role,
                                class_filter=class_filter, subject_filter=subject))

    flash(f'Attendance marked for {date} ({subject}).', 'success')
    return redirect(url_for('admin_attendance', date=date, role=role,
                            class_filter=class_filter, subject_filter=subject))
    

# --------- Attendance record export route system ---------
@app.route('/admin/attendance/export')
@admin_required
def admin_attendance_export():
    """Professional B&W attendance report — print / save-as-PDF.

    Guarantees:
      • Every enrolled user appears (even with 0 records).
      • Names always render (name → unique_id → '—' fallback).
      • Class-wise grouping in natural school order.
      • Each class group has header + subtotal + grand total.
      • All context vars (school_name, logo, etc.) always defined.
    """
    from collections import OrderedDict

    db = get_db()

    # ---------- 1. Query params ----------
    period = (request.args.get('period') or 'daily').strip().lower()
    if period not in ('daily', 'weekly', 'monthly', 'yearly'):
        period = 'daily'

    role = (request.args.get('role') or 'student').strip().lower()
    if role not in ('student', 'teacher'):
        role = 'student'

    date_str = (request.args.get('date')
                or datetime.now().strftime('%Y-%m-%d')).strip()
    try:
        base_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        base_date = date.today()

    subject = ((request.args.get('subject_filter')
                or request.args.get('subject')
                or 'General').strip()[:100]) or 'General'

    class_filter = (request.args.get('class_filter') or 'all').strip()

    # ---------- 2. Date range ----------
    if period == 'daily':
        start = end = base_date
        period_label = base_date.strftime('%d %B %Y')
        period_sub = 'Daily Attendance Report'
    elif period == 'weekly':
        start = base_date - timedelta(days=base_date.weekday())
        end = start + timedelta(days=6)
        period_label = (f"{start.strftime('%d %b %Y')} — "
                        f"{end.strftime('%d %b %Y')}")
        period_sub = 'Weekly Attendance Report'
    elif period == 'monthly':
        start = base_date.replace(day=1)
        if base_date.month == 12:
            end = (base_date.replace(year=base_date.year + 1,
                                     month=1, day=1)
                   - timedelta(days=1))
        else:
            end = (base_date.replace(month=base_date.month + 1, day=1)
                   - timedelta(days=1))
        period_label = base_date.strftime('%B %Y')
        period_sub = 'Monthly Attendance Report'
    else:  # yearly
        start = base_date.replace(month=1, day=1)
        end = base_date.replace(month=12, day=31)
        period_label = str(base_date.year)
        period_sub = 'Yearly Attendance Report'

    # ---------- 3. Enrolled users ----------
    if role == 'student':
        user_query = ("SELECT * FROM users "
                      "WHERE role = ? AND is_active = 1")
        user_params = [role]
        if class_filter != 'all':
            user_query += " AND (class_name = ? OR child_class = ?)"
            user_params.extend([class_filter, class_filter])
        user_query += (
            " ORDER BY "
            "COALESCE(class_name, child_class, 'Unassigned') COLLATE NOCASE, "
            "name COLLATE NOCASE"
        )
    else:
        user_query = ("SELECT * FROM users "
                      "WHERE role = ? AND is_active = 1 "
                      "ORDER BY name COLLATE NOCASE")
        user_params = [role]

    users = db.execute(user_query, tuple(user_params)).fetchall()

    # ---------- 4. Attendance records ----------
    attendance_records = []
    if users:
        user_ids = [u['id'] for u in users]
        ph = ','.join(['?'] * len(user_ids))
        attendance_records = db.execute(f"""
            SELECT a.id, a.user_id, a.date, a.status, a.subject
            FROM attendance a
            WHERE a.date BETWEEN ? AND ?
              AND a.subject = ?
              AND a.user_id IN ({ph})
            ORDER BY a.date, a.user_id
        """, [start.isoformat(), end.isoformat(), subject, *user_ids]).fetchall()

    # ---------- 5. Per-user summary (seeded for ALL users) ----------
    summary = {
        u['id']: {'present': 0, 'absent': 0, 'leave': 0,
                  'half-day': 0, 'total_marked': 0}
        for u in users
    }
    daily_status = {}

    for rec in attendance_records:
        uid = rec['user_id']
        st  = rec['status']
        if uid in summary and st in ('present', 'absent', 'leave', 'half-day'):
            summary[uid][st] += 1
            summary[uid]['total_marked'] += 1
        if period == 'daily':
            daily_status[uid] = st

    # ---------- 6. Grand totals ----------
    grand_present = sum(s['present']  for s in summary.values())
    grand_absent  = sum(s['absent']   for s in summary.values())
    grand_leave   = sum(s['leave']    for s in summary.values())
    grand_halfday = sum(s['half-day'] for s in summary.values())
    grand_marked  = grand_present + grand_absent + grand_leave + grand_halfday
    overall_pct = (round(((grand_present + 0.5 * grand_halfday)
                          / grand_marked) * 100, 1)
                   if grand_marked else 0.0)

    # ---------- 7. Class-wise grouping ----------
    STANDARD_CLASS_ORDER = [
        'Pre-Nursery', 'Nursery', 'LKG', 'UKG',
        '1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th',
    ]
    _CLASS_RANK = {n.lower(): i for i, n in enumerate(STANDARD_CLASS_ORDER)}

    def _class_sort_key(name):
        return (_CLASS_RANK.get(name.lower(), len(STANDARD_CLASS_ORDER)),
                name.lower())

    raw_groups = OrderedDict()
    for u in users:
        if role == 'student':
            cname = (u['class_name'] or u['child_class'] or 'Unassigned')
            cname = (cname or '').strip() or 'Unassigned'
        else:
            cname = 'All Teachers'
        raw_groups.setdefault(cname, []).append(u)

    grouped = []
    for cname in sorted(raw_groups.keys(), key=_class_sort_key):
        ulist = raw_groups[cname]
        if not ulist:
            continue

        student_display = []
        for u in ulist:
            raw_name = (u['name'] or '').strip()
            uid_val  = (u['unique_id'] or '').strip()
            if role == 'student':
                row_class = (u['class_name']
                             or u['child_class']
                             or 'Unassigned')
                row_class = (row_class or '').strip() or 'Unassigned'
            else:
                row_class = 'All Teachers'
            student_display.append({
                'id':         u['id'],
                'name':       raw_name or uid_val or '—',
                'unique_id':  uid_val or '—',
                'class_name': row_class,
            })

        g_present = sum(summary[u['id']]['present']   for u in ulist)
        g_absent  = sum(summary[u['id']]['absent']    for u in ulist)
        g_leave   = sum(summary[u['id']]['leave']     for u in ulist)
        g_halfday = sum(summary[u['id']]['half-day']  for u in ulist)
        g_marked  = g_present + g_absent + g_leave + g_halfday
        g_pct = (round(((g_present + 0.5 * g_halfday) / g_marked) * 100, 1)
                 if g_marked else 0.0)

        grouped.append({
            'class_name': cname,
            'students':   student_display,
            'count':      len(student_display),
            'present':    g_present,
            'absent':     g_absent,
            'leave':      g_leave,
            'halfday':    g_halfday,
            'marked':     g_marked,
            'pct':        g_pct,
        })

    # ---------- 8. SAFE context vars (school_name / logo) ----------
    # Every value guaranteed non-empty → no UndefinedError possible.
    school_name    = (get_setting('school_name')
                      or 'Residential Shanti Niketan')
    school_address = (get_setting('school_address')
                      or 'Navinagar (Jamui)')

    logo_setting = get_setting('school_logo_url')
    if logo_setting:
        school_logo = logo_setting
    else:
        # Fallback to bundled logo file at static/images/school_logo.png
        school_logo = url_for('static',
                              filename='images/school_logo.png')

    # ---------- 9. Render ----------
    return render_template(
        'admin_attendance_export.html',

        period=period,
        period_label=period_label,
        period_sub=period_sub,
        start=start, end=end, base_date=base_date,

        role=role,
        subject=subject,
        class_filter=class_filter,

        users=users,
        summary=summary,
        daily_status=daily_status,
        grouped=grouped,

        grand_present=grand_present,
        grand_absent=grand_absent,
        grand_leave=grand_leave,
        grand_halfday=grand_halfday,
        grand_marked=grand_marked,
        overall_pct=overall_pct,
        total_users=len(users),

        generated_at=datetime.now().strftime('%d %b %Y, %I:%M %p'),
        school_name=school_name,
        school_address=school_address,
        school_logo=school_logo,
        auto_print=(request.args.get('auto') == '1'),
    )

# === LEAVE REQUESTS ===
@app.route('/admin/leaves')
@admin_required
def admin_leaves():
    db = get_db()
    leaves = db.execute('''SELECT lr.*, u.name as user_name, u.unique_id as user_uid, u.role as user_role
                            FROM leave_requests lr JOIN users u ON lr.user_id = u.id
                            ORDER BY lr.id DESC''').fetchall()
    return render_template('admin_leaves.html', leaves=leaves, active_page='leaves')

@app.route('/admin/leaves/update/<int:lid>', methods=['POST'])
@admin_required
def admin_update_leave(lid):
    status = request.form.get('status', 'pending')
    remarks = request.form.get('remarks', '')
    db = get_db()
    db.execute('UPDATE leave_requests SET status = ?, admin_remarks = ? WHERE id = ?',
               (status, remarks, lid))
    db.commit()
    flash(f'Leave {status}.', 'success')
    return redirect(url_for('admin_leaves'))

# === FEE MANAGEMENT ===
@app.route('/admin/fees')
@admin_required
def admin_fees():
    db = get_db()
    payments = db.execute('''SELECT fp.*, u.name as student_name, u.unique_id as student_uid
                              FROM fee_payments fp JOIN users u ON fp.student_id = u.id
                              ORDER BY fp.id DESC''').fetchall()
    return render_template('admin_fees.html', payments=payments,
                          fee_qr=get_setting('fee_qr_url'),
                          upi_link=get_setting('upi_link'),
                          active_page='fees')

@app.route('/admin/fees/qr', methods=['POST'])
@admin_required
def admin_update_qr():
    upi_link = request.form.get('upi_link', '').strip()
    if upi_link:
        set_setting('upi_link', upi_link)

    qr_file = request.files.get('qr_image')
    if qr_file and qr_file.filename:
        if allowed_file(qr_file.filename):
            ext = qr_file.filename.rsplit('.', 1)[1].lower()
            filename = f"fee_qr_{secrets.token_hex(6)}.{ext}"
            filepath = app.config['UPLOAD_FOLDER'] / filename
            qr_file.save(filepath)
            qr_url = url_for('static', filename=f'uploads/{filename}')
            set_setting('fee_qr_url', qr_url)
            flash('QR image uploaded successfully!', 'success')
        else:
            flash('Invalid file type. Only PNG, JPG, JPEG, GIF, WEBP allowed.', 'error')

    qr_url_input = request.form.get('fee_qr_url', '').strip()
    if qr_url_input:
        set_setting('fee_qr_url', qr_url_input)
        flash('QR URL updated successfully!', 'success')

    if request.form.get('delete_qr') == '1':
        set_setting('fee_qr_url', '')
        flash('QR code removed.', 'success')

    if upi_link:
        flash('UPI link saved successfully!', 'success')

    return redirect(url_for('admin_fees'))

@app.route('/admin/fees/verify/<int:pid>', methods=['POST'])
@admin_required
def admin_verify_fee(pid):
    status = request.form.get('status', 'verified')
    db = get_db()
    db.execute('UPDATE fee_payments SET status = ? WHERE id = ?', (status, pid))
    db.commit()
    flash(f'Payment {status}.', 'success')
    return redirect(url_for('admin_fees'))

# === MESSAGES ===
@app.route('/admin/messages', methods=['GET', 'POST'])
@admin_required
def admin_messages():
    db = get_db()
    if request.method == 'POST':
        to_role = request.form.get('to_role', 'all')
        to_user_id = request.form.get('to_user_id', '')
        subject = request.form.get('subject', '').strip()
        body = request.form.get('body', '').strip()

        if not subject or not body:
            flash('Subject and body required.', 'error')
            return redirect(url_for('admin_messages'))

        try:
            uid = int(to_user_id)
            if not db.execute('SELECT 1 FROM users WHERE id=?', (uid,)).fetchone():
                flash('Invalid recipient.', 'error')
                return redirect(url_for('admin_messages'))
        except (TypeError, ValueError):
            flash('Invalid recipient.', 'error')
            return redirect(url_for('admin_messages'))
        else:
            db.execute('INSERT INTO messages (from_user_id, to_role, subject, body) VALUES (?,?,?,?)',
                       (session['user_id'], to_role, subject, body))
        db.commit()
        flash('Message sent successfully.', 'success')
        return redirect(url_for('admin_messages'))

    sent = db.execute('''SELECT m.*, u.name as from_name FROM messages m
                          JOIN users u ON m.from_user_id = u.id
                          ORDER BY m.id DESC LIMIT 30''').fetchall()
    users_list = db.execute("SELECT id, name, unique_id, role FROM users ORDER BY name").fetchall()
    return render_template('admin_messages.html', sent=sent, users_list=users_list, active_page='messages')

# === ENQUIRIES ===
@app.route('/admin/enquiries')
@admin_required
def admin_enquiries():
    db = get_db()
    kind = request.args.get('kind', 'all')
    if kind != 'all':
        enq = db.execute('SELECT * FROM enquiries WHERE kind = ? ORDER BY id DESC', (kind,)).fetchall()
    else:
        enq = db.execute('SELECT * FROM enquiries ORDER BY id DESC').fetchall()
    return render_template('admin_enquiries.html', enquiries=enq, kind_filter=kind, active_page='enquiries')

@app.route('/admin/enquiries/delete/<int:eid>', methods=['POST'])
@admin_required
def admin_delete_enquiry(eid):
    db = get_db()
    db.execute('DELETE FROM enquiries WHERE id = ?', (eid,))
    db.commit()
    flash('Enquiry deleted.', 'success')
    return redirect(url_for('admin_enquiries'))


# =========================================
# 10.5. ADMIN — CONTENT MANAGEMENT ROUTES
# =========================================

# === FACULTY ===
@app.route('/admin/faculty')
@admin_required
def admin_faculty():
    db = get_db()
    faculty = get_combined_faculty()

    rows = db.execute('''
        SELECT a.*, f.name AS faculty_name
        FROM faculty_subject_assignments a
        JOIN faculty f ON a.faculty_id = f.id
        ORDER BY
            CASE a.day
                WHEN 'Monday'    THEN 1
                WHEN 'Tuesday'   THEN 2
                WHEN 'Wednesday' THEN 3
                WHEN 'Thursday'  THEN 4
                WHEN 'Friday'    THEN 5
                WHEN 'Saturday'  THEN 6
                WHEN 'Sunday'    THEN 7
                WHEN 'All Days'  THEN 8
                ELSE 9
            END,
            a.class_name, COALESCE(a.period, ''), a.id
    ''').fetchall()
    assignments = [dict(r) for r in rows]

    classes = [
        r['class_name'] for r in db.execute(
            "SELECT DISTINCT class_name FROM users "
            "WHERE role='student' AND class_name IS NOT NULL "
            "AND class_name != '' ORDER BY class_name"
        ).fetchall() if r['class_name']
    ]
    subjects = [
        r['subject'] for r in db.execute(
            "SELECT DISTINCT subject FROM users "
            "WHERE role='teacher' AND subject IS NOT NULL "
            "AND subject != '' ORDER BY subject"
        ).fetchall() if r['subject']
    ]

    return render_template(
        'admin_faculty.html',
        faculty=faculty,
        assignments=assignments,
        classes=classes,
        subjects=subjects,
        active_page='faculty'
    )


@app.route('/admin/faculty/assign-subject', methods=['POST'])
@admin_required
def admin_assign_subject():
    faculty_id = (request.form.get('faculty_id') or '').strip()
    class_name = (request.form.get('class_name') or '').strip()
    day        = (request.form.get('day') or '').strip()
    subject    = (request.form.get('subject') or '').strip()
    period     = (request.form.get('period') or '').strip()
    room       = (request.form.get('room') or '').strip()

    if not faculty_id or not class_name or not day or not subject:
        flash('Faculty, Class, Day and Subject are required.', 'error')
        return redirect(url_for('admin_faculty'))

    try:
        faculty_id = int(faculty_id)
    except (TypeError, ValueError):
        flash('Invalid faculty selection.', 'error')
        return redirect(url_for('admin_faculty'))

    db = get_db()
    if not db.execute('SELECT 1 FROM faculty WHERE id = ?', (faculty_id,)).fetchone():
        flash('Selected faculty not found.', 'error')
        return redirect(url_for('admin_faculty'))

    days_to_assign = (
        ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        if day == 'All Days' else [day]
    )

    inserted = 0
    skipped  = 0
    for d in days_to_assign:
        exists = db.execute(
            'SELECT id FROM faculty_subject_assignments '
            'WHERE faculty_id=? AND class_name=? AND day=? AND subject=? '
            'AND COALESCE(period, "") = ?',
            (faculty_id, class_name, d, subject, period)
        ).fetchone()
        if exists:
            skipped += 1
            continue
        db.execute(
            'INSERT INTO faculty_subject_assignments '
            '(faculty_id, class_name, day, subject, period, room) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (faculty_id, class_name, d, subject,
             period or None, room or None)
        )
        inserted += 1

    db.commit()

    if inserted and not skipped:
        flash(f'{inserted} assignment(s) added successfully.', 'success')
    elif inserted and skipped:
        flash(f'{inserted} added, {skipped} skipped (already exist).', 'success')
    else:
        flash('Assignment already exists for the selected day(s).', 'info')

    return redirect(url_for('admin_faculty'))


@app.route('/admin/faculty/assignment/<int:aid>/delete', methods=['POST'])
@admin_required
def admin_delete_assignment(aid):
    db = get_db()
    db.execute('DELETE FROM faculty_subject_assignments WHERE id = ?', (aid,))
    db.commit()
    flash('Assignment removed.', 'success')
    return redirect(url_for('admin_faculty'))


@app.route('/admin/faculty/add', methods=['POST'])
@admin_required
def admin_add_faculty():
    name = request.form.get('name', '').strip()
    subject = request.form.get('subject', '').strip()
    qualification = request.form.get('qualification', '').strip()
    experience = request.form.get('experience', '').strip()
    bio = request.form.get('bio', '').strip()
    display_order = request.form.get('display_order', '0')

    if not name or not subject:
        flash('Name and Subject are required.', 'error')
        return redirect(url_for('admin_faculty'))

    db = get_db()
    db.execute('INSERT INTO faculty (name, subject, qualification, experience, bio, display_order) VALUES (?,?,?,?,?,?)',
               (name, subject, qualification, experience, bio, int(display_order) if display_order else 0))
    db.commit()
    flash(f'Faculty "{name}" added!', 'success')
    return redirect(url_for('admin_faculty'))


@app.route('/admin/faculty/edit/<int:fid>', methods=['GET', 'POST'])
@admin_required
def admin_edit_faculty(fid):
    db = get_db()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        subject = request.form.get('subject', '').strip()
        qualification = request.form.get('qualification', '').strip()
        experience = request.form.get('experience', '').strip()
        bio = request.form.get('bio', '').strip()
        display_order = request.form.get('display_order', '0')

        if not name or not subject:
            flash('Name and Subject are required.', 'error')
            return redirect(url_for('admin_edit_faculty', fid=fid))

        db.execute('''UPDATE faculty SET name = ?, subject = ?, qualification = ?, 
                      experience = ?, bio = ?, display_order = ? WHERE id = ?''',
                   (name, subject, qualification, experience, bio, int(display_order) if display_order else 0, fid))
        db.commit()
        flash('Faculty updated successfully!', 'success')
        return redirect(url_for('admin_faculty'))

    edit_faculty = db.execute('SELECT * FROM faculty WHERE id = ?', (fid,)).fetchone()
    if not edit_faculty:
        flash('Faculty not found.', 'error')
        return redirect(url_for('admin_faculty'))

    faculty = get_combined_faculty()
    return render_template('admin_faculty.html', faculty=faculty, edit_faculty=edit_faculty, active_page='faculty')

@app.route('/admin/faculty/delete/<int:fid>', methods=['POST'])
@admin_required
def admin_delete_faculty(fid):
    db = get_db()
    db.execute('DELETE FROM faculty_subject_assignments WHERE faculty_id = ?', (fid,))
    db.execute('DELETE FROM faculty WHERE id = ?', (fid,))
    db.commit()
    flash('Faculty and their assignments removed.', 'success')
    return redirect(url_for('admin_faculty'))


# === EVENTS (ADMIN) ===
@app.route('/admin/events')
@admin_required
def admin_events():
    db = get_db()
    events = db.execute('SELECT * FROM events ORDER BY event_date DESC').fetchall()
    return render_template(
        'admin_events.html',
        events=events,
        now_date=date.today().isoformat(),   # Added missing info   
        active_page='events'
    )

@app.route('/admin/events/add', methods=['POST'])
@admin_required
def admin_add_event():
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    event_date = request.form.get('event_date', '').strip()
    event_time = request.form.get('event_time', '').strip()
    location = request.form.get('location', '').strip()
    category = request.form.get('category', 'general')
    is_featured = 1 if request.form.get('is_featured') else 0

    if not title or not event_date:
        flash('Title and Date are required.', 'error')
        return redirect(url_for('admin_events'))

    cover_image_url = None
    image_file = request.files.get('cover_image')
    if image_file and image_file.filename:
        if allowed_file(image_file.filename):
            compressed = compress_image(image_file, target_kb=100)
            if compressed:
                filename = f"event_{secrets.token_hex(8)}.jpg"
                images_folder = BASE_DIR / 'static' / 'images'
                images_folder.mkdir(parents=True, exist_ok=True)
                (images_folder / filename).write_bytes(compressed)
                cover_image_url = filename
        else:
            flash('Invalid image type for event cover.', 'error')
            return redirect(url_for('admin_events'))

    db = get_db()
    db.execute(
        'INSERT INTO events '
        '(title, description, event_date, event_time, location, category, is_featured, cover_image_url) '
        'VALUES (?,?,?,?,?,?,?,?)',
        (title, description, event_date, event_time, location, category, is_featured, cover_image_url)
    )
    db.commit()
    flash(f'Event "{title}" published!', 'success')
    return redirect(url_for('admin_events'))

# ---------- Manage Participants ----------
@app.route('/admin/events/<int:eid>/participants', methods=['GET'])
def admin_event_participants(eid):
    event = Event.query.get_or_404(eid)

    q              = request.args.get('q', '')
    class_filter   = request.args.get('class_name', '')
    section_filter = request.args.get('section', '')

    query = Student.query.filter_by(role='student') 
    
    if class_filter:   query = query.filter_by(class_name=class_filter)
    if section_filter: query = query.filter_by(section=section_filter)
    if q:
        like = f'%{q}%'
        query = query.filter(db.or_(
            Student.name.ilike(like),
            Student.roll_no.ilike(like),
            Student.admission_no.ilike(like),
        ))

    students        = query.order_by(Student.class_name, Student.section, Student.roll_no).all()
    participant_ids = {p.student_id for p in event.participants}

    classes  = [type('X', (), {'class_name': c[0]}) for c in
                db.session.query(Student.class_name).filter_by(role='student').distinct().all() if c[0]]
    sections = [type('X', (), {'section': s[0]}) for s in
                db.session.query(Student.section).filter_by(role='student').distinct().all() if s[0]]

    return render_template('admin_event_participants.html',
                           event=event, students=students,
                           participant_ids=participant_ids,
                           classes=classes, sections=sections,
                           class_filter=class_filter,
                           section_filter=section_filter, search=q)

@app.route('/admin/events/<int:eid>/participants', methods=['POST'])
def admin_event_participants_save(eid):
    event  = Event.query.get_or_404(eid)
    action = request.form.get('action', 'add')
    sids   = [int(x) for x in request.form.getlist('student_ids') if x.isdigit()]

    if action == 'add' and sids:
        valid_student_ids = {s.id for s in Student.query.filter(Student.id.in_(sids), Student.role == 'student').all()}
        
        existing = {p.student_id for p in EventParticipant.query
                    .filter_by(event_id=eid)
                    .filter(EventParticipant.student_id.in_(valid_student_ids)).all()}
        
        added_count = 0
        for sid in valid_student_ids:
            if sid not in existing:
                db.session.add(EventParticipant(event_id=eid, student_id=sid))
                added_count += 1
                
        db.session.commit()
        flash(f'{added_count} participant(s) added.', 'success')

    elif action == 'remove' and sids:
        EventParticipant.query.filter_by(event_id=eid) \
            .filter(EventParticipant.student_id.in_(sids)) \
            .delete(synchronize_session=False)
        db.session.commit()
        flash(f'{len(sids)} participant(s) removed.', 'success')

    return redirect(url_for('admin_event_participants', eid=eid,
                            class_name=request.form.get('class_name', ''),
                            section=request.form.get('section', ''),
                            q=request.form.get('q', '')))

@app.route('/admin/events/edit/<int:eid>', methods=['GET', 'POST'])
@admin_required
def admin_edit_event(eid):
    db = get_db()
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        event_date = request.form.get('event_date', '').strip()
        event_time = request.form.get('event_time', '').strip()
        location = request.form.get('location', '').strip()
        category = request.form.get('category', 'general')
        is_featured = 1 if request.form.get('is_featured') else 0

        if not title or not event_date:
            flash('Title and Date are required.', 'error')
            return redirect(url_for('admin_edit_event', eid=eid))

        db.execute(
            'UPDATE events SET title=?, description=?, event_date=?, '
            'event_time=?, location=?, category=?, is_featured=? WHERE id=?',
            (title, description, event_date, event_time, location, category, is_featured, eid)
        )
        db.commit()
        flash('Event updated successfully!', 'success')
        return redirect(url_for('admin_events'))

    event = db.execute('SELECT * FROM events WHERE id = ?', (eid,)).fetchone()
    if not event:
        flash('Event not found.', 'error')
        return redirect(url_for('admin_events'))

    events = db.execute('SELECT * FROM events ORDER BY event_date DESC').fetchall()
    return render_template(
        'admin_events.html',
        events=events, edit_event=event,
        now_date=date.today().isoformat(),
        active_page='events'
    )

@app.route('/admin/events/delete/<int:eid>', methods=['POST'])
@admin_required
def admin_delete_event(eid):
    db = get_db()
    
    try:
        db.execute('DELETE FROM event_participants WHERE event_id = ?', (eid,))
        db.execute('DELETE FROM event_certificates WHERE event_id = ?', (eid,))
        db.execute('DELETE FROM events WHERE id = ?', (eid,))
        
        db.commit()
        flash('Event and related data deleted successfully.', 'success')
        
    except Exception:
        db.rollback()
        app.logger.exception(f"Error deleting event {eid}")
        flash('Failed to delete the event. Please check server logs.', 'error')
        
    return redirect(url_for('admin_events'))

# =========================================
# EVENT CERTIFICATES — ADMIN
# =========================================
@app.route('/admin/events/<int:eid>/certificates')
def admin_event_certificates(eid):
    event = Event.query.get_or_404(eid)

    q              = request.args.get('q', '')
    class_filter   = request.args.get('class_name', '')
    section_filter = request.args.get('section', '')

    query = (Student.query
             .filter(Student.role == 'student') 
             .join(EventParticipant, EventParticipant.student_id == Student.id)
             .filter(EventParticipant.event_id == eid))

    if class_filter:   query = query.filter(Student.class_name == class_filter)
    if section_filter: query = query.filter(Student.section    == section_filter)
    if q:
        like = f'%{q}%'
        query = query.filter(db.or_(
            Student.name.ilike(like),
            Student.roll_no.ilike(like),
            Student.admission_no.ilike(like),
        ))

    students   = query.order_by(Student.class_name, Student.section, Student.roll_no).all()
    issued_map = {c.student_id: c for c in
                  Certificate.query.filter_by(event_id=eid).all()}

    classes = [type('X', (), {'class_name': c[0]}) for c in
               db.session.query(Student.class_name)
               .filter(Student.role == 'student')
               .join(EventParticipant, EventParticipant.student_id == Student.id)
               .filter(EventParticipant.event_id == eid).distinct().all() if c[0]]
               
    sections = [type('X', (), {'section': s[0]}) for s in
                db.session.query(Student.section)
                .filter(Student.role == 'student')
                .join(EventParticipant, EventParticipant.student_id == Student.id)
                .filter(EventParticipant.event_id == eid).distinct().all() if s[0]]

    return render_template('admin_event_certificates.html',
                           event=event, students=students,
                           issued_map=issued_map, classes=classes, sections=sections,
                           class_filter=class_filter,
                           section_filter=section_filter, search=q)

@app.route('/admin/events/<int:eid>/certificates/print-all')
@admin_required
def admin_print_all_event_certificates(eid):
    """Render all issued certificates for an event on a single printable page."""
    db = get_db()
    event = db.execute('SELECT * FROM events WHERE id = ?', (eid,)).fetchone()
    if not event:
        flash('Event not found.', 'error')
        return redirect(url_for('admin_events'))

    certs = db.execute('''
        SELECT ec.id, ec.certificate_type, ec.position, ec.issued_at,
               u.name AS student_name, u.unique_id,
               COALESCE(u.class_name, u.child_class) AS class_name,
               u.section, u.roll_no, u.admission_no
        FROM event_certificates ec
        JOIN users u ON ec.student_id = u.id
        WHERE ec.event_id = ?
        ORDER BY u.name
    ''', (eid,)).fetchall()

    if not certs:
        flash('No certificates issued yet for this event.', 'error')
        return redirect(url_for('admin_event_certificates', eid=eid))

    return render_template(
        'event_certificates_bulk_print.html',
        event=event,
        certs=certs,
        school_name=get_setting('school_name') or 'RESIDENTIAL SHANTI NIKETAN'
    )

@app.route('/admin/events/<int:eid>/certificates/issue', methods=['POST'])
def admin_issue_event_certificates(eid):
    event = Event.query.get_or_404(eid)
    student_ids = [int(x) for x in request.form.getlist('student_ids') if x.isdigit()]

    if not student_ids:
        flash('Please select at least one student.', 'warning')
    else:
        participant_ids = {p.student_id for p in event.participants}
        skipped = 0

        for sid in student_ids:
            if sid not in participant_ids:
                skipped += 1
                continue   # non-participant — skip silently

            cert_type = request.form.get(f'certificate_type_{sid}', 'participation')
            position  = (request.form.get(f'position_{sid}') or '').strip() or None

            cert = Certificate.query.filter_by(event_id=eid, student_id=sid).first()
            if cert:
                cert.certificate_type = cert_type
                cert.position = position
            else:
                db.session.add(Certificate(
                    event_id=eid, student_id=sid,
                    certificate_type=cert_type, position=position))
        db.session.commit()

        msg = 'Certificates generated / updated.'
        if skipped:
            msg += f' ({skipped} non-participant student(s) skipped.)'
        flash(msg, 'success' if not skipped else 'warning')

    # ✅ redirect WITH filters — page reset nahi hoga
    return redirect(url_for(
        'admin_event_certificates', eid=eid,
        class_name=request.form.get('class_name', ''),
        section=request.form.get('section', ''),
        q=request.form.get('q', ''),
    ))


@app.route('/event-certificates/<int:certificate_id>')
@login_required
def event_certificate(certificate_id):
    db = get_db()
    
    # 🚀 Yahan ec.event_id add kiya gaya hai
    cert = db.execute('''
        SELECT ec.id, ec.event_id, ec.certificate_type, ec.position, ec.issued_at,
               e.title AS event_title, e.event_date, e.location, e.category,
               u.name AS student_name, u.unique_id,
               COALESCE(u.class_name, u.child_class) AS class_name,
               u.section, u.roll_no, u.admission_no
        FROM event_certificates ec
        JOIN events e ON ec.event_id = e.id
        JOIN users  u ON ec.student_id = u.id
        WHERE ec.id = ?
    ''', (certificate_id,)).fetchone()

    if not cert:
        flash('Certificate not found.', 'error')
        return redirect(url_for('admin_events'))

    # 🚀 Event ki details fetch karein (cover_image ke liye)
    event = db.execute('SELECT * FROM events WHERE id = ?', (cert['event_id'],)).fetchone()

    # Access control
    role = session.get('user_role')
    if role not in ('admin', 'administrator'):
        current = get_user_by_id(session['user_id'])
        allowed = False
        if current and current['role'] == 'student' and current['name'] == cert['student_name']:
            allowed = True
        elif current and current['role'] == 'parent':
            child = get_parent_child(db, current)
            if child and child['name'] == cert['student_name']:
                allowed = True
        if not allowed:
            flash('You are not allowed to view this certificate.', 'error')
            return redirect(url_for('user_dashboard'))

    # 🚀 Template me event=event pass karein
    return render_template(
        'event_certificate_print.html',
        cert=cert,
        event=event, 
        school_name=get_setting('school_name') or 'RESIDENTIAL SHANTI NIKETAN'
    )

# === GALLERY ===
@app.route('/admin/gallery')
@admin_required
def admin_gallery():
    db = get_db()
    images = db.execute('SELECT * FROM gallery ORDER BY display_order, id').fetchall()
    return render_template('admin_gallery.html', images=images, active_page='gallery')

@app.route('/admin/gallery/add', methods=['POST'])
@admin_required
def admin_add_gallery():
    title = request.form.get('title', '').strip()
    category = request.form.get('category', 'campus')
    display_order = request.form.get('display_order', '0')
    image_url = request.form.get('image_url', '').strip()

    image_file = request.files.get('image_file')
    if image_file and image_file.filename:
        if allowed_file(image_file.filename):
            compressed = compress_image(image_file, target_kb=45)
            if compressed is None:
                flash('Image process nahi ho payi. Doosri image try karein.', 'error')
                return redirect(url_for('admin_gallery'))
            filename = f"gallery_{secrets.token_hex(6)}.jpg"
            images_folder = BASE_DIR / 'static' / 'images'
            images_folder.mkdir(parents=True, exist_ok=True)
            (images_folder / filename).write_bytes(compressed)
            image_url = filename
        else:
            flash('Invalid image type.', 'error')
            return redirect(url_for('admin_gallery'))

    if not title or not image_url:
        flash('Title and Image are required.', 'error')
        return redirect(url_for('admin_gallery'))

    db = get_db()
    db.execute('INSERT INTO gallery (title, image_url, category, display_order) VALUES (?,?,?,?)',
               (title, image_url, category, int(display_order) if display_order else 0))
    db.commit()
    flash(f'Photo "{title}" added!', 'success')
    return redirect(url_for('admin_gallery'))

@app.route('/admin/gallery/delete/<int:gid>', methods=['POST'])
@admin_required
def admin_delete_gallery(gid):
    db = get_db()
    db.execute('DELETE FROM gallery WHERE id = ?', (gid,))
    db.commit()
    flash('Photo removed.', 'success')
    return redirect(url_for('admin_gallery'))


# === ACHIEVEMENTS ===
@app.route('/admin/achievements')
@admin_required
def admin_achievements():
    db = get_db()
    achievements = db.execute('SELECT * FROM achievements ORDER BY id DESC').fetchall()
    return render_template('admin_achievements.html', achievements=achievements, active_page='achievements')

@app.route('/admin/achievements/add', methods=['POST'])
@admin_required
def admin_add_achievement():
    student_name = request.form.get('student_name', '').strip()
    class_name = request.form.get('class_name', '').strip()
    achievement = request.form.get('achievement', '').strip()
    year = request.form.get('year', '').strip()
    category = request.form.get('category', 'academic')

    if not student_name or not achievement:
        flash('Student name and Achievement required.', 'error')
        return redirect(url_for('admin_achievements'))

    db = get_db()
    db.execute('INSERT INTO achievements (student_name, class_name, achievement, year, category) VALUES (?,?,?,?,?)',
               (student_name, class_name, achievement, year, category))
    db.commit()
    flash(f'Achievement added for {student_name}!', 'success')
    return redirect(url_for('admin_achievements'))

@app.route('/admin/achievements/delete/<int:aid>', methods=['POST'])
@admin_required
def admin_delete_achievement(aid):
    db = get_db()
    db.execute('DELETE FROM achievements WHERE id = ?', (aid,))
    db.commit()
    flash('Achievement deleted.', 'success')
    return redirect(url_for('admin_achievements'))


# === TESTIMONIALS ===
@app.route('/admin/testimonials')
@admin_required
def admin_testimonials():
    db = get_db()
    testimonials = db.execute('SELECT * FROM testimonials ORDER BY id DESC').fetchall()
    return render_template('admin_testimonials.html', testimonials=testimonials, active_page='testimonials')

@app.route('/admin/testimonials/add', methods=['POST'])
@admin_required
def admin_add_testimonial():
    author_name = request.form.get('author_name', '').strip()
    author_role = request.form.get('author_role', 'Parent')
    message = request.form.get('message', '').strip()
    rating = request.form.get('rating', '5')

    if not author_name or not message:
        flash('Name and Message required.', 'error')
        return redirect(url_for('admin_testimonials'))

    db = get_db()
    db.execute('INSERT INTO testimonials (author_name, author_role, message, rating) VALUES (?,?,?,?)',
               (author_name, author_role, message, int(rating)))
    db.commit()
    flash(f'Testimonial from {author_name} added!', 'success')
    return redirect(url_for('admin_testimonials'))

@app.route('/admin/testimonials/delete/<int:tid>', methods=['POST'])
@admin_required
def admin_delete_testimonial(tid):
    db = get_db()
    db.execute('DELETE FROM testimonials WHERE id = ?', (tid,))
    db.commit()
    flash('Testimonial removed.', 'success')
    return redirect(url_for('admin_testimonials'))


# === FAQ ===
@app.route('/admin/faq')
@admin_required
def admin_faq():
    db = get_db()
    faqs = db.execute('SELECT * FROM faq ORDER BY display_order, id').fetchall()
    return render_template('admin_faq.html', faqs=faqs, active_page='faq')

@app.route('/admin/faq/add', methods=['POST'])
@admin_required
def admin_add_faq():
    question = request.form.get('question', '').strip()
    answer = request.form.get('answer', '').strip()
    display_order = request.form.get('display_order', '0')

    if not question or not answer:
        flash('Question and Answer required.', 'error')
        return redirect(url_for('admin_faq'))

    db = get_db()
    db.execute('INSERT INTO faq (question, answer, display_order) VALUES (?,?,?)',
               (question, answer, int(display_order) if display_order else 0))
    db.commit()
    flash('FAQ added!', 'success')
    return redirect(url_for('admin_faq'))

@app.route('/admin/faq/delete/<int:fid>', methods=['POST'])
@admin_required
def admin_delete_faq(fid):
    db = get_db()
    db.execute('DELETE FROM faq WHERE id = ?', (fid,))
    db.commit()
    flash('FAQ deleted.', 'success')
    return redirect(url_for('admin_faq'))


# =========================================
# 10.6. ADMIN — HOMEWORK MANAGEMENT
# =========================================
@app.route('/admin/homework')
@admin_required
def admin_homework():
    db = get_db()
    homework = db.execute(
        'SELECT h.*, u.name as assigned_by_name '
        'FROM homework h LEFT JOIN users u ON h.assigned_by = u.id '
        'ORDER BY h.due_date DESC, h.id DESC'
    ).fetchall()
    return render_template('admin_homework.html',
                          homework=homework, active_page='homework')


@app.route('/admin/homework/add', methods=['POST'])
@admin_required
def admin_add_homework():
    class_name  = request.form.get('class_name', '').strip()
    subject     = request.form.get('subject', '').strip()
    title       = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    due_date    = request.form.get('due_date', '').strip()

    if not class_name or not subject or not title:
        flash('Class, Subject, and Title are required.', 'error')
        return redirect(url_for('admin_homework'))

    db = get_db()
    db.execute('''INSERT INTO homework
                  (class_name, subject, title, description, due_date, assigned_by)
                  VALUES (?, ?, ?, ?, ?, ?)''',
               (class_name, subject, title, description,
                due_date or None, session['user_id']))
    db.commit()
    flash(f'Homework assigned to {class_name}.', 'success')
    return redirect(url_for('admin_homework'))


@app.route('/admin/homework/delete/<int:hid>', methods=['POST'])
@admin_required
def admin_delete_homework(hid):
    db = get_db()
    db.execute('DELETE FROM homework WHERE id = ?', (hid,))
    db.commit()
    flash('Homework deleted.', 'success')
    return redirect(url_for('admin_homework'))


# =========================================
# TEACHER — MARK OWN & CLASSROOM ATTENDANCE
# =========================================
@app.route('/teacher/attendance', methods=['GET', 'POST'])
@login_required
def teacher_attendance():
    """
    Teacher self-attendance and class attendance.

    POST processing is transactional. Student IDs and status values are
    validated before writing, so malformed form data cannot create attendance
    for unrelated users.
    """
    user = get_user_by_id(session['user_id'])
    if not user or user['role'] not in ('teacher', 'admin', 'administrator'):
        flash('Only teachers can access this page.', 'error')
        return redirect(url_for('user_dashboard'))

    db = get_db()

    date = (
        request.args.get('date')
        or request.form.get('date')
        or datetime.now().strftime('%Y-%m-%d')
    )
    subject = (
        request.args.get('subject')
        or request.form.get('subject')
        or (user['subject'] or 'General')
    )
    selected_class = (
        request.args.get('class_filter')
        or request.form.get('class_filter')
        or 'all'
    )

    # Validate date and normalize filter values.
    try:
        datetime.strptime(date, '%Y-%m-%d')
    except (TypeError, ValueError):
        date = datetime.now().strftime('%Y-%m-%d')
        flash('Invalid attendance date. Today\'s date has been selected.', 'error')

    subject = str(subject).strip()[:100] or 'General'
    selected_class = str(selected_class).strip() or 'all'

    raw_classes = user['classes_assigned'] or ''
    assigned_classes = [c.strip() for c in raw_classes.split(',') if c.strip()]

    # Build the same student list for GET display and POST validation.
    # Teachers are restricted to exact assigned classes; administrators retain full access.
    is_admin_attendance = user['role'] in ('admin', 'administrator')
    if not is_admin_attendance and selected_class != 'all' and selected_class not in assigned_classes:
        flash('You are not assigned to this class.', 'error')
        return redirect(url_for('teacher_attendance', class_filter='all'))

    student_query = "SELECT * FROM users WHERE role='student' AND is_active=1"
    student_params = []
    if selected_class != 'all':
        student_query += " AND (class_name = ? OR child_class = ?)"
        student_params.extend([selected_class, selected_class])
    elif not is_admin_attendance:
        if assigned_classes:
            placeholders = ','.join('?' for _ in assigned_classes)
            student_query += f" AND (class_name IN ({placeholders}) OR child_class IN ({placeholders}))"
            student_params.extend(assigned_classes)
            student_params.extend(assigned_classes)
        else:
            student_query += " AND 1 = 0"

    student_query += " ORDER BY COALESCE(class_name, child_class), name"
    students = db.execute(student_query, tuple(student_params)).fetchall()
    allowed_student_ids = {int(student['id']) for student in students}

    if request.method == 'POST':
        valid_statuses = {'present', 'absent', 'leave', 'half-day'}
        saved_count = 0

        # Collect only valid student attendance fields.
        submitted_statuses = []
        for key, value in request.form.items():
            if not key.startswith('status_'):
                continue

            try:
                student_id = int(key[len('status_'):])
            except (TypeError, ValueError):
                continue

            # A submitted ID must belong to the currently displayed student set.
            if student_id not in allowed_student_ids:
                continue

            status = (value or '').strip().lower()
            if status and status not in valid_statuses:
                continue

            submitted_statuses.append((student_id, status))

        self_status = (request.form.get('teacher_self_status') or '').strip().lower()
        if self_status not in valid_statuses:
            self_status = None

        try:
            # One atomic transaction: either all attendance writes succeed or none do.
            db.execute('BEGIN IMMEDIATE')

            if self_status:
                existing_self = db.execute(
                    "SELECT id FROM attendance "
                    "WHERE user_id=? AND date=? AND subject='General' "
                    "ORDER BY id DESC LIMIT 1",
                    (user['id'], date)
                ).fetchone()

                if existing_self:
                    db.execute(
                        'UPDATE attendance SET status=?, marked_by=? WHERE id=?',
                        (self_status, user['id'], existing_self['id'])
                    )
                else:
                    db.execute(
                        "INSERT INTO attendance "
                        "(user_id, date, status, subject, marked_by) "
                        "VALUES (?, ?, ?, 'General', ?)",
                        (user['id'], date, self_status, user['id'])
                    )

            for student_id, status in submitted_statuses:
                existing = db.execute(
                    "SELECT id FROM attendance "
                    "WHERE user_id=? AND date=? AND subject=? "
                    "ORDER BY id DESC LIMIT 1",
                    (student_id, date, subject)
                ).fetchone()

                if not status:
                    # Keep the original clear/toggle-off behavior.
                    if existing:
                        db.execute(
                            'DELETE FROM attendance WHERE id=?',
                            (existing['id'],)
                        )
                    continue

                if existing:
                    db.execute(
                        'UPDATE attendance SET status=?, marked_by=? WHERE id=?',
                        (status, user['id'], existing['id'])
                    )
                else:
                    db.execute(
                        'INSERT INTO attendance '
                        '(user_id, date, status, subject, marked_by) '
                        'VALUES (?, ?, ?, ?, ?)',
                        (student_id, date, status, subject, user['id'])
                    )

                saved_count += 1

            db.commit()

        except Exception:
            db.rollback()
            app.logger.exception(
                "Attendance save failed for teacher_id=%s date=%s subject=%s",
                user['id'], date, subject
            )
            flash('Attendance could not be saved. Please try again.', 'error')
            return redirect(url_for(
                'teacher_attendance',
                date=date,
                subject=subject,
                class_filter=selected_class
            ))

        if saved_count:
            flash(
                f'Attendance saved successfully for {saved_count} student(s) '
                f'on {date} ({subject}).',
                'success'
            )
        else:
            flash(
                f'No student attendance changes were received for {date} ({subject}). '
                'Please mark students and try again.',
                'warning'
            )

        return redirect(url_for(
            'teacher_attendance',
            date=date,
            subject=subject,
            class_filter=selected_class
        ))

    self_rec = db.execute(
        "SELECT status FROM attendance "
        "WHERE user_id=? AND date=? AND subject='General' "
        "ORDER BY id DESC LIMIT 1",
        (user['id'], date)
    ).fetchone()
    self_status = self_rec['status'] if self_rec else 'not-marked'

    student_att_map = {}
    if students:
        student_ids = [int(student['id']) for student in students]
        placeholders = ','.join(['?'] * len(student_ids))
        attendance_rows = db.execute(
            f"SELECT user_id, status FROM attendance "
            f"WHERE date=? AND subject=? AND user_id IN ({placeholders})",
            (date, subject, *student_ids)
        ).fetchall()
        student_att_map = {
            row['user_id']: row['status'] for row in attendance_rows
        }

    class_rows = db.execute(
        "SELECT DISTINCT COALESCE(class_name, child_class) AS c FROM users "
        "WHERE role='student' "
        "AND COALESCE(class_name, child_class) IS NOT NULL "
        "AND COALESCE(class_name, child_class) != '' ORDER BY c"
    ).fetchall()
    class_list = [row['c'] for row in class_rows if row['c']]
    if user['role'] == 'teacher':
        class_list = [cls for cls in class_list if cls in assigned_classes]

    subject_rows = [
        row['subject'] for row in db.execute(
            "SELECT DISTINCT subject FROM attendance "
            "WHERE subject IS NOT NULL AND subject != '' ORDER BY subject"
        ).fetchall()
    ]
    subjects = []
    if user['subject'] and user['subject'] not in subject_rows:
        subjects.append(user['subject'])
    subjects.extend(subject_rows or ['General'])
    if subject not in subjects:
        subjects.insert(0, subject)

    return render_template(
        'teacher_attendance.html',
        user=user,
        date=date,
        subject=subject,
        selected_class=selected_class,
        assigned_classes=assigned_classes,
        class_list=class_list,
        subjects=subjects,
        students=students,
        student_att_map=student_att_map,
        self_status=self_status,
        total_students=len(students)
    )


# =========================================
# TEACHER — HOMEWORK MANAGEMENT
# =========================================
@app.route('/teacher/homework', methods=['GET'])
@login_required
def teacher_homework():
    user = get_user_by_id(session['user_id'])
    if not user or user['role'] not in ('teacher', 'admin', 'administrator'):
        flash('Only teachers can access this page.', 'error')
        return redirect(url_for('user_dashboard'))

    db = get_db()

    raw_classes = user['classes_assigned'] or ''
    assigned_classes = [c.strip() for c in raw_classes.split(',') if c.strip()]

    selected_class = request.args.get('class_filter', 'all')
    search_q = (request.args.get('q') or '').strip().lower()

    query = '''
        SELECT h.*, u.name AS assigned_by_name, u.role AS assigner_role
        FROM homework h
        LEFT JOIN users u ON h.assigned_by = u.id
        WHERE 1=1
    '''
    params = []

    if assigned_classes:
        ors = []
        for c in assigned_classes:
            ors.append("h.class_name = ?")
            params.append(c)
        query += " AND (" + " OR ".join(ors) + " OR h.assigned_by = ?)"
        params.append(user['id'])
    else:
        query += " AND h.assigned_by = ?"
        params.append(user['id'])

    if selected_class != 'all':
        query += " AND h.class_name = ?"
        params.append(selected_class)

    query += " ORDER BY h.id DESC"
    all_homework = db.execute(query, tuple(params)).fetchall()

    if search_q:
        all_homework = [
            h for h in all_homework
            if search_q in (h['title'] or '').lower()
            or search_q in (h['subject'] or '').lower()
            or search_q in (h['class_name'] or '').lower()
            or search_q in (h['description'] or '').lower()
        ]

    class_set = set(assigned_classes)
    for h in all_homework:
        if h['class_name']:
            class_set.add(h['class_name'])
    class_list = sorted(class_set)

    subjects = []
    if user['subject']:
        subjects.append(user['subject'])
    for h in all_homework:
        if h['subject'] and h['subject'] not in subjects:
            subjects.append(h['subject'])

    my_count = sum(1 for h in all_homework if h['assigned_by'] == user['id'])
    stats = {
        'total':   len(all_homework),
        'mine':    my_count,
        'classes': len(set(h['class_name'] for h in all_homework)),
    }

    return render_template(
        'teacher_homework.html',
        user=user,
        homework_list=all_homework,
        assigned_classes=assigned_classes,
        class_list=class_list,
        subjects=subjects,
        selected_class=selected_class,
        search_q=search_q,
        stats=stats
    )

# =========================================
# QUESTION PAPER GENERATOR ROUTES (Teacher & Admin)
# =========================================
@app.route('/teacher/question-papers')
@app.route('/question-papers')
@login_required
def teacher_question_papers():
    """List papers: teachers see their own; admins see all."""
    user = get_user_by_id(session.get('user_id'))
    if not user or user['role'] not in ('teacher', 'admin', 'administrator'):
        flash('Access denied.', 'error')
        return redirect(url_for('user_dashboard'))

    db = get_db()
    is_admin = user['role'] in ('admin', 'administrator')

    if is_admin:
        papers = db.execute("""
            SELECT p.*, u.name AS teacher_name, u.unique_id AS teacher_uid,
                   COUNT(q.id) AS question_count
            FROM exam_papers p
            LEFT JOIN users u ON u.id = p.teacher_id
            LEFT JOIN exam_questions q ON q.paper_id = p.id
            GROUP BY p.id
            ORDER BY p.id DESC
        """).fetchall()
    else:
        papers = db.execute("""
            SELECT p.*, COUNT(q.id) AS question_count
            FROM exam_papers p
            LEFT JOIN exam_questions q ON q.paper_id = p.id
            WHERE p.teacher_id = ?
            GROUP BY p.id
            ORDER BY p.id DESC
        """, (user['id'],)).fetchall()

    # 🚀 Dropdown ke liye saari standard classes nikalain
    class_list = get_all_classes(db)

    return render_template(
        'teacher_question_papers.html',
        user=user,
        papers=papers,
        is_admin=is_admin,
        class_list=class_list  # Naya variable pass kiya
    )

# =========================================
# QUESTION PAPER GENERATOR — CLASS-WISE SUBJECT SELECTION
# =========================================

def get_question_paper_classes(db, user):
    """
    Admin: Standard + Dynamic classes.
    Teacher: Assigned classes + Dynamic classes.
    """
    role = user['role']
    
    if role in ('admin', 'administrator'):
        return get_all_classes(db)  # 🚀 Saari classes (Pre-Nursery se 8th tak) return karega
    else:
        classes = set()
        # Teacher ke directly assigned classes
        raw_classes = user['classes_assigned'] or ''
        classes.update(
            cls.strip()
            for cls in raw_classes.split(',')
            if cls.strip()
        )
        # Faculty subject assignments se additional classes
        faculty = db.execute("SELECT id FROM faculty WHERE user_id = ? LIMIT 1", (user['id'],)).fetchone()
        if faculty:
            rows = db.execute("SELECT DISTINCT class_name FROM faculty_subject_assignments WHERE faculty_id = ? AND TRIM(class_name) != ''", (faculty['id'],)).fetchall()
            classes.update(row['class_name'].strip() for row in rows)
            
        # 🚀 Agar koi teacher ki class assigned nahi hai, toh usko standard classes show karo (optional)
        if not classes:
            return get_all_classes(db)
            
        return sorted(classes)


def get_question_paper_subjects(db, class_name):
    """Selected class ke registered subjects return karta hai."""
    return db.execute("""
        SELECT subject_name, MAX(max_marks) AS max_marks
        FROM subjects
        WHERE class_name = ?
          AND TRIM(subject_name) != ''
        GROUP BY subject_name
        ORDER BY MIN(display_order), subject_name
    """, (class_name,)).fetchall()


@app.route('/api/question-papers/subjects')
@login_required
def question_paper_subjects_api():
    """AJAX API: selected class ke subjects load karna."""

    user = get_user_by_id(session.get('user_id'))

    if not user or user['role'] not in (
        'teacher', 'admin', 'administrator'
    ):
        return jsonify({
            'success': False,
            'message': 'Access denied.',
            'subjects': []
        }), 403

    class_name = request.args.get('class_name', '').strip()

    if not class_name:
        return jsonify({
            'success': False,
            'message': 'Please select a class.',
            'subjects': []
        }), 400

    db = get_db()

    allowed_classes = get_question_paper_classes(db, user)

    if class_name not in allowed_classes:
        return jsonify({
            'success': False,
            'message': 'You are not allowed to access this class.',
            'subjects': []
        }), 403

    subjects = get_question_paper_subjects(db, class_name)

    return jsonify({
        'success': True,
        'subjects': [
            {
                'subject_name': row['subject_name'],
                'max_marks': row['max_marks']
            }
            for row in subjects
        ]
    })


@app.route('/question-papers/create', methods=['GET', 'POST'])
@login_required
def create_question_paper():

    user = get_user_by_id(session.get('user_id'))

    if not user or user['role'] not in (
        'teacher', 'admin', 'administrator'
    ):
        flash('Access denied.', 'error')
        return redirect(url_for('user_dashboard'))

    db = get_db()
    classes = get_question_paper_classes(db, user)

    if request.method == 'POST':

        title = request.form.get('title', '').strip()
        class_name = request.form.get('class_name', '').strip()

        # Multiple selected subjects
        selected_subjects = list(dict.fromkeys(
            subject.strip()
            for subject in request.form.getlist('subject[]')
            if subject.strip()
        ))

        time_allowed = request.form.get('time_allowed', '').strip()
        exam_year = request.form.get('exam_year', '').strip()
        max_marks_raw = request.form.get('max_marks', '').strip()

        errors = []

        if not title or len(title) > 200:
            errors.append(
                'Enter an examination title (maximum 200 characters).'
            )

        if not class_name or class_name not in classes:
            errors.append('Please select a valid assigned class.')

        if not selected_subjects:
            errors.append('Please select at least one subject.')

        if len(selected_subjects) > 50:
            errors.append('You can select a maximum of 50 subjects.')

        if not time_allowed or len(time_allowed) > 40:
            errors.append('Enter the examination duration.')

        if not exam_year or len(exam_year) > 30:
            errors.append('Enter the academic/examination year.')

        try:
            max_marks = int(max_marks_raw)

            if not 1 <= max_marks <= 1000:
                raise ValueError

        except (TypeError, ValueError):
            max_marks = 0
            errors.append(
                'Full marks must be a number between 1 and 1000.'
            )

        # Verify every subject belongs to the selected class.
        valid_subject_rows = []

        if class_name in classes and selected_subjects:

            placeholders = ','.join('?' for _ in selected_subjects)

            valid_subject_rows = db.execute(
                f"""
                SELECT DISTINCT subject_name
                FROM subjects
                WHERE class_name = ?
                  AND subject_name IN ({placeholders})
                """,
                [class_name] + selected_subjects
            ).fetchall()

            valid_subject_names = {
                row['subject_name'] for row in valid_subject_rows
            }

            invalid_subjects = [
                subject for subject in selected_subjects
                if subject not in valid_subject_names
            ]

            if invalid_subjects:
                errors.append(
                    'Some selected subjects do not belong to this class. '
                    'Please select the subjects again.'
                )

        if errors:
            for message in errors:
                flash(message, 'error')

            subjects = (
                get_question_paper_subjects(db, class_name)
                if class_name in classes else []
            )

            return render_template(
                'create_question_paper.html',
                user=user,
                classes=classes,
                subjects=subjects,
                selected_class=class_name,
                selected_subjects=selected_subjects
            ), 400

        # Create one paper for every selected subject.
        created_paper_ids = []

        try:
            db.execute('BEGIN')

            for subject in selected_subjects:

                cursor = db.execute("""
                    INSERT INTO exam_papers
                    (
                        title,
                        class_name,
                        subject,
                        time_allowed,
                        max_marks,
                        exam_year,
                        teacher_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    title,
                    class_name,
                    subject,
                    time_allowed,
                    max_marks,
                    exam_year,
                    user['id']
                ))

                created_paper_ids.append(cursor.lastrowid)

            db.commit()

        except Exception:
            db.rollback()
            app.logger.exception(
                'Question paper creation failed.'
            )

            flash(
                'Question papers could not be created. Please try again.',
                'error'
            )

            subjects = get_question_paper_subjects(db, class_name)

            return render_template(
                'create_question_paper.html',
                user=user,
                classes=classes,
                subjects=subjects,
                selected_class=class_name,
                selected_subjects=selected_subjects
            ), 500

        if len(created_paper_ids) == 1:
            flash(
                'Question paper created successfully. Now add your questions.',
                'success'
            )

            return redirect(url_for(
                'edit_question_paper',
                paper_id=created_paper_ids[0]
            ))

        flash(
            f'{len(created_paper_ids)} question papers created successfully.',
            'success'
        )

        return redirect(url_for('teacher_question_papers'))

    # GET request
    selected_class = request.args.get('class_name', '').strip()

    if selected_class not in classes:
        selected_class = ''

    subjects = (
        get_question_paper_subjects(db, selected_class)
        if selected_class else []
    )

    return render_template(
        'create_question_paper.html',
        user=user,
        classes=classes,
        subjects=subjects,
        selected_class=selected_class,
        selected_subjects=[]
    )

def _get_accessible_question_paper(db, user, paper_id):
    """Return a paper only if the signed-in user is allowed to manage it."""
    if not user or user['role'] not in ('teacher', 'admin', 'administrator'):
        return None

    if user['role'] in ('admin', 'administrator'):
        return db.execute(
            'SELECT * FROM exam_papers WHERE id = ?', (paper_id,)
        ).fetchone()

    return db.execute(
        'SELECT * FROM exam_papers WHERE id = ? AND teacher_id = ?',
        (paper_id, user['id'])
    ).fetchone()


@app.route('/question-papers/<int:paper_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_question_paper(paper_id):
    user = get_user_by_id(session.get('user_id'))
    db = get_db()
    paper = _get_accessible_question_paper(db, user, paper_id)

    if not paper:
        flash('Paper not found or you do not have permission to edit it.', 'error')
        return redirect(url_for('teacher_question_papers'))

    if request.method == 'POST':
        # The builder submits one value per question using repeated [] fields.
        sections = request.form.getlist('section[]')
        question_texts = request.form.getlist('question[]')
        options_list = request.form.getlist('options[]')
        marks_list = request.form.getlist('marks[]')
        lines_list = request.form.getlist('lines[]')

        lengths = {len(sections), len(question_texts), len(options_list),
                   len(marks_list), len(lines_list)}

        if len(lengths) != 1:
            flash('Some question fields were not submitted correctly. Please retry.', 'error')
            return redirect(url_for('edit_question_paper', paper_id=paper_id))

        if not question_texts or len(question_texts) > 100:
            flash('Add between 1 and 100 questions per save.', 'error')
            return redirect(url_for('edit_question_paper', paper_id=paper_id))

        rows = []
        errors = []

        for index, (section, question, options, marks_raw, lines_raw) in enumerate(
            zip(sections, question_texts, options_list, marks_list, lines_list), start=1
        ):
            section = section.strip()
            question = question.strip()
            options = options.strip()

            # Ignore completely blank rows; reject partially completed rows.
            if not section and not question and not options:
                continue

            if not section:
                errors.append(f'Question {index}: section name is required.')
                continue
            if not question:
                errors.append(f'Question {index}: question text is required.')
                continue
            if len(section) > 120 or len(question) > 2000 or len(options) > 2000:
                errors.append(f'Question {index}: one or more fields are too long.')
                continue

            try:
                marks = int(marks_raw)
                lines = int(lines_raw)
                if not 1 <= marks <= 1000:
                    raise ValueError
                if not 0 <= lines <= 30:
                    raise ValueError
            except (TypeError, ValueError):
                errors.append(f'Question {index}: marks must be 1–1000 and answer lines 0–30.')
                continue

            rows.append((paper_id, section, question, options or None, marks, lines))

        if errors:
            for message in errors[:10]:
                flash(message, 'error')
            if len(errors) > 10:
                flash(f'And {len(errors) - 10} more validation errors.', 'error')
            return redirect(url_for('edit_question_paper', paper_id=paper_id))

        if not rows:
            flash('No valid questions found. Please enter at least one question.', 'error')
            return redirect(url_for('edit_question_paper', paper_id=paper_id))

        try:
            db.executemany("""
                INSERT INTO exam_questions
                    (paper_id, section_name, question_text, options, marks, lines)
                VALUES (?, ?, ?, ?, ?, ?)
            """, rows)
            db.commit()
        except sqlite3.Error:
            db.rollback()
            app.logger.exception("Unable to save questions for paper_id=%s", paper_id)
            flash('Questions could not be saved due to a database error. Please try again.', 'error')
            return redirect(url_for('edit_question_paper', paper_id=paper_id))

        flash(f'{len(rows)} question(s) saved successfully.', 'success')
        return redirect(url_for('edit_question_paper', paper_id=paper_id))

    questions = db.execute("""
        SELECT id, paper_id, section_name, question_text, options, marks, lines
        FROM exam_questions
        WHERE paper_id = ?
        ORDER BY id
    """, (paper_id,)).fetchall()

    grouped_questions = {}
    for question in questions:
        grouped_questions.setdefault(question['section_name'], []).append(question)

    total_questions = len(questions)
    saved_marks = sum((q['marks'] or 0) for q in questions)

    return render_template(
        'edit_question_paper.html',
        user=user,
        paper=paper,
        grouped_questions=grouped_questions,
        total_questions=total_questions,
        saved_marks=saved_marks
    )


@app.route('/question-papers/<int:paper_id>/delete-question/<int:q_id>', methods=['POST'])
@login_required
def delete_question(paper_id, q_id):
    user = get_user_by_id(session.get('user_id'))
    db = get_db()
    paper = _get_accessible_question_paper(db, user, paper_id)

    if not paper:
        flash('You are not allowed to delete questions from this paper.', 'error')
        return redirect(url_for('teacher_question_papers'))

    cur = db.execute(
        'DELETE FROM exam_questions WHERE id = ? AND paper_id = ?',
        (q_id, paper_id)
    )
    db.commit()

    flash('Question deleted.' if cur.rowcount else 'Question was not found.', 
          'success' if cur.rowcount else 'error')
    return redirect(url_for('edit_question_paper', paper_id=paper_id))


@app.route('/question-papers/<int:paper_id>/delete-paper', methods=['POST'])
@login_required
def delete_question_paper(paper_id):
    user = get_user_by_id(session.get('user_id'))
    db = get_db()
    paper = _get_accessible_question_paper(db, user, paper_id)

    if not paper:
        flash('You are not allowed to delete this paper.', 'error')
        return redirect(url_for('teacher_question_papers'))

    db.execute('DELETE FROM exam_questions WHERE paper_id = ?', (paper_id,))
    db.execute('DELETE FROM exam_papers WHERE id = ?', (paper_id,))
    db.commit()
    flash('Question paper deleted.', 'success')
    return redirect(url_for('teacher_question_papers'))

@app.route('/question-papers/<int:paper_id>/api/delete-questions', methods=['POST'])
@login_required
def api_delete_questions(paper_id):
    user = get_user_by_id(session.get('user_id'))
    db = get_db()
    paper = _get_accessible_question_paper(db, user, paper_id)

    if not paper:
        return jsonify({'success': False, 'error': 'Permission denied'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400

    try:
        if data.get('delete_all'):
            # Delete all questions for this paper
            db.execute('DELETE FROM exam_questions WHERE paper_id = ?', (paper_id,))
        else:
            # Delete selected questions
            q_ids = data.get('question_ids', [])
            if not q_ids:
                return jsonify({'success': False, 'error': 'No questions selected'}), 400
            
            # Create placeholders for the IN clause (e.g., ?, ?, ?)
            placeholders = ','.join(['?'] * len(q_ids))
            db.execute(
                f'DELETE FROM exam_questions WHERE paper_id = ? AND id IN ({placeholders})', 
                [paper_id] + q_ids
            )

        db.commit()
        return jsonify({'success': True})
    except Exception:
        db.rollback()
        app.logger.exception('Bulk question deletion failed for paper_id=%s', paper_id)
        return jsonify({'success': False, 'error': 'Unable to delete questions right now.'}), 500

@app.route('/question-papers/<int:paper_id>/print')
@login_required
def print_question_paper(paper_id):
    user = get_user_by_id(session.get('user_id'))
    db = get_db()
    paper = _get_accessible_question_paper(db, user, paper_id)

    if not paper:
        flash('Paper not found or you do not have permission to view it.', 'error')
        return redirect(url_for('teacher_question_papers'))

    questions = db.execute("""
        SELECT id, paper_id, section_name, question_text, options, marks, lines
        FROM exam_questions
        WHERE paper_id = ?
        ORDER BY id
    """, (paper_id,)).fetchall()

    grouped_questions = {}
    total_marks = 0
    for question in questions:
        grouped_questions.setdefault(question['section_name'], []).append(question)
        total_marks += int(question['marks'] or 0)

    return render_template(
    'print_question_paper.html',
    paper=paper,
    grouped_questions=grouped_questions,
    total_marks=total_marks,
    question_count=len(questions),
    school_name=get_setting('school_name') or 'RES. SHANTI NIKETAN SHISHU VIDYA MANDIR',
    school_address=get_setting('school_address') or 'NAVINAGAR (JAMUI)',
    school_logo=get_setting('school_logo_url') or get_setting('school_logo')
)


@app.route('/teacher/homework/add', methods=['POST'])
@login_required
def teacher_add_homework():
    user = get_user_by_id(session['user_id'])
    if not user or user['role'] not in ('teacher', 'admin', 'administrator'):
        flash('Only teachers can access this page.', 'error')
        return redirect(url_for('user_dashboard'))

    class_name = request.form.get('class_name', '').strip()
    subject    = request.form.get('subject', '').strip() or (user['subject'] or 'General')
    title      = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    due_date   = request.form.get('due_date', '').strip()

    if not class_name or not title:
        flash('Class and Title are required.', 'error')
        return redirect(url_for('teacher_homework'))

    db = get_db()
    db.execute(
        '''INSERT INTO homework (class_name, subject, title, description, due_date, assigned_by)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (class_name, subject, title, description or None, due_date or None, user['id'])
    )
    db.commit()
    flash(f'Homework "{title}" assigned to {class_name}.', 'success')
    return redirect(url_for('teacher_homework'))


@app.route('/teacher/homework/delete/<int:hid>', methods=['POST'])
@login_required
def teacher_delete_homework(hid):
    user = get_user_by_id(session['user_id'])
    if not user or user['role'] not in ('teacher', 'admin', 'administrator'):
        flash('Only teachers can access this page.', 'error')
        return redirect(url_for('user_dashboard'))

    db = get_db()
    hw = db.execute('SELECT * FROM homework WHERE id = ?', (hid,)).fetchone()

    if not hw:
        flash('Homework not found.', 'error')
        return redirect(url_for('teacher_homework'))

    if user['role'] not in ('admin', 'administrator') and hw['assigned_by'] != user['id']:
        flash('You can only delete homework you assigned.', 'error')
        return redirect(url_for('teacher_homework'))

    db.execute('DELETE FROM homework WHERE id = ?', (hid,))
    db.commit()
    flash('Homework deleted.', 'success')
    return redirect(url_for('teacher_homework'))


# =========================================
# USER SELF-SERVICE — PROFILE PHOTO
# =========================================
@app.route('/update-profile-photo', methods=['POST'])
@login_required
def update_profile_photo():
    user = get_user_by_id(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login_page'))

    photo_file = request.files.get('photo')
    if not photo_file or not photo_file.filename:
        flash('Please select an image file.', 'error')
        return redirect(safe_redirect_url(url_for('user_dashboard')))

    if not allowed_file(photo_file.filename):
        flash('Only JPG / PNG / WEBP / GIF allowed.', 'error')
        return redirect(safe_redirect_url(url_for('user_dashboard')))

    photo_url = save_user_photo(photo_file)
    if not photo_url:
        flash('Image is too large (max 2MB) or could not be saved.', 'error')
        return redirect(safe_redirect_url(url_for('user_dashboard')))

    db = get_db()
    db.execute('UPDATE users SET photo_url = ? WHERE id = ?', (photo_url, user['id']))
    db.commit()

    if user['role'] == 'teacher':
        db.execute('UPDATE faculty SET photo_url = ? WHERE user_id = ?', (photo_url, user['id']))
        db.commit()

    session['photo_url'] = photo_url

    flash('Profile photo updated successfully!', 'success')
    return redirect(safe_redirect_url(url_for('user_dashboard')))


@app.route('/remove-profile-photo', methods=['POST'])
@login_required
def remove_profile_photo():
    user = get_user_by_id(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login_page'))

    db = get_db()
    db.execute('UPDATE users SET photo_url = NULL WHERE id = ?', (user['id'],))
    db.commit()

    if user['role'] == 'teacher':
        db.execute('UPDATE faculty SET photo_url = NULL WHERE user_id = ?', (user['id'],))
        db.commit()

    session['photo_url'] = None

    flash('Profile photo removed.', 'success')
    return redirect(safe_redirect_url(url_for('user_dashboard')))

# =========================================
# MESSAGING SYSTEM — ROLE-BASED
# =========================================
def _allowed_recipients(db, user):
    """Returns list of dicts {id, name, unique_id, role} this user can message."""
    role = user['role']
    uid = user['id']
    recipients = []

    if role in ('admin', 'administrator'):
        rows = db.execute(
            "SELECT id, name, unique_id, role FROM users "
            "WHERE is_active=1 AND id != ? ORDER BY role, name",
            (uid,)
        ).fetchall()
        recipients = [dict(r) for r in rows]

    elif role == 'teacher':
        rows = db.execute(
            "SELECT id, name, unique_id, role FROM users "
            "WHERE is_active=1 AND role IN ('admin', 'administrator', 'teacher') AND id != ? "
            "ORDER BY role, name",
            (uid,)
        ).fetchall()
        recipients.extend([dict(r) for r in rows])

        raw = user['classes_assigned'] or ''
        teacher_classes = [c.strip() for c in raw.split(',') if c.strip()]
        if teacher_classes:
            ph = " OR ".join(["class_name = ? OR child_class = ?"] * len(teacher_classes))
            params = []
            for c in teacher_classes:
                params.extend([c, c])

            rows = db.execute(
                f"SELECT id, name, unique_id, role FROM users "
                f"WHERE is_active=1 AND role='student' AND ({ph}) ORDER BY name",
                tuple(params)
            ).fetchall()
            recipients.extend([dict(r) for r in rows])

            ph_p = " OR ".join(["child_class = ?"] * len(teacher_classes))
            rows = db.execute(
                f"SELECT id, name, unique_id, role FROM users "
                f"WHERE is_active=1 AND role='parent' AND ({ph_p}) ORDER BY name",
                tuple(teacher_classes)
            ).fetchall()
            recipients.extend([dict(r) for r in rows])

    elif role == 'parent':
        rows = db.execute(
            "SELECT id, name, unique_id, role FROM users "
            "WHERE is_active=1 AND role IN ('admin', 'administrator', 'teacher') AND id != ? "
            "ORDER BY role, name",
            (uid,)
        ).fetchall()
        recipients = [dict(r) for r in rows]

    elif role == 'student':
        rows = db.execute(
            "SELECT id, name, unique_id, role FROM users "
            "WHERE is_active=1 AND role IN ('admin', 'administrator', 'teacher') AND id != ? "
            "ORDER BY role, name",
            (uid,)
        ).fetchall()
        recipients = [dict(r) for r in rows]

    return recipients


# =========================================
# MESSAGING ROUTES
# =========================================
@app.route('/messages')
@login_required
def messages_inbox():
    user = get_user_by_id(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login_page'))

    db = get_db()
    view = request.args.get('view', 'inbox')
    search_q = (request.args.get('q') or '').strip().lower()

    if view == 'sent':
        rows = db.execute(
            '''SELECT m.*, 
                   uf.name AS from_name, uf.unique_id AS from_uid, uf.role AS from_role,
                   ut.name AS to_name, ut.unique_id AS to_uid, ut.role AS to_role
               FROM messages m
               LEFT JOIN users uf ON m.from_user_id = uf.id
               LEFT JOIN users ut ON m.to_user_id = ut.id
               WHERE m.from_user_id = ?
               ORDER BY m.id DESC''',
            (user['id'],)
        ).fetchall()
    else:
        rows = db.execute(
            '''SELECT m.*, 
                   uf.name AS from_name, uf.unique_id AS from_uid, uf.role AS from_role,
                   ut.name AS to_name, ut.unique_id AS to_uid, ut.role AS to_role
               FROM messages m
               LEFT JOIN users uf ON m.from_user_id = uf.id
               LEFT JOIN users ut ON m.to_user_id = ut.id
               WHERE (m.to_user_id = ? OR m.to_role = ?)
               ORDER BY m.id DESC''',
            (user['id'], user['role'])
        ).fetchall()

    if search_q:
        rows = [
            r for r in rows
            if search_q in (r['subject'] or '').lower()
            or search_q in (r['body'] or '').lower()
            or search_q in (r['from_name'] or '').lower()
            or search_q in (r['to_name'] or '').lower()
        ]

    inbox_count = db.execute(
        "SELECT COUNT(*) FROM messages WHERE to_user_id = ? OR to_role = ?",
        (user['id'], user['role'])
    ).fetchone()[0]

    sent_count = db.execute(
        "SELECT COUNT(*) FROM messages WHERE from_user_id = ?",
        (user['id'],)
    ).fetchone()[0]

    unread_count = db.execute(
        "SELECT COUNT(*) FROM messages WHERE to_user_id = ? AND is_read = 0",
        (user['id'],)
    ).fetchone()[0]

    return render_template(
        'messages_inbox.html',
        user=user,
        messages=rows,
        view=view,
        search_q=search_q,
        inbox_count=inbox_count,
        sent_count=sent_count,
        unread_count=unread_count
    )


@app.route('/messages/compose', methods=['GET', 'POST'])
@login_required
def messages_compose():
    user = get_user_by_id(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login_page'))

    db = get_db()
    recipients = _allowed_recipients(db, user)

    reply_to = request.args.get('reply_to', type=int)
    pre_subject = ''
    pre_to = ''

    if reply_to:
        orig = db.execute('SELECT * FROM messages WHERE id = ?', (reply_to,)).fetchone()
        if orig:
            pre_subject = orig['subject'] or ''
            if not pre_subject.lower().startswith('re:'):
                pre_subject = 'Re: ' + pre_subject
            if orig['from_user_id'] != user['id']:
                pre_to = str(orig['from_user_id'])

    if request.method == 'POST':
        to_user_id = (request.form.get('to_user_id') or '').strip()
        subject    = (request.form.get('subject') or '').strip()
        body       = (request.form.get('body') or '').strip()

        errors = []
        if not to_user_id:
            errors.append('Please choose a recipient.')
        if not subject:
            errors.append('Subject is required.')
        if not body:
            errors.append('Message body is required.')

        allowed_ids = {str(r['id']) for r in recipients}
        if to_user_id and to_user_id not in allowed_ids:
            errors.append('You are not allowed to message this user.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return redirect(url_for('messages_compose', reply_to=reply_to) if reply_to
                            else url_for('messages_compose'))

        db.execute(
            'INSERT INTO messages (from_user_id, to_user_id, subject, body, is_read) '
            'VALUES (?, ?, ?, ?, 0)',
            (user['id'], int(to_user_id), subject, body)
        )
        db.commit()
        flash('Message sent successfully.', 'success')
        return redirect(url_for('messages_inbox', view='sent'))

    return render_template(
        'messages_compose.html',
        user=user,
        recipients=recipients,
        pre_subject=pre_subject,
        pre_to=pre_to,
        reply_to=reply_to
    )


@app.route('/messages/<int:msg_id>')
@login_required
def messages_view(msg_id):
    user = get_user_by_id(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login_page'))

    db = get_db()

    msg = db.execute(
        '''SELECT m.*, 
               uf.name AS from_name, uf.unique_id AS from_uid, uf.role AS from_role,
               ut.name AS to_name, ut.unique_id AS to_uid, ut.role AS to_role
           FROM messages m
           LEFT JOIN users uf ON m.from_user_id = uf.id
           LEFT JOIN users ut ON m.to_user_id = ut.id
           WHERE m.id = ?''',
        (msg_id,)
    ).fetchone()

    if not msg:
        flash('Message not found.', 'error')
        return redirect(url_for('messages_inbox'))

    is_sender      = (msg['from_user_id'] == user['id'])
    is_recipient   = (msg['to_user_id'] == user['id'])
    is_role_recip  = (msg['to_user_id'] is None and msg['to_role'] == user['role'])

    if not (is_sender or is_recipient or is_role_recip):
        flash('You do not have access to this message.', 'error')
        return redirect(url_for('messages_inbox'))

    if is_recipient and not msg['is_read']:
        db.execute('UPDATE messages SET is_read = 1 WHERE id = ?', (msg_id,))
        db.commit()

    can_reply = not is_sender

    return render_template(
        'messages_view.html',
        user=user,
        msg=msg,
        can_reply=can_reply,
        is_sender=is_sender,
        is_role_recip=is_role_recip
    )


@app.route('/messages/delete/<int:msg_id>', methods=['POST'])
@login_required
def messages_delete(msg_id):
    user = get_user_by_id(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login_page'))

    db = get_db()
    msg = db.execute('SELECT * FROM messages WHERE id = ?', (msg_id,)).fetchone()
    if not msg:
        flash('Message not found.', 'error')
        return redirect(url_for('messages_inbox'))

    if msg['from_user_id'] != user['id'] and user['role'] not in ('admin', 'administrator'):
        flash('You can only delete messages you sent.', 'error')
        return redirect(url_for('messages_inbox'))

    db.execute('DELETE FROM messages WHERE id = ?', (msg_id,))
    db.commit()
    flash('Message deleted.', 'success')
    return redirect(url_for('messages_inbox', view='sent'))


# =========================================
# 10.7. ADMIN — STUDY MATERIALS
# =========================================
@app.route('/admin/study-materials')
@admin_required
def admin_study_materials():
    db = get_db()
    materials = db.execute(
        'SELECT sm.*, u.name AS uploaded_by_name '
        'FROM study_materials sm LEFT JOIN users u ON sm.uploaded_by = u.id '
        'ORDER BY sm.id DESC'
    ).fetchall()
    return render_template('admin_study_materials.html',
                          materials=materials,
                          active_page='study_materials')


@app.route('/admin/study-materials/add', methods=['POST'])
@admin_required
def admin_add_study_material():
    class_name   = request.form.get('class_name', '').strip()
    subject      = request.form.get('subject', '').strip()
    title        = request.form.get('title', '').strip()
    description  = request.form.get('description', '').strip()
    external_link= request.form.get('external_link', '').strip()
    material_type= request.form.get('material_type', 'notes')

    if not class_name or not title:
        flash('Class and Title are required.', 'error')
        return redirect(url_for('admin_study_materials'))

    db = get_db()
    db.execute(
        '''INSERT INTO study_materials
           (class_name, subject, title, description, external_link,
            material_type, uploaded_by)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (class_name, subject or None, title, description or None,
         external_link or None, material_type, session['user_id'])
    )
    db.commit()
    flash(f'Material "{title}" added for {class_name}.', 'success')
    return redirect(url_for('admin_study_materials'))


@app.route('/admin/study-materials/delete/<int:mid>', methods=['POST'])
@admin_required
def admin_delete_study_material(mid):
    db = get_db()
    db.execute('DELETE FROM study_materials WHERE id = ?', (mid,))
    db.commit()
    flash('Study material deleted.', 'success')
    return redirect(url_for('admin_study_materials'))


# =========================================
# 10.8. STUDENT/PARENT — STUDY MATERIALS
# =========================================
@app.route('/study-materials')
@login_required
def study_materials_page():
    user = get_user_by_id(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login_page'))

    role = user['role']
    db = get_db()

    target_class = None
    if role == 'student':
        target_class = user['class_name'] or user['child_class']
    elif role == 'parent':
        target_class = user['child_class']

    materials = []
    if target_class:
        materials = db.execute(
            'SELECT * FROM study_materials WHERE class_name = ? '
            'ORDER BY id DESC',
            (target_class,)
        ).fetchall()

    return render_template('study_materials_page.html',
                          user=user,
                          target_class=target_class,
                          materials=materials)


# =========================================
# 10.9. STUDENT/PARENT — RESULTS PAGE
# =========================================
@app.route('/results')
@login_required
def results_page():
    user = get_user_by_id(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login_page'))

    role = user['role']
    db = get_db()
    exam_marks = []
    student_name = None
    student_class = None

    if role == 'student':
        student_name = user['name']
        student_class = user['class_name'] or user['child_class']
        exam_marks = db.execute(
            'SELECT * FROM exam_marks WHERE student_id = ? '
            'ORDER BY exam_type, subject',
            (user['id'],)
        ).fetchall()

    elif role == 'parent':
        student_name = user['child_name']
        student_class = user['child_class']
        child = get_parent_child(db, user)
        if child:
            exam_marks = db.execute(
                'SELECT * FROM exam_marks WHERE student_id = ? '
                'ORDER BY exam_type, subject',
                (child['id'],)
            ).fetchall()

    grouped = {}
    for m in exam_marks:
        et = m['exam_type'] or 'General'
        grouped.setdefault(et, []).append(m)

    return render_template('results.html',
                          user=user,
                          role=role,
                          student_name=student_name,
                          student_class=student_class,
                          exam_marks=exam_marks,
                          grouped=grouped)


# =========================================
# NEW: ONLINE EXAM FORM ROUTE
# =========================================
@app.route('/exam-form', methods=['GET', 'POST'])
@login_required
def exam_form():
    user = get_user_by_id(session['user_id'])
    if not user:
        return redirect(url_for('login_page'))

    db = get_db()
    
    # Agar form submit hua hai
    if request.method == 'POST':
        selected_subjects = request.form.getlist('subjects')
        
        db.execute('''INSERT INTO exam_registrations 
                      (student_id, student_name, father_name, mother_name, dob, gender, 
                       class_name, section, roll_no, admission_no, student_mobile, 
                       parent_mobile, address, exam_type, selected_subjects)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                   (user['id'], request.form.get('studentName'), request.form.get('fatherName'),
                    request.form.get('motherName'), request.form.get('dob'), request.form.get('gender'),
                    request.form.get('className'), request.form.get('section'), request.form.get('rollNumber'),
                    request.form.get('admissionNumber'), request.form.get('studentMobile'),
                    request.form.get('parentMobile'), request.form.get('address'), request.form.get('examType'),
                    json.dumps(selected_subjects)))
        db.commit()
        flash('Exam form submitted successfully!', 'success')
        return redirect(url_for('user_dashboard'))

    # Agar page open kiya hai (GET)
    # 🚀 YAHAN FIX KIYA GAYA HAI
    classes = get_all_classes(db)
    
    # Admin dwara add kiye gaye subjects fetch karein
    subjects_raw = db.execute('SELECT class_name, subject_name FROM subjects').fetchall()
    subjects_dict = {}
    for row in subjects_raw:
        cls = row['class_name']
        if cls not in subjects_dict:
            subjects_dict[cls] = []
        subjects_dict[cls].append(row['subject_name'])

    # Auto-fill ke liye data taiyar karein
    prefill = {
        'studentName': '', 'fatherName': '', 'motherName': '', 'dob': '',
        'gender': '', 'className': '', 'section': '', 'rollNumber': '',
        'admissionNumber': '', 'studentMobile': '', 'parentMobile': '', 'address': ''
    }

    if user['role'] == 'student':
        prefill['studentName'] = user['name']
        prefill['fatherName'] = user['father_name'] or ''
        prefill['motherName'] = user['mother_name'] or ''
        prefill['dob'] = user['dob'] or ''
        prefill['gender'] = user['gender'] or ''
        prefill['className'] = user['class_name'] or user['child_class'] or ''
        prefill['section'] = user['section'] or ''
        prefill['rollNumber'] = user['roll_no'] or ''
        prefill['admissionNumber'] = user['admission_no'] or ''
        prefill['studentMobile'] = user['phone'] or ''
        prefill['parentMobile'] = user['father_mobile'] or ''
        prefill['address'] = user['address'] or ''
    elif user['role'] == 'parent':
        child = get_parent_child(db, user)
        if child:
            prefill['studentName'] = child['name']
            prefill['fatherName'] = child['father_name'] or ''
            prefill['motherName'] = child['mother_name'] or ''
            prefill['dob'] = child['dob'] or ''
            prefill['gender'] = child['gender'] or ''
            prefill['className'] = child['class_name'] or ''
            prefill['section'] = child['section'] or ''
            prefill['rollNumber'] = child['roll_no'] or ''
            prefill['admissionNumber'] = child['admission_no'] or ''
            prefill['parentMobile'] = child['father_mobile'] or ''
            prefill['address'] = child['address'] or ''
            
    return render_template('exam_form.html', 
                           user=user, 
                           classes=classes, 
                           subjects_dict=subjects_dict,
                           prefill=prefill)
    
# =========================================
# 10.10. SETTINGS PAGE
# =========================================
@app.route('/settings')
@login_required
def settings_page():
    user = get_user_by_id(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login_page'))
    return render_template('settings.html', user=user)


# =========================================
# 11. API & FORM ROUTES (Public)
# =========================================
@app.route('/api/notices')
def api_notices():
    return jsonify({'notices': [dict(n) for n in get_all_notices()]})

@app.route('/admission-enquiry', methods=['POST'])
def admission_enquiry():
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip()
    class_name = request.form.get('class_name', '').strip()
    message = request.form.get('message', '').strip()

    if not name or not phone or not re.match(r'^[0-9+() -]{10,18}$', phone):
        flash('Valid name and phone required.', 'error')
        return redirect(url_for('home') + '#admission')

    db = get_db()
    db.execute('INSERT INTO enquiries (kind, name, phone, email, class_name, message) VALUES (?,?,?,?,?,?)',
               ('admission', name, phone, email, class_name, message))
    db.commit()
    flash('Enquiry submitted!', 'success')
    return redirect(url_for('home') + '#admission')

@app.route('/contact', methods=['POST'])
def contact():
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    message = request.form.get('message', '').strip()
    if not name or not phone or not message:
        flash('Please complete all fields.', 'error')
        return redirect(url_for('home') + '#contact')
    db = get_db()
    db.execute('INSERT INTO enquiries (kind, name, phone, message) VALUES (?,?,?,?)',
               ('contact', name, phone, message))
    db.commit()
    flash('Message received.', 'success')
    return redirect(url_for('home') + '#contact')

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

# =========================================
# 12. ERROR HANDLERS
# =========================================
@app.errorhandler(404)
def nf(e): return "Page not found", 404

@app.errorhandler(413)
def request_entity_too_large(error):
    flash('File is too large! Maximum allowed size is 20MB. Please compress your image and try again.', 'error')
    return redirect(safe_redirect_url(url_for('admin_gallery')) or url_for('admin_events'))

@app.errorhandler(500)
def ie(e):
    app.logger.exception('Unhandled server error: %s', e)
    return "An unexpected server error occurred. Please try again later.", 500

@app.after_request
def add_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    response.headers['Cache-Control'] = 'no-store' if session.get('user_id') else response.headers.get('Cache-Control', 'public, max-age=0')
    if request.is_secure:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    # CSP is intentionally not forced here: existing templates may use inline
    # scripts/styles and third-party CDNs. Add a nonce-based CSP after template audit.
    return response


# =========================================
# EXAM SYSTEM — ADMIN ROUTES
# =========================================

# ----- Backward-compat stubs → redirect to new system -----
@app.route('/admin/enter-marks')
@admin_required
def admin_enter_marks():
    """Legacy link → new exams list."""
    return redirect(url_for('admin_exams_list'))

@app.route('/admin/bulk-marks')
@admin_required
def admin_bulk_marks():
    """Legacy link → reports dashboard where bulk entry lives."""
    return redirect(url_for('admin_reports_dashboard'))

@app.route('/admin/reports')
@admin_required
def admin_reports():
    """Legacy link → reports dashboard."""
    return redirect(url_for('admin_reports_dashboard'))


# ---------- EXAM CRUD ----------
@app.route('/admin/exams')
@admin_required
def admin_exams_list():
    db = get_db()
    exams = db.execute('SELECT * FROM exams ORDER BY id DESC').fetchall()
    return render_template('admin_exams_list.html', exams=exams, active_page='exams')


@app.route('/admin/exams/create', methods=['GET', 'POST'])
@admin_required
def admin_exam_create():
    db = get_db()
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('Exam title is required.', 'error')
            return redirect(url_for('admin_exam_create'))

        cur = db.execute('''INSERT INTO exams
            (title, academic_year, term_label, notice_text, custom_message, created_by)
            VALUES (?, ?, ?, ?, ?, ?)''',
            (title,
             request.form.get('academic_year', '').strip(),
             request.form.get('term_label', '2nd TERM').strip(),
             request.form.get('notice_text', '').strip(),
             request.form.get('custom_message', '').strip(),
             session['user_id']))
        db.commit()
        flash('Exam saved as draft. Add subjects below, then publish.', 'success')
        return redirect(url_for('admin_exam_edit', eid=cur.lastrowid))

    class_list = get_all_classes(db)

    for cls in class_list:
        ensure_common_subjects(db, cls)

    return render_template('admin_exam_form.html', exam=None,
                           subjects_by_class={}, class_list=class_list, active_page='exams')

@app.route('/admin/exams/<int:eid>/edit', methods=['GET', 'POST'])
@admin_required
def admin_exam_edit(eid):
    db = get_db()
    exam = db.execute('SELECT * FROM exams WHERE id = ?', (eid,)).fetchone()
    if not exam:
        flash('Exam not found.', 'error')
        return redirect(url_for('admin_exams_list'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('Exam title is required.', 'error')
            return redirect(url_for('admin_exam_edit', eid=eid))

        db.execute('''UPDATE exams SET
            title = ?, academic_year = ?, term_label = ?,
            notice_text = ?, custom_message = ?
            WHERE id = ?''',
            (title,
             request.form.get('academic_year', '').strip(),
             request.form.get('term_label', '2nd TERM').strip(),
             request.form.get('notice_text', '').strip(),
             request.form.get('custom_message', '').strip(),
             eid))
        db.commit()
        flash('Exam updated successfully!', 'success')
        return redirect(url_for('admin_exams_list'))

    class_list = get_all_classes(db)
    for cls in class_list:
        ensure_common_subjects(db, cls)

    subjects_by_class = {}
    subject_rows = db.execute(
        'SELECT id, class_name, subject_name, max_marks, display_order '
        'FROM subjects ORDER BY class_name, display_order, id'
    ).fetchall()
    for row in subject_rows:
        class_name = row['class_name']
        subjects_by_class.setdefault(class_name, []).append({
            'id': row['id'],
            'class_name': row['class_name'],
            'subject_name': row['subject_name'],
            'max_marks': row['max_marks'],
            'display_order': row['display_order']
        })

    # to fetch Selected subjects
    selected_subjects_by_class = {}
    selected_max_marks_by_class = {}
    selected_rows = db.execute(
        '''SELECT class_name, subject_id, max_marks FROM exam_subjects
           WHERE exam_id = ? ORDER BY class_name, subject_id''', (eid,)
    ).fetchall()
    for row in selected_rows:
        class_name = row['class_name']
        selected_subjects_by_class.setdefault(class_name, []).append(str(row['subject_id']))
        selected_max_marks_by_class.setdefault(class_name, {})[str(row['subject_id'])] = row['max_marks']

    return render_template(
        'admin_exam_form.html', exam=exam,
        subjects_by_class=subjects_by_class,
        selected_subjects_by_class=selected_subjects_by_class,
        selected_max_marks_by_class=selected_max_marks_by_class,
        class_list=class_list, active_page='exams'
    )
    
@app.route('/admin/exams/<int:eid>/subjects/save', methods=['POST'])
@admin_required
def admin_exam_save_subjects(eid):
    db = get_db()
    exam = db.execute('SELECT id FROM exams WHERE id = ?', (eid,)).fetchone()
    if not exam:
        flash('Exam not found.', 'error')
        return redirect(url_for('admin_exams_list'))

    raw_payload = request.form.get('selected_subjects_json', '{}')
    try:
        payload = json.loads(raw_payload or '{}')
        if not isinstance(payload, dict):
            raise ValueError('Expected an object of classes and subjects.')
    except (json.JSONDecodeError, ValueError, TypeError):
        flash('Invalid subject selection. Please select subjects again.', 'error')
        return redirect(url_for('admin_exam_edit', eid=eid))

    rows_to_save = []
    for class_name, selection in payload.items():
        class_name = str(class_name).strip()
        if not class_name or not isinstance(selection, dict):
            continue
        subject_ids = selection.get('subject_ids', [])
        marks_map = selection.get('max_marks_by_subject', {})
        if not isinstance(subject_ids, list) or not isinstance(marks_map, dict):
            continue

        for raw_sid in subject_ids:
            try:
                sid = int(raw_sid)
            except (TypeError, ValueError):
                continue
            subject = db.execute(
                'SELECT id, class_name, max_marks FROM subjects WHERE id = ? AND class_name = ?',
                (sid, class_name)
            ).fetchone()
            if not subject:
                continue

            raw_max = marks_map.get(str(sid))
            try:
                max_marks = float(raw_max) if raw_max not in (None, '') else float(subject['max_marks'])
            except (TypeError, ValueError):
                max_marks = float(subject['max_marks'])
            if not (0 < max_marks < 10000000):
                flash(f'Max marks for subject ID {sid} must be greater than zero.', 'error')
                return redirect(url_for('admin_exam_edit', eid=eid))
            rows_to_save.append((eid, class_name, sid, max_marks))

    try:
        db.execute('DELETE FROM exam_subjects WHERE exam_id = ?', (eid,))
        db.executemany(
            '''INSERT INTO exam_subjects (exam_id, class_name, subject_id, max_marks)
               VALUES (?, ?, ?, ?)''', rows_to_save
        )
        # Keep teacher submission statuses for classes that remain selected.
        selected_classes = sorted({row[1] for row in rows_to_save})
        if selected_classes:
            placeholders = ','.join('?' for _ in selected_classes)
            db.execute(
                f'DELETE FROM exam_submissions WHERE exam_id = ? AND class_name NOT IN ({placeholders})',
                [eid, *selected_classes]
            )
            db.executemany(
                '''INSERT OR IGNORE INTO exam_submissions (exam_id, class_name, status)
                   VALUES (?, ?, 'pending')''',
                [(eid, cls) for cls in selected_classes]
            )
        else:
            db.execute('DELETE FROM exam_submissions WHERE exam_id = ?', (eid,))
        db.commit()
    except Exception:
        db.rollback()
        app.logger.exception('Could not save selected subjects for exam %s', eid)
        flash('Subjects save nahi ho paye. Server log check karein.', 'error')
        return redirect(url_for('admin_exam_edit', eid=eid))

    flash(f'Selected subjects saved successfully ({len(rows_to_save)} subject(s)).', 'success')
    return redirect(url_for('admin_exam_edit', eid=eid))


# =========================================
# 🚀 API — ADD NEW SUBJECT ON THE FLY (For Exam Form)
# =========================================
@app.route('/admin/subjects/api/add', methods=['POST'])
@admin_required
def admin_api_add_subject():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request data'})

    class_name = data.get('class_name', '').strip()
    subject_name = data.get('subject_name', '').strip().upper()
    exam_id = data.get('exam_id')
    
    try:
        max_marks = float(data.get('max_marks', 100))
    except (ValueError, TypeError):
        max_marks = 100.0

    if not class_name or not subject_name:
        return jsonify({'success': False, 'error': 'Class and subject name required'})

    db = get_db()
    
    # Saari classes ki list nikalain (Standard + Dynamic)
    all_classes = get_all_classes(db)
    created_subjects_map = {}
    active_subject_id = None

    try:
        for cls in all_classes:
            # Check karein ki subject pehle se us class me hai ya nahi
            existing = db.execute(
                'SELECT id, max_marks FROM subjects WHERE class_name=? AND subject_name=?', 
                (cls, subject_name)
            ).fetchone()
            
            if existing:
                # Agar pehle se hai, toh bas map me daal dein
                created_subjects_map[cls] = {
                    'id': existing['id'],
                    'subject_name': subject_name,
                    'max_marks': existing['max_marks']
                }
                if cls == class_name:
                    active_subject_id = existing['id']
            else:
                # Agar nahi hai, toh nayi class me insert karein
                cur = db.execute(
                    'INSERT INTO subjects (class_name, subject_name, max_marks) VALUES (?, ?, ?)',
                    (cls, subject_name, max_marks)
                )
                created_subjects_map[cls] = {
                    'id': cur.lastrowid,
                    'subject_name': subject_name,
                    'max_marks': max_marks
                }
                if cls == class_name:
                    active_subject_id = cur.lastrowid

        # Agar exam_id diya gaya hai, toh current class ke liye auto-save bhi kar dein
        if exam_id and active_subject_id:
            db.execute('''INSERT OR IGNORE INTO exam_subjects 
                          (exam_id, class_name, subject_id, max_marks) 
                          VALUES (?, ?, ?, ?)''',
                       (exam_id, class_name, active_subject_id, max_marks))
                       
        db.commit()
        
        return jsonify({
            'success': True,
            'active_subject_id': active_subject_id,
            'all_subjects_map': created_subjects_map
        })
        
    except Exception:
        db.rollback()
        app.logger.exception('Subject creation API failed')
        return jsonify({'success': False, 'error': 'Unable to add subject right now.'}), 500
    
@app.route('/admin/exams/<int:eid>/publish', methods=['POST'])
@admin_required
def admin_exam_publish(eid):
    db = get_db()
    if not db.execute('SELECT 1 FROM exams WHERE id=?', (eid,)).fetchone():
        flash('Exam not found.', 'error')
        return redirect(url_for('admin_exams_list'))

    sub_count = db.execute('SELECT COUNT(*) FROM exam_subjects WHERE exam_id=?', (eid,)).fetchone()[0]
    if not sub_count:
        flash('Select and save at least one subject for this exam before publishing.', 'error')
        return redirect(url_for('admin_exam_edit', eid=eid))

    db.execute("UPDATE exams SET status='published', published_at=? WHERE id=?",
               (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), eid))

    classes = db.execute('SELECT DISTINCT class_name FROM exam_subjects WHERE exam_id=? ORDER BY class_name', (eid,)).fetchall()
    for row in classes:
        db.execute('''INSERT OR IGNORE INTO exam_submissions
                     (exam_id, class_name, status) VALUES (?, ?, 'pending')''',
                   (eid, row['class_name']))
    db.commit()
    flash(f'Exam published! {len(classes)} class(es) notified to teachers.', 'success')
    return redirect(url_for('admin_exams_list'))


@app.route('/admin/exams/<int:eid>/unpublish', methods=['POST'])
@admin_required
def admin_exam_unpublish(eid):
    db = get_db()
    db.execute("UPDATE exams SET status='draft' WHERE id=?", (eid,))
    db.commit()
    flash('Exam unpublished.', 'success')
    return redirect(url_for('admin_exams_list'))


@app.route('/admin/exams/<int:eid>/delete', methods=['POST'])
@admin_required
def admin_exam_delete(eid):
    db = get_db()
    db.execute('DELETE FROM exam_marks WHERE exam_id = ?', (eid,))
    db.execute('DELETE FROM exam_submissions WHERE exam_id = ?', (eid,))
    db.execute('DELETE FROM exam_subjects WHERE exam_id = ?', (eid,))
    db.execute('DELETE FROM exams WHERE id = ?', (eid,))
    db.commit()
    flash('Exam and all its marks deleted.', 'success')
    return redirect(url_for('admin_exams_list'))


# ---------- SUBJECTS MANAGEMENT ----------
@app.route('/admin/subjects/add', methods=['POST'])
@admin_required
def admin_add_subject():

    class_name = request.form.get('class_name', '').strip()

    # Singular aur plural dono field support
    subjects_raw = (
        request.form.get('subject_names', '').strip()
        or request.form.get('subject_name', '').strip()
    )

    try:
        max_marks = float(request.form.get('max_marks', 100))
    except (ValueError, TypeError):
        max_marks = 100

    if not class_name or not subjects_raw:
        flash('Class and subject name are required.', 'error')
        return redirect(safe_redirect_url(url_for('admin_exams_list')))

    if not (0 < max_marks <= 1000):
        flash('Maximum marks must be between 1 and 1000.', 'error')
        return redirect(safe_redirect_url(url_for('admin_exams_list')))

    import re

    subjects_list = [
        name.strip().upper()
        for name in re.split(r'[\n,]+', subjects_raw)
        if name.strip()
    ]

    db = get_db()

    added = 0
    skipped = 0

    for subject_name in subjects_list:

        exists = db.execute(
            '''SELECT id FROM subjects
               WHERE class_name = ? AND subject_name = ?''',
            (class_name, subject_name)
        ).fetchone()

        if exists:
            skipped += 1
            continue

        db.execute(
            '''INSERT INTO subjects
               (class_name, subject_name, max_marks)
               VALUES (?, ?, ?)''',
            (class_name, subject_name, max_marks)
        )

        added += 1

    db.commit()

    if added:
        flash(
            f'{added} subject(s) added to {class_name}. '
            f'{skipped} duplicate(s) skipped.',
            'success'
        )
    else:
        flash('These subjects already exist.', 'error')

    return redirect(safe_redirect_url(url_for('admin_exams_list')))

@app.route('/admin/subjects/<int:sid>/delete', methods=['POST'])
@admin_required
def admin_delete_subject(sid):
    db = get_db()
    sub = db.execute('SELECT * FROM subjects WHERE id = ?', (sid,)).fetchone()
    if sub:
        db.execute('DELETE FROM exam_subjects WHERE subject_id = ?', (sid,))
        db.execute('''DELETE FROM exam_marks WHERE subject = ? AND student_id IN (
                        SELECT id FROM users WHERE role='student'
                        AND COALESCE(class_name, child_class) = ?)''',
                   (sub['subject_name'], sub['class_name']))
        db.execute('DELETE FROM subjects WHERE id = ?', (sid,))
        db.commit()
    flash('Subject deleted (and its marks).', 'success')
    return redirect(safe_redirect_url(url_for('admin_reports_dashboard')))


# ---------- REPORTS DASHBOARD ----------
@app.route('/admin/reports-dashboard')
@admin_required
def admin_reports_dashboard():
    db = get_db()
    selected_class = request.args.get('class', '').strip()
    selected_exam_id = request.args.get('exam_id', type=int)

    # 🚀 Saari standard + dynamic classes ki list
    class_list = get_all_classes(db)

    subjects = []
    if selected_class:
        # 🚀 Auto-seed missing common subjects for the selected class
        ensure_common_subjects(db, selected_class)

        subjects = db.execute(
            'SELECT * FROM subjects WHERE class_name = ? ORDER BY display_order, id',
            (selected_class,)).fetchall()

    all_exams = db.execute('SELECT * FROM exams ORDER BY id DESC').fetchall()
    if not selected_exam_id and all_exams:
        selected_exam_id = all_exams[0]['id']

    selected_exam = None
    if selected_exam_id:
        selected_exam = db.execute(
            'SELECT * FROM exams WHERE id = ?', (selected_exam_id,)).fetchone()

    return render_template('admin_reports_dashboard.html',
                           class_list=class_list,
                           selected_class=selected_class,
                           subjects=subjects,
                           all_exams=all_exams,
                           selected_exam=selected_exam,
                           selected_exam_id=selected_exam_id,
                           active_page='reports_dashboard')
    

# NEW: ADMIN VIEW SUBMITTED EXAM FORMS
@app.route('/admin/exam-forms')
@admin_required
def admin_exam_forms():
    db = get_db()
    forms = db.execute('''SELECT er.*, u.unique_id as student_uid 
                          FROM exam_registrations er 
                          LEFT JOIN users u ON er.student_id = u.id 
                          ORDER BY er.id DESC''').fetchall()
    
    parsed_forms = []
    for f in forms:
        f_dict = dict(f)
        try:
            f_dict['subjects_list'] = json.loads(f_dict['selected_subjects'])
        except:
            f_dict['subjects_list'] = []
        parsed_forms.append(f_dict)

    return render_template('admin_exam_forms.html', forms=parsed_forms, active_page='exam_forms')


# ---------- BULK MARKS ENTRY (admin) ----------
@app.route('/admin/bulk-marks-entry', methods=['GET', 'POST'])
@admin_required
def admin_bulk_marks_entry():
    db = get_db()
    class_name = (request.args.get('class') or request.form.get('class_name') or '').strip()
    exam_id = request.args.get('exam_id', type=int) or request.form.get('exam_id', type=int)

    if request.method == 'POST':
        exam = db.execute('SELECT * FROM exams WHERE id = ?', (exam_id,)).fetchone()
        if not exam:
            flash('Exam not found.', 'error')
            return redirect(url_for('admin_reports_dashboard'))

        students = db.execute(
            "SELECT * FROM users WHERE role='student' "
            "AND (class_name = ? OR child_class = ?) ORDER BY name",
            (class_name, class_name)).fetchall()
        subjects = db.execute(
            '''SELECT s.id, s.class_name, s.subject_name, es.max_marks, s.display_order
               FROM exam_subjects es JOIN subjects s ON s.id = es.subject_id
               WHERE es.exam_id = ? AND es.class_name = ?
               ORDER BY s.display_order, s.id''', (exam_id, class_name)).fetchall()

        for s in students:
            for sub in subjects:
                key = f"mark_{s['id']}_{sub['id']}"
                val = request.form.get(key, '').strip()
                existing = db.execute(
                    'SELECT id FROM exam_marks WHERE student_id=? AND subject=? AND exam_id=?',
                    (s['id'], sub['subject_name'], exam_id)).fetchone()

                if val == '':
                    if existing:
                        db.execute('DELETE FROM exam_marks WHERE id=?', (existing['id'],))
                else:
                    try:
                        m = float(val)
                    except (TypeError, ValueError):
                        db.rollback()
                        flash(f"Invalid marks entered for {s['name']} - {sub['subject_name']}.", 'error')
                        return redirect(url_for('teacher_marks_entry', eid=eid, **{'class': class_name}))
                    if not math.isfinite(m) or m < 0 or m > float(sub['max_marks']):
                        db.rollback()
                        flash(f"Marks for {s['name']} - {sub['subject_name']} must be between 0 and {sub['max_marks']}.", 'error')
                        return redirect(url_for('teacher_marks_entry', eid=eid, **{'class': class_name}))
                    if existing:
                        db.execute('UPDATE exam_marks SET marks_obtained=?, total_marks=? WHERE id=?',
                                   (m, sub['max_marks'], existing['id']))
                    else:
                        db.execute('''INSERT INTO exam_marks
                            (student_id, exam_type, subject, marks_obtained, total_marks, exam_id)
                            VALUES (?, ?, ?, ?, ?, ?)''',
                                   (s['id'], exam['title'], sub['subject_name'],
                                    m, sub['max_marks'], exam_id))

        db.execute('''INSERT OR IGNORE INTO exam_submissions (exam_id, class_name, status)
                     VALUES (?, ?, 'in_progress')''', (exam_id, class_name))
        db.execute('''UPDATE exam_submissions SET status='in_progress', teacher_id=?
                     WHERE exam_id=? AND class_name=?''',
                   (session['user_id'], exam_id, class_name))
        db.commit()
        flash('Marks saved successfully.', 'success')
        return redirect(url_for('admin_bulk_marks_entry', **{'class': class_name, 'exam_id': exam_id}))

    exam = db.execute('SELECT * FROM exams WHERE id = ?', (exam_id,)).fetchone() if exam_id else None
    students = db.execute(
        "SELECT * FROM users WHERE role='student' "
        "AND (class_name = ? OR child_class = ?) ORDER BY name",
        (class_name, class_name)).fetchall() if class_name else []
    subjects = db.execute(
        '''SELECT s.id, s.class_name, s.subject_name, es.max_marks, s.display_order
           FROM exam_subjects es JOIN subjects s ON s.id = es.subject_id
           WHERE es.exam_id = ? AND es.class_name = ?
           ORDER BY s.display_order, s.id''', (exam_id, class_name)).fetchall() if exam_id and class_name else []

    existing_marks = {}
    if exam_id and students and subjects:
        marks = db.execute('SELECT * FROM exam_marks WHERE exam_id = ?', (exam_id,)).fetchall()
        sub_by_name = {s['subject_name']: s for s in subjects}
        for m in marks:
            if m['subject'] in sub_by_name:
                existing_marks[f"{m['student_id']}_{sub_by_name[m['subject']]['id']}"] = m['marks_obtained']

    return render_template('admin_bulk_marks_entry.html',
                           class_name=class_name, exam=exam, exam_id=exam_id,
                           exam_type=exam['title'] if exam else '',
                           students=students, subjects=subjects,
                           existing_marks=existing_marks,
                           active_page='reports_dashboard')


# ---------- GENERATE REPORTS (individual preview) ----------
@app.route('/admin/generate-reports')
@admin_required
def admin_generate_reports():
    db = get_db()
    selected_class = request.args.get('class', '').strip()
    exam_id = request.args.get('exam_id', type=int)

    # 🚀 YAHAN FIX KIYA GAYA HAI
    class_list = get_all_classes(db)

    all_exams = db.execute('SELECT * FROM exams ORDER BY id DESC').fetchall()
    if not exam_id and all_exams:
        exam_id = all_exams[0]['id']

    exam = db.execute('SELECT * FROM exams WHERE id = ?', (exam_id,)).fetchone() if exam_id else None

    students = db.execute(
        "SELECT * FROM users WHERE role='student' "
        "AND (class_name = ? OR child_class = ?) ORDER BY name",
        (selected_class, selected_class)).fetchall() if selected_class else []

    return render_template('admin_generate_reports.html',
                           class_list=class_list, selected_class=selected_class,
                           students=students, all_exams=all_exams,
                           exam=exam, exam_id=exam_id,
                           active_page='generate_reports')

# ---------- REPORT CARD PRINT (individual) ----------
@app.route('/admin/print-report/<int:student_id>')
@admin_required
def print_report_card(student_id):
    db = get_db()
    student = db.execute("SELECT * FROM users WHERE id=? AND role='student'", (student_id,)).fetchone()
    if not student:
        flash('Student not found.', 'error')
        return redirect(url_for('admin_reports_dashboard'))

    exam_id = request.args.get('exam_id', type=int)
    if exam_id:
        exam = db.execute('SELECT * FROM exams WHERE id=?', (exam_id,)).fetchone()
    else:
        exam = db.execute("SELECT * FROM exams WHERE status='published' ORDER BY id DESC LIMIT 1").fetchone()
    if not exam:
        flash('No exam selected or published.', 'error')
        return redirect(url_for('admin_reports_dashboard'))

    cls = student['class_name'] or student['child_class']
    subjects = db.execute(
        '''SELECT s.id, s.class_name, s.subject_name, es.max_marks, s.display_order
           FROM exam_subjects es JOIN subjects s ON s.id = es.subject_id
           WHERE es.exam_id=? AND es.class_name=?
           ORDER BY s.display_order, s.id''', (exam['id'], cls)).fetchall()
    marks = db.execute('SELECT * FROM exam_marks WHERE student_id=? AND exam_id=?',
                       (student_id, exam['id'])).fetchall()
    marks_map = {m['subject']: m['marks_obtained'] for m in marks}

    return render_template('report_card_print.html',
                           students=[student], exam=exam,
                           subjects=subjects, class_name=cls,
                           marks_by_student={student_id: marks_map})


# ---------- REPORT CARD PRINT (bulk, 2 per A4 landscape page) ----------
@app.route('/admin/print-all-reports')
@admin_required
def admin_print_all_reports():
    db = get_db()
    cls = request.args.get('class', '').strip()
    exam_id = request.args.get('exam_id', type=int)
    if not cls:
        flash('Class is required.', 'error')
        return redirect(url_for('admin_reports_dashboard'))

    if exam_id:
        exam = db.execute('SELECT * FROM exams WHERE id=?', (exam_id,)).fetchone()
    else:
        exam = db.execute("SELECT * FROM exams WHERE status='published' ORDER BY id DESC LIMIT 1").fetchone()
    if not exam:
        flash('No exam selected.', 'error')
        return redirect(url_for('admin_reports_dashboard'))

    students = db.execute(
        "SELECT * FROM users WHERE role='student' "
        "AND (class_name = ? OR child_class = ?) ORDER BY name",
        (cls, cls)).fetchall()
    subjects = db.execute(
        '''SELECT s.id, s.class_name, s.subject_name, es.max_marks, s.display_order
           FROM exam_subjects es JOIN subjects s ON s.id = es.subject_id
           WHERE es.exam_id=? AND es.class_name=?
           ORDER BY s.display_order, s.id''', (exam['id'], cls)).fetchall()
    marks = db.execute('SELECT * FROM exam_marks WHERE exam_id=?', (exam['id'],)).fetchall()

    marks_by_student = {}
    for m in marks:
        marks_by_student.setdefault(m['student_id'], {})[m['subject']] = m['marks_obtained']

    return render_template('report_card_print.html',
                           students=students, exam=exam,
                           subjects=subjects, class_name=cls,
                           marks_by_student=marks_by_student)


# =========================================
# EXAM SYSTEM — TEACHER ROUTES
# =========================================

@app.route('/teacher/exams')
@login_required
def teacher_exams():
    user = get_user_by_id(session['user_id'])
    if not user or user['role'] != 'teacher':
        flash('Access denied.', 'error')
        return redirect(url_for('user_dashboard'))

    db = get_db()
    exams = db.execute(
        "SELECT * FROM exams WHERE status='published' ORDER BY published_at DESC").fetchall()

    raw = user['classes_assigned'] or ''
    teacher_classes = [c.strip() for c in raw.split(',') if c.strip()]

    exam_info = []
    for exam in exams:
        subs = []
        for cls in teacher_classes:
            sub = db.execute(
                'SELECT * FROM exam_submissions WHERE exam_id=? AND class_name=?',
                (exam['id'], cls)).fetchone()
            if sub:
                subs.append({'class_name': cls, 'status': sub['status'], 'sub': sub})
        if subs:
            exam_info.append({'exam': exam, 'subs': subs})

    return render_template('teacher_exams.html', user=user, exam_info=exam_info)


@app.route('/teacher/exams/<int:eid>/marks', methods=['GET', 'POST'])
@login_required
def teacher_marks_entry(eid):
    user = get_user_by_id(session['user_id'])
    if not user or user['role'] != 'teacher':
        flash('Access denied.', 'error')
        return redirect(url_for('user_dashboard'))

    db = get_db()
    exam = db.execute('SELECT * FROM exams WHERE id=?', (eid,)).fetchone()
    if not exam:
        flash('Exam not found.', 'error')
        return redirect(url_for('teacher_exams'))

    raw = user['classes_assigned'] or ''
    teacher_classes = [c.strip() for c in raw.split(',') if c.strip()]

    class_name = (request.args.get('class') or request.form.get('class') or '').strip()
    if not class_name or class_name not in teacher_classes:
        flash('Aap is class ke liye assigned nahi hain.', 'error')
        return redirect(url_for('teacher_exams'))

    if request.method == 'POST':
        students = db.execute(
            "SELECT * FROM users WHERE role='student' "
            "AND (class_name = ? OR child_class = ?) ORDER BY name",
            (class_name, class_name)).fetchall()
        subjects = db.execute(
            '''SELECT s.id, s.class_name, s.subject_name, es.max_marks, s.display_order
               FROM exam_subjects es JOIN subjects s ON s.id = es.subject_id
               WHERE es.exam_id = ? AND es.class_name = ?
               ORDER BY s.display_order, s.id''', (eid, class_name)).fetchall()

        for s in students:
            for sub in subjects:
                key = f"mark_{s['id']}_{sub['id']}"
                val = request.form.get(key, '').strip()
                existing = db.execute(
                    'SELECT id FROM exam_marks WHERE student_id=? AND subject=? AND exam_id=?',
                    (s['id'], sub['subject_name'], eid)).fetchone()

                if val == '':
                    if existing:
                        db.execute('DELETE FROM exam_marks WHERE id=?', (existing['id'],))
                else:
                    try:
                        m = float(val)
                    except ValueError:
                        continue
                    if existing:
                        db.execute('UPDATE exam_marks SET marks_obtained=?, total_marks=? WHERE id=?',
                                   (m, sub['max_marks'], existing['id']))
                    else:
                        db.execute('''INSERT INTO exam_marks
                            (student_id, exam_type, subject, marks_obtained, total_marks, exam_id)
                            VALUES (?, ?, ?, ?, ?, ?)''',
                                   (s['id'], exam['title'], sub['subject_name'],
                                    m, sub['max_marks'], eid))

        action = (request.form.get('action') or 'draft').strip().lower()
        if action not in {'draft', 'submit'}:
            db.rollback()
            flash('Invalid marks submission action.', 'error')
            return redirect(url_for('teacher_marks_entry', eid=eid, **{'class': class_name}))
        new_status = 'submitted' if action == 'submit' else 'in_progress'
        db.execute('''INSERT OR IGNORE INTO exam_submissions
                     (exam_id, class_name, teacher_id, status)
                     VALUES (?, ?, ?, ?)''', (eid, class_name, user['id'], new_status))
        db.execute('''UPDATE exam_submissions SET status=?, teacher_id=?
                     WHERE exam_id=? AND class_name=?''',
                   (new_status, user['id'], eid, class_name))
        if action == 'submit':
            db.execute("UPDATE exam_submissions SET submitted_at=? WHERE exam_id=? AND class_name=?",
                       (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), eid, class_name))
        db.commit()

        flash('Marks submitted to admin!' if action == 'submit' else 'Draft saved.',
              'success')
        if action == 'submit':
            return redirect(url_for('teacher_exams'))
        return redirect(url_for('teacher_marks_entry', eid=eid, **{'class': class_name}))

    students = db.execute(
        "SELECT * FROM users WHERE role='student' "
        "AND (class_name = ? OR child_class = ?) ORDER BY name",
        (class_name, class_name)).fetchall()
    subjects = db.execute(
        '''SELECT s.id, s.class_name, s.subject_name, es.max_marks, s.display_order
           FROM exam_subjects es JOIN subjects s ON s.id = es.subject_id
           WHERE es.exam_id = ? AND es.class_name = ?
           ORDER BY s.display_order, s.id''', (eid, class_name)).fetchall()
    marks = db.execute('SELECT * FROM exam_marks WHERE exam_id=?', (eid,)).fetchall()

    sub_by_name = {s['subject_name']: s for s in subjects}
    existing_marks = {}
    for m in marks:
        if m['subject'] in sub_by_name:
            existing_marks[f"{m['student_id']}_{sub_by_name[m['subject']]['id']}"] = m['marks_obtained']

    submission = db.execute(
        'SELECT * FROM exam_submissions WHERE exam_id=? AND class_name=?',
        (eid, class_name)).fetchone()

    return render_template('teacher_marks_entry.html',
                           user=user, exam=exam, class_name=class_name,
                           students=students, subjects=subjects,
                           existing_marks=existing_marks,
                           submission=submission,
                           teacher_classes=teacher_classes)


# =========================================
# INIT
# =========================================
init_db()

if __name__ == '__main__':
    app.run(
        debug=False,
        use_reloader=False,
        host=os.environ.get('HOST', '127.0.0.1'),
        port=int(os.environ.get('PORT', 5000))
    )
