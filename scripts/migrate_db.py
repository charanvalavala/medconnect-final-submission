"""Apply additive database updates while retaining the current clinic records."""
import asyncio
import sys
from pathlib import Path

import asyncpg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app import config


async def apply_migrations(conn):
    for path in sorted((ROOT / 'database/migrations').glob('*.sql')):
        await conn.execute(path.read_text(encoding='utf-8'))


async def main():
    conn = await asyncpg.connect(config.DATABASE_URL)
    try:
        async with conn.transaction():
            await apply_migrations(conn)
        print('Database updates applied; existing clinic records retained.')
    finally:
        await conn.close()


if __name__ == '__main__':
    asyncio.run(main())
