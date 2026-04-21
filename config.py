from datetime import timedelta
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Security
    SECRET_KEY = os.environ.get(
        'SECRET_KEY') or 'dev-secret-key-change-in-production'

    # Database - Supabase PostgreSQL
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_SECURE = True  # HTTPS only (Render provides this)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # Groq API
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
    GROQ_MODEL = 'llama-3.1-70b-versatile'  # For complex parsing
    GROQ_MODEL_FAST = 'llama-3.1-8b-instant'  # For simple queries

    # Twilio (WhatsApp) - Optional, only for your personal use
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
    TWILIO_WHATSAPP_NUMBER = os.environ.get('TWILIO_WHATSAPP_NUMBER')

    # Push Notifications (will configure in GROUP 4)
    VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY')
    VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY')
    VAPID_CLAIMS = {"sub": "mailto:your-email@example.com"}

    # App Settings
    TASKS_PER_PAGE = 100
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max

    # AI Features
    MORNING_BRIEFING_TIME = '08:00'
    EVENING_REFLECTION_TIME = '20:00'
    STUCK_TASK_THRESHOLD_DAYS = 5

    # Rate Limiting (token optimization)
    RATELIMIT_STORAGE_URL = 'memory://'
    RATELIMIT_DEFAULT = "20 per hour"  # 20 AI requests per user per hour
