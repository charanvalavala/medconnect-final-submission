import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://medconnect:medconnect@localhost:5432/medconnect')
DATABASE_SCHEMA = os.getenv('DATABASE_SCHEMA', 'public')
JWT_SECRET = os.getenv('JWT_SECRET', '')
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@medconnect.local')
ADMIN_PASSWORD_HASH = os.getenv('ADMIN_PASSWORD_HASH', '')
CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',')
