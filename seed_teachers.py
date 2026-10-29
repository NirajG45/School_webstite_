"""
seed_teachers.py
--------------------------------------------------
Populates the users + faculty tables with 11 teachers.

Teachers (as given):
  • Punit Kumar Singh  (PK Sir)          → Mathematics
  • Joyti Kumari       (Badi Maam)       → Hindi
  • Mahesh             (Mahesh Sir)      → Social Science
  • Baby               (Baby Maam)       → English
  • Dinanath           (Dinanath Sir)    → Sanskrit
  • Suraj              (Suraj Sir)       → Physical Education
  • Niraj Kumar        (Niraj Sir)       → Computer Science
  • Payal              (Payal Maam)      → Science
  • Sweta              (Sweta Maam)      → English
  • Mushkan            (Mushkan Maam)    → Hindi
  • Khushi Kumari      (Khushi Maam)     → Mathematics

Run:  python seed_teachers.py
Safe to run multiple times (idempotent).
"""

import random
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

# ⚠️ Change 'app' if your main file has a different name
from app import app, get_db, generate_unique_id, DEFAULT_PASSWORD

random.seed(7)

# ─────────────────────────────────────────────────────────
# 1. TEACHER DEFINITIONS
# ─────────────────────────────────────────────────────────
# 'name'        → stored in DB (users.name)
# 'display'     → console me dikhane ke liye (nickname/title)
# 'qualification' → "Graduate" (user ne bola sabhi graduated hain)
TEACHERS = [
    {
        "name":             "Punit Kumar Singh",
        "display":          "PK Sir",
        "gender":           "Male",
        "subject":          "Mathematics",
        "qualification":    "Graduate",
        "specialization":   "Mathematics",
        "classes_assigned": "6th,7th,8th",
        "experience":       "6 years",
        "designation":      "Senior Teacher",
    },
    {
        "name":             "Joyti Kumari",
        "display":          "Badi Maam",
        "gender":           "Female",
        "subject":          "Hindi",
        "qualification":    "Graduate",
        "specialization":   "Hindi Literature",
        "classes_assigned": "5th,6th,7th,8th",
        "experience":       "8 years",
        "designation":      "Senior Teacher",
    },
    {
        "name":             "Mahesh",
        "display":          "Mahesh Sir",
        "gender":           "Male",
        "subject":          "Social Science",
        "qualification":    "Graduate",
        "specialization":   "History & Civics",
        "classes_assigned": "5th,6th,7th,8th",
        "experience":       "4 years",
        "designation":      "Teacher",
    },
    {
        "name":             "Baby",
        "display":          "Baby Maam",
        "gender":           "Female",
        "subject":          "English",
        "qualification":    "Graduate",
        "specialization":   "English Literature",
        "classes_assigned": "1st,2nd,3rd,4th",
        "experience":       "5 years",
        "designation":      "Teacher",
    },
    {
        "name":             "Dinanath",
        "display":          "Dinanath Sir",
        "gender":           "Male",
        "subject":          "Sanskrit",
        "qualification":    "Graduate",
        "specialization":   "Sanskrit",
        "classes_assigned": "5th,6th,7th,8th",
        "experience":       "7 years",
        "designation":      "Teacher",
    },
    {
        "name":             "Suraj",
        "display":          "Suraj Sir",
        "gender":           "Male",
        "subject":          "Physical Education",
        "qualification":    "Graduate",
        "specialization":   "Sports & Physical Education",
        "classes_assigned": "Pre,1st,2nd,3rd,4th,5th,6th,7th,8th",
        "experience":       "3 years",
        "designation":      "Sports Teacher",
    },
    {
        "name":             "Niraj Kumar",
        "display":          "Niraj Sir",
        "gender":           "Male",
        "subject":          "Computer Science",
        "qualification":    "Graduate in Computer Science",
        "specialization":   "Computer Science",
        "classes_assigned": "4th,5th,6th,7th,8th",
        "experience":       "3 years",
        "designation":      "Computer Teacher",
    },
    {
        "name":             "Payal",
        "display":          "Payal Maam",
        "gender":           "Female",
        "subject":          "Science",
        "qualification":    "Graduate",
        "specialization":   "Science",
        "classes_assigned": "5th,6th,7th,8th",
        "experience":       "2 years",
        "designation":      "Teacher",
    },
    {
        "name":             "Sweta",
        "display":          "Sweta Maam",
        "gender":           "Female",
        "subject":          "English",
        "qualification":    "Graduate",
        "specialization":   "English",
        "classes_assigned": "5th,6th,7th,8th",
        "experience":       "4 years",
        "designation":      "Teacher",
    },
    {
        "name":             "Mushkan",
        "display":          "Mushkan Maam",
        "gender":           "Female",
        "subject":          "Hindi",
        "qualification":    "Graduate",
        "specialization":   "Hindi",
        "classes_assigned": "1st,2nd,3rd,4th",
        "experience":       "2 years",
        "designation":      "Teacher",
    },
    {
        "name":             "Khushi Kumari",
        "display":          "Khushi Maam",
        "gender":           "Female",
        "subject":          "Mathematics",
        "qualification":    "Graduate",
        "specialization":   "Mathematics",
        "classes_assigned": "Pre,1st,2nd,3rd,4th",
        "experience":       "2 years",
        "designation":      "Teacher",
    },
]

# ─────────────────────────────────────────────────────────
# 2. UNIQUENESS HELPERS
# ─────────────────────────────────────────────────────────
_phone_seq  = [7100000000]
_aadhar_seq = [200000000000]

def fresh_phone(db):
    while True:
        _phone_seq[0] += random.randint(11, 999)
        p = str(_phone_seq[0])
        if len(p) == 10 and not db.execute(
            'SELECT 1 FROM users WHERE phone = ?', (p,)
        ).fetchone():
            return p

def fresh_aadhar(db):
    while True:
        _aadhar_seq[0] += 1
        a = str(_aadhar_seq[0])
        if len(a) == 12 and not db.execute(
            'SELECT 1 FROM users WHERE aadhar = ?', (a,)
        ).fetchone():
            return a

def fresh_email(db, name):
    clean = ''.join(c for c in name.lower() if c.isalnum())
    base  = f"{clean}.teacher@snv.edu"
    cand, i = base, 1
    while db.execute('SELECT 1 FROM users WHERE email = ?', (cand,)).fetchone():
        i += 1
        cand = base.replace('@', f".{i}@")
    return cand

# ─────────────────────────────────────────────────────────
# 3. MISC GENERATORS
# ─────────────────────────────────────────────────────────
def random_address():
    colony = random.choice([
        "Gandhi Nagar", "Nehru Colony", "Shanti Vihar",
        "Krishna Nagar", "Ram Nagar", "Shivaji Nagar", "Lajpat Nagar",
    ])
    return f"{random.randint(1, 250)}, {colony}, Patna"

def pick_dob():
    y = random.randint(1985, 1998)
    return f"{y}-{random.randint(1,12):02d}-{random.randint(1,28):02d}"

def random_join_date():
    days = random.randint(180, 365 * 6)
    return (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

def random_blood_group():
    return random.choice(['A+', 'B+', 'O+', 'AB+', 'A-', 'B-', 'O-'])

# ─────────────────────────────────────────────────────────
# 4. CORE INSERT FUNCTION
# ─────────────────────────────────────────────────────────
def insert_teacher(db, t):
    """
    Insert one teacher into users + faculty tables.
    Returns dict on success, None if already exists.
    """
    # Skip if user with same name + role='teacher' already exists
    if db.execute(
        "SELECT 1 FROM users WHERE role='teacher' AND name = ?",
        (t['name'],)
    ).fetchone():
        return None

    unique_id    = generate_unique_id('teacher')          # SNVT00001
    phone        = fresh_phone(db)
    aadhar       = fresh_aadhar(db)
    email        = fresh_email(db, t['name'])
    employee_id  = f"EMP{unique_id.replace('SNVT', '').zfill(5)}"
    dob          = pick_dob()
    joining_date = random_join_date()

    data = {
        # ── base
        'unique_id':             unique_id,
        'role':                  'teacher',
        'name':                  t['name'],
        'email':                 email,
        'phone':                 phone,
        'password_hash':         generate_password_hash(DEFAULT_PASSWORD),
        'force_password_change': 1,
        'gender':                t['gender'],
        'dob':                   dob,

        # ── teacher-specific
        'qualification':         t['qualification'],
        'specialization':        t['specialization'],
        'experience':            t['experience'],
        'total_experience':      t['experience'],
        'subject':               t['subject'],
        'classes_assigned':      t['classes_assigned'],
        'designation':           t['designation'],
        'employee_id':           employee_id,
        'joining_date':          joining_date,
        'employment_type':       'Full-time',
        'languages':             'Hindi, English',

        # ── common
        'address':               random_address(),
        'city':                  'Patna',
        'state':                 'Bihar',
        'pincode':               '800001',
        'nationality':           'Indian',
        'aadhar':                aadhar,
        'blood_group':           random_blood_group(),
        'marital_status':        random.choice(['Married', 'Single']),
    }

    cols = ', '.join(data.keys())
    ph   = ', '.join(['?'] * len(data))
    db.execute(f'INSERT INTO users ({cols}) VALUES ({ph})', tuple(data.values()))

    # Get the new user id
    new_user_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

    # ── Sync into faculty table (so faculty page & subject assignments work)
    if not db.execute('SELECT 1 FROM faculty WHERE user_id = ?', (new_user_id,)).fetchone():
        db.execute(
            '''INSERT INTO faculty
               (user_id, name, subject, qualification, experience, bio, display_order)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (new_user_id, t['name'], t['subject'], t['qualification'],
             t['experience'],
             f"{t['designation']} at Residential Shanti Niketan, teaching {t['subject']}.",
             0)
        )

    db.commit()

    return {
        'unique_id': unique_id,
        'name':      t['name'],
        'display':   t['display'],
        'subject':   t['subject'],
        'emp_id':    employee_id,
    }

# ─────────────────────────────────────────────────────────
# 5. MAIN
# ─────────────────────────────────────────────────────────
def main():
    print("\n" + "=" * 70)
    print("👨‍🏫 TEACHER SEED SCRIPT — Residential Shanti Niketan")
    print("=" * 70)

    with app.app_context():
        db      = get_db()
        created = 0
        skipped = 0

        print(f"\n📚 Inserting {len(TEACHERS)} teachers...\n")

        for t in TEACHERS:
            res = insert_teacher(db, t)
            if res:
                created += 1
                print(f"   ✓ {t['display']:<15} ({t['name']:<22}) "
                      f"→ {res['unique_id']}  |  {res['subject']}")
            else:
                skipped += 1
                print(f"   – {t['display']:<15} ({t['name']}) already exists")

        # ── Final report
        total_teachers = db.execute(
            "SELECT COUNT(*) FROM users WHERE role='teacher'"
        ).fetchone()[0]
        total_faculty = db.execute(
            "SELECT COUNT(*) FROM faculty"
        ).fetchone()[0]

        print("\n" + "=" * 70)
        print(f"✅ Teachers Created : {created}")
        print(f"⏭  Teachers Skipped : {skipped} (already existed)")
        print(f"👨‍🏫 Total Teachers in DB  : {total_teachers}")
        print(f"🏫 Total Faculty entries  : {total_faculty}")
        print("=" * 70)
        print(f"\n🔑 Default password for all teachers: {DEFAULT_PASSWORD}")
        print("   Login with Unique ID (e.g. SNVT00001)\n")

        # ── Preview table
        print("\n" + "=" * 90)
        print("📋 TEACHER SUMMARY")
        print("=" * 90)
        print(f"{'Unique ID':<12} {'Name':<22} {'Subject':<20} {'Classes Assigned':<30}")
        print("-" * 90)
        rows = db.execute(
            "SELECT unique_id, name, subject, classes_assigned "
            "FROM users WHERE role='teacher' ORDER BY id"
        ).fetchall()
        for r in rows:
            print(f"{r['unique_id']:<12} {r['name']:<22} "
                  f"{r['subject'] or '-':<20} {r['classes_assigned'] or '-':<30}")
        print("=" * 90 + "\n")


if __name__ == '__main__':
    main()