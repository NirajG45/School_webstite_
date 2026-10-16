# 🏫 Residential Shanti Niketan - School Website & Management System

A modern, fully responsive, full-stack **School Management System** built using **Flask, SQLite, HTML, CSS, and Vanilla JavaScript**.

This project provides a professional digital presence for **"Residential Shanti Niketan, Navinagar Jamui"** with a complete **Role-Based Portal System** including separate dashboards for Teachers, Students, Parents, and Admin (Principal), along with a dynamic Notice Board, Attendance tracking, Leave management, Fee payment via QR/UPI, and Messaging system.

---

## 🚀 Key Features

### 🎯 **Role-Based Portal System**
- **Single Login Page** — No public registration (only Admin can create users)
- **Auto-Role Detection** — User redirected to their specific dashboard after login
- **Unique ID System** — Auto-generated IDs like:
  - Admin → `SNV00001`
  - Teacher → `TSNV00001`
  - Parent → `PSNV00001`
  - Student → `STSNV00001`
- **Default Password** — `snv@450` with **Force Change on First Login**
- **Session Management** — 7-day persistent sessions

### 👨‍🏫 **Teacher Dashboard** (`teacher_dashboard.html`)
- Personal profile (ID, qualification, subject, experience)
- **My Attendance** — View attendance history with summary
- **Apply for Leave** — Submit leave requests with date range and reason
- **Leave History** — Track leave status (pending/approved/rejected)
- **Notices for Teachers** — Targeted notices from Principal
- **Messages from Principal** — Direct messages inbox

### 🎓 **Student Dashboard** (`student_dashboard.html`)
- Personal profile (ID, class, DOB, contact)
- **Attendance Record** — View personal attendance
- **Fee Payment** — Pay online via QR code or UPI link
- **Fee History** — Track all past payments with status
- **Notices for Students** — Class-specific announcements
- **Messages from School** — Important updates

### 👨‍👩‍👧 **Parent Dashboard** (`parent_dashboard.html`)
- Personal profile (Parent ID, relation)
- **Child Info** — View child's details, class, and DOB
- **Child's Attendance** — Monitor child's attendance record
- **Pay Child's Fees** — Online payment via QR/UPI
- **Fee Payment History** — Complete payment records
- **Notices for Parents** — PTM and school updates
- **Messages from School** — Direct communication

### 🛡️ **Admin Panel** (`admin_base.html` + 8 sub-pages)
- **Dashboard** — Stats cards (users, teachers, parents, students, notices, enquiries, pending leaves/fees)
- **Create User** — Create Teachers, Parents, Students, or Admin with role-specific fields
- **All Users** — Manage users with inline role change, password reset, activate/deactivate, delete
- **Attendance** — Mark daily attendance for students/teachers/parents
- **Leave Requests** — Approve or reject teacher leave applications with remarks
- **Notices** — Publish notices with target audience (All/Teachers/Parents/Students)
- **Messages** — Send messages to all users, specific role, or individual user
- **Fees & QR** — Upload QR image OR paste UPI link, verify/reject student payments
- **Enquiries** — View and manage admission & contact enquiries

---

## 🌟 Website Features

### 🏠 **Home Page**
- **Hero Section** — Attractive bilingual banner (English + Hindi)
- **Dynamic Notice Board** — Fetches notices from database with live preview
- **Auto-Sliding Gallery Banner** — Background image slider that pauses on hover
- **Quick Access Strip** — Fast links to Vision, Facilities, Routine, Notices, Contact
- **Stats Section** — School highlights
- **Admission Enquiry Form** — Direct enquiry submission with regex validation
- **Contact Band** — Quick contact form
- **Enhanced Header** — User avatar with hover dropdown showing name, ID, and role
- **Mobile Sidebar** — User info box with "Please Login First" for guests

### 📢 **Notice Board Page** (`notice.html`)
- Live search functionality
- Category filters (Admissions, Academics, Activities, General)
- Beautiful card layout with color-coded borders
- Dynamic pagination

### 📚 **Academics Page** (`academics.html`)
- Learning stages (Pre-Primary, Primary, Middle School)
- Subject grid with icons
- Routine banner section

---

## 🔧 Complete Tech Stack

### **Backend**
- **Framework:** Flask (Python)
- **Database:** SQLite3 (file-based)
- **Templating:** Jinja2
- **Security:** Werkzeug password hashing (generate_password_hash, check_password_hash)
- **File Handling:** Werkzeug secure uploads with extension validation
- **Session:** Flask session with 7-day lifetime

### **Frontend**
- **HTML5** — Semantic markup
- **CSS3** — Custom properties (variables), Flexbox, CSS Grid, Media Queries
- **JavaScript (Vanilla ES6)** — Mobile menu, auto-slider, scrollspy, form interactions
- **Icons:** Font Awesome 6.5.2 (CDN)
- **Fonts:** Google Fonts (DM Sans & Playfair Display)

---

## 📁 Complete Project Structure

```text
📁 shanti_niketan_flask/
│
├── app.py                      # Main Flask app (30+ routes, DB logic, auth, uploads)
├── school.db                   # SQLite Database (auto-generated with 8 tables)
├── requirements.txt            # Python dependencies (Flask, Werkzeug)
├── README.md                   # This documentation
├── .gitignore                  # Git ignore rules
│
├── 📁 static/
│   ├── 📁 css/
│   │   └── style.css           # 2500+ lines of custom CSS
│   ├── 📁 js/
│   │   └── main.js             # Mobile menu, slider, scrollspy logic
│   ├── 📁 images/              # School logo, campus photos, gallery images
│   └── 📁 uploads/             # Auto-created for QR code image uploads
│
└── 📁 templates/
    │
    ├── 🏫 PUBLIC PAGES
    ├── index.html              # Home page with user avatar
    ├── notice.html             # Dynamic Notice Board
    ├── academics.html          # Academics page
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
        └── admin_enquiries.html      # View enquiries

        