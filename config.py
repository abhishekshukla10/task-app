import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "Tasks")

# Validate on startup
if not GROQ_API_KEY:
    raise EnvironmentError("❌ GROQ_API_KEY is missing from .env")

if not GOOGLE_SHEET_NAME:
    raise EnvironmentError("❌ GOOGLE_SHEET_NAME is missing from .env")
