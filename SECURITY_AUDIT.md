# Residential Shanti Niketan — Security & Compatibility Audit

## Changes applied

- Added session-bound CSRF token validation for POST/PUT/PATCH/DELETE requests. Added tokens to all 110 POST forms, including logout forms, and CSRF headers to the three mutating AJAX fetch flows.
- Changed logout from a state-changing GET route to a POST route and converted existing logout links into CSRF-protected forms while retaining their existing labels/classes.
- Added persistent SQLite login throttling: five failed attempts per hashed IP/account key within the 15-minute window trigger a 15-minute lockout. Expired records are pruned.
- Removed shared default-password behavior from active account creation/reset flows. Each created/reset account gets an independent random temporary password and must change it at first login.
- Hardened `setup_db.py`: it no longer embeds or prints a default admin password; it requires `INITIAL_ADMIN_PASSWORD` from the local environment and forces a password change.
- Updated seed scripts to generate a unique temporary password per created student, parent, and teacher.
- Replaced unsafe Jinja `subjects_dict | safe` with `tojson`, and escaped the dynamic form number in the client-side preview builder.
- Updated `requirements.txt` for Flask, python-dotenv, and Pillow. Added `.env.example`, expanded `.gitignore`, and updated setup/security notes.
- Preserved the existing route set, templates, static assets, SQLite database, and existing backup files. No database rows were intentionally changed during this audit.

## Verification performed

- Python syntax compilation passed for `app.py`, `models.py`, `setup_db.py`, `seed_students.py`, and `seed_teachers.py`.
- Static scan found 110 POST forms and confirmed each contains a CSRF hidden field.
- Confirmed all existing logout links were converted to POST forms.
- Confirmed the active templates no longer contain the Jinja `safe` filter.
- Confirmed the project still declares 116 Flask routes.
- Database integrity checks are performed separately against the supplied SQLite database files.

## Remaining limitations / actions before production

- Runtime Flask/browser integration tests could not be run in the audit container because Flask/Werkzeug were not installed and package network access was unavailable. Install `requirements.txt` locally and test every role/module.
- A full manual penetration test has not been performed. Do not interpret this static audit as a guarantee of being vulnerability-free.
- Existing user accounts were not silently changed. If any account still uses an old shared password, reset it from Admin → Users; each reset now generates a unique temporary password.
- The ZIP contained a real `.env`. It is excluded from this output package; generate a fresh `SECRET_KEY` and replace the key in your local `.env` before deployment.
- No Content-Security-Policy is forced yet because the existing frontend uses inline scripts/styles and external CDNs. A nonce-based CSP requires a dedicated template refactor and browser testing.
- `models.py` appears to be a separate, currently unused SQLAlchemy-style model fragment; the active application uses SQLite directly in `app.py`. It was preserved rather than wired into a different ORM architecture.
- Production deployment still requires HTTPS, a production WSGI server, secure host/proxy configuration, protected backups, and monitoring.
