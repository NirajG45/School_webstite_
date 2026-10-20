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

# =========================================
# 1. APP CONFIGURATION
# =========================================
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get('SCHOOL_DB_PATH', BASE_DIR / 'school.db'))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-before-deployment')
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

DEFAULT_PASSWORD = 'snv@450'  # Default password for new users

INITIAL_NOTICES = [
    {'date': '05 Oct 2026', 'title': 'Admissions enquiry open for Session 2026–27', 'tag': 'Admissions', 'desc': 'Admissions are now open for the upcoming academic session.', 'target_role': 'all'},
    {'date': '28 Sep 2026', 'title': 'Class-wise timetable published', 'tag': 'Academics', 'desc': 'The new timetable is available.', 'target_role': 'all'},
    {'date': '22 Sep 2026', 'title': 'Annual sports day update', 'tag': 'Activities', 'desc': 'Annual sports day is approaching.', 'target_role': 'all'},
    {'date': '15 Sep 2026', 'title': 'Parent–teacher meeting', 'tag': 'Notice', 'desc': 'A PTM is scheduled for all classes.', 'target_role': 'all'},
]

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
        
    # One-time sync for existing teachers
    teachers = db.execute("SELECT id, name, subject, qualification, experience, photo_url FROM users WHERE role='teacher'").fetchall()
    for t in teachers:
        if not db.execute("SELECT 1 FROM faculty WHERE user_id = ? OR name = ?", (t['id'], t['name'])).fetchone():
            db.execute('''INSERT INTO faculty (user_id, name, subject, qualification, experience, photo_url) 
                          VALUES (?, ?, ?, ?, ?, ?)''',
                       (t['id'], t['name'], t['subject'] or 'General', t['qualification'] or '', t['experience'] or '', t['photo_url']))

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        # 👇 YE LINE ADD KAREIN (Ye error fix kar degi)
        db.row_factory = sqlite3.Row  
        
        # Enquiries
        db.execute('''CREATE TABLE IF NOT EXISTS enquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, name TEXT NOT NULL,
            phone TEXT NOT NULL, email TEXT, class_name TEXT, message TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        
        # Notices (with target_role)
        db.execute('''CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, title TEXT NOT NULL,
            tag TEXT NOT NULL, description TEXT, target_role TEXT DEFAULT 'all',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        
        # Users (with unique_id, force_password_change)
        db.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, unique_id TEXT UNIQUE, role TEXT NOT NULL,
            name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, phone TEXT NOT NULL,
            password_hash TEXT NOT NULL, force_password_change INTEGER DEFAULT 1,
            dob TEXT, gender TEXT, qualification TEXT, experience TEXT, subject TEXT,
            designation TEXT, department TEXT, relation TEXT, child_name TEXT,
            child_class TEXT, address TEXT, is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')

        # UPGRADE: add all new columns for teacher/admin/parent/student
        migrate_users_table(db)
        
        # Leave Requests
        db.execute('''CREATE TABLE IF NOT EXISTS leave_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            leave_type TEXT NOT NULL, from_date TEXT NOT NULL, to_date TEXT NOT NULL,
            reason TEXT NOT NULL, status TEXT DEFAULT 'pending',
            admin_remarks TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        
        # Attendance (UPDATED: added subject column)
        db.execute('''CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            date TEXT NOT NULL, status TEXT NOT NULL, subject TEXT DEFAULT 'General', 
            remarks TEXT, marked_by INTEGER, 
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        
        # Call migration for attendance table
        migrate_attendance_table(db)
        
        # NEW: Exam Marks Table
        db.execute('''CREATE TABLE IF NOT EXISTS exam_marks (
            id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL,
            exam_type TEXT NOT NULL, subject TEXT NOT NULL, 
            marks_obtained REAL NOT NULL, total_marks REAL NOT NULL DEFAULT 100,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        
        # Fee Payments
        db.execute('''CREATE TABLE IF NOT EXISTS fee_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL,
            amount REAL NOT NULL, payment_date TEXT NOT NULL,
            transaction_id TEXT, status TEXT DEFAULT 'pending',
            remarks TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        
        # School Settings (for QR code, etc.)
        db.execute('''CREATE TABLE IF NOT EXISTS school_settings (
            key TEXT PRIMARY KEY, value TEXT)''')
        
        # Messages (admin to users)
        db.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, from_user_id INTEGER NOT NULL,
            to_user_id INTEGER, to_role TEXT, subject TEXT NOT NULL, body TEXT NOT NULL,
            is_read INTEGER DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        
        # =========================================
        # NEW TABLES
        # =========================================
        
        # Events / News Table
        db.execute('''CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
            description TEXT, event_date TEXT NOT NULL, event_time TEXT,
            location TEXT, category TEXT DEFAULT 'general',
            is_featured INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        
        # Faculty Directory Table
        db.execute('''CREATE TABLE IF NOT EXISTS faculty (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT NOT NULL,
            subject TEXT NOT NULL, qualification TEXT, experience TEXT,
            photo_url TEXT, bio TEXT, display_order INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        
        # Call migration for faculty table
        migrate_faculty_table(db)
        
        # Testimonials Table
        db.execute('''CREATE TABLE IF NOT EXISTS testimonials (
            id INTEGER PRIMARY KEY AUTOINCREMENT, author_name TEXT NOT NULL,
            author_role TEXT DEFAULT 'Parent', message TEXT NOT NULL,
            rating INTEGER DEFAULT 5, is_approved INTEGER DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        
        # Achievements Table
        db.execute('''CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT, student_name TEXT NOT NULL,
            class_name TEXT, achievement TEXT NOT NULL, year TEXT,
            category TEXT DEFAULT 'academic', photo_url TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        
        # Gallery Images Table
        db.execute('''CREATE TABLE IF NOT EXISTS gallery (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
            image_url TEXT NOT NULL, category TEXT DEFAULT 'campus',
            display_order INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        
        # FAQ Table
        db.execute('''CREATE TABLE IF NOT EXISTS faq (
            id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT NOT NULL,
            answer TEXT NOT NULL, display_order INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        
        # =========================================
        # SEED DATA (Only once per table)
        # =========================================
        def _is_seeded(key):
            r = db.execute("SELECT value FROM school_settings WHERE key = ?", (f'_seed_{key}',)).fetchone()
            return r and r[0] == '1'
        
        def _mark_seeded(key):
            db.execute("INSERT OR REPLACE INTO school_settings (key, value) VALUES (?, '1')", (f'_seed_{key}',))
        
        # Seed Notices
        if not _is_seeded('notices'):
            for n in INITIAL_NOTICES:
                db.execute('INSERT INTO notices (date, title, tag, description, target_role) VALUES (?,?,?,?,?)',
                           (n['date'], n['title'], n['tag'], n['desc'], n['target_role']))
            _mark_seeded('notices')
        
        # Seed Events
        if not _is_seeded('events'):
            events_seed = [
                ('Annual Sports Day 2026', 'A day full of sports, teamwork and fun for all students.', '2026-12-15', '09:00 AM', 'Main Playground', 'sports', 1),
                ('Parent-Teacher Meeting', 'PTM for all classes — parents are requested to attend.', '2026-11-20', '10:00 AM', 'School Hall', 'meeting', 1),
                ('Annual Function 2026', 'Cultural program showcasing student talents.', '2026-12-25', '05:00 PM', 'School Auditorium', 'cultural', 1),
                ('Winter Vacation Begins', 'School will remain closed for winter vacation.', '2026-12-28', 'All Day', 'School', 'holiday', 0),
                ('Republic Day Celebration', 'Flag hoisting ceremony followed by cultural program.', '2027-01-26', '08:00 AM', 'School Ground', 'cultural', 0),
                ('Science Exhibition', 'Students showcase innovative science projects.', '2027-02-10', '10:00 AM', 'Science Lab', 'academic', 0),
            ]
            for e in events_seed:
                db.execute('INSERT INTO events (title, description, event_date, event_time, location, category, is_featured) VALUES (?,?,?,?,?,?,?)', e)
            _mark_seeded('events')
        
        # Seed Faculty
        if not _is_seeded('faculty'):
            faculty_seed = [
                ('Mr. Niraj Kumar', 'Mathematics', 'M.Sc., B.Ed', '8+ Years', 'Passionate about making math fun and accessible for every student.', 1),
                ('Mrs. Priya Sharma', 'English', 'M.A. English, B.Ed', '10+ Years', 'Believes in developing strong communication skills through literature.', 2),
                ('Mr. Rajesh Verma', 'Science', 'M.Sc. Physics, B.Ed', '6+ Years', 'Encourages curiosity and hands-on learning in science.', 3),
                ('Mrs. Anita Kumari', 'Hindi', 'M.A. Hindi, B.Ed', '12+ Years', 'Dedicated to promoting Hindi language and cultural values.', 4),
                ('Mr. Sanjay Prasad', 'Social Science', 'M.A. History, B.Ed', '5+ Years', 'Makes history come alive with engaging storytelling.', 5),
                ('Ms. Neha Singh', 'Computer Science', 'MCA', '4+ Years', 'Prepares students for the digital future.', 6),
            ]
            for f in faculty_seed:
                db.execute('INSERT INTO faculty (name, subject, qualification, experience, bio, display_order) VALUES (?,?,?,?,?,?)', f)
            _mark_seeded('faculty')
        
        # Seed Testimonials
        if not _is_seeded('testimonials'):
            test_seed = [
                ('Mrs. Sunita Devi', 'Parent', 'Excellent school with caring teachers. My daughter has grown so much in confidence.', 5),
                ('Mr. Ramesh Kumar', 'Parent', 'The attention given to each student is remarkable. Highly recommend RSN.', 5),
                ('Mr. Anil Yadav', 'Parent', 'Best school in Navinagar Jamui. Quality education and strong values.', 5),
                ('Mrs. Kavita Verma', 'Parent', 'My son loves going to school every day. The teachers are wonderful.', 5),
                ('Mr. Deepak Singh', 'Parent', 'Great balance of academics and extracurricular activities.', 5),
            ]
            for t in test_seed:
                db.execute('INSERT INTO testimonials (author_name, author_role, message, rating) VALUES (?,?,?,?)', t)
            _mark_seeded('testimonials')
        
        # Seed Achievements
        if not _is_seeded('achievements'):
            ach_seed = [
                ('Aarav Kumar', 'Class 8', '1st Position in District Math Olympiad', '2026', 'academic'),
                ('Priya Kumari', 'Class 7', 'Gold Medal in State Chess Championship', '2026', 'sports'),
                ('Rohit Raj', 'Class 6', 'Winner — Inter-School Science Quiz', '2026', 'academic'),
                ('Ananya Singh', 'Class 5', 'Best Performer in Annual Dance Competition', '2026', 'cultural'),
                ('Vivaan Sharma', 'Class 4', '1st Place in Drawing Competition', '2026', 'cultural'),
                ('Aadhya Verma', 'Class 3', 'Best Student Award — Session 2025-26', '2026', 'academic'),
            ]
            for a in ach_seed:
                db.execute('INSERT INTO achievements (student_name, class_name, achievement, year, category) VALUES (?,?,?,?,?)', a)
            _mark_seeded('achievements')
        
        # Seed Gallery
        if not _is_seeded('gallery'):
            gallery_seed = [
                ('School Campus', 'campus.jpg', 'campus', 1),
                ('Annual Day', 'head2.jpeg', 'events', 2),
                ('Group Photo', 'all.jpeg', 'events', 3),
                ('Our Staff', 'all_starfs.jpeg', 'faculty', 4),
                ('Teachers', 'Doc.jpeg', 'faculty', 5),
                ('Management', 'head.jpeg', 'faculty', 6),
                ('Principal Ma\'am', 'head_maam.jpeg', 'faculty', 7),
                ('Cultural Program', 'Radhay_Krishna.jpeg', 'events', 8),
                ('Teachers Day', 'teachers_day.jpeg', 'events', 9),
                ('Teaching Staff', 'teachers.jpeg', 'faculty', 10),
                ('Student Art', 'drawings.jpeg', 'activities', 11),
                ('Sports Day', 'Niraj.jpeg', 'sports', 12),
            ]
            for g in gallery_seed:
                db.execute('INSERT INTO gallery (title, image_url, category, display_order) VALUES (?,?,?,?)', g)
            _mark_seeded('gallery')
        
        # Seed FAQ
        if not _is_seeded('faq'):
            faq_seed = [
                ('What classes does the school offer?', 'Residential Shanti Niketan offers education from Pre-Nursery to Class 8, covering Pre-Primary, Primary, and Middle School.', 1),
                ('How can I apply for admission?', 'You can fill the admission enquiry form on our homepage, or contact the school office directly at 9155658081.', 2),
                ('How can I pay the school fees?', 'Fees can be paid online through our Parent/Student Portal using UPI (Google Pay, PhonePe, Paytm).', 3),
                ('How do I get my login credentials?', 'Login credentials are created by the school admin. You will receive your Unique ID and default password.', 4),
                ('What are the school timings?', 'The school operates from Monday to Saturday, with class timings varying by grade.', 5),
                ('Is transportation available?', 'Please contact the school office for information about transportation facilities.', 6),
                ('How can parents track their child\'s attendance?', 'Parents can log into their Parent Dashboard to view their child\'s complete attendance record.', 7),
                ('Is the school environment safe for children?', 'Absolutely! We prioritize student safety with a caring environment and trained staff.', 8),
            ]
            for f in faq_seed:
                db.execute('INSERT INTO faq (question, answer, display_order) VALUES (?,?,?)', f)
            _mark_seeded('faq')
        
        # Default school settings
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
    """Generate unique ID like TSNV00001, PSNV00001, STSNV00001"""
    db = get_db()
    prefixes = {'admin': 'SNV', 'teacher': 'TSNV', 'parent': 'PSNV', 'student': 'STSNV'}
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

# 🚀 Combine both faculty and users (teachers) for display
def get_combined_faculty():
    """Fetches manual faculty AND registered teachers (from users) to show them together."""
    db = get_db()
    
    # 1. Manually added faculty (Admin -> Faculty page)
    manual_faculty = db.execute(
        'SELECT id, name, subject, qualification, experience, photo_url, bio, display_order FROM faculty ORDER BY display_order, id'
    ).fetchall()
    
    # 2. Registered teachers (Admin -> Create User page)
    teachers = db.execute(
        "SELECT id, name, subject, qualification, experience, photo_url FROM users WHERE role = 'teacher' AND is_active = 1"
    ).fetchall()
    
    combined = []
    seen_names = set() 
    
    # Add manual faculty first
    for f in manual_faculty:
        combined.append(dict(f))
        seen_names.add(f['name'].strip().lower())
        
    # Add registered teachers (if not already in manual faculty)
    for t in teachers:
        if t['name'].strip().lower() not in seen_names:
            t_dict = dict(t)
            t_dict['bio'] = t_dict.get('bio') or 'Dedicated teacher at Residential Shanti Niketan.'
            t_dict['display_order'] = 999 # Place at the end
            combined.append(t_dict)
            seen_names.add(t['name'].strip().lower())
            
    # Sort by display order, then name
    combined.sort(key=lambda x: (x.get('display_order', 0), x['name']))
    return combined


# =========================================
# 3.1. USER PHOTO + FIELD HELPERS
# =========================================
def save_user_photo(file_storage, max_mb=2):
    """Save uploaded user photo to static/uploads/photos/. Returns public URL or None."""
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_file(file_storage.filename):
        return None
    # Optional size check
    try:
        file_storage.stream.seek(0, os.SEEK_END)
        size = file_storage.stream.tell()
        file_storage.stream.seek(0)
        if size > max_mb * 1024 * 1024:
            return None
    except (AttributeError, OSError):
        pass  # stream not seekable — skip size check
    ext = file_storage.filename.rsplit('.', 1)[1].lower()
    filename = f"user_{secrets.token_hex(8)}.{ext}"
    photos_dir = UPLOAD_FOLDER / 'photos'
    photos_dir.mkdir(parents=True, exist_ok=True)
    file_storage.save(photos_dir / filename)
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
    # Normalization (safety net even if JS bypassed)
    if data.get('pan'):
        data['pan'] = data['pan'].upper()
    if data.get('ifsc'):
        data['ifsc'] = data['ifsc'].upper()
    if data.get('aadhar'):
        data['aadhar'] = re.sub(r'\D', '', data['aadhar']) or None
    return data

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
        if session.get('user_role') != 'admin':
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('user_dashboard'))
        return f(*args, **kwargs)
    return decorated

def get_dashboard_url(role):
    return url_for('admin_dashboard') if role == 'admin' else url_for('user_dashboard')

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
    
    # NEW: Fetch Gallery Images dynamically
    gallery_images = db.execute('SELECT * FROM gallery ORDER BY display_order, id').fetchall()
    
    return render_template('index.html', 
                          notices=notices,
                          upcoming_events=upcoming_events,
                          testimonials=testimonials,
                          achievements=achievements,
                          gallery_images=gallery_images) # <-- Passed to template

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
    # 🚀 CHANGED: Ab ye dono tables ka data combine karke layega
    faculty_list = get_combined_faculty()
    return render_template('faculty.html', faculty=faculty_list)

# PUBLIC EVENTS PAGE (For all users)
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

    # Form se data receive karo
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    role = request.form.get('role', user['role'])

    # Validation
    if not name or not email or not phone or not role:
        flash('Name, Email, Phone and Role are required.', 'error')
        return redirect(request.referrer or url_for('admin_users'))

    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        flash('Invalid email format.', 'error')
        return redirect(request.referrer or url_for('admin_users'))

    if role not in ('teacher', 'admin', 'parent', 'student'):
        flash('Invalid role.', 'error')
        return redirect(request.referrer or url_for('admin_users'))

    # Collect any extra fields present in the submitted form (role-aware)
    editable = set(COMMON_FIELDS) | set(ROLE_FIELDS.get(role, []))
    updates = {}
    for f in editable:
        if f in request.form:
            updates[f] = request.form.get(f, '').strip() or None

    # Normalization
    if updates.get('pan'):
        updates['pan'] = updates['pan'].upper()
    if updates.get('ifsc'):
        updates['ifsc'] = updates['ifsc'].upper()
    if updates.get('aadhar'):
        updates['aadhar'] = re.sub(r'\D', '', updates['aadhar']) or None

    # Student: keep class_name <-> child_class in sync for backward compat
    if role == 'student':
        if updates.get('class_name'):
            updates['child_class'] = updates['class_name']
        elif updates.get('child_class') and 'class_name' not in updates:
            updates['class_name'] = updates['child_class']

    # Photo (optional upload during edit)
    new_photo = request.files.get('photo')
    if new_photo and new_photo.filename:
        saved_url = save_user_photo(new_photo)
        if saved_url:
            updates['photo_url'] = saved_url

    # Build UPDATE
    set_parts = ['name = ?', 'email = ?', 'phone = ?', 'role = ?']
    params = [name, email, phone, role]
    for k, v in updates.items():
        set_parts.append(f'{k} = ?')
        params.append(v)
    params.append(user_id)

    try:
        db.execute(f"UPDATE users SET {', '.join(set_parts)} WHERE id = ?", tuple(params))
        
        # 🚀 Sync Edit to Faculty Table
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
            db.execute('DELETE FROM faculty WHERE user_id = ?', (user_id,))

        db.commit()

        # Agar admin apna hi profile edit kar raha hai, to session update karo
        if session['user_id'] == user_id:
            session['user_name'] = name
            session['user_role'] = role

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
    db = get_db()
    role = user['role']
    
    # Fetch all attendance for stats
    all_attendance = db.execute(
        'SELECT * FROM attendance WHERE user_id = ? ORDER BY date DESC',
        (user['id'],)
    ).fetchall()
    
    # Keep only 30 for the recent logs display (as per template)
    attendance = all_attendance[:30]
    
    messages = db.execute(
        'SELECT * FROM messages WHERE to_user_id = ? OR to_role = ? ORDER BY id DESC LIMIT 20',
        (user['id'], role)
    ).fetchall()
    
    if role == 'teacher':
        leaves = db.execute(
            'SELECT * FROM leave_requests WHERE user_id = ? ORDER BY id DESC',
            (user['id'],)
        ).fetchall()
        return render_template('teacher_dashboard.html',
                              user=user, notices=notices, attendance=attendance,
                              leaves=leaves, messages=messages)
    
    elif role == 'student':
        fees = db.execute(
            'SELECT * FROM fee_payments WHERE student_id = ? ORDER BY id DESC',
            (user['id'],)
        ).fetchall()
        
        # 🚀 NEW: Calculate Subject-wise Attendance
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

        # 🚀 NEW: Fetch Exam Marks
        exam_marks = db.execute('SELECT * FROM exam_marks WHERE student_id = ? ORDER BY exam_type, subject', (user['id'],)).fetchall()
        
        return render_template('student_dashboard.html',
                              user=user, notices=notices, attendance=attendance,
                              subject_stats=subject_stats, exam_marks=exam_marks,
                              fees=fees, messages=messages,
                              fee_qr=get_setting('fee_qr_url'),
                              upi_link=get_setting('upi_link'))
    
    elif role == 'parent':
        fees = db.execute(
            'SELECT * FROM fee_payments WHERE student_id = ? ORDER BY id DESC',
            (user['id'],)
        ).fetchall()
        return render_template('parent_dashboard.html',
                              user=user, notices=notices, attendance=attendance,
                              fees=fees, messages=messages,
                              fee_qr=get_setting('fee_qr_url'),
                              upi_link=get_setting('upi_link'))
    
    else:
        return render_template('user.html',
                              user=user, notices=notices, attendance=attendance,
                              leaves=[], fees=[], messages=messages,
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
    db.execute('INSERT INTO fee_payments (student_id, amount, payment_date, transaction_id, status, remarks) VALUES (?,?,?,?,?,?)',
               (session['user_id'], amount, datetime.now().strftime('%Y-%m-%d'), txn_id, 'pending', remarks))
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
        'total_users': db.execute('SELECT COUNT(*) FROM users').fetchone()[0],
        'total_teachers': db.execute("SELECT COUNT(*) FROM users WHERE role='teacher'").fetchone()[0],
        'total_parents': db.execute("SELECT COUNT(*) FROM users WHERE role='parent'").fetchone()[0],
        'total_students': db.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0],
        'total_notices': db.execute('SELECT COUNT(*) FROM notices').fetchone()[0],
        'total_enquiries': db.execute('SELECT COUNT(*) FROM enquiries').fetchone()[0],
        'pending_leaves': db.execute("SELECT COUNT(*) FROM leave_requests WHERE status='pending'").fetchone()[0],
        'pending_fees': db.execute("SELECT COUNT(*) FROM fee_payments WHERE status='pending'").fetchone()[0],
    }
    recent_users = db.execute('SELECT * FROM users ORDER BY id DESC LIMIT 6').fetchall()
    recent_leaves = db.execute('''SELECT lr.*, u.name as user_name, u.unique_id as user_uid, u.role as user_role 
                                   FROM leave_requests lr JOIN users u ON lr.user_id = u.id 
                                   ORDER BY lr.id DESC LIMIT 5''').fetchall()
    return render_template('admin.html', stats=stats, recent_users=recent_users, 
                          recent_leaves=recent_leaves, active_page='dashboard')

@app.route('/admin/users')
@admin_required
def admin_users():
    db = get_db()
    role_filter = request.args.get('role', 'all')
    if role_filter != 'all':
        users = db.execute('SELECT * FROM users WHERE role = ? ORDER BY id DESC', (role_filter,)).fetchall()
    else:
        users = db.execute('SELECT * FROM users ORDER BY id DESC').fetchall()
    return render_template('admin_users.html', users=users, role_filter=role_filter, active_page='users')

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

        # ---------- ROLE ----------
        if not role:
            errors['role'] = 'Please select a role'
        elif role not in ('teacher', 'admin', 'parent', 'student'):
            errors['role'] = 'Invalid role selected'

        # ---------- NAME ----------
        if not name:
            errors['name'] = 'Full name is required'
        elif len(name) < 2:
            errors['name'] = 'Name must be at least 2 characters'
        elif len(name) > 100:
            errors['name'] = 'Name must be at most 100 characters'

        # ---------- EMAIL ----------
        if not email:
            errors['email'] = 'Email is required'
        elif not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            errors['email'] = 'Invalid email format (e.g. user@example.com)'
        elif db.execute('SELECT 1 FROM users WHERE LOWER(email) = LOWER(?)',
                        (email,)).fetchone():
            errors['email'] = 'This email is already registered'

        # ---------- PHONE ----------
        if not phone:
            errors['phone'] = 'Mobile number is required'
        elif not re.match(r'^[0-9]{10}$', phone):
            errors['phone'] = 'Mobile number must be exactly 10 digits'
        elif db.execute('SELECT 1 FROM users WHERE phone = ?',
                        (phone,)).fetchone():
            errors['phone'] = 'This mobile number is already registered'

        # ---------- COMMON FORMAT CHECKS ----------
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

        # ---------- ROLE-SPECIFIC REQUIRED ----------
        if role == 'teacher':
            if not (form.get('qualification') or '').strip():
                errors['qualification'] = 'Qualification is required'
            if not (form.get('subject') or '').strip():
                errors['subject'] = 'Primary Subject is required'

        elif role == 'admin':
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
                # 'admission_no':  'Admission number is required',  <-- REMOVED
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

        # ---------- PHOTO (Optional) ----------
        photo_file = request.files.get('photo')
        has_photo = bool(photo_file and photo_file.filename)
        
        # if role == 'student' and not has_photo:
        #     errors['photo'] = 'Profile photo is required for student'  <-- REMOVED

        if has_photo and not allowed_file(photo_file.filename):
            errors['photo'] = 'Only JPG / PNG / WEBP / GIF allowed'

        # ---------- STOP & RE-RENDER IF ANY ERROR ----------
        if errors:
            flash(f'Please fix {len(errors)} error{"s" if len(errors)>1 else ""} below.', 'error')
            return render_template(
                'admin_create_user.html',
                form=form, errors=errors,
                active_page='create_user'
            )

        # ---------- SUCCESS: INSERT ----------
        fields = _collect_form_fields(role)

        if role == 'student' and fields.get('class_name'):
            fields['child_class']   = fields['class_name']
            fields['child_section'] = fields.get('section')

        photo_url = save_user_photo(photo_file)
        if photo_url:
            fields['photo_url'] = photo_url

        unique_id = generate_unique_id(role)
        hashed    = generate_password_hash(DEFAULT_PASSWORD)

        # NEW: Auto-generate admission_no if blank for student
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
            
            # 🚀 Sync Teacher to Faculty Table
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

    # ---------- GET ----------
    return render_template('admin_create_user.html',
                           form={}, errors={},
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
    db.execute('DELETE FROM users WHERE id = ?', (user_id,))
    db.execute('DELETE FROM faculty WHERE user_id = ?', (user_id,)) # 🚀 Faculty se bhi delete karein
    db.commit()
    flash('User deleted.', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/change-role/<int:user_id>', methods=['POST'])
@admin_required
def admin_change_role(user_id):
    new_role = request.form.get('role', 'student')
    if new_role not in ['teacher', 'admin', 'parent', 'student']:
        flash('Invalid role.', 'error')
        return redirect(url_for('admin_users'))
    
    if user_id == session['user_id']:
        flash('You cannot change your own role!', 'error')
        return redirect(url_for('admin_users'))
    
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    db.execute('UPDATE users SET role = ? WHERE id = ?', (new_role, user_id))
    
    # 🚀 Sync Role Change to Faculty
    if new_role == 'teacher':
        if not db.execute('SELECT 1 FROM faculty WHERE user_id = ?', (user_id,)).fetchone():
            db.execute('INSERT INTO faculty (user_id, name, subject) VALUES (?, ?, ?)', 
                       (user_id, user['name'], user['subject'] or 'General'))
    else:
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
    role = request.args.get('role', 'student')
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    users = db.execute('SELECT * FROM users WHERE role = ? ORDER BY name', (role,)).fetchall()
    records = db.execute('SELECT * FROM attendance WHERE date = ?', (date,)).fetchall()
    attendance_map = {r['user_id']: r['status'] for r in records}
    
    return render_template('admin_attendance.html', users=users, role=role, 
                          date=date, attendance_map=attendance_map, active_page='attendance')

@app.route('/admin/attendance/mark', methods=['POST'])
@admin_required
def admin_mark_attendance():
    date = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))
    subject = request.form.get('subject', 'General') # 🚀 NEW: Subject field
    db = get_db()
    
    for key, val in request.form.items():
        if key.startswith('status_'):
            uid = int(key.replace('status_', ''))
            existing = db.execute('SELECT id FROM attendance WHERE user_id = ? AND date = ? AND subject = ?', (uid, date, subject)).fetchone()
            if existing:
                db.execute('UPDATE attendance SET status = ?, marked_by = ? WHERE id = ?',
                           (val, session['user_id'], existing['id']))
            else:
                db.execute('INSERT INTO attendance (user_id, date, status, subject, marked_by) VALUES (?,?,?,?,?)',
                           (uid, date, val, subject, session['user_id']))
    db.commit()
    flash(f'Attendance marked for {date} ({subject}).', 'success')
    return redirect(url_for('admin_attendance', date=date))

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
    # 🚀 CHANGED: Ab admin page pe bhi dono tables ka data show hoga
    faculty = get_combined_faculty()
    return render_template('admin_faculty.html', faculty=faculty, active_page='faculty')

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
    
    # GET request: load faculty member to edit
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
    db.execute('DELETE FROM faculty WHERE id = ?', (fid,))
    db.commit()
    flash('Faculty removed.', 'success')
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

# NEW: EDIT EVENT ROUTE
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
    
    # GET request: load event to edit
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
            ext = image_file.filename.rsplit('.', 1)[1].lower()
            filename = f"gallery_{secrets.token_hex(6)}.{ext}"
            images_folder = BASE_DIR / 'static' / 'images'
            images_folder.mkdir(parents=True, exist_ok=True)
            image_file.save(images_folder / filename)
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
# INIT
# =========================================
init_db()

# ... baaki code ...

if __name__ == '__main__':
    app.run(
        debug=True,
        use_reloader=True,
        host=os.environ.get('HOST', '127.0.0.1'),
        port=int(os.environ.get('PORT', 5000))
    )
    
    # gayatrinirajng@gmail.com