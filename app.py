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
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
app.config['SESSION_COOKIE_SECURE'] = True if os.environ.get('FLASK_ENV') == 'production' else False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

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

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
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
        
        # Leave Requests
        db.execute('''CREATE TABLE IF NOT EXISTS leave_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            leave_type TEXT NOT NULL, from_date TEXT NOT NULL, to_date TEXT NOT NULL,
            reason TEXT NOT NULL, status TEXT DEFAULT 'pending',
            admin_remarks TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        
        # Attendance
        db.execute('''CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            date TEXT NOT NULL, status TEXT NOT NULL, remarks TEXT,
            marked_by INTEGER, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        
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
        
        # Seed notices
        count = db.execute('SELECT COUNT(*) FROM notices').fetchone()[0]
        if count == 0:
            for n in INITIAL_NOTICES:
                db.execute('INSERT INTO notices (date, title, tag, description, target_role) VALUES (?,?,?,?,?)',
                           (n['date'], n['title'], n['tag'], n['desc'], n['target_role']))
        
        # Default school settings
        db.execute("INSERT OR IGNORE INTO school_settings (key, value) VALUES ('fee_qr_url', '')")
        db.execute("INSERT OR IGNORE INTO school_settings (key, value) VALUES ('school_name', 'Residential Shanti Niketan')")
        # UPGRADE: Default UPI link setting
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
    
    # Ensure uniqueness
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

# =========================================
# 4. DECORATORS
# =========================================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please login to access this page.', 'error')
            return redirect(url_for('login_page'))
        # Force password change
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
    return render_template('index.html', notices=notices)

@app.route('/notice')
def notices_page():
    notices = get_all_notices()
    return render_template('notice.html', notices=notices)

@app.route('/academics')
def academics_page():
    return render_template('academics.html')

# =========================================
# 6. AUTH ROUTES (LOGIN ONLY - NO REGISTRATION)
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
# 7. USER DASHBOARD (ROLE-SPECIFIC ROUTING)
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
    
    # ===== Common data for all roles =====
    attendance = db.execute(
        'SELECT * FROM attendance WHERE user_id = ? ORDER BY date DESC LIMIT 30',
        (user['id'],)
    ).fetchall()
    
    messages = db.execute(
        'SELECT * FROM messages WHERE to_user_id = ? OR to_role = ? ORDER BY id DESC LIMIT 20',
        (user['id'], role)
    ).fetchall()
    
    # ===== ROLE-SPECIFIC ROUTING =====
    
    # ---------- TEACHER DASHBOARD ----------
    if role == 'teacher':
        leaves = db.execute(
            'SELECT * FROM leave_requests WHERE user_id = ? ORDER BY id DESC',
            (user['id'],)
        ).fetchall()
        return render_template('teacher_dashboard.html',
                              user=user, notices=notices, attendance=attendance,
                              leaves=leaves, messages=messages)
    
    # ---------- STUDENT DASHBOARD ----------
    elif role == 'student':
        fees = db.execute(
            'SELECT * FROM fee_payments WHERE student_id = ? ORDER BY id DESC',
            (user['id'],)
        ).fetchall()
        return render_template('student_dashboard.html',
                              user=user, notices=notices, attendance=attendance,
                              fees=fees, messages=messages,
                              fee_qr=get_setting('fee_qr_url'),
                              upi_link=get_setting('upi_link'))
    
    # ---------- PARENT DASHBOARD ----------
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
    
    # ---------- FALLBACK (Admin or unknown role) ----------
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
# 9. FEE PAYMENT (Student/Parent)
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
        role = request.form.get('role', '')
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        
        if not role or not name or not email or not phone:
            flash('Please fill required fields.', 'error')
            return redirect(url_for('admin_create_user'))
        
        db = get_db()
        if db.execute('SELECT 1 FROM users WHERE email = ?', (email,)).fetchone():
            flash('Email already exists.', 'error')
            return redirect(url_for('admin_create_user'))
        
        unique_id = generate_unique_id(role)
        hashed = generate_password_hash(DEFAULT_PASSWORD)
        
        # Collect role-specific fields
        dob = request.form.get('dob', '')
        gender = request.form.get('gender', '')
        address = request.form.get('address', '')
        qualification = experience = subject = designation = department = relation = child_name = child_class = None
        
        if role == 'teacher':
            qualification = request.form.get('qualification', '')
            experience = request.form.get('experience', '')
            subject = request.form.get('subject', '')
        elif role == 'admin':
            designation = request.form.get('designation', '')
            department = request.form.get('department', '')
        elif role == 'parent':
            relation = request.form.get('relation', '')
            child_name = request.form.get('child_name', '')
            child_class = request.form.get('child_class', '')
        elif role == 'student':
            child_class = request.form.get('child_class', '')
        
        db.execute('''INSERT INTO users 
            (unique_id, role, name, email, phone, password_hash, dob, gender, qualification, 
             experience, subject, designation, department, relation, child_name, child_class, address)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (unique_id, role, name, email, phone, hashed, dob, gender, qualification,
             experience, subject, designation, department, relation, child_name, child_class, address))
        db.commit()
        
        flash(f'{role.capitalize()} created! ID: {unique_id} | Default Password: {DEFAULT_PASSWORD}', 'success')
        return redirect(url_for('admin_users'))
    
    return render_template('admin_create_user.html', active_page='create_user')

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    if user_id == session['user_id']:
        flash('You cannot delete your own account!', 'error')
        return redirect(url_for('admin_users'))
    db = get_db()
    db.execute('DELETE FROM users WHERE id = ?', (user_id,))
    db.commit()
    flash('User deleted.', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/change-role/<int:user_id>', methods=['POST'])
@admin_required
def admin_change_role(user_id):
    """User का role बदलें"""
    new_role = request.form.get('role', 'student')
    if new_role not in ['teacher', 'admin', 'parent', 'student']:
        flash('Invalid role.', 'error')
        return redirect(url_for('admin_users'))
    
    # खुद का role न बदल पाए
    if user_id == session['user_id']:
        flash('You cannot change your own role!', 'error')
        return redirect(url_for('admin_users'))
    
    db = get_db()
    db.execute('UPDATE users SET role = ? WHERE id = ?', (new_role, user_id))
    db.commit()
    flash('User role updated successfully.', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/reset-password/<int:user_id>', methods=['POST'])
@admin_required
def admin_reset_password(user_id):
    """Password reset करके default पर लाएं"""
    db = get_db()
    db.execute('UPDATE users SET password_hash = ?, force_password_change = 1 WHERE id = ?',
               (generate_password_hash(DEFAULT_PASSWORD), user_id))
    db.commit()
    flash(f'Password reset to default: {DEFAULT_PASSWORD}', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/toggle/<int:user_id>', methods=['POST'])
@admin_required
def admin_toggle_user(user_id):
    """User को Active/Inactive करें"""
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
    
    # Get today's attendance map
    records = db.execute('SELECT * FROM attendance WHERE date = ?', (date,)).fetchall()
    attendance_map = {r['user_id']: r['status'] for r in records}
    
    return render_template('admin_attendance.html', users=users, role=role, 
                          date=date, attendance_map=attendance_map, active_page='attendance')

@app.route('/admin/attendance/mark', methods=['POST'])
@admin_required
def admin_mark_attendance():
    date = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))
    db = get_db()
    
    for key, val in request.form.items():
        if key.startswith('status_'):
            uid = int(key.replace('status_', ''))
            # Upsert
            existing = db.execute('SELECT id FROM attendance WHERE user_id = ? AND date = ?', (uid, date)).fetchone()
            if existing:
                db.execute('UPDATE attendance SET status = ?, marked_by = ? WHERE id = ?',
                           (val, session['user_id'], existing['id']))
            else:
                db.execute('INSERT INTO attendance (user_id, date, status, marked_by) VALUES (?,?,?,?)',
                           (uid, date, val, session['user_id']))
    db.commit()
    flash(f'Attendance marked for {date}.', 'success')
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
    # UPGRADE: Pass upi_link to admin fees page
    return render_template('admin_fees.html', payments=payments,
                          fee_qr=get_setting('fee_qr_url'),
                          upi_link=get_setting('upi_link'),
                          active_page='fees')

@app.route('/admin/fees/qr', methods=['POST'])
@admin_required
def admin_update_qr():
    """UPGRADE: QR image upload या UPI link update करें"""
    
    # UPI Link
    upi_link = request.form.get('upi_link', '').strip()
    if upi_link:
        set_setting('upi_link', upi_link)
    
    # QR Image - File Upload
    qr_file = request.files.get('qr_image')
    if qr_file and qr_file.filename:
        if allowed_file(qr_file.filename):
            ext = qr_file.filename.rsplit('.', 1)[1].lower()
            filename = f"fee_qr_{secrets.token_hex(6)}.{ext}"
            filepath = app.config['UPLOAD_FOLDER'] / filename
            qr_file.save(filepath)
            # Store relative URL for template
            qr_url = url_for('static', filename=f'uploads/{filename}')
            set_setting('fee_qr_url', qr_url)
            flash('QR image uploaded successfully!', 'success')
        else:
            flash('Invalid file type. Only PNG, JPG, JPEG, GIF, WEBP allowed.', 'error')
    
    # QR Image - URL (fallback)
    qr_url_input = request.form.get('fee_qr_url', '').strip()
    if qr_url_input:
        set_setting('fee_qr_url', qr_url_input)
        flash('QR URL updated successfully!', 'success')
    
    # Delete QR
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

if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG', '0') == '1', host='127.0.0.1', port=int(os.environ.get('PORT', 5000)))