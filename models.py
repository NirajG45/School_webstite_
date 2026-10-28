from datetime import datetime

class Exam(db.Model):
    __tablename__ = 'exam'
    id            = db.Column(db.Integer, primary_key=True)
    title         = db.Column(db.String(200), nullable=False)      # "Half Yearly Examination 2026-2027"
    academic_year = db.Column(db.String(20))                        # "2026-2027"
    term_label    = db.Column(db.String(50), default='2nd TERM')   # table column header
    notice_text   = db.Column(db.Text)                              # custom notice body
    custom_message= db.Column(db.Text)                              # footer message on report card
    status        = db.Column(db.String(20), default='draft')      # draft | published | completed
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
    status       = db.Column(db.String(20), default='pending')     # pending | in_progress | submitted
    submitted_at = db.Column(db.DateTime)

# Extend your existing Mark model:
class Mark(db.Model):
    __tablename__ = 'mark'
    id            = db.Column(db.Integer, primary_key=True)
    student_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject_id    = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    exam_id       = db.Column(db.Integer, db.ForeignKey('exam.id'))  # NEW
    exam_type     = db.Column(db.String(100))                         # keep for backward-compat
    marks_obtained= db.Column(db.Float)
    __table_args__ = (db.UniqueConstraint('student_id','subject_id','exam_id', name='uq_mark'),)