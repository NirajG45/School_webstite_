import app
import sqlite3
from werkzeug.security import generate_password_hash

def setup_database():
    print("[INFO] Initializing Database Tables...")
    # 1. creating to all required tables
    app.init_db()
    print("[SUCCESS] Tables created successfully.")

    # 2. connecting to database
    db = sqlite3.connect('school.db')
    cursor = db.cursor()

    # Default Password
    default_pw = 'admin@123'
    hashed_pw = generate_password_hash(default_pw)

    # 3. (Admin और Administrator)
    users_to_create = [
        {
            'unique_id': 'SNV00001',
            'role': 'admin',
            'name': 'Principal (Admin)',
            'email': 'admin@rsn.com',
            'phone': '9155658081'
        },
        {
            'unique_id': 'SNV00002',
            'role': 'administrator',
            'name': 'System Administrator',
            'email': 'administrator@rsn.com',
            'phone': '9155658082'
        }
    ]

    # 4. inserting the new head or priority users...
    for user in users_to_create:
        # चेक करें कि यूज़र पहले से तो नहीं है (Unique ID या Email से)
        cursor.execute("SELECT id FROM users WHERE unique_id = ? OR email = ?", (user['unique_id'], user['email']))
        if cursor.fetchone():
            print(f"[SKIP] User {user['unique_id']} ({user['email']}) already exists. Skipping.")
        else:
            # force_password_change = 0 (ताकि पहली बार लॉगिन करते ही पासवर्ड चेंज न करना पड़े)
            cursor.execute('''
                INSERT INTO users (unique_id, role, name, email, phone, password_hash, force_password_change)
                VALUES (?, ?, ?, ?, ?, ?, 0)
            ''', (user['unique_id'], user['role'], user['name'], user['email'], user['phone'], hashed_pw))
            print(f"[SUCCESS] Created {user['role'].capitalize()}: {user['name']} | ID: {user['unique_id']}")

    # 5. this line are commited and closing backend database file and saving new changes and functionality...
    db.commit()
    db.close()
    
    print("\n================================================")
    print("SETUP COMPLETE! You can now login with:")
    print(f"Admin:         ID: SNV00001 | Password: {default_pw}")
    print(f"Administrator: ID: SNV00002 | Password: {default_pw}")
    print("================================================")

if __name__ == '__main__':
    setup_database()