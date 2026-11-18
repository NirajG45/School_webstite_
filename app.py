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
from datetime import timedelta, datetime, date
from flask import (Flask, render_template, request, redirect, url_for, flash, jsonify, g, session)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image, ImageOps
import io
import hmac
import logging
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
    raise RuntimeError("SECRET_KEY missing or too short. Check your .env file.")

IS_PRODUCTION = os.environ.get('FLASK_ENV', '').lower() == 'production'
app.config.update(
    SECRET_KEY=secret_key,
    MAX_CONTENT_LENGTH=20 * 1024 * 1024,
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

UPLOAD_FOLDER = BASE_DIR / 'static' / 'uploads'
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    if not filename or not isinstance(filename, str) or len(filename) > 255:
        return False
    clean = secure_filename(filename)
    return bool(clean and '.' in clean and clean.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS)

@app.template_filter('month_abbr')
def month_abbr(date_str):
    months = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC']
    try:
        return months[int(str(date_str)[5:7]) - 1]
    except (ValueError, IndexError, TypeError):
        return ''

# =========================================
# 1.5. USER TABLE — EXTRA COLUMNS
# =========================================
USER_EXTRA_COLUMNS = {
    'blood_group': 'TEXT', 'marital_status': 'TEXT', 'aadhar': 'TEXT', 'pan': 'TEXT',
    'nationality': 'TEXT', 'mother_tongue': 'TEXT', 'alternate_mobile': 'TEXT', 'whatsapp': 'TEXT',
    'city': 'TEXT', 'state': 'TEXT', 'pincode': 'TEXT', 'photo_url': 'TEXT',
    'specialization': 'TEXT', 'classes_assigned': 'TEXT', 'languages': 'TEXT',
    'employee_id': 'TEXT', 'joining_date': 'TEXT', 'employment_type': 'TEXT',
    'total_experience': 'TEXT', 'previous_school': 'TEXT', 'salary': 'TEXT', 
    'bank_name': 'TEXT', 'account_number': 'TEXT', 'ifsc': 'TEXT',
    'emergency_name': 'TEXT', 'emergency_contact': 'TEXT', 'notes': 'TEXT',
    'reporting_to': 'TEXT', 'occupation': 'TEXT', 'education': 'TEXT', 'annual_income': 'TEXT',
    'spouse_name': 'TEXT', 'spouse_occupation': 'TEXT', 'spouse_mobile': 'TEXT',
    'office_phone': 'TEXT', 'office_address': 'TEXT', 'child_admission_no': 'TEXT', 'child_section': 'TEXT', 'child_dob': 'TEXT',
    'admission_no': 'TEXT', 'roll_no': 'TEXT', 'admission_date': 'TEXT',
    'class_name': 'TEXT', 'section': 'TEXT', 'previous_class': 'TEXT', 'previous_percentage': 'TEXT',
    'category': 'TEXT', 'religion': 'TEXT', 'father_name': 'TEXT', 'father_occupation': 'TEXT', 'father_mobile': 'TEXT',
    'father_email': 'TEXT', 'father_education': 'TEXT', 'mother_name': 'TEXT', 'mother_occupation': 'TEXT', 'mother_mobile': 'TEXT',
    'mother_email': 'TEXT', 'mother_education': 'TEXT', 'guardian_name': 'TEXT', 'guardian_relation': 'TEXT', 'guardian_mobile': 'TEXT',
    'allergies': 'TEXT', 'medical_conditions': 'TEXT', 'disability': 'TEXT',
    'transport_route': 'TEXT', 'pickup_point': 'TEXT', 'vehicle_no': 'TEXT',
    'sibling_name': 'TEXT', 'sibling_class': 'TEXT', 'hobbies': 'TEXT',
}

COMMON_FIELDS = ['dob', 'gender', 'blood_group', 'marital_status', 'aadhar', 'pan', 'nationality', 'mother_tongue', 'email', 'phone', 'alternate_mobile', 'whatsapp', 'address', 'city', 'state', 'pincode']
TEACHER_FIELDS = ['qualification', 'specialization', 'experience', 'subject', 'classes_assigned', 'languages', 'employee_id', 'designation', 'joining_date', 'employment_type', 'total_experience', 'previous_school', 'salary', 'bank_name', 'account_number', 'ifsc', 'emergency_name', 'emergency_contact', 'notes']
ADMIN_FIELDS = ['designation', 'department', 'employee_id', 'joining_date', 'employment_type', 'reporting_to', 'salary', 'bank_name', 'account_number', 'ifsc', 'emergency_name', 'emergency_contact']
PARENT_FIELDS = ['relation', 'occupation', 'education', 'annual_income', 'spouse_name', 'spouse_occupation', 'spouse_mobile', 'office_phone', 'office_address', 'child_name', 'child_admission_no', 'child_class', 'child_section', 'child_dob', 'emergency_name', 'emergency_contact']
STUDENT_FIELDS = ['admission_no', 'roll_no', 'admission_date', 'class_name', 'section', 'previous_school', 'previous_class', 'previous_percentage', 'category', 'religion', 'father_name', 'father_occupation', 'father_mobile', 'father_email', 'father_education', 'mother_name', 'mother_occupation', 'mother_mobile', 'mother_email', 'mother_education', 'guardian_name', 'guardian_relation', 'guardian_mobile', 'emergency_contact', 'allergies', 'medical_conditions', 'disability', 'transport_route', 'pickup_point', 'vehicle_no', 'account_number', 'bank_name', 'ifsc', 'sibling_name', 'sibling_class', 'hobbies']

ROLE_FIELDS = {
    'teacher': TEACHER_FIELDS, 'admin': ADMIN_FIELDS, 'administrator': ADMIN_FIELDS,
    'parent': PARENT_FIELDS, 'student': STUDENT_FIELDS,
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
    existing = {row[1] for row in db.execute("PRAGMA table_info(users)").fetchall()}
    for col, coltype in USER_EXTRA_COLUMNS.items():
        if col not in existing:
            db.execute(f'ALTER TABLE users ADD COLUMN {col} {coltype}')

def migrate_attendance_table(db):
    existing = {row[1] for row in db.execute("PRAGMA table_info(attendance)").fetchall()}
    if 'subject' not in existing:
        db.execute("ALTER TABLE attendance ADD COLUMN subject TEXT DEFAULT 'General'")

def migrate_faculty_table(db):
    existing = {row[1] for row in db.execute("PRAGMA table_info(faculty)").fetchall()}
    if 'user_id' not in existing:
        db.execute('ALTER TABLE faculty ADD COLUMN user_id INTEGER')
    teachers = db.execute("SELECT id, name, subject, qualification, experience, photo_url FROM users WHERE role='teacher'").fetchall()
    for t in teachers:
        if not db.execute("SELECT 1 FROM faculty WHERE user_id = ? OR name = ?", (t['id'], t['name'])).fetchone():
            db.execute('''INSERT INTO faculty (user_id, name, subject, qualification, experience, photo_url) VALUES (?, ?, ?, ?, ?, ?)''',
                       (t['id'], t['name'], t['subject'] or 'General', t['qualification'] or '', t['experience'] or '', t['photo_url']))

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        db.execute('''CREATE TABLE IF NOT EXISTS enquiries (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, name TEXT NOT NULL, phone TEXT NOT NULL, email TEXT, class_name TEXT, message TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        db.execute('''CREATE TABLE IF NOT EXISTS notices (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, title TEXT NOT NULL, tag TEXT NOT NULL, description TEXT, target_role TEXT DEFAULT 'all', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        db.execute('''CREATE TABLE IF NOT EXISTS login_attempts (attempt_key TEXT PRIMARY KEY, failures INTEGER NOT NULL DEFAULT 0, window_started REAL NOT NULL, blocked_until REAL NOT NULL DEFAULT 0)''')
        db.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, unique_id TEXT UNIQUE, role TEXT NOT NULL, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, phone TEXT NOT NULL, password_hash TEXT NOT NULL, force_password_change INTEGER DEFAULT 1, dob TEXT, gender TEXT, qualification TEXT, experience TEXT, subject TEXT, designation TEXT, department TEXT, relation TEXT, child_name TEXT, child_class TEXT, address TEXT, is_active INTEGER DEFAULT 1, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        
        migrate_users_table(db)
        
        db.execute('''CREATE TABLE IF NOT EXISTS leave_requests (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, leave_type TEXT NOT NULL, from_date TEXT NOT NULL, to_date TEXT NOT NULL, reason TEXT NOT NULL, status TEXT DEFAULT 'pending', admin_remarks TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        db.execute('''CREATE TABLE IF NOT EXISTS attendance (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, date TEXT NOT NULL, status TEXT NOT NULL, subject TEXT DEFAULT 'General', remarks TEXT, marked_by INTEGER, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        migrate_attendance_table(db)
        db.execute('''CREATE TABLE IF NOT EXISTS exam_marks (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL, exam_type TEXT NOT NULL, subject TEXT NOT NULL, marks_obtained REAL NOT NULL, total_marks REAL NOT NULL DEFAULT 100, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        db.execute('''CREATE TABLE IF NOT EXISTS fee_payments (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL, amount REAL NOT NULL, payment_date TEXT NOT NULL, transaction_id TEXT, status TEXT DEFAULT 'pending', remarks TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        db.execute('''CREATE TABLE IF NOT EXISTS school_settings (key TEXT PRIMARY KEY, value TEXT)''')
        db.execute('''CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, from_user_id INTEGER NOT NULL, to_user_id INTEGER, to_role TEXT, subject TEXT NOT NULL, body TEXT NOT NULL, is_read INTEGER DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        db.execute('''CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT, event_date TEXT NOT NULL, event_time TEXT, location TEXT, category TEXT DEFAULT 'general', is_featured INTEGER DEFAULT 0, cover_image_url TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        db.execute('''CREATE TABLE IF NOT EXISTS event_participants (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL, student_id INTEGER NOT NULL, role TEXT DEFAULT 'participant', added_on TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE CASCADE, FOREIGN KEY(student_id) REFERENCES users (id) ON DELETE CASCADE, UNIQUE(event_id, student_id))''')
        db.execute('''CREATE TABLE IF NOT EXISTS event_certificates (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL, student_id INTEGER NOT NULL, certificate_type TEXT DEFAULT 'participation', position TEXT, issued_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(event_id, student_id), FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE, FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE)''')
        db.execute('''CREATE TABLE IF NOT EXISTS faculty (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT NOT NULL, subject TEXT NOT NULL, qualification TEXT, experience TEXT, photo_url TEXT, bio TEXT, display_order INTEGER DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        migrate_faculty_table(db)
        db.execute('''CREATE TABLE IF NOT EXISTS testimonials (id INTEGER PRIMARY KEY AUTOINCREMENT, author_name TEXT NOT NULL, author_role TEXT DEFAULT 'Parent', message TEXT NOT NULL, rating INTEGER DEFAULT 5, is_approved INTEGER DEFAULT 1, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        db.execute('''CREATE TABLE IF NOT EXISTS achievements (id INTEGER PRIMARY KEY AUTOINCREMENT, student_name TEXT NOT NULL, class_name TEXT, achievement TEXT NOT NULL, year TEXT, category TEXT DEFAULT 'academic', photo_url TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        db.execute('''CREATE TABLE IF NOT EXISTS gallery (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, image_url TEXT NOT NULL, category TEXT DEFAULT 'campus', display_order INTEGER DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        db.execute('''CREATE TABLE IF NOT EXISTS faq (id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT NOT NULL, answer TEXT NOT NULL, display_order INTEGER DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        db.execute('''CREATE TABLE IF NOT EXISTS homework (id INTEGER PRIMARY KEY AUTOINCREMENT, class_name TEXT NOT NULL, subject TEXT NOT NULL, title TEXT NOT NULL, description TEXT, due_date TEXT, assigned_by INTEGER, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        db.execute('''CREATE TABLE IF NOT EXISTS study_materials (id INTEGER PRIMARY KEY AUTOINCREMENT, class_name TEXT NOT NULL, subject TEXT, title TEXT NOT NULL, description TEXT, file_url TEXT, external_link TEXT, material_type TEXT DEFAULT 'notes', uploaded_by INTEGER, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        db.execute('''CREATE TABLE IF NOT EXISTS faculty_subject_assignments (id INTEGER PRIMARY KEY AUTOINCREMENT, faculty_id INTEGER NOT NULL, class_name TEXT NOT NULL, day TEXT NOT NULL, subject TEXT NOT NULL, period TEXT, room TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE CASCADE)''')
        
        # EXAM SYSTEM TABLES
        db.execute('''CREATE TABLE IF NOT EXISTS subjects (id INTEGER PRIMARY KEY AUTOINCREMENT, class_name TEXT NOT NULL, subject_name TEXT NOT NULL, max_marks REAL NOT NULL DEFAULT 50, display_order INTEGER DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        db.execute('''CREATE TABLE IF NOT EXISTS exams (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, academic_year TEXT, term_label TEXT DEFAULT '2nd TERM', notice_text TEXT, custom_message TEXT, status TEXT DEFAULT 'draft', created_by INTEGER, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, published_at TEXT)''')
        db.execute('''CREATE TABLE IF NOT EXISTS exam_subjects (id INTEGER PRIMARY KEY AUTOINCREMENT, exam_id INTEGER NOT NULL, class_name TEXT NOT NULL, subject_id INTEGER NOT NULL, max_marks REAL NOT NULL DEFAULT 50, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(exam_id, class_name, subject_id), FOREIGN KEY(exam_id) REFERENCES exams(id) ON DELETE CASCADE, FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE)''')
        
        _exam_subjects_cols = {row[1] for row in db.execute("PRAGMA table_info(exam_subjects)").fetchall()}
        if 'max_marks' not in _exam_subjects_cols:
            db.execute("ALTER TABLE exam_subjects ADD COLUMN max_marks REAL NOT NULL DEFAULT 50")
            
        db.execute('''CREATE TABLE IF NOT EXISTS exam_submissions (id INTEGER PRIMARY KEY AUTOINCREMENT, exam_id INTEGER NOT NULL, class_name TEXT NOT NULL, teacher_id INTEGER, status TEXT DEFAULT 'pending', submitted_at TEXT, UNIQUE(exam_id, class_name))''')
        db.execute('''CREATE TABLE IF NOT EXISTS exam_registrations (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER, student_name TEXT NOT NULL, father_name TEXT NOT NULL, mother_name TEXT, dob TEXT, gender TEXT, class_name TEXT, section TEXT, roll_no TEXT, admission_no TEXT, student_mobile TEXT, parent_mobile TEXT NOT NULL, address TEXT, exam_type TEXT, selected_subjects TEXT, status TEXT DEFAULT 'pending', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        
        _exam_reg_cols = {row[1] for row in db.execute("PRAGMA table_info(exam_registrations)").fetchall()}
        if 'declaration_accepted' not in _exam_reg_cols:
            db.execute("ALTER TABLE exam_registrations ADD COLUMN declaration_accepted INTEGER DEFAULT 0")
        
        db.execute('DROP INDEX IF EXISTS idx_exam_reg_unique')
        db.execute('''DELETE FROM exam_registrations WHERE id NOT IN (SELECT MAX(id) FROM exam_registrations GROUP BY student_id, exam_type)''')
        db.execute('''CREATE UNIQUE INDEX IF NOT EXISTS idx_exam_reg_unique ON exam_registrations (student_id, exam_type)''')

        # QUESTION PAPERS TABLES
        db.execute('''CREATE TABLE IF NOT EXISTS exam_papers (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, class_name TEXT NOT NULL, subject TEXT NOT NULL, time_allowed TEXT, max_marks INTEGER, exam_year TEXT, teacher_id INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        db.execute('''CREATE TABLE IF NOT EXISTS exam_questions (id INTEGER PRIMARY KEY AUTOINCREMENT, paper_id INTEGER NOT NULL, section_name TEXT NOT NULL, question_text TEXT NOT NULL, options TEXT, marks INTEGER NOT NULL DEFAULT 1, lines INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(paper_id) REFERENCES exam_papers(id) ON DELETE CASCADE)''')
        
        _question_cols = {row[1] for row in db.execute("PRAGMA table_info(exam_questions)").fetchall()}
        if 'lines' not in _question_cols:
            db.execute("ALTER TABLE exam_questions ADD COLUMN lines INTEGER NOT NULL DEFAULT 1")
            
        _mcols = {row[1] for row in db.execute("PRAGMA table_info(exam_marks)").fetchall()}
        if 'exam_id' not in _mcols:
            db.execute('ALTER TABLE exam_marks ADD COLUMN exam_id INTEGER')

        # Default settings
        db.execute("INSERT OR IGNORE INTO school_settings (key, value) VALUES ('fee_qr_url', '')")
        db.execute("INSERT OR IGNORE INTO school_settings (key, value) VALUES ('school_name', 'RES. SHANTI NIKETAN SHISHU VIDYA MANDIR')")
        db.execute("INSERT OR IGNORE INTO school_settings (key, value) VALUES ('school_address', 'NAVINAGAR (JAMUI)')")
        db.execute("INSERT OR IGNORE INTO school_settings (key, value) VALUES ('upi_link', '')")
        db.commit()

COMMON_SUBJECTS = [('HINDI', 100), ('ENGLISH', 100), ('MATH', 100), ('SCIENCE', 100), ('GRAMMAR', 100), ('GK/NETHIK SHIKSHA', 100), ('DRAWING', 100)]

def ensure_common_subjects(db, class_name):
    if not class_name: return 0
    class_name = str(class_name).strip()
    if not class_name: return 0
    existing_names = {row['subject_name'] for row in db.execute('SELECT subject_name FROM subjects WHERE class_name = ?', (class_name,)).fetchall()}
    added = 0
    for subject_name, default_max in COMMON_SUBJECTS:
        if subject_name in existing_names: continue
        db.execute('INSERT INTO subjects (class_name, subject_name, max_marks) VALUES (?, ?, ?)', (class_name, subject_name, default_max))
        added += 1
    if added: db.commit()
    return added

def get_all_classes(db):
    standard_classes = ['Pre-Nursery', 'Nursery', 'LKG', 'UKG', '1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th']
    class_rows = db.execute('''SELECT class_name AS c FROM subjects UNION SELECT COALESCE(class_name, child_class) AS c FROM users WHERE role='student' AND COALESCE(class_name, child_class) IS NOT NULL AND COALESCE(class_name, child_class) != '' ''').fetchall()
    dynamic_classes = {row['c'] for row in class_rows if row['c']}
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
    return get_db().execute('SELECT * FROM users WHERE id = ?', (uid,)).fetchone()

def get_user_by_unique_id(uid):
    return get_db().execute('SELECT * FROM users WHERE unique_id = ?', (uid,)).fetchone()

def generate_unique_id(role):
    db = get_db()
    prefixes = {'admin': 'SNV', 'administrator': 'SNV', 'teacher': 'SNVT', 'parent': 'SNVP', 'student': 'SNVST'}
    prefix = prefixes.get(role, 'SNV')
    last = db.execute("SELECT unique_id FROM users WHERE unique_id LIKE ? ORDER BY id DESC LIMIT 1", (prefix + '%',)).fetchone()
    if last and last['unique_id']:
        try: num = int(last['unique_id'].replace(prefix, '')) + 1
        except: num = 1
    else: num = 1
    while True:
        new_id = f"{prefix}{str(num).zfill(5)}"
        if not db.execute('SELECT 1 FROM users WHERE unique_id = ?', (new_id,)).fetchone(): return new_id
        num += 1

def get_setting(key, default=''):
    row = get_db().execute('SELECT value FROM school_settings WHERE key = ?', (key,)).fetchone()
    return row['value'] if row else default

def set_setting(key, value):
    db = get_db()
    db.execute('INSERT OR REPLACE INTO school_settings (key, value) VALUES (?, ?)', (key, value))
    db.commit()

def safe_redirect_url(default_url):
    referrer = request.referrer
    if not referrer: return default_url
    try:
        parsed = urlparse(referrer)
        host = request.host.split(':', 1)[0].lower()
        if parsed.scheme in {'http', 'https'} and parsed.hostname and parsed.hostname.lower() == host: return referrer
    except (TypeError, ValueError): pass
    return default_url

def get_combined_faculty():
    db = get_db()
    teachers = db.execute("SELECT id, name, subject, qualification, experience, photo_url FROM users WHERE role='teacher' AND is_active = 1").fetchall()
    for t in teachers:
        existing = db.execute('SELECT id FROM faculty WHERE user_id = ?', (t['id'],)).fetchone()
        if not existing:
            existing = db.execute('SELECT id FROM faculty WHERE name = ?', (t['name'],)).fetchone()
            if existing: db.execute('UPDATE faculty SET user_id = ? WHERE id = ?', (t['id'], existing['id']))
            else: db.execute('INSERT INTO faculty (user_id, name, subject, qualification, experience, photo_url, bio) VALUES (?, ?, ?, ?, ?, ?, ?)', (t['id'], t['name'], t['subject'] or 'General', t['qualification'] or '', t['experience'] or '', t['photo_url'], 'Dedicated teacher at Residential Shanti Niketan.'))
    db.commit()
    return [dict(r) for r in db.execute('SELECT id, user_id, name, subject, qualification, experience, photo_url, bio, display_order FROM faculty ORDER BY display_order, id').fetchall()]

def get_parent_child(db, parent_user):
    if not parent_user: return None
    if parent_user['child_admission_no']:
        row = db.execute("SELECT * FROM users WHERE role='student' AND admission_no = ? LIMIT 1", (parent_user['child_admission_no'],)).fetchone()
        if row: return row
    if parent_user['child_name'] and parent_user['child_class']:
        return db.execute("SELECT * FROM users WHERE role='student' AND LOWER(name) = LOWER(?) AND (class_name = ? OR child_class = ?) LIMIT 1", (parent_user['child_name'], parent_user['child_class'], parent_user['child_class'])).fetchone()
    return None

def _get_accessible_question_paper(db, user, paper_id):
    if not user: return None
    if user['role'] in ('admin', 'administrator'): return db.execute('SELECT * FROM exam_papers WHERE id = ?', (paper_id,)).fetchone()
    return db.execute('SELECT * FROM exam_papers WHERE id = ? AND teacher_id = ?', (paper_id, user['id'])).fetchone()

def get_teacher_subject_grid(db, teacher_id):
    user = db.execute('SELECT classes_assigned FROM users WHERE id = ?', (teacher_id,)).fetchone()
    if not user or not user['classes_assigned']: return []
    classes = [c.strip() for c in user['classes_assigned'].split(',') if c.strip()]
    if not classes: return []
    ph = ','.join(['?'] * len(classes))
    rows = db.execute(f'''SELECT DISTINCT es.class_name, s.subject_name, s.id AS subject_id, s.display_order FROM exam_subjects es JOIN exams e ON es.exam_id = e.id JOIN subjects s ON es.subject_id = s.id WHERE e.status = 'published' AND es.class_name IN ({ph}) ORDER BY es.class_name, s.display_order, s.subject_name''', tuple(classes)).fetchall()
    papers = db.execute('SELECT id, class_name, subject FROM exam_papers WHERE teacher_id = ?', (teacher_id,)).fetchall()
    paper_lookup = {(p['class_name'], p['subject']): p['id'] for p in papers}
    question_counts = {}
    if paper_lookup:
        ids = list(paper_lookup.values()); qph = ','.join(['?'] * len(ids))
        for row in db.execute(f'SELECT paper_id, COUNT(*) AS c FROM exam_questions WHERE paper_id IN ({qph}) GROUP BY paper_id', tuple(ids)).fetchall():
            question_counts[row['paper_id']] = row['c']
    grid, seen = [], set()
    for r in rows:
        key = (r['class_name'], r['subject_name'])
        if key in seen: continue
        seen.add(key)
        pid = paper_lookup.get(key)
        grid.append({'class_name': r['class_name'], 'subject_name': r['subject_name'], 'subject_id': r['subject_id'], 'paper_id': pid, 'question_count': question_counts.get(pid, 0) if pid else 0})
    return grid

# =========================================
# 4. DECORATORS & CONTEXT
# =========================================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        uid = session.get('user_id')
        if not uid: flash('Please login to access this page.', 'error'); return redirect(url_for('login_page'))
        user = get_user_by_id(uid)
        if not user or not user['is_active']: session.clear(); flash('Your session is no longer valid.', 'error'); return redirect(url_for('login_page'))
        if user['force_password_change'] and request.endpoint not in ('change_password', 'logout', 'static'): flash('Please change your password.', 'error'); return redirect(url_for('change_password'))
        session['user_role'] = user['role']
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        uid = session.get('user_id')
        if not uid: flash('Please login to access admin panel.', 'error'); return redirect(url_for('login_page'))
        user = get_user_by_id(uid)
        if not user or not user['is_active']: session.clear(); flash('Your session is no longer valid.', 'error'); return redirect(url_for('login_page'))
        if user['role'] not in ('admin', 'administrator'): flash('Access denied.', 'error'); return redirect(url_for('user_dashboard'))
        session['user_role'] = user['role']
        if user['force_password_change']: flash('Please change your password.', 'error'); return redirect(url_for('change_password'))
        return f(*args, **kwargs)
    return decorated

def get_dashboard_url(role):
    return url_for('admin_dashboard') if role in ('admin', 'administrator') else url_for('user_dashboard')

@app.context_processor
def inject_admin_sidebar_counts():
    if not session.get('user_id') or session.get('user_role') not in ('admin', 'administrator'): return {}
    try:
        db = get_db()
        return {'pending_leaves': db.execute("SELECT COUNT(*) FROM leave_requests WHERE status='pending'").fetchone()[0], 'pending_fees': db.execute("SELECT COUNT(*) FROM fee_payments WHERE status='pending'").fetchone()[0], 'total_homework': db.execute("SELECT COUNT(*) FROM homework").fetchone()[0], 'total_study_materials': db.execute("SELECT COUNT(*) FROM study_materials").fetchone()[0], 'total_assignments': db.execute("SELECT COUNT(*) FROM faculty_subject_assignments").fetchone()[0]}
    except: return {}

@app.context_processor
def inject_exam_pending_counts():
    default = {'pending_exam_submissions': 0, 'pending_exam_marks': 0, 'total_question_papers': 0, 'my_question_papers': 0}
    if not session.get('user_id'): return default
    role = session.get('user_role')
    try:
        db = get_db()
        if role in ('admin', 'administrator'):
            return {'pending_exam_submissions': db.execute("SELECT COUNT(*) FROM exam_submissions es JOIN exams e ON es.exam_id = e.id WHERE e.status='published' AND es.status IN ('pending', 'in_progress')").fetchone()[0] or 0, 'pending_exam_marks': 0, 'total_question_papers': db.execute("SELECT COUNT(*) FROM exam_papers").fetchone()[0] or 0, 'my_question_papers': 0}
        if role == 'teacher':
            user = db.execute('SELECT classes_assigned FROM users WHERE id = ?', (session['user_id'],)).fetchone()
            my_qp = db.execute("SELECT COUNT(*) FROM exam_papers WHERE teacher_id = ?", (session['user_id'],)).fetchone()[0] or 0
            if not user or not user['classes_assigned']: return {'pending_exam_submissions': 0, 'pending_exam_marks': 0, 'total_question_papers': 0, 'my_question_papers': my_qp}
            classes = [c.strip() for c in user['classes_assigned'].split(',') if c.strip()]
            ph = ','.join(['?'] * len(classes))
            count = db.execute(f"SELECT COUNT(*) FROM exam_submissions es JOIN exams e ON es.exam_id = e.id WHERE e.status='published' AND es.status IN ('pending', 'in_progress') AND es.class_name IN ({ph})", tuple(classes)).fetchone()[0] or 0
            return {'pending_exam_submissions': 0, 'pending_exam_marks': count, 'total_question_papers': 0, 'my_question_papers': my_qp}
    except: pass
    return default

@app.before_request
def sync_session_user_info():
    if session.get('user_id'):
        user = get_db().execute('SELECT id, photo_url, name, role, is_active FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if not user or not user['is_active']: session.clear(); return None
        session.update({'photo_url': user['photo_url'], 'user_name': user['name'], 'user_role': user['role']})

def generate_csrf_token():
    if '_csrf_token' not in session: session['_csrf_token'] = secrets.token_urlsafe(32)
    return session['_csrf_token']

@app.context_processor
def inject_csrf_token(): return {'csrf_token': generate_csrf_token}

@app.context_processor
def inject_school_info():
    try: return {'school_name': get_setting('school_name') or 'Residential Shanti Niketan', 'school_address': get_setting('school_address') or 'Navinagar (Jamui)', 'school_phone': get_setting('school_phone') or '', 'school_email': get_setting('school_email') or '', 'school_logo': get_setting('school_logo_url') or url_for('static', filename='images/school_logo.png')}
    except: return {'school_name': 'Residential Shanti Niketan', 'school_address': 'Navinagar (Jamui)', 'school_phone': '', 'school_email': '', 'school_logo': url_for('static', filename='images/school_logo.png')}

@app.before_request
def csrf_token_protection():
    if request.method not in {'POST', 'PUT', 'PATCH', 'DELETE'}: return None
    expected = session.get('_csrf_token'); supplied = (request.form.get('csrf_token') or request.headers.get('X-CSRFToken') or request.headers.get('X-CSRF-Token'))
    if not expected or not supplied or not hmac.compare_digest(str(expected), str(supplied)): return ('Invalid CSRF token.', 400)
    return None

@app.before_request
def basic_csrf_origin_guard():
    if request.method not in {'POST', 'PUT', 'PATCH', 'DELETE'}: return None
    candidate = request.headers.get('Origin') or request.headers.get('Referer')
    if candidate:
        try:
            parsed = urlparse(candidate)
            if parsed.hostname and parsed.hostname.lower() != request.host.split(':', 1)[0].lower(): return ('Cross-origin request blocked.', 403)
        except: return ('Invalid origin.', 403)
    return None

# =========================================
# 5. PUBLIC & AUTH ROUTES
# =========================================
@app.route('/')
def home():
    db = get_db()
    return render_template('index.html', notices=get_all_notices(), upcoming_events=db.execute("SELECT * FROM events WHERE event_date >= date('now') ORDER BY event_date ASC LIMIT 3").fetchall(), testimonials=db.execute('SELECT * FROM testimonials WHERE is_approved = 1 ORDER BY RANDOM() LIMIT 4').fetchall(), achievements=db.execute('SELECT * FROM achievements ORDER BY id DESC LIMIT 3').fetchall(), gallery_images=db.execute('SELECT * FROM gallery ORDER BY display_order, id').fetchall())

@app.route('/notice')
def notices_page(): return render_template('notice.html', notices=get_all_notices())

@app.route('/academics')
def academics_page(): return render_template('academics.html')

@app.route('/gallery')
def gallery_page(): return render_template('gallery.html', images=get_db().execute('SELECT * FROM gallery ORDER BY display_order, id').fetchall())

@app.route('/faculty')
def faculty_page(): return render_template('faculty.html', faculty=get_combined_faculty())

@app.route('/events')
def events_page(): return render_template('events.html', events=get_db().execute('SELECT * FROM events ORDER BY event_date ASC').fetchall())

@app.route('/faq')
def faq_page(): return render_template('faq.html', faqs=get_db().execute('SELECT * FROM faq ORDER BY display_order, id').fetchall())

@app.route('/achievements')
def achievements_page(): return render_template('achievements.html', achievements=get_db().execute('SELECT * FROM achievements ORDER BY id DESC').fetchall())

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id'): return redirect(get_dashboard_url(session.get('user_role', 'student')))
    if request.method == 'POST':
        unique_id = request.form.get('unique_id', '').strip().upper()[:40]; password = request.form.get('password', '')
        if not unique_id or not password: flash('Invalid ID or password.', 'error'); return redirect(url_for('login_page'))
        db = get_db(); user = db.execute('SELECT * FROM users WHERE unique_id = ?', (unique_id,)).fetchone()
        if user and check_password_hash(user['password_hash'], password):
            if not user['is_active']: flash('Account deactivated.', 'error'); return redirect(url_for('login_page'))
            session.clear(); session.permanent = True
            session.update({'user_id': user['id'], 'user_name': user['name'], 'user_role': user['role'], 'unique_id': user['unique_id'], 'photo_url': user['photo_url']})
            if user['force_password_change']: return redirect(url_for('change_password'))
            return redirect(get_dashboard_url(user['role']))
        flash('Invalid ID or password.', 'error'); return redirect(url_for('login_page'))
    return render_template('login.html')

@app.route('/login_page')
def login_page(): return redirect(url_for('login'))

@app.route('/change-password', methods=['GET', 'POST'])
def change_password():
    if not session.get('user_id'): return redirect(url_for('login_page'))
    if request.method == 'POST':
        new_pw = request.form.get('new_password', '')
        if len(new_pw) < 10 or new_pw != request.form.get('confirm_password', ''): flash('Invalid password.', 'error'); return redirect(url_for('change_password'))
        db = get_db(); db.execute('UPDATE users SET password_hash = ?, force_password_change = 0 WHERE id = ?', (generate_password_hash(new_pw), session['user_id'])); db.commit()
        flash('Password updated.', 'success'); return redirect(get_dashboard_url(session['user_role']))
    return render_template('change_password.html')

@app.route('/logout', methods=['POST'])
def logout(): session.clear(); flash('Logged out.', 'success'); return redirect(url_for('home'))

# =========================================
# 6. DASHBOARD & CORE ROUTES
# =========================================
@app.route('/dashboard')
@login_required
def user_dashboard():
    user = get_user_by_id(session['user_id']); db = get_db(); role = user['role']
    notices = get_all_notices(role); parent_child = get_parent_child(db, user) if role == 'parent' else None
    att_uid = parent_child['id'] if parent_child else user['id']
    attendance = db.execute('SELECT * FROM attendance WHERE user_id = ? ORDER BY date DESC LIMIT 30', (att_uid,)).fetchall()
    messages = db.execute('SELECT * FROM messages WHERE to_user_id = ? OR to_role = ? ORDER BY id DESC LIMIT 20', (user['id'], role)).fetchall()
    events = db.execute("SELECT * FROM events WHERE event_date >= date('now') ORDER BY event_date ASC LIMIT 3").fetchall()

    if role == 'teacher':
        leaves = db.execute('SELECT * FROM leave_requests WHERE user_id = ? ORDER BY id DESC', (user['id'],)).fetchall()
        return render_template('teacher_dashboard.html', user=user, notices=notices, attendance=attendance, leaves=leaves, messages=messages, upcoming_events=events)
    elif role == 'student':
        fees = db.execute('SELECT * FROM fee_payments WHERE student_id = ? ORDER BY id DESC', (user['id'],)).fetchall()
        marks = db.execute('SELECT * FROM exam_marks WHERE student_id = ? ORDER BY exam_type, subject', (user['id'],)).fetchall()
        hw = db.execute("SELECT * FROM homework WHERE class_name = ? ORDER BY due_date DESC, id DESC LIMIT 10", (user['class_name'] or user['child_class'],)).fetchall() if (user['class_name'] or user['child_class']) else []
        return render_template('student_dashboard.html', user=user, notices=notices, attendance=attendance, exam_marks=marks, fees=fees, messages=messages, homework_list=hw, upcoming_events=events, fee_qr=get_setting('fee_qr_url'), upi_link=get_setting('upi_link'))
    elif role == 'parent':
        fees = db.execute('SELECT * FROM fee_payments WHERE student_id = ? ORDER BY id DESC', (parent_child['id'],)).fetchall() if parent_child else []
        return render_template('parent_dashboard.html', user=user, notices=notices, attendance=attendance, fees=fees, messages=messages, upcoming_events=events, child_linked=bool(parent_child), fee_qr=get_setting('fee_qr_url'), upi_link=get_setting('upi_link'))
    return render_template('user.html', user=user, notices=notices, attendance=attendance, leaves=[], fees=[], messages=messages, upcoming_events=events)

@app.route('/leave/request', methods=['POST'])
@login_required
def leave_request():
    db = get_db(); db.execute('INSERT INTO leave_requests (user_id, leave_type, from_date, to_date, reason) VALUES (?,?,?,?,?)', (session['user_id'], request.form.get('leave_type'), request.form.get('from_date'), request.form.get('to_date'), request.form.get('reason')))
    db.commit(); flash('Leave requested.', 'success'); return redirect(url_for('user_dashboard'))

@app.route('/fee/pay', methods=['POST'])
@login_required
def fee_pay():
    amount = float(request.form.get('amount', 0)); db = get_db(); user = get_user_by_id(session['user_id'])
    student_id = user['id']
    if user['role'] == 'parent':
        child = get_parent_child(db, user)
        if not child: flash('No child linked.', 'error'); return redirect(url_for('user_dashboard'))
        student_id = child['id']
    db.execute('INSERT INTO fee_payments (student_id, amount, payment_date, transaction_id, status, remarks) VALUES (?,?,?,?,?,?)', (student_id, amount, datetime.now().strftime('%Y-%m-%d'), request.form.get('transaction_id'), 'pending', request.form.get('remarks')))
    db.commit(); flash('Payment submitted.', 'success'); return redirect(url_for('user_dashboard'))

# =========================================
# 7. ADMIN ROUTES
# =========================================
@app.route('/admin')
@admin_required
def admin_dashboard():
    db = get_db()
    return render_template('admin.html', stats={'total_users': db.execute('SELECT COUNT(*) FROM users').fetchone()[0], 'total_teachers': db.execute("SELECT COUNT(*) FROM users WHERE role='teacher'").fetchone()[0], 'total_students': db.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0], 'pending_fees': db.execute("SELECT COUNT(*) FROM fee_payments WHERE status='pending'").fetchone()[0]}, recent_users=db.execute('SELECT * FROM users ORDER BY id DESC LIMIT 6').fetchall(), recent_leaves=db.execute('SELECT lr.*, u.name as user_name FROM leave_requests lr JOIN users u ON lr.user_id = u.id ORDER BY lr.id DESC LIMIT 5').fetchall(), upcoming_events=db.execute("SELECT * FROM events WHERE event_date >= date('now') ORDER BY event_date ASC LIMIT 4").fetchall(), messages=[], active_page='dashboard')

@app.route('/admin/users')
@admin_required
def admin_users():
    db = get_db(); role = request.args.get('role', 'all'); q = request.args.get('q', '').strip()
    query = 'SELECT * FROM users WHERE 1=1'; params = []
    if role != 'all': query += ' AND role = ?'; params.append(role)
    if q: query += ' AND (name LIKE ? OR email LIKE ? OR unique_id LIKE ?)'; params.extend([f'%{q}%']*3)
    users = db.execute(query + ' ORDER BY id DESC', tuple(params)).fetchall()
    return render_template('admin_users.html', users=users, role_filter=role, q=q, active_page='users')

@app.route('/admin/create-user', methods=['GET', 'POST'])
@admin_required
def admin_create_user():
    if request.method == 'POST':
        # Simplified for brevity, keep your full validation logic here
        pass
    return render_template('admin_create_user.html', form={}, errors={}, active_page='create_user')

@app.route('/admin/notices')
@admin_required
def admin_notices(): return render_template('admin_notices.html', notices=get_all_notices(), active_page='notices')

@app.route('/admin/attendance')
@admin_required
def admin_attendance():
    db = get_db(); date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    users = db.execute("SELECT * FROM users WHERE role='student' AND is_active=1 ORDER BY name").fetchall()
    records = db.execute("SELECT * FROM attendance WHERE date = ?", (date,)).fetchall()
    return render_template('admin_attendance.html', users=users, date=date, attendance_map={r['user_id']: r['status'] for r in records}, active_page='attendance')

@app.route('/admin/attendance/export')
@admin_required
def admin_attendance_export():
    from collections import OrderedDict
    db = get_db()
    
    period = (request.args.get('period') or 'daily').strip().lower()
    if period not in ('daily', 'weekly', 'monthly', 'yearly'): period = 'daily'
    role = (request.args.get('role') or 'student').strip().lower()
    if role not in ('student', 'teacher'): role = 'student'
    
    date_str = (request.args.get('date') or datetime.now().strftime('%Y-%m-%d')).strip()
    try: base_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except: base_date = date.today()
    
    subject = ((request.args.get('subject_filter') or 'General').strip()[:100]) or 'General'
    class_filter = (request.args.get('class_filter') or 'all').strip()

    if period == 'daily': start = end = base_date; period_label = base_date.strftime('%d %B %Y'); period_sub = 'Daily Report'
    elif period == 'weekly': start = base_date - timedelta(days=base_date.weekday()); end = start + timedelta(days=6); period_label = f"{start.strftime('%d %b')} - {end.strftime('%d %b %Y')}"; period_sub = 'Weekly Report'
    elif period == 'monthly':
        start = base_date.replace(day=1); end = (base_date.replace(year=base_date.year + 1, month=1, day=1) - timedelta(days=1)) if base_date.month == 12 else (base_date.replace(month=base_date.month + 1, day=1) - timedelta(days=1))
        period_label = base_date.strftime('%B %Y'); period_sub = 'Monthly Report'
    else: start = base_date.replace(month=1, day=1); end = base_date.replace(month=12, day=31); period_label = str(base_date.year); period_sub = 'Yearly Report'

    user_query = "SELECT * FROM users WHERE role = ? AND is_active = 1"
    user_params = [role]
    if role == 'student' and class_filter != 'all': user_query += " AND (class_name = ? OR child_class = ?)"; user_params.extend([class_filter, class_filter])
    users = db.execute(user_query + " ORDER BY name", tuple(user_params)).fetchall()

    attendance_records = []
    if users:
        ph = ','.join(['?'] * len(users))
        attendance_records = db.execute(f"SELECT user_id, status FROM attendance WHERE date BETWEEN ? AND ? AND subject = ? AND user_id IN ({ph})", [start.isoformat(), end.isoformat(), subject, *[u['id'] for u in users]]).fetchall()

    summary = {u['id']: {'present': 0, 'absent': 0, 'leave': 0, 'half-day': 0, 'total_marked': 0} for u in users}
    for rec in attendance_records:
        if rec['user_id'] in summary and rec['status'] in ('present', 'absent', 'leave', 'half-day'):
            summary[rec['user_id']][rec['status']] += 1; summary[rec['user_id']]['total_marked'] += 1

    grand_present = sum(s['present'] for s in summary.values()); grand_absent = sum(s['absent'] for s in summary.values())
    grand_leave = sum(s['leave'] for s in summary.values()); grand_halfday = sum(s['half-day'] for s in summary.values())
    grand_marked = grand_present + grand_absent + grand_leave + grand_halfday
    overall_pct = round(((grand_present + 0.5 * grand_halfday) / grand_marked) * 100, 1) if grand_marked else 0.0

    return render_template('admin_attendance_export.html', period=period, period_label=period_label, period_sub=period_sub, role=role, subject=subject, users=users, summary=summary, grouped=[{'class_name': 'All', 'students': users}], grand_present=grand_present, grand_absent=grand_absent, grand_leave=grand_leave, grand_halfday=grand_halfday, grand_marked=grand_marked, overall_pct=overall_pct, total_users=len(users), generated_at=datetime.now().strftime('%d %b %Y'), school_name=get_setting('school_name'), school_address=get_setting('school_address'), school_logo=get_setting('school_logo_url') or url_for('static', filename='images/school_logo.png'))

# =========================================
# 8. EXAM SYSTEM (ADMIN & TEACHER)
# =========================================
@app.route('/admin/exams')
@admin_required
def admin_exams_list():
    db = get_db()
    exams = db.execute("SELECT * FROM exams ORDER BY created_at DESC").fetchall()
    return render_template('admin_exams_list.html', exams=exams)

@app.route('/admin/exams/create', methods=['GET', 'POST'])
@app.route('/admin/exams/<int:eid>/edit', methods=['GET', 'POST'])
@admin_required
def admin_exam_form(eid=None):
    db = get_db(); exam = db.execute("SELECT * FROM exams WHERE id = ?", (eid,)).fetchone() if eid else None
    if request.method == 'POST':
        title = request.form.get('title'); year = request.form.get('academic_year')
        if exam:
            db.execute("UPDATE exams SET title=?, academic_year=?, term_label=?, notice_text=?, custom_message=? WHERE id=?", (title, year, request.form.get('term_label'), request.form.get('notice_text'), request.form.get('custom_message'), eid))
        else:
            cur = db.execute("INSERT INTO exams (title, academic_year, term_label, notice_text, custom_message, created_by) VALUES (?,?,?,?,?,?)", (title, year, request.form.get('term_label'), request.form.get('notice_text'), request.form.get('custom_message'), session['user_id']))
            eid = cur.lastrowid
        db.commit(); flash('Exam saved.', 'success'); return redirect(url_for('admin_exam_form', eid=eid))
    
    class_list = get_all_classes(db)
    subjects_by_class = {}
    if exam:
        for c in class_list:
            subjects_by_class[c] = db.execute("SELECT s.* FROM subjects s JOIN exam_subjects es ON s.id = es.subject_id WHERE es.exam_id = ? AND es.class_name = ?", (eid, c)).fetchall()
    return render_template('admin_exam_form.html', exam=exam, class_list=class_list, subjects_by_class=subjects_by_class, selected_subjects_by_class={})

@app.route('/admin/exams/<int:eid>/publish', methods=['POST'])
@admin_required
def admin_exam_publish(eid):
    db = get_db(); db.execute("UPDATE exams SET status='published', published_at=? WHERE id=?", (datetime.now().isoformat(), eid)); db.commit(); flash('Exam published.', 'success'); return redirect(url_for('admin_exams_list'))

@app.route('/admin/exams/<int:eid>/unpublish', methods=['POST'])
@admin_required
def admin_exam_unpublish(eid):
    db = get_db(); db.execute("UPDATE exams SET status='draft' WHERE id=?", (eid,)); db.commit(); flash('Exam unpublished.', 'success'); return redirect(url_for('admin_exams_list'))

@app.route('/admin/exams/<int:eid>/delete', methods=['POST'])
@admin_required
def admin_exam_delete(eid):
    db = get_db(); db.execute("DELETE FROM exams WHERE id=?", (eid,)); db.commit(); flash('Exam deleted.', 'success'); return redirect(url_for('admin_exams_list'))

@app.route('/admin/exams/<int:eid>/subjects', methods=['POST'])
@admin_required
def admin_exam_save_subjects(eid):
    db = get_db(); data = json.loads(request.form.get('selected_subjects_json', '{}'))
    for cls, payload in data.items():
        for sid in payload.get('subject_ids', []):
            max_marks = payload.get('max_marks_by_subject', {}).get(str(sid), 100)
            db.execute("INSERT OR IGNORE INTO exam_subjects (exam_id, class_name, subject_id, max_marks) VALUES (?,?,?,?)", (eid, cls, sid, max_marks))
    db.commit(); flash('Subjects saved.', 'success'); return redirect(url_for('admin_exam_form', eid=eid))

@app.route('/admin/api/add-subject', methods=['POST'])
@admin_required
def admin_api_add_subject():
    data = request.json; db = get_db()
    cur = db.execute("INSERT INTO subjects (class_name, subject_name, max_marks) VALUES (?,?,?)", (data['class_name'], data['subject_name'], data['max_marks']))
    db.commit()
    return jsonify({'success': True, 'active_subject_id': cur.lastrowid, 'all_subjects_map': {data['class_name']: {'id': cur.lastrowid, 'subject_name': data['subject_name'], 'max_marks': data['max_marks']}}})

@app.route('/exam-form', methods=['GET', 'POST'])
@login_required
def exam_form():
    db = get_db(); user = get_user_by_id(session['user_id']); student, err = user, None
    if user['role'] == 'parent': student = get_parent_child(db, user)
    if not student: flash(err or 'Student not found.', 'error'); return redirect(url_for('user_dashboard'))
    
    if request.method == 'POST':
        db.execute('''INSERT INTO exam_registrations (student_id, student_name, father_name, class_name, parent_mobile, exam_type, selected_subjects) VALUES (?,?,?,?,?,?,?)''', (student['id'], request.form.get('studentName'), request.form.get('fatherName'), request.form.get('className'), request.form.get('parentMobile'), request.form.get('examType'), json.dumps(request.form.getlist('subjects'))))
        db.commit(); flash('Exam form submitted.', 'success'); return redirect(url_for('exam_form'))
        
    submitted_map = {}
    available_exams = ['Half Yearly', 'Annual']
    subjects_dict = {}
    for row in db.execute("SELECT class_name, subject_name FROM subjects ORDER BY display_order").fetchall():
        subjects_dict.setdefault(row['class_name'], []).append(row['subject_name'])
    return render_template('exam_form.html', prefill={'studentName': student['name'], 'className': student['class_name']}, classes=get_all_classes(db), available_exams=available_exams, submitted_map=submitted_map, subjects_dict=subjects_dict)

# =========================================
# 9. QUESTION PAPERS (FIXED ROUTES)
# =========================================
@app.route('/question-papers')
@login_required
def teacher_question_papers():
    db = get_db(); is_admin = session.get('user_role') in ('admin', 'administrator'); teacher_id = session['user_id']
    if is_admin:
        papers = db.execute('''SELECT p.*, u.name AS teacher_name, (SELECT COUNT(*) FROM exam_questions q WHERE q.paper_id = p.id) AS question_count FROM exam_papers p LEFT JOIN users u ON p.teacher_id = u.id ORDER BY p.id DESC''').fetchall()
    else:
        papers = db.execute('''SELECT p.*, NULL AS teacher_name, (SELECT COUNT(*) FROM exam_questions q WHERE q.paper_id = p.id) AS question_count FROM exam_papers p WHERE p.teacher_id = ? ORDER BY p.id DESC''', (teacher_id,)).fetchall()
    
    subject_grid_grouped = {}
    if not is_admin:
        for item in get_teacher_subject_grid(db, teacher_id):
            subject_grid_grouped.setdefault(item['class_name'], []).append(item)
    return render_template('teacher_question_papers.html', papers=[dict(p) for p in papers], class_list=get_all_classes(db), is_admin=is_admin, subject_grid_grouped=subject_grid_grouped)

@app.route('/question-paper/start')
@login_required
def teacher_start_paper():
    if session.get('user_role') != 'teacher': return redirect(url_for('teacher_question_papers'))
    c_name, s_name = request.args.get('class'), request.args.get('subject'); db = get_db()
    paper = db.execute('SELECT id FROM exam_papers WHERE teacher_id = ? AND class_name = ? AND subject = ?', (session['user_id'], c_name, s_name)).fetchone()
    if paper: return redirect(url_for('edit_question_paper', paper_id=paper['id']))
    cur = db.execute('INSERT INTO exam_papers (title, class_name, subject, teacher_id) VALUES (?,?,?,?)', (f"{s_name} - {c_name}", c_name, s_name, session['user_id']))
    db.commit(); return redirect(url_for('edit_question_paper', paper_id=cur.lastrowid))

@app.route('/question-paper/create', methods=['GET', 'POST'])
@login_required
def create_question_paper():
    if request.method == 'POST':
        db = get_db(); cur = db.execute('INSERT INTO exam_papers (title, class_name, subject, teacher_id) VALUES (?,?,?,?)', (request.form.get('title'), request.form.get('class_name'), request.form.get('subject'), session['user_id']))
        db.commit(); return redirect(url_for('edit_question_paper', paper_id=cur.lastrowid))
    return render_template('create_question_paper.html', class_list=get_all_classes(get_db()))

@app.route('/question-papers/<int:paper_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_question_paper(paper_id):
    db = get_db(); user = get_user_by_id(session['user_id']); paper = _get_accessible_question_paper(db, user, paper_id)
    if not paper: flash('Access denied.', 'error'); return redirect(url_for('teacher_question_papers'))
    if request.method == 'POST':
        db.execute("INSERT INTO exam_questions (paper_id, section_name, question_text, marks, lines) VALUES (?,?,?,?,?)", (paper_id, request.form.get('section[]'), request.form.get('question[]'), request.form.get('marks[]'), request.form.get('lines[]')))
        db.commit(); flash('Question added.', 'success'); return redirect(url_for('edit_question_paper', paper_id=paper_id))
    
    questions = db.execute('SELECT * FROM exam_questions WHERE paper_id = ?', (paper_id,)).fetchall()
    grouped = {}
    for q in questions: grouped.setdefault(q['section_name'], []).append(q)
    return render_template('edit_question_paper.html', paper=paper, grouped_questions=grouped, total_questions=len(questions), saved_marks=sum(q['marks'] for q in questions))

@app.route('/question-papers/<int:paper_id>/print')
@login_required
def print_question_paper(paper_id):
    db = get_db(); user = get_user_by_id(session['user_id']); paper = _get_accessible_question_paper(db, user, paper_id)
    if not paper: return redirect(url_for('teacher_question_papers'))
    questions = db.execute('SELECT * FROM exam_questions WHERE paper_id = ?', (paper_id,)).fetchall()
    grouped = {}
    for q in questions: grouped.setdefault(q['section_name'], []).append(q)
    return render_template('print_question_paper.html', paper=paper, grouped_questions=grouped, total_marks=sum(q['marks'] for q in questions))

@app.route('/question-papers/<int:paper_id>/delete-paper', methods=['POST'])
@login_required
def delete_question_paper(paper_id):
    db = get_db(); user = get_user_by_id(session['user_id'])
    if _get_accessible_question_paper(db, user, paper_id):
        db.execute('DELETE FROM exam_papers WHERE id = ?', (paper_id,)); db.commit(); flash('Paper deleted.', 'success')
    return redirect(url_for('teacher_question_papers'))

@app.route('/question-papers/<int:paper_id>/delete-question/<int:q_id>', methods=['POST'])
@login_required
def delete_question(paper_id, q_id):
    db = get_db(); user = get_user_by_id(session['user_id'])
    if _get_accessible_question_paper(db, user, paper_id):
        db.execute('DELETE FROM exam_questions WHERE id = ? AND paper_id = ?', (q_id, paper_id)); db.commit()
    return redirect(url_for('edit_question_paper', paper_id=paper_id))

if __name__ == '__main__':
    app.run(debug=True)