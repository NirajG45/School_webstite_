import os
import sqlite3
import app
from werkzeug.security import generate_password_hash

def setup_database():
    initial_password = os.environ.get("INITIAL_ADMIN_PASSWORD", "")
    if len(initial_password) < 12 or len(initial_password) > 128:
        raise SystemExit("Set INITIAL_ADMIN_PASSWORD in .env (12-128 characters) before running setup_db.py.")

    print("[INFO] Initializing Database Tables...")
    app.init_db()
    db = sqlite3.connect(app.DB_PATH)
    try:
        users_to_create = [
            {"unique_id": "SNV00001", "role": "admin", "name": "Principal (Admin)",
             "email": "admin@rsn.com", "phone": "9155658081"},
            {"unique_id": "SNV00002", "role": "administrator", "name": "System Administrator",
             "email": "administrator@rsn.com", "phone": "9155658082"},
        ]
        for user in users_to_create:
            exists = db.execute("SELECT id FROM users WHERE unique_id = ? OR email = ?",
                                (user["unique_id"], user["email"])).fetchone()
            if exists:
                print(f"[SKIP] {user['unique_id']} already exists.")
                continue
            db.execute(
                "INSERT INTO users (unique_id, role, name, email, phone, password_hash, force_password_change) "
                "VALUES (?, ?, ?, ?, ?, ?, 1)",
                (user["unique_id"], user["role"], user["name"], user["email"],
                 user["phone"], generate_password_hash(initial_password)),
            )
            print(f"[SUCCESS] Created {user['role']} account: {user['unique_id']} (password change required).")
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    print("[SUCCESS] Setup complete. Initial password was not printed or stored in source code.")

if __name__ == "__main__":
    setup_database()
