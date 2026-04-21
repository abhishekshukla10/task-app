from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), unique=True,
                             nullable=True)  # For WhatsApp users
    email = db.Column(db.String(120), unique=True,
                      nullable=True)  # For web users
    password_hash = db.Column(db.String(255), nullable=True)  # For web users
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    tasks = db.relationship('Task', backref='user',
                            lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        """Hash and set password for web login"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify password for web login"""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    @property
    def display_name(self):
        """Return email or phone for display"""
        return self.email or self.phone_number or f"User {self.id}"

    def __repr__(self):
        return f'<User {self.id}: {self.display_name}>'


class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Core fields
    title = db.Column(db.String(500), nullable=False)
    # Pending, In Progress, Completed, Dropped
    status = db.Column(db.String(20), default='Pending')
    priority = db.Column(db.Boolean, default=False)  # Important or not
    remarks = db.Column(db.Text, nullable=True)

    # Dates and times
    due_date = db.Column(db.Date, nullable=False)
    reminder_time = db.Column(db.DateTime, nullable=True)
    snoozed_until = db.Column(db.DateTime, nullable=True)

    # Recurrence
    # None, Daily, Weekly, Monthly
    repeat = db.Column(db.String(20), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        """Convert task to dictionary for JSON responses"""
        return {
            'id': self.id,
            'title': self.title,
            'status': self.status,
            'priority': self.priority,
            'remarks': self.remarks,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'reminder_time': self.reminder_time.isoformat() if self.reminder_time else None,
            'snoozed_until': self.snoozed_until.isoformat() if self.snoozed_until else None,
            'repeat': self.repeat,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    def __repr__(self):
        return f'<Task {self.id}: {self.title}>'
