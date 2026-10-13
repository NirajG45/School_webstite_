from pathlib import Path
import os
import sqlite3
import re
from functools import wraps
from datetime import timedelta
from flask import (Flask, render_template, request, redirect, url_for, flash, jsonify, g, session)
from werkzeug.security import generate_password_hash, check_password_hash

# =========================================
# 1. APP CONFIGURATION & SETUP
# =========================================
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get('SCHOOL_DB_PATH', BASE_DIR / 'school.db'))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-before-deployment')
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2MB for Resume uploads

# Security Headers for Production
app.config['SESSION_COOKIE_SECURE'] = True if os.environ.get('FLASK_ENV') == 'production' else False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)  # Session 7 दिन तक valid रहेगा

# Initial Seed Data for Notices
INITIAL_NOTICES = [
    {'date': '05 Oct 2026', 'title': 'Admissions enquiry open for Session 2026–27', 'tag': 'Admissions', 'desc': 'Admissions are now open for the upcoming academic session. Please contact the school office for details.'},
    {'date': '28 Sep 2026', 'title': 'Class-wise timetable and school routine', 'tag': 'Academics', 'desc': 'The new class-wise timetable has been published. Students can collect it from their respective class teachers.'},
    {'date': '22 Sep 2026', 'title': 'Annual sports and activities update', 'tag': 'Activities', 'desc': 'Annual sports day is approaching. All students are encouraged to participate in various events.'},
    {'date': '15 Sep 2026', 'title': 'Parent–teacher meeting information', 'tag': 'Notice', 'desc': 'A PTM is scheduled for all classes. Parents are requested to attend without fail.'},
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
    """Creates tables and seeds initial data if empty."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        # Enquiries Table
        db.execute('''CREATE TABLE IF NOT EXISTS enquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT,
            class_name TEXT,
            message TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Notices Table
        db.execute('''CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            title TEXT NOT NULL,
            tag TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Users Table (For Login & Registration)
        db.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            dob TEXT,
            gender TEXT,
            qualification TEXT,
            experience TEXT,
            subject TEXT,
            designation TEXT,
            department TEXT,
            relation TEXT,
            child_name TEXT,
            child_class TEXT,
            address TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Seed initial notices
        count = db.execute('SELECT COUNT(*) FROM notices').fetchone()[0]
        if count == 0:
            for notice in INITIAL_NOTICES:
                db.execute('INSERT INTO notices (date, title, tag, description) VALUES (?, ?, ?, ?)',
                           (notice['date'], notice['title'], notice['tag'], notice['desc']))
        db.commit()

def get_all_notices():
    db = get_db()
    return db.execute('SELECT * FROM notices ORDER BY id DESC').fetchall()

def get_user_by_id(user_id):
    db = get_db()
    return db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

# =========================================
# 3. LOGIN DECORATOR (Protects Routes)
# =========================================
def login_required(f):
    """UPGRADE: कोई भी प्रोटेक्टेड राउट सिर्फ लॉगिन यूज़र ही खोल सके।"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please login to access this page.', 'error')
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

# =========================================
# 4. ROUTES (PAGES & API)
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
# 5. AUTHENTICATION ROUTES
# =========================================
@app.route('/login', methods=['GET'])
def login_page():
    # UPGRADE: अगर यूज़र पहले से लॉगिन है, तो डैशबोर्ड पर भेजें
    if session.get('user_id'):
        return redirect(url_for('user_dashboard'))
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    role = request.form.get('role', 'student')
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    
    # Basic Validation
    if not name or not email or not phone or not password:
        flash('Please fill all required fields.', 'error')
        return redirect(url_for('login_page'))
        
    if password != confirm_password:
        flash('Passwords do not match.', 'error')
        return redirect(url_for('login_page'))

    if len(password) < 6:
        flash('Password must be at least 6 characters long.', 'error')
        return redirect(url_for('login_page'))

    # UPGRADE: Email format check
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        flash('Please enter a valid email address.', 'error')
        return redirect(url_for('login_page'))

    # Check if email already exists
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    if user:
        flash('Email already registered. Please login.', 'error')
        return redirect(url_for('login_page'))

    # Hash password
    hashed_password = generate_password_hash(password)
    
    # Collect common fields
    address = request.form.get('address', '')
    dob = request.form.get('dob', '')
    gender = request.form.get('gender', '')
    
    # Role-specific fields
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
        child_class = request.form.get('class_applying', '')

    # Insert into DB
    db.execute('''INSERT INTO users 
                  (role, name, email, phone, password_hash, dob, gender, qualification, experience, subject, designation, department, relation, child_name, child_class, address) 
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
               (role, name, email, phone, hashed_password, dob, gender, qualification, experience, subject, designation, department, relation, child_name, child_class, address))
    db.commit()
    
    flash('Registration successful! Please login to continue.', 'success')
    return redirect(url_for('login_page'))

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email', '').strip()
    password = request.form.get('password')
    
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    
    if user and check_password_hash(user['password_hash'], password):
        # UPGRADE: Session को Permanent बनाएं (7 दिन तक valid)
        session.permanent = True
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        session['user_role'] = user['role']
        flash(f'Welcome back, {user["name"]}!', 'success')
        # UPGRADE: होम की जगह डैशबोर्ड पर भेजें
        return redirect(url_for('user_dashboard'))
    else:
        flash('Invalid email or password.', 'error')
        return redirect(url_for('login_page'))

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('home'))

# =========================================
# 6. USER DASHBOARD & PROFILE
# =========================================
@app.route('/dashboard')
@login_required
def user_dashboard():
    """UPGRADE: यूज़र का निजी डैशबोर्ड।"""
    user = get_user_by_id(session['user_id'])
    if not user:
        # अगर किसी कारणवश DB में यूज़र न मिले
        session.clear()
        flash('Session expired. Please login again.', 'error')
        return redirect(url_for('login_page'))
    
    notices = get_all_notices()
    return render_template('user.html', user=user, notices=notices)

@app.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    """UPGRADE: यूज़र अपनी प्रोफाइल अपडेट कर सके।"""
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    address = request.form.get('address', '').strip()
    
    if not name or not phone:
        flash('Name and phone are required.', 'error')
        return redirect(url_for('user_dashboard'))
    
    db = get_db()
    db.execute('UPDATE users SET name = ?, phone = ?, address = ? WHERE id = ?',
               (name, phone, address, session['user_id']))
    db.commit()
    
    # Session में नाम भी अपडेट करें
    session['user_name'] = name
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('user_dashboard'))

# =========================================
# 7. API & FORM ROUTES
# =========================================
@app.route('/api/notices')
def api_notices():
    notices = get_all_notices()
    return jsonify({'notices': [dict(notice) for notice in notices]})

@app.route('/admission-enquiry', methods=['POST'])
def admission_enquiry():
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip()
    class_name = request.form.get('class_name', '').strip()
    message = request.form.get('message', '').strip()

    if not name or len(name) < 2:
        flash('Please enter a valid name (at least 2 characters).', 'error')
        return redirect(url_for('home') + '#admission')
        
    if not phone or not re.match(r'^[0-9+() -]{10,18}$', phone):
        flash('Please enter a valid phone number.', 'error')
        return redirect(url_for('home') + '#admission')

    db = get_db()
    db.execute('INSERT INTO enquiries (kind, name, phone, email, class_name, message) VALUES (?, ?, ?, ?, ?, ?)',
               ('admission', name, phone, email, class_name, message))
    db.commit()
    flash('Thank you! Your admission enquiry has been submitted.', 'success')
    return redirect(url_for('home') + '#admission')

@app.route('/contact', methods=['POST'])
def contact():
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    message = request.form.get('message', '').strip()

    if not name or not phone or not message:
        flash('Please complete your name, phone and message.', 'error')
        return redirect(url_for('home') + '#contact')
        
    if not re.match(r'^[0-9+() -]{10,18}$', phone):
        flash('Please enter a valid phone number.', 'error')
        return redirect(url_for('home') + '#contact')

    db = get_db()
    db.execute('INSERT INTO enquiries (kind, name, phone, message) VALUES (?, ?, ?, ?)',
               ('contact', name, phone, message))
    db.commit()
    flash('Your message has been received.', 'success')
    return redirect(url_for('home') + '#contact')

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'application': 'Residential Shanti Niketan'})

# =========================================
# 8. ERROR HANDLERS & SECURITY
# =========================================
@app.errorhandler(404)
def page_not_found(e):
    return "Page not found", 404

@app.errorhandler(413)
def too_large(_error):
    flash('The submitted form is too large. Please shorten your message.', 'error')
    return redirect(url_for('home') + '#contact')

@app.errorhandler(500)
def internal_error(e):
    return "Internal Server Error. Please try again later.", 500

@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

# =========================================
# 9. APP INITIALIZATION
# =========================================
init_db()

if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG', '0') == '1', host='127.0.0.1', port=int(os.environ.get('PORT', 5000)))