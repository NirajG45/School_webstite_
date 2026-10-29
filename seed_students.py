"""
seed_students.py
--------------------------------------------------
Populates the users table with 180 students + 180 parents:
  • Pre, 1st, 2nd, 3rd, 4th, 5th  → 20 students each (generated names)
  • 6th, 7th, 8th                 → listed names + fill to 20
  • Har student ka ek Father (parent) bhi create hota hai

Run:  python seed_students.py
Safe to run multiple times (idempotent).
"""

import random
from werkzeug.security import generate_password_hash

# ⚠️ Change 'app' if your main file has a different name
from app import app, get_db, generate_unique_id, DEFAULT_PASSWORD

random.seed(42)

# ─────────────────────────────────────────────────────────
# 1. DATA DEFINITIONS
# ─────────────────────────────────────────────────────────
LISTED_STUDENTS = {
    "6th": [
        "Omgeet kumar", "Sintu", "Pintu", "Alok", "Chahat kumar",
        "Vishal", "Amit", "Suman", "Sweta", "Alshama",
        "Mariya", "Shidhant", "Divanshu", "Lav Kumar",
    ],
    "7th": [
        "Rishu", "Rishika", "Manshi", "Navneet", "Subham",
        "Rajnanadani", "Prataksha", "Arushi", "Sashikant Devraj",
    ],
    "8th": [
        "Anushka", "Divanshu", "Aayush", "Rajveer", "Gaurav",
        "Shiva", "Mahi", "Akanksha", "Anjali", "Agam",
    ],
}

LISTED_GENDER = {
    "Omgeet kumar": "Male", "Sintu": "Male", "Pintu": "Male", "Alok": "Male",
    "Chahat kumar": "Male", "Vishal": "Male", "Amit": "Male", "Suman": "Male",
    "Sweta": "Female", "Alshama": "Female", "Mariya": "Female",
    "Shidhant": "Male", "Divanshu": "Male", "Lav Kumar": "Male",
    "Rishu": "Male", "Rishika": "Female", "Manshi": "Female",
    "Navneet": "Male", "Subham": "Male", "Rajnanadani": "Female",
    "Prataksha": "Female", "Arushi": "Female", "Sashikant Devraj": "Male",
    "Anushka": "Female", "Aayush": "Male", "Rajveer": "Male",
    "Gaurav": "Male", "Shiva": "Male", "Mahi": "Female",
    "Akanksha": "Female", "Anjali": "Female", "Agam": "Male",
}

MALE_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Reyansh", "Ayaan",
    "Krishna", "Ishaan", "Shaurya", "Atharv", "Advik", "Pranav", "Dhruv",
    "Kabir", "Aryan", "Ansh", "Rudra", "Yuvraj", "Lakshya", "Siddharth",
    "Harsh", "Yash", "Rohan", "Mohit", "Nikhil", "Saurabh", "Ankit",
    "Deepak", "Manish", "Rahul", "Vikas", "Sachin", "Akash", "Abhishek",
    "Raj", "Naveen", "Piyush", "Shivam", "Karan",
]
FEMALE_NAMES = [
    "Diya", "Aanya", "Aadhya", "Ananya", "Pari", "Anika", "Navya", "Saanvi",
    "Angel", "Myra", "Sara", "Ira", "Kavya", "Riya", "Tara", "Pihu",
    "Misha", "Kiara", "Aarohi", "Prisha", "Sneha", "Priya", "Neha",
    "Pooja", "Nisha", "Komal", "Shreya", "Simran", "Anamika", "Ritika",
    "Aditi", "Megha", "Kritika", "Palak", "Naina", "Sakshi", "Ayushi",
    "Muskan", "Ayesha", "Bhavna",
]
SURNAMES = [
    "Sharma", "Verma", "Gupta", "Singh", "Kumar", "Yadav", "Mishra",
    "Tiwari", "Pandey", "Joshi", "Rao", "Nair", "Reddy", "Patel",
    "Chauhan", "Rajput", "Agarwal", "Saxena", "Srivastava", "Dubey",
    "Sinha", "Jha", "Thakur", "Kashyap",
]

CLASS_ORDER     = ["Pre", "1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th"]
TARGET_PER_CLASS = 20

BIRTH_YEAR = {
    "Pre": 2022, "1st": 2019, "2nd": 2018, "3rd": 2017,
    "4th": 2016, "5th": 2015, "6th": 2014, "7th": 2013, "8th": 2012,
}

# ─────────────────────────────────────────────────────────
# 2. UNIQUENESS HELPERS  (phone / aadhar / email)
# ─────────────────────────────────────────────────────────
_phone_seq  = [7000000000]
_aadhar_seq = [100000000000]

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

def fresh_email(db, name, class_name, roll):
    clean = ''.join(c for c in name.lower() if c.isalnum())
    base  = f"{clean}.{class_name.lower()}{roll}@student.snv.edu"
    cand, i = base, 1
    while db.execute('SELECT 1 FROM users WHERE email = ?', (cand,)).fetchone():
        i += 1
        cand = base.replace('@', f".{i}@")
    return cand

# ─────────────────────────────────────────────────────────
# 3. MISC GENERATORS
# ─────────────────────────────────────────────────────────
def pick_dob(class_name):
    y = BIRTH_YEAR.get(class_name, 2015)
    return f"{y}-{random.randint(1,12):02d}-{random.randint(1,28):02d}"

def make_parent(relation):
    pool   = MALE_NAMES if relation == 'father' else FEMALE_NAMES
    prefix = "Mr." if relation == 'father' else "Mrs."
    return f"{prefix} {random.choice(pool)} {random.choice(SURNAMES)}"

def random_address():
    colony = random.choice([
        "Gandhi Nagar", "Nehru Colony", "Shanti Vihar",
        "Krishna Nagar", "Ram Nagar", "Shivaji Nagar", "Lajpat Nagar",
    ])
    return f"{random.randint(1, 250)}, {colony}, Patna"

def section_for(roll):
    return 'A' if roll <= 10 else 'B'

# ─────────────────────────────────────────────────────────
# 4. CORE INSERT FUNCTION (STUDENT)
# ─────────────────────────────────────────────────────────
def insert_student(db, class_name, name, roll, gender):
    """
    Insert one student. Returns dict on success, None if already exists.
    """
    email = fresh_email(db, name, class_name, roll)
    if db.execute('SELECT 1 FROM users WHERE email = ?', (email,)).fetchone():
        return None

    unique_id    = generate_unique_id('student')
    phone        = fresh_phone(db)
    father_phone = fresh_phone(db)
    mother_phone = fresh_phone(db)
    aadhar       = fresh_aadhar(db)
    father_name  = make_parent('father')
    mother_name  = make_parent('mother')
    dob          = pick_dob(class_name)
    section      = section_for(roll)

    data = {
        # base
        'unique_id':             unique_id,
        'role':                  'student',
        'name':                  name,
        'email':                 email,
        'phone':                 phone,
        'password_hash':         generate_password_hash(DEFAULT_PASSWORD),
        'force_password_change': 1,
        'dob':                   dob,
        'gender':                gender,
        'address':               random_address(),
        'class_name':            class_name,
        'child_class':           class_name,
        'section':               section,
        'child_section':         section,
        'roll_no':               str(roll),
        'admission_no':          unique_id,
        'admission_date':        "2025-04-01",
        'father_name':           father_name,
        'father_mobile':         father_phone,
        'mother_name':           mother_name,
        'mother_mobile':         mother_phone,
        'aadhar':                aadhar,
        'category':              'General',
        'religion':              'Hindu',
        'city':                  'Patna',
        'state':                 'Bihar',
        'pincode':               '800001',
        'nationality':           'Indian',
        'blood_group':           random.choice(['A+', 'B+', 'O+', 'AB+', 'A-', 'O-']),
    }

    cols = ', '.join(data.keys())
    ph   = ', '.join(['?'] * len(data))
    db.execute(f'INSERT INTO users ({cols}) VALUES ({ph})', tuple(data.values()))
    db.commit()

    return {'unique_id': unique_id, 'name': name, 'class': class_name, 'roll': roll}

# ─────────────────────────────────────────────────────────
# 5. PARENT INSERT FUNCTION
# ─────────────────────────────────────────────────────────
def insert_parent_for_student(db, s):
    """
    Ek student ke liye ek Father (parent) user banao.
    - Skip if parent already linked (child_admission_no).
    - Returns True if created, False if skipped.
    """
    # Already linked?
    if db.execute(
        "SELECT 1 FROM users WHERE role='parent' AND child_admission_no=?",
        (s['admission_no'],)
    ).fetchone():
        return False

    pid            = generate_unique_id('parent')
    pphone         = fresh_phone(db)
    pemail         = f"parent.{s['unique_id'].lower()}@snv.edu"

    # Email collision guard (very rare, but safe)
    if db.execute('SELECT 1 FROM users WHERE email=?', (pemail,)).fetchone():
        pemail = f"parent.{s['unique_id'].lower()}.{random.randint(10,999)}@snv.edu"

    parent_name    = s['father_name'] or f"Parent of {s['name']}"

    db.execute("""
        INSERT INTO users
          (unique_id, role, name, email, phone, password_hash,
           force_password_change, relation, child_name, child_class,
           child_section, child_admission_no, child_dob, city, state,
           pincode, nationality)
        VALUES (?, 'parent', ?, ?, ?, ?, 1, 'Father',
                ?, ?, ?, ?, ?, 'Patna', 'Bihar', '800001', 'Indian')
    """, (
        pid,
        parent_name,
        pemail,
        pphone,
        generate_password_hash(DEFAULT_PASSWORD),
        s['name'],
        s['class_name'],
        s['section'],
        s['admission_no'],
        s['dob'],
    ))
    return True

# ─────────────────────────────────────────────────────────
# 6. MAIN
# ─────────────────────────────────────────────────────────
def main():
    print("\n" + "=" * 60)
    print("🎓 STUDENT + PARENT SEED SCRIPT")
    print("=" * 60)

    with app.app_context():
        db       = get_db()
        created  = 0
        skipped  = 0

        # ─────────────────────────────────────────
        # PHASE 1: STUDENTS
        # ─────────────────────────────────────────
        for cls in CLASS_ORDER:
            print(f"\n📚 Processing: {cls}")

            listed    = LISTED_STUDENTS.get(cls, [])
            used      = set(listed)
            male_i    = female_i = 0

            # (a) Insert listed names
            for idx, name in enumerate(listed, start=1):
                gender = LISTED_GENDER.get(name, 'Male')
                res = insert_student(db, cls, name, idx, gender)
                if res:
                    created += 1
                    print(f"   ✓ {name:<25} → {res['unique_id']}")
                else:
                    skipped += 1
                    print(f"   – {name:<25} (already exists)")

            # (b) Fill to 20
            next_roll = len(listed) + 1
            guard     = 0

            while next_roll <= TARGET_PER_CLASS and guard < 300:
                guard += 1
                if next_roll % 2 == 0:
                    first    = FEMALE_NAMES[female_i % len(FEMALE_NAMES)]
                    female_i += 1
                    gender   = 'Female'
                else:
                    first   = MALE_NAMES[male_i % len(MALE_NAMES)]
                    male_i += 1
                    gender  = 'Male'

                full = f"{first} {random.choice(SURNAMES)}"
                if full in used:
                    continue

                res = insert_student(db, cls, full, next_roll, gender)
                if res:
                    created += 1
                    used.add(full)
                    print(f"   + {full:<25} → {res['unique_id']}")
                else:
                    skipped += 1
                next_roll += 1

            total = db.execute(
                "SELECT COUNT(*) FROM users WHERE role='student' AND class_name=?",
                (cls,)
            ).fetchone()[0]
            print(f"   📊 Total in {cls}: {total}")

        # ─────────────────────────────────────────
        # PHASE 2: PARENTS
        # ─────────────────────────────────────────
        print("\n" + "=" * 60)
        print("👨‍👩‍👧 CREATING PARENTS")
        print("=" * 60)

        parent_created = 0
        parent_skipped = 0

        for cls in CLASS_ORDER:
            students = db.execute(
                "SELECT * FROM users WHERE role='student' AND class_name=? ORDER BY roll_no",
                (cls,)
            ).fetchall()

            class_p_created = 0
            for s in students:
                if insert_parent_for_student(db, s):
                    parent_created += 1
                    class_p_created += 1
                else:
                    parent_skipped += 1

            db.commit()
            print(f"   ✓ {cls:<5}: +{class_p_created} parents created")

        # ─────────────────────────────────────────
        # PHASE 3: FINAL REPORT
        # ─────────────────────────────────────────
        grand_total_students = db.execute(
            "SELECT COUNT(*) FROM users WHERE role='student'"
        ).fetchone()[0]

        grand_total_parents = db.execute(
            "SELECT COUNT(*) FROM users WHERE role='parent'"
        ).fetchone()[0]

        print("\n" + "=" * 60)
        print(f"✅ Students Created     : {created}")
        print(f"⏭  Students Skipped     : {skipped} (already existed)")
        print(f"👨‍👩‍👧 Parents Created      : {parent_created}")
        print(f"⏭  Parents Skipped      : {parent_skipped} (already existed)")
        print(f"👨‍🎓 Total Students in DB : {grand_total_students}")
        print(f"👨‍👩‍👧 Total Parents  in DB : {grand_total_parents}")
        print("=" * 60)
        print(f"\n🔑 Default password for everyone: {DEFAULT_PASSWORD}")
        print("   Students login → SNVST00001")
        print("   Parents  login → SNVP00001\n")


if __name__ == '__main__':
    main()