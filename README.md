# Residential Shanti Niketan - School Website & Management System

A modern, fully responsive, full-stack school website built using **Flask, SQLite, HTML, CSS, and Vanilla JavaScript**. 

This project was designed to provide a clean, user-friendly, and professional digital presence for "Residential Shanti Niketan, Navinagar Jamui". It features a dynamic Notice Board, Admission Enquiry system, dedicated Academics page, and an elegant off-canvas sidebar navigation for smaller screens.

## 🚀 Features

- **Full-Stack Flask Application:** Powered by Python (Flask) with an SQLite database for dynamic content and form submissions.
- **Dynamic Notice Board:** 
  - Fetches notices directly from the database.
  - Includes live search and category filters (Admissions, Academics, Activities, General).
  - Beautiful card layout with color-coded borders for each category.
- **Admission & Contact Forms:**
  - Secure backend form handling with Regex validation (Name, Phone, Email).
  - Data is safely stored in the SQLite database for follow-ups.
  - Success/Error flash messages for user feedback.
- **Dedicated Academics Page:** Showcases learning stages (Pre-Primary to Middle School) and subject offerings in a clean grid layout.
- **Auto-Sliding Gallery Banner:** A smooth, automatic image slider on the home page that pauses on hover.
- **Smart Navigation System:**
  - **Desktop:** Clean, horizontal navigation bar.
  - **Mobile/Tablet:** A smooth sliding sidebar (Off-Canvas) triggered by a hamburger menu.
- **Interactive Sidebar:** Can be closed by clicking the 'X', clicking the overlay, or clicking a navigation link.
- **Security & Error Handling:** Includes security headers (XSS Protection, Clickjacking Protection), custom 404 page, and 413 (Payload Too Large) error handler.
- **Developer Credit:** A beautifully designed glowing credit badge in the footer ("Developed by Niraj Kumar").
- **Fully Responsive Layout:** Optimized for all devices using CSS Grid, Flexbox, and Media Queries.
- **Modern Aesthetics:** Smooth hover effects, subtle shadows, and clean typography using Google Fonts (DM Sans & Playfair Display).

## 🛠️ Tech Stack

- **Backend:** Python, Flask, SQLite3, Jinja2 Templates
- **Frontend:** HTML5, CSS3 (Custom properties, Flexbox, CSS Grid), Vanilla JavaScript (ES6)
- **Icons:** Font Awesome (CDN)
- **Fonts:** Google Fonts (DM Sans & Playfair Display)

## 📁 Project Structure

The project follows a standard Flask directory structure:

```text
📁 shanti_niketan_flask/
│
├── app.py                 # Main Flask application (Routes, DB logic, Validation)
├── school.db              # SQLite Database (Auto-generated on first run)
├── requirements.txt       # Python dependencies (e.g., Flask)
├── README.md              # Project documentation
│
├── 📁 static/
│   ├── 📁 css/
│   │   └── style.css      # All custom CSS styles
│   ├── 📁 js/
│   │   └── main.js        # Mobile menu, Slider, Scrollspy logic
│   └── 📁 images/         # School logo, campus photos, gallery images
│
└── 📁 templates/
    ├── index.html         # Home page
    ├── notice.html        # Dynamic Notice Board page
    ├── academics.html     # Academics and curriculum page
    └── 404.html           # Custom 404 Error page