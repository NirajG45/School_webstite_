from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Student(db.Model):
    __tablename__ = 'users'
    id           = db.Column(db.Integer, primary_key=True)
    unique_id    = db.Column(db.String(50), unique=True)
    name         = db.Column(db.String(100), nullable=False)
    role         = db.Column(db.String(50))
    class_name   = db.Column(db.String(50))
    section      = db.Column(db.String(50))
    roll_no      = db.Column(db.String(50))
    admission_no = db.Column(db.String(50))

class Event(db.Model):
    __tablename__ = 'events'
    id              = db.Column(db.Integer, primary_key=True)
    title           = db.Column(db.String(200), nullable=False)
    description     = db.Column(db.Text)
    event_date      = db.Column(db.String(50))
    event_time      = db.Column(db.String(50))
    location        = db.Column(db.String(250))
    category        = db.Column(db.String(50), default='general')
    is_featured     = db.Column(db.Boolean, default=False)
    cover_image_url = db.Column(db.String(255))

class Certificate(db.Model):
    __tablename__ = 'certificates'
    id               = db.Column(db.Integer, primary_key=True)
    event_id         = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    student_id       = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    certificate_type = db.Column(db.String(50), default='participation')
    position         = db.Column(db.String(100)) 

class Exam(db.Model):
    __tablename__ = 'exam'
    id            = db.Column(db.Integer, primary_key=True)
    title         = db.Column(db.String(200), nullable=False)
    academic_year = db.Column(db.String(20))
    term_label    = db.Column(db.String(50), default='2nd TERM')
    notice_text   = db.Column(db.Text)
    custom_message= db.Column(db.Text)
    status        = db.Column(db.String(20), default='draft')
    created_by    = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    published_at  = db.Column(db.DateTime)

    submissions = db.relationship('ExamSubmission', backref='exam', lazy=True, cascade='all, delete-orphan')

class ExamSubmission(db.Model):
    """Tracks each class's marks-entry status for an exam."""
    __tablename__ = 'exam_submission'
    id           = db.Column(db.Integer, primary_key=True)
    exam_id      = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=False)
    class_name   = db.Column(db.String(50), nullable=False)
    teacher_id   = db.Column(db.Integer, db.ForeignKey('user.id'))
    status       = db.Column(db.String(20), default='pending')
    submitted_at = db.Column(db.DateTime)

# Extend your existing Mark model:
class Mark(db.Model):
    __tablename__ = 'mark'
    id            = db.Column(db.Integer, primary_key=True)
    student_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject_id    = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    exam_id       = db.Column(db.Integer, db.ForeignKey('exam.id'))
    exam_type     = db.Column(db.String(100))
    marks_obtained= db.Column(db.Float)
    __table_args__ = (db.UniqueConstraint('student_id','subject_id','exam_id', name='uq_mark'),)
    
class EventParticipant(db.Model):
    __tablename__ = 'event_participants'
    id         = db.Column(db.Integer, primary_key=True)
    event_id   = db.Column(db.Integer, db.ForeignKey('events.id'),   nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    role       = db.Column(db.String(40), default='participant')
    added_on   = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('event_id', 'student_id',
                                          name='uq_event_student'),)

    event   = db.relationship('Event',   backref=db.backref('participants',
                                cascade='all, delete-orphan', lazy='dynamic'))
    student = db.relationship('Student')