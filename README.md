# Residential Shanti Niketan — Flask Website

A responsive school homepage with a Flask backend, SQLite-backed admission/contact enquiries, and a JSON notices endpoint.

## Run locally

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

## Backend routes
- `GET /` — homepage
- `POST /admission-enquiry` — validates and stores an admission enquiry in `school.db`
- `POST /contact` — validates and stores a contact message in `school.db`
- `GET /api/notices` — notices as JSON
- `GET /health` — health check

## Important before public deployment
- Set a strong `SECRET_KEY` environment variable.
- Use production WSGI (for example Gunicorn on Linux or Waitress on Windows), HTTPS, and a real deployment server; do not expose Flask's development server.
- Add authentication/authorization before creating any staff dashboard or allowing access to saved enquiries.
- Replace demo notice text and school contact details with verified school information. Login, payment and student-result links are intentionally not presented as working services until those systems are integrated.
