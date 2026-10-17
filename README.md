# 🏫 Residential Shanti Niketan - School Website & Management System

A modern, fully responsive, full-stack **School Management System** built using **Flask, SQLite, HTML, CSS, and Vanilla JavaScript**.

This project provides a professional digital presence for **"Residential Shanti Niketan, Navinagar Jamui"** with a complete **Role-Based Portal System** including separate dashboards for Teachers, Students, Parents, and Admin (Principal), along with dynamic content management, attendance tracking, leave management, fee payment via QR/UPI, and a robust messaging system.

---

## 📑 Table of Contents (Sidebar)
- [🎯 Key Features](#-key-features)
  - [Role-Based Portals](#-role-based-portals)
  - [Admin Panel (CMS)](#️-admin-panel-cms)
  - [Public Website Pages](#-public-website-pages)
- [🛠️ Tech Stack](#️-tech-stack)
- [📁 Project Structure](#-project-structure)
- [🗄️ Database Schema](#️-database-schema)
- [⚙️ Setup & Installation](#️-setup--installation)
- [🔐 Default Credentials](#-default-credentials)
- [🔄 System Workflows](#-system-workflows)
- [🛡️ Security & Validations](#️-security--validations)
- [👨‍💻 Developer](#-developer)

---

## 🎯 Key Features

### 👥 Role-Based Portals
*   **Single Login Page** — No public registration (only Admin can create users).
*   **Auto-Role Detection** — User is automatically redirected to their specific dashboard after login.
*   **Unique ID System** — Auto-generated IDs like:
    *   Admin → `SNV00001`
    *   Teacher → `TSNV00001`
    *   Parent → `PSNV00001`
    *   Student → `STSNV00001`
*   **Default Password** — `snv@450` with **Force Change on First Login**.
*   **Session Management** — 7-day persistent sessions.

#### 👨‍🏫 Teacher Dashboard
*   View Profile (ID, qualification, subject, experience).
*   **My Attendance** — View attendance history with summary.
*   **Apply for Leave** — Submit leave requests with date range and reason.
*   **Leave History** — Track leave status (pending/approved/rejected).
*   Receive targeted Notices and Messages from Principal.

#### 🎓 Student Dashboard
*   View Profile (ID, class, DOB, contact).
*   **Attendance Record** — View personal attendance.
*   **Fee Payment** — Pay online via scanned QR code or UPI link.
*   **Fee History** — Track all past payments with status.
*   Receive Notices and Messages from the school.

#### 👨‍👩‍👧 Parent Dashboard
*   View Profile (Parent ID, relation).
*   **Child Info** — View child's details, class, and DOB.
*   **Child's Attendance** — Monitor child's daily attendance.
*   **Pay Child's Fees** — Online payment via QR/UPI.
*   **Fee Payment History** — Complete payment records.
*   Receive Notices and Messages from the school.

---

### 🛡️ Admin Panel (CMS)
*   **Dashboard Overview** — Real-time stats of users, pending leaves, fees, and enquiries.
*   **User Management** — Create users (Teacher/Parent/Student), change roles, reset passwords, activate/deactivate, or delete users.
*   **Attendance Management** — Mark daily attendance (Present, Absent, Leave, Half-Day) for students and teachers.
*   **Leave Requests** — Approve or reject leave applications with admin remarks.
*   **Fees & QR Management** — Upload UPI QR Image (up to 20MB), set UPI Link, verify/reject student payments.
*   **Notice Board** — Publish targeted notices (All, Teachers, Parents, Students).
*   **Messaging System** — Send messages to specific roles or individual users.
*   **Enquiries** — View and manage admission and contact form submissions.
*   **Complete Content Management System (CMS):**
    *   **Faculty:** Add/Delete teachers and staff.
    *   **Events:** Add, **Edit**, and Delete school events.
    *   **Gallery:** Upload new images and delete existing ones.
    *   **Achievements:** Add and remove student achievements.
    *   **Testimonials:** Add and remove parent reviews.
    *   **FAQ:** Add and remove frequently asked questions.

---

### 🌟 Public Website Pages
*   **Home Page:** Hero section, Quick Access Strip, About, Stats, **Upcoming Events**, **Parent Testimonials**, **Recent Achievements**, Auto-sliding Gallery, Admission Enquiry Form, and Contact Band.
*   **Gallery (`/gallery`):** Dynamic category filters (Campus, Events, Sports, etc.) with a smooth **Lightbox** view. 100% DB-driven.
*   **Faculty (`/faculty`):** Beautiful directory showcasing teachers with their qualifications and subjects. 100% DB-driven.
*   **Events & News (`/events`):** A timeline view of all upcoming and past school events. 100% DB-driven.
*   **Achievements (`/achievements`):** Showcases the success and awards of students. 100% DB-driven.
*   **FAQ (`/faq`):** Smooth accordion-style frequently asked questions. 100% DB-driven.
*   **Notice Board (`/notice`):** Live search and category filters for announcements.

---

## 🛠️ Tech Stack

### Backend
*   **Framework:** Flask (Python)
*   **Database:** SQLite3 (file-based)
*   **Templating:** Jinja2
*   **Security:** Werkzeug password hashing (`generate_password_hash`, `check_password_hash`).
*   **File Handling:** Werkzeug secure uploads with extension and size validation (**Max 20MB**).

### Frontend
*   **HTML5** — Semantic markup.
*   **CSS3** — Custom properties (variables), Flexbox, CSS Grid, Media Queries.
*   **JavaScript (Vanilla ES6)** — Mobile menu, auto-slider, lightbox, scrollspy, form interactions.
*   **Icons:** Font Awesome 6.5.2 (CDN).
*   **Fonts:** Google Fonts (DM Sans & Playfair Display).

---

## 📁 Project Structure

```text
📁 shanti_niketan_flask/
│
├── app.py                      # Main Flask app (Routes, DB logic, Auth, Uploads)
├── school.db                   # SQLite Database (auto-generated with 14 tables)
├── requirements.txt            # Python dependencies (Flask, Werkzeug)
├── README.md                   # This documentation
├── .gitignore                  # Git ignore rules
│
├── 📁 static/
│   ├── 📁 css/
│   │   └── style.css           # All custom CSS styles
│   ├── 📁 js/
│   │   └── main.js             # Mobile menu, slider, scrollspy logic
│   ├── 📁 images/              # School logo, campus photos, dynamic gallery images
│   └── 📁 uploads/             # Auto-created for QR code image uploads
│
└── 📁 templates/
    │
    ├── 🏫 PUBLIC PAGES
    ├── index.html              # Home page
    ├── notice.html             # Dynamic Notice Board
    ├── academics.html          # Academics page
    ├── gallery.html            # Dynamic Photo Gallery
    ├── faculty.html            # Dynamic Faculty Directory
    ├── events.html             # Dynamic Public Events Page
    ├── achievements.html       # Dynamic Achievements Showcase
    ├── faq.html                # Dynamic FAQ Accordion
    │
    ├── 🔐 AUTHENTICATION
    ├── login.html              # Login page (Unique ID + Password)
    ├── change_password.html    # Force password change on first login
    │
    ├── 👥 USER DASHBOARDS
    ├── user.html               # Fallback/Admin profile view
    ├── teacher_dashboard.html  # Teacher portal (blue theme)
    ├── student_dashboard.html  # Student portal (orange theme)
    ├── parent_dashboard.html   # Parent portal (maroon theme)
    │
    └── 🛡️ ADMIN PANEL
        ├── admin_base.html     # Base template with sidebar & topbar
        ├── admin.html          # Dashboard with stats
        ├── admin_create_user.html    # Create new user form
        ├── admin_users.html          # All users management
        ├── admin_attendance.html     # Mark/view attendance
        ├── admin_leaves.html         # Approve/reject leaves
        ├── admin_notices.html        # Publish/manage notices
        ├── admin_messages.html       # Send messages
        ├── admin_fees.html           # QR upload & fee verification
        ├── admin_enquiries.html      # View enquiries
        ├── admin_faculty.html        # Manage Faculty (CMS)
        ├── admin_events.html         # Manage Events (Add/Edit/Delete)
        ├── admin_gallery.html        # Manage Gallery (Upload/Delete)
        ├── admin_achievements.html   # Manage Achievements (CMS)
        ├── admin_testimonials.html   # Manage Testimonials (CMS)
        └── admin_faq.html            # Manage FAQs (CMS)