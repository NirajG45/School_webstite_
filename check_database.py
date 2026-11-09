
from app import app, get_db

def inspect_database():
    with app.app_context():
        db = get_db()

        print("\n========== USERS TABLE COLUMNS ==========")

        columns = db.execute(
            "PRAGMA table_info(users)"
        ).fetchall()

        for col in columns:
            print(dict(col))

        print("\n========== UNIQUE INDEXES ==========")

        indexes = db.execute(
            "PRAGMA index_list(users)"
        ).fetchall()

        for idx in indexes:
            if idx["unique"]:
                print(dict(idx))

        print("\n========== DATABASE COUNTS ==========")

        for role in ("student", "parent", "admin", "administrator", "teacher"):
            count = db.execute(
                "SELECT COUNT(*) FROM users WHERE role = ?",
                (role,)
            ).fetchone()[0]

            print(f"{role.upper()}: {count}")


if __name__ == "__main__":
    inspect_database()
