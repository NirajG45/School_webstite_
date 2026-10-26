from dotenv import load_dotenv
from pathlib import Path
import os
import sqlite3
import re
import secrets
from functools import wraps
from datetime import timedelta, datetime
from flask import (Flask, render_template, request, redirect, url_for, flash, jsonify, g, session)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image, ImageOps
import io

# =========================================
# 1. APP CONFIGURATION
# =========================================
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get('SCHOOL_DB_PATH', BASE_DIR / 'school.db'))

load_dotenv(Path(__file__).resolve().with_name(".env"))
app = Flask(__name__)
secret_key = os.environ.get("SECRET_KEY")

if not secret_key or len(secret_key) < 32:
    raise RuntimeError(
        "SECRET_KEY missing or too short. Check your .env file."
    )

app.config["SECRET_KEY"] = secret_key
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20MB limit
app.config['SESSION_COOKIE_SECURE'] = True if os.environ.get('FLASK_ENV') == 'production' else False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# UPGRADE: Upload folder for QR codes
UPLOAD_FOLDER = BASE_DIR / 'static' / 'uploads'
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# === Jinja filter to format YYYY-MM-DD → "OCT" ===
@app.template_filter('month_abbr')
def month_abbr(date_str):
    months = ['JAN','FEB','MAR','APR','MAY','JUN',
              'JUL','AUG','SEP','OCT','NOV','DEC']
    try:
        return months[int(str(date_str)[5:7]) - 1]
    except (ValueError, IndexError, TypeError):
        return ''

DEFAULT_PASSWORD = 'snv@450'  # Default password for new users

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
    'administrator': ADMIN_FIELDS, # UPGRADE: Administrator gets same fields as Admin
    'parent': PARENT_FIELDS,
    'student': STUDENT_FIELDS,
}

# =========================================
# 2. DATABASE HELPERS
# =========================================
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
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
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')

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

        # 🚀 NEW: Faculty subject assignments (class-wise + day-wise)
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

        # Default school settings (required — not dummy data)
        db.execute("INSERT OR IGNORE INTO school_settings (key, value) VALUES ('fee_qr_url', '')")
        db.execute("INSERT OR IGNORE INTO school_settings (key, value) VALUES ('school_name', 'Residential Shanti Niketan')")
        db.execute("INSERT OR IGNORE INTO school_settings (key, value) VALUES ('upi_link', '')")

        db.commit()

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
    # 🚀 UPGRADE: Added 'administrator' mapping
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

def get_combined_faculty():
    """Fetches faculty records. Ensures every active teacher has a faculty row
       so that faculty.id is always available for subject assignments."""
    db = get_db()

    # --- Defensive sync: every active teacher must have a faculty row ---
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
        # Fallback: try matching by name (legacy rows without user_id)
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
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_file(file_storage.filename):
        return None

    compressed = compress_image(file_storage, target_kb=max_kb)
    if not compressed:
        return None

    filename = f"user_{secrets.token_hex(8)}.jpg"
    photos_dir = UPLOAD_FOLDER / 'photos'
    photos_dir.mkdir(parents=True, exist_ok=True)
    (photos_dir / filename).write_bytes(compressed)
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
    """
    Kisi bhi size ki image ko target_kb (~45KB) tak compress karta hai.
    Returns: bytes (JPEG)  OR  None (agar fail ho jaye)
    """
    try:
        file_storage.stream.seek(0)
        img = Image.open(file_storage.stream)
        img = ImageOps.exif_transpose(img)  # phone camera ka rotation fix

        # RGBA / P / LA → RGB (JPEG alpha support nahi karta)
        if img.mode in ('RGBA', 'LA', 'P'):
            if img.mode == 'P':
                img = img.convert('RGBA')
            bg = Image.new('RGB', img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            img = bg
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # Bahut bada dimension ho to pehle resize
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.LANCZOS)

        buf = io.BytesIO()

        # Quality ghataate jao jab tak size ~target na ho jaye
        quality = quality_start
        while quality >= quality_min:
            buf.seek(0); buf.truncate()
            img.save(buf, format='JPEG', quality=quality,
                     optimize=True, progressive=True)
            if buf.tell() <= target_kb * 1024:
                break
            quality -= 5

        # Agar min quality par bhi bada hai, to progressively shrink
        while buf.tell() > target_kb * 1024 and max(img.size) > 400:
            new_size = (int(img.width * 0.85), int(img.height * 0.85))
            img = img.resize(new_size, Image.LANCZOS)
            buf.seek(0); buf.truncate()
            img.save(buf, format='JPEG', quality=quality_min,
                     optimize=True, progressive=True)

        buf.seek(0)
        return buf.getvalue()
    except Exception as e:
        print(f"[compress_image] error: {e}")
        return None

# =========================================
# 4. DECORATORS
# =========================================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please login to access this page.', 'error')
            return redirect(url_for('login_page'))
        user = get_user_by_id(session['user_id'])
        if user and user['force_password_change'] and request.endpoint not in ('change_password', 'logout', 'static'):
            flash('Please change your default password to continue.', 'error')
            return redirect(url_for('change_password'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please login to access admin panel.', 'error')
            return redirect(url_for('login_page'))
        # 🚀 UPGRADE: Allowed both admin and administrator
        if session.get('user_role') not in ('admin', 'administrator'):
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('user_dashboard'))
        return f(*args, **kwargs)
    return decorated

def get_dashboard_url(role):
    # 🚀 UPGRADE: Allowed both admin and administrator
    return url_for('admin_dashboard') if role in ('admin', 'administrator') else url_for('user_dashboard')

# === Context processor for admin sidebar pending counts ===
@app.context_processor
def inject_admin_sidebar_counts():
    """Make pending counts available to all admin templates."""
    # 🚀 UPGRADE: Allowed both admin and administrator
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
# 🚀 SESSION SYNC — Ensures DB photo_url is always in session
# =========================================
@app.before_request
def sync_session_user_info():
    """Har request par check karta hai ki DB aur Session me photo_url sync hai ya nahi."""
    if session.get('user_id'):
        db = get_db()
        user = db.execute('SELECT photo_url, name, role FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if user:
            session['photo_url'] = user['photo_url']
            session['user_name'] = user['name']
            session['user_role'] = user['role']

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
        return redirect(request.referrer or url_for('admin_users'))

    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    role = request.form.get('role', user['role'])

    if not name or not email or not phone or not role:
        flash('Name, Email, Phone and Role are required.', 'error')
        return redirect(request.referrer or url_for('admin_users'))

    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        flash('Invalid email format.', 'error')
        return redirect(request.referrer or url_for('admin_users'))

    # 🚀 UPGRADE: Added administrator
    if role not in ('teacher', 'admin', 'administrator', 'parent', 'student'):
        flash('Invalid role.', 'error')
        return redirect(request.referrer or url_for('admin_users'))

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
            # 🚀 CASCADE: remove faculty row AND its subject assignments
            fac_row = db.execute('SELECT id FROM faculty WHERE user_id = ?', (user_id,)).fetchone()
            if fac_row:
                db.execute('DELETE FROM faculty_subject_assignments WHERE faculty_id = ?',
                           (fac_row['id'],))
            db.execute('DELETE FROM faculty WHERE user_id = ?', (user_id,))

        db.commit()

        # 🚀 FIX: Session Update if Admin edits own profile
        if session['user_id'] == user_id:
            session['user_name'] = name
            session['user_role'] = role
            session['photo_url'] = updates.get('photo_url', user['photo_url'])

        flash('Profile updated successfully!', 'success')
    except sqlite3.IntegrityError:
        flash('Email already exists. Please use a different email.', 'error')
    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'error')

    return redirect(request.referrer or url_for('admin_users'))


# =========================================
# 6. AUTH ROUTES
# =========================================
@app.route('/login', methods=['GET'])
def login_page():
    if session.get('user_id'):
        return redirect(get_dashboard_url(session.get('user_role', 'student')))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    unique_id = request.form.get('unique_id', '').strip().upper()
    password = request.form.get('password', '')

    db = get_db()
    user = db.execute('SELECT * FROM users WHERE unique_id = ?', (unique_id,)).fetchone()

    if user and check_password_hash(user['password_hash'], password):
        if not user['is_active']:
            flash('Your account has been deactivated. Contact admin.', 'error')
            return redirect(url_for('login_page'))
        session.permanent = True
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        session['user_role'] = user['role']
        session['unique_id'] = user['unique_id']
        session['photo_url'] = user['photo_url']  # 🚀 FIX: Photo URL saved on login

        if user['force_password_change']:
            flash('Welcome! Please set a new password.', 'success')
            return redirect(url_for('change_password'))

        flash(f'Welcome back, {user["name"]}!', 'success')
        return redirect(get_dashboard_url(user['role']))
    else:
        flash('Invalid ID or password.', 'error')
        return redirect(url_for('login_page'))

@app.route('/change-password', methods=['GET', 'POST'])
def change_password():
    if not session.get('user_id'):
        return redirect(url_for('login_page'))

    if request.method == 'POST':
        new_pw = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')

        if len(new_pw) < 6:
            flash('Password must be at least 6 characters.', 'error')
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

@app.route('/logout')
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
    amount = request.form.get('amount', '0')
    txn_id = request.form.get('transaction_id', '').strip()
    remarks = request.form.get('remarks', '').strip()

    try:
        amount = float(amount)
    except:
        flash('Invalid amount.', 'error')
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
# ADMIN DEDICATED PHOTO ROUTES (For Admin Users Page Modal)
# =========================================
@app.route('/admin/users/<int:user_id>/update-photo', methods=['POST'])
@admin_required
def admin_update_user_photo(user_id):
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        flash('User not found.', 'error')
        return redirect(request.referrer or url_for('admin_users'))

    photo_file = request.files.get('photo')
    if not photo_file or not photo_file.filename:
        flash('No file uploaded.', 'error')
        return redirect(request.referrer or url_for('admin_users'))

    if not allowed_file(photo_file.filename):
        flash('Invalid file type.', 'error')
        return redirect(request.referrer or url_for('admin_users'))

    photo_url = save_user_photo(photo_file)
    if not photo_url:
        flash('Image too large (max 2MB) or could not be saved.', 'error')
        return redirect(request.referrer or url_for('admin_users'))

    db.execute('UPDATE users SET photo_url = ? WHERE id = ?', (photo_url, user_id))
    if user['role'] == 'teacher':
        db.execute('UPDATE faculty SET photo_url = ? WHERE user_id = ?', (photo_url, user_id))
    db.commit()

    if session['user_id'] == user_id:
        session['photo_url'] = photo_url

    flash('User photo updated successfully.', 'success')
    return redirect(request.referrer or url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/remove-photo', methods=['POST'])
@admin_required
def admin_remove_user_photo(user_id):
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        flash('User not found.', 'error')
        return redirect(request.referrer or url_for('admin_users'))

    db.execute('UPDATE users SET photo_url = NULL WHERE id = ?', (user_id,))
    if user['role'] == 'teacher':
        db.execute('UPDATE faculty SET photo_url = NULL WHERE user_id = ?', (user_id,))
    db.commit()

    if session['user_id'] == user_id:
        session['photo_url'] = None

    flash('User photo removed.', 'success')
    return redirect(request.referrer or url_for('admin_users'))
# =========================================

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
        # 🚀 UPGRADE: Added administrator
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

        # 🚀 UPGRADE: Added administrator block
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
        hashed    = generate_password_hash(DEFAULT_PASSWORD)

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
        except sqlite3.IntegrityError as e:
            flash(f'Database error: {e}', 'error')
            return render_template('admin_create_user.html',
                                   form=form, errors={'_': str(e)},
                                   active_page='create_user')
        except Exception as e:
            flash(f'Error creating user: {e}', 'error')
            return render_template('admin_create_user.html',
                                   form=form, errors={'_': str(e)},
                                   active_page='create_user')

        flash(f'{role.capitalize()} created! ID: {unique_id} | '
              f'Default Password: {DEFAULT_PASSWORD}', 'success')
        return redirect(url_for('admin_users'))

    pre_role = request.args.get('role', '')
    if pre_role and pre_role in ('teacher', 'admin', 'administrator', 'parent', 'student'):
        initial_form = {'role': pre_role}
    else:
        initial_form = {}

    return render_template('admin_create_user.html',
                           form=initial_form, errors={},
                           active_page='create_user')


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

    # 🚀 CASCADE: remove assignments before removing faculty row
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
    # 🚀 UPGRADE: Added administrator
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
        # 🚀 CASCADE: remove faculty row AND its assignments
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
    db.execute('UPDATE users SET password_hash = ?, force_password_change = 1 WHERE id = ?',
               (generate_password_hash(DEFAULT_PASSWORD), user_id))
    db.commit()
    flash(f'Password reset to default: {DEFAULT_PASSWORD}', 'success')
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
    subject_filter = request.args.get('subject_filter', 'General')

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
    date         = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))
    subject      = request.form.get('subject', 'General')
    role         = request.form.get('role', 'student')
    class_filter = request.form.get('class_filter', 'all')
    db = get_db()

    for key, val in request.form.items():
        if key.startswith('status_'):
            try:
                uid = int(key.replace('status_', ''))
            except ValueError:
                continue
            val = (val or '').strip()

            existing = db.execute(
                'SELECT id FROM attendance WHERE user_id = ? AND date = ? AND subject = ?',
                (uid, date, subject)
            ).fetchone()

            if not val:
                if existing:
                    db.execute('DELETE FROM attendance WHERE id = ?', (existing['id'],))
            elif existing:
                db.execute(
                    'UPDATE attendance SET status = ?, marked_by = ? WHERE id = ?',
                    (val, session['user_id'], existing['id'])
                )
            else:
                db.execute(
                    'INSERT INTO attendance (user_id, date, status, subject, marked_by) '
                    'VALUES (?,?,?,?,?)',
                    (uid, date, val, subject, session['user_id'])
                )

    db.commit()
    flash(f'Attendance marked for {date} ({subject}).', 'success')
    return redirect(url_for(
        'admin_attendance',
        date=date, role=role,
        class_filter=class_filter, subject_filter=subject
    ))

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

        if to_user_id:
            db.execute('INSERT INTO messages (from_user_id, to_user_id, subject, body) VALUES (?,?,?,?)',
                       (session['user_id'], int(to_user_id), subject, body))
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
# 10.5. ADMIN — NEW CONTENT MANAGEMENT ROUTES
# =========================================

# === FACULTY ===
@app.route('/admin/faculty')
@admin_required
def admin_faculty():
    db = get_db()
    faculty = get_combined_faculty()

    # --- All subject assignments (with faculty name joined) ---
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

    # --- Datalist suggestions ---
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


# 🚀 NEW: Assign subject to faculty (class-wise + day-wise)
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

    # "All Days" → expand to Mon–Sat
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


# 🚀 NEW: Delete a specific assignment
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
    # 🚀 CASCADE — remove all assignments tied to this faculty row
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
    return render_template('admin_events.html', events=events, active_page='events')

@app.route('/admin/events/add', methods=['POST'])
@admin_required
def admin_add_event():
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    event_date = request.form.get('event_date', '').strip()
    event_time = request.form.get('event_time', '').strip()
    location = request.form.get('location', '').strip()
    category = request.form.get('category', 'general')

    if not title or not event_date:
        flash('Title and Date are required.', 'error')
        return redirect(url_for('admin_events'))

    db = get_db()
    db.execute('INSERT INTO events (title, description, event_date, event_time, location, category) VALUES (?,?,?,?,?,?)',
               (title, description, event_date, event_time, location, category))
    db.commit()
    flash(f'Event "{title}" published!', 'success')
    return redirect(url_for('admin_events'))

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

        if not title or not event_date:
            flash('Title and Date are required.', 'error')
            return redirect(url_for('admin_edit_event', eid=eid))

        db.execute('''UPDATE events SET title = ?, description = ?, event_date = ?, 
                      event_time = ?, location = ?, category = ? WHERE id = ?''',
                   (title, description, event_date, event_time, location, category, eid))
        db.commit()
        flash('Event updated successfully!', 'success')
        return redirect(url_for('admin_events'))

    event = db.execute('SELECT * FROM events WHERE id = ?', (eid,)).fetchone()
    if not event:
        flash('Event not found.', 'error')
        return redirect(url_for('admin_events'))

    events = db.execute('SELECT * FROM events ORDER BY event_date DESC').fetchall()
    return render_template('admin_events.html', events=events, edit_event=event, active_page='events')

@app.route('/admin/events/delete/<int:eid>', methods=['POST'])
@admin_required
def admin_delete_event(eid):
    db = get_db()
    db.execute('DELETE FROM events WHERE id = ?', (eid,))
    db.commit()
    flash('Event deleted.', 'success')
    return redirect(url_for('admin_events'))


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
            filename = f"gallery_{secrets.token_hex(6)}.jpg"   # always .jpg
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
    user = get_user_by_id(session['user_id'])
    # 🚀 UPGRADE: Allowed both admin and administrator
    if not user or user['role'] not in ('teacher', 'admin', 'administrator'):
        flash('Only teachers can access this page.', 'error')
        return redirect(url_for('user_dashboard'))

    db = get_db()
    date = (request.args.get('date') or request.form.get('date')
            or datetime.now().strftime('%Y-%m-%d'))
    subject = (request.args.get('subject') or request.form.get('subject')
               or (user['subject'] or 'General'))
    selected_class = (request.args.get('class_filter')
                      or request.form.get('class_filter') or 'all')

    raw_classes = user['classes_assigned'] or ''
    assigned_classes = [c.strip() for c in raw_classes.split(',') if c.strip()]

    # ---------- POST handler ----------
    if request.method == 'POST':
        # 1) Self attendance
        self_status = request.form.get('teacher_self_status')
        if self_status in ('present', 'absent', 'leave', 'half-day'):
            existing = db.execute(
                "SELECT id FROM attendance WHERE user_id=? AND date=? AND subject='General'",
                (user['id'], date)
            ).fetchone()
            if existing:
                db.execute(
                    'UPDATE attendance SET status=?, marked_by=? WHERE id=?',
                    (self_status, user['id'], existing['id'])
                )
            else:
                db.execute(
                    'INSERT INTO attendance (user_id, date, status, subject, marked_by) '
                    "VALUES (?,?,?,'General',?)",
                    (user['id'], date, self_status, user['id'])
                )

        # 2) Classroom attendance — handles empty (reset) status too
        for key, val in request.form.items():
            if key.startswith('status_'):
                try:
                    uid = int(key.replace('status_', ''))
                except ValueError:
                    continue
                val = (val or '').strip()

                existing = db.execute(
                    'SELECT id FROM attendance WHERE user_id=? AND date=? AND subject=?',
                    (uid, date, subject)
                ).fetchone()

                if not val:
                    if existing:
                        db.execute('DELETE FROM attendance WHERE id = ?', (existing['id'],))
                elif existing:
                    db.execute(
                        'UPDATE attendance SET status=?, marked_by=? WHERE id=?',
                        (val, user['id'], existing['id'])
                    )
                else:
                    db.execute(
                        'INSERT INTO attendance (user_id, date, status, subject, marked_by) '
                        'VALUES (?,?,?,?,?)',
                        (uid, date, val, subject, user['id'])
                    )
        db.commit()
        flash(f'Attendance saved for {date} ({subject}).', 'success')
        return redirect(url_for(
            'teacher_attendance',
            date=date, subject=subject, class_filter=selected_class
        ))

    # ---------- GET handler ----------
    self_rec = db.execute(
        "SELECT status FROM attendance WHERE user_id=? AND date=? AND subject='General'",
        (user['id'], date)
    ).fetchone()
    self_status = self_rec['status'] if self_rec else 'not-marked'

    sq = "SELECT * FROM users WHERE role='student' AND is_active=1"
    sp = []
    if selected_class != 'all':
        sq += " AND (class_name = ? OR child_class = ?)"
        sp.extend([selected_class, selected_class])
    elif assigned_classes:
        ors = []
        for c in assigned_classes:
            ors.append("(class_name LIKE ? OR child_class LIKE ?)")
            sp.extend([f'%{c}%', f'%{c}%'])
        sq += " AND (" + " OR ".join(ors) + ")"
    sq += " ORDER BY COALESCE(class_name, child_class), name"
    students = db.execute(sq, tuple(sp)).fetchall()

    student_att_map = {}
    if students:
        ids = [s['id'] for s in students]
        ph = ','.join(['?'] * len(ids))
        rows = db.execute(
            f"SELECT user_id, status FROM attendance "
            f"WHERE date=? AND subject=? AND user_id IN ({ph})",
            (date, subject, *ids)
        ).fetchall()
        student_att_map = {r['user_id']: r['status'] for r in rows}

    class_rows = db.execute(
        "SELECT DISTINCT COALESCE(class_name, child_class) AS c FROM users "
        "WHERE role='student' AND COALESCE(class_name, child_class) IS NOT NULL "
        "AND COALESCE(class_name, child_class) != '' ORDER BY c"
    ).fetchall()
    class_list = [r['c'] for r in class_rows if r['c']]

    subject_rows = [row['subject'] for row in db.execute(
        "SELECT DISTINCT subject FROM attendance "
        "WHERE subject IS NOT NULL AND subject != '' ORDER BY subject"
    ).fetchall()]
    subjects = []
    if user['subject'] and user['subject'] not in subject_rows:
        subjects.append(user['subject'])
    subjects.extend(subject_rows or ['General'])
    if subject not in subjects:
        subjects.insert(0, subject)

    return render_template(
        'teacher_attendance.html',
        user=user, date=date, subject=subject,
        selected_class=selected_class,
        assigned_classes=assigned_classes,
        class_list=class_list, subjects=subjects,
        students=students, student_att_map=student_att_map,
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
    # 🚀 UPGRADE: Allowed both admin and administrator
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


@app.route('/teacher/homework/add', methods=['POST'])
@login_required
def teacher_add_homework():
    user = get_user_by_id(session['user_id'])
    # 🚀 UPGRADE: Allowed both admin and administrator
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
    # 🚀 UPGRADE: Allowed both admin and administrator
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
        return redirect(request.referrer or url_for('user_dashboard'))

    if not allowed_file(photo_file.filename):
        flash('Only JPG / PNG / WEBP / GIF allowed.', 'error')
        return redirect(request.referrer or url_for('user_dashboard'))

    photo_url = save_user_photo(photo_file)
    if not photo_url:
        flash('Image is too large (max 2MB) or could not be saved.', 'error')
        return redirect(request.referrer or url_for('user_dashboard'))

    db = get_db()
    db.execute('UPDATE users SET photo_url = ? WHERE id = ?', (photo_url, user['id']))
    db.commit()

    # Sync to faculty table for teachers so public faculty page reflects new photo
    if user['role'] == 'teacher':
        db.execute('UPDATE faculty SET photo_url = ? WHERE user_id = ?', (photo_url, user['id']))
        db.commit()

    # Refresh session so it appears immediately everywhere
    session['photo_url'] = photo_url

    flash('Profile photo updated successfully!', 'success')
    return redirect(request.referrer or url_for('user_dashboard'))


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
    return redirect(request.referrer or url_for('user_dashboard'))

# =========================================
# MESSAGING SYSTEM — ROLE-BASED
# =========================================
def _allowed_recipients(db, user):
    """
    Returns list of dicts {id, name, unique_id, role} this user can message.

    Rules:
      admin / administrator   → everyone (students, teachers, parents, other admins)
      teacher → admin, teachers, their students, parents of those students
      parent  → admin, teachers
      student → admin, teachers
    """
    role = user['role']
    uid = user['id']
    recipients = []

    # 🚀 UPGRADE: Allowed both admin and administrator
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
    view = request.args.get('view', 'inbox')  # inbox | sent
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

    # 🚀 UPGRADE: Allowed both admin and administrator
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
    return redirect(request.referrer or url_for('admin_gallery') or url_for('admin_events'))

@app.errorhandler(500)
def ie(e): return "Server error", 500

@app.after_request
def add_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    return response

# =========================================
# MISSING ADMIN ROUTES (For Sidebar Links)
# =========================================

@app.route('/admin/enter-marks')
@admin_required
def admin_enter_marks():
    # यहाँ आप मार्क्स एंटर करने का लॉजिक बाद में जोड़ सकते हैं
    return render_template('admin_enter_marks.html', active_page='enter_marks')

@app.route('/admin/bulk-marks')
@admin_required
def admin_bulk_marks():
    return render_template('admin_bulk_marks.html', active_page='bulk_marks')

@app.route('/admin/reports')
@admin_required
def admin_reports():
    return render_template('admin_reports.html', active_page='reports')

@app.route('/admin/reports-dashboard')
@admin_required
def admin_reports_dashboard():
    return render_template('admin_generate_reports.html', active_page='reports_dashboard')

@app.route('/admin/generate-reports')
@admin_required
def admin_generate_reports():
    return render_template('admin_generate_reports.html', active_page='generate_reports')

# =========================================
# INIT
# =========================================
init_db()

if __name__ == '__main__':
    app.run(
        debug=True,
        use_reloader=True,
        host=os.environ.get('HOST', '127.0.0.1'),
        port=int(os.environ.get('PORT', 5000))
    )