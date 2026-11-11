"""Create local demonstration configuration without overwriting an existing file."""
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.auth import hash_password


def main():
    target = ROOT / '.env'
    if target.exists():
        print('.env already exists; configuration was retained.')
        return
    target.write_text(
        'DATABASE_URL=postgresql://medconnect:medconnect@localhost:5432/medconnect\n'
        f'JWT_SECRET={secrets.token_urlsafe(48)}\n'
        'ADMIN_EMAIL=admin@medconnect.local\n'
        f'ADMIN_PASSWORD_HASH={hash_password("Clinic@2026")}\n'
        'CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080\n',
        encoding='utf-8')
    print('Created .env with a random signing key and a hashed demonstration password.')


if __name__ == '__main__':
    main()
