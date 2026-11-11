"""Create and populate a fresh database; retain an existing clinic on restart."""
import asyncio
import sys
from pathlib import Path

import asyncpg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app import config
from scripts.seed import populate


async def main():
    conn = await asyncpg.connect(config.DATABASE_URL, server_settings={'timezone': 'Asia/Kolkata'})
    try:
        async with conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock(1102026)")
            if await conn.fetchval("SELECT to_regclass('departments') IS NOT NULL"):
                print('Existing clinic database retained. Use init_db.py --reset only for an intentional demo reset.')
                return
            await conn.execute((ROOT / 'schema.sql').read_text(encoding='utf-8'))
            counts = await populate(conn)
        print(f'Initialized MedConnect with {sum(counts.values())} synthetic records.')
    finally:
        await conn.close()


if __name__ == '__main__':
    asyncio.run(main())
