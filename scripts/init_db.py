"""Initialize or explicitly reset the configured demonstration database."""
import argparse
import asyncio
import sys
from pathlib import Path

import asyncpg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app import config


async def initialize(reset=False):
    conn = await asyncpg.connect(config.DATABASE_URL, server_settings={'timezone': 'Asia/Kolkata'})
    try:
        if await conn.fetchval("SELECT to_regclass('departments') IS NOT NULL") and not reset:
            raise SystemExit('Database already contains MedConnect tables. Use --reset only for disposable demo data.')
        async with conn.transaction():
            await conn.execute((ROOT / 'schema.sql').read_text(encoding='utf-8'))
        print('Created ten MedConnect relations and their database routines.')
    finally:
        await conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reset', action='store_true', help='Delete and rebuild the configured demo tables.')
    asyncio.run(initialize(parser.parse_args().reset))
