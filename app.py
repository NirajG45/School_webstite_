from pathlib import Path
import os
import sqlite3
import re
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, g

# =========================================
# 1. APP CONFIGURATION & SETUP
# =========================================
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get('SCHOOL_DB_PATH', BASE_DIR / 'school.db'))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-before-deployment')
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024

# 🚀 UPGRADE: Security Headers for Production
app.config['SESSION_COOKIE_SECURE'] = True if os.environ.get('FLASK_ENV') == 'production' else False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Initial Seed Data for Notices (Agar DB khali hai toh yeh add ho jayega)
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
    """Creates tables and seeds initial notice data if empty."""
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
        
        # 🚀 UPGRADE: Notices Table (Ab notices dynamic hain)
        db.execute('''CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            title TEXT NOT NULL,
            tag TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # 🚀 UPGRADE: Seed initial notices if table is empty
        count = db.execute('SELECT COUNT(*) FROM notices').fetchone()[0]
        if count == 0:
            for notice in INITIAL_NOTICES:
                db.execute('INSERT INTO notices (date, title, tag, description) VALUES (?, ?, ?, ?)',
                           (notice['date'], notice['title'], notice['tag'], notice['desc']))
        db.commit()

def get_all_notices():
    """Helper to fetch notices for templates and API."""
    db = get_db()
    return db.execute('SELECT * FROM notices ORDER BY id DESC').fetchall()

# =========================================
# 3. ROUTES (PAGES & API)
# =========================================
@app.route('/')
def home():
    notices = get_all_notices()
    return render_template('index.html', notices=notices)

# 🚀 UPGRADE: New Notices Page Route
@app.route('/notice')
def notices_page():
    notices = get_all_notices()
    return render_template('notice.html', notices=notices)

# 🚀 UPGRADE: New Academics Page Route
@app.route('/academics')
def academics_page():
    return render_template('academics.html')

@app.route('/api/notices')
def api_notices():
    notices = get_all_notices()
    # Convert sqlite3.Row objects to dictionaries for JSON serialization
    notices_list = [dict(notice) for notice in notices]
    return jsonify({'notices': notices_list})

@app.route('/admission-enquiry', methods=['POST'])
def admission_enquiry():
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip()
    class_name = request.form.get('class_name', '').strip()
    message = request.form.get('message', '').strip()

    # 🚀 UPGRADE: Better Validation using Regex
    if not name or len(name) < 2:
        flash('Please enter a valid name (at least 2 characters).', 'error')
        return redirect(url_for('home') + '#admission')
        
    if not phone or not re.match(r'^[0-9+() -]{10,18}$', phone):
        flash('Please enter a valid phone number.', 'error')
        return redirect(url_for('home') + '#admission')

    if email and not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        flash('Please enter a valid email address.', 'error')
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
    flash('Your message has been received. The school team can follow up with you.', 'success')
    return redirect(url_for('home') + '#contact')

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'application': 'Residential Shanti Niketan'})

# =========================================
# 4. ERROR HANDLERS
# =========================================
@app.errorhandler(404)
def page_not_found(e):
    # Check karein ki 404.html file exist karti hai ya nahi
    template_path = os.path.join(BASE_DIR, 'templates', '404.html')
    if os.path.exists(template_path):
        return render_template('404.html'), 404
    return "Page not found", 404

@app.errorhandler(413)
def too_large(_error):
    flash('The submitted form is too large. Please shorten your message.', 'error')
    return redirect(url_for('home') + '#contact')

@app.errorhandler(500)
def internal_error(e):
    return "Internal Server Error. Please try again later.", 500

# =========================================
# 5. SECURITY HEADERS (Middleware)
# =========================================
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

# =========================================
# 6. APP INITIALIZATION
# =========================================
init_db()

if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG', '0') == '1', host='127.0.0.1', port=int(os.environ.get('PORT', 5000)))