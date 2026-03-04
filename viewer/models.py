"""Database models for progress tracking and bookmarks."""
from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """Registered user (only used when AUTH_ENABLED=true)."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(128), nullable=False)
    display_name = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_login_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    reads = db.relationship("LessonRead", backref="user", lazy="dynamic")
    bookmarks = db.relationship("Bookmark", backref="user", lazy="dynamic")

    def __repr__(self):
        return f"<User {self.username}>"


class LessonRead(db.Model):
    """Track which lessons have been read."""
    __tablename__ = "lessons_read"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    language = db.Column(db.String(10), nullable=False, default="ko")
    topic = db.Column(db.String(100), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    read_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint("user_id", "language", "topic", "filename", name="unique_user_lesson"),
    )

    def __repr__(self):
        return f"<LessonRead user={self.user_id} {self.language}/{self.topic}/{self.filename}>"


class Bookmark(db.Model):
    """Bookmarked lessons."""
    __tablename__ = "bookmarks"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    language = db.Column(db.String(10), nullable=False, default="ko")
    topic = db.Column(db.String(100), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint("user_id", "language", "topic", "filename", name="unique_user_bookmark"),
    )

    def __repr__(self):
        return f"<Bookmark user={self.user_id} {self.language}/{self.topic}/{self.filename}>"


class VocabularyProgress(db.Model):
    """SRS state for a vocabulary word."""
    __tablename__ = "vocabulary_progress"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    course = db.Column(db.String(100), nullable=False)
    word_key = db.Column(db.String(200), nullable=False)  # "lesson:category:spanish" unique key
    ease_factor = db.Column(db.Float, default=2.5, nullable=False)
    interval = db.Column(db.Integer, default=0, nullable=False)
    repetitions = db.Column(db.Integer, default=0, nullable=False)
    next_review = db.Column(db.DateTime, nullable=True)
    last_reviewed = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    __table_args__ = (
        db.UniqueConstraint("user_id", "course", "word_key", name="uq_vocab_progress"),
    )

    def __repr__(self):
        return f"<VocabularyProgress user={self.user_id} {self.course}:{self.word_key}>"


class QuizAttempt(db.Model):
    """Record of a completed quiz session."""
    __tablename__ = "quiz_attempts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    course = db.Column(db.String(100), nullable=False)
    quiz_type = db.Column(db.String(50), nullable=False)  # vocab, fill_blank, conjugation, mixed
    score = db.Column(db.Integer, nullable=False, default=0)
    total = db.Column(db.Integer, nullable=False, default=0)
    lesson_filter = db.Column(db.String(50), nullable=True)
    cefr_filter = db.Column(db.String(10), nullable=True)
    attempted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<QuizAttempt user={self.user_id} {self.course} {self.quiz_type} {self.score}/{self.total}>"
