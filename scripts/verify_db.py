"""Print database object counts, sample-data totals, and execute all five reports."""
import asyncio
import sys
from pathlib import Path

import asyncpg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app import config
from scripts.seed import TABLES


async def main():
    conn = await asyncpg.connect(config.DATABASE_URL, server_settings={'timezone': 'Asia/Kolkata'})
    try:
        print(await conn.fetchval('SELECT version()'))
        counts = {table: await conn.fetchval(f'SELECT COUNT(*) FROM {table}') for table in TABLES}
        for table, count in counts.items():
            print(f'{table}: {count}')
        print(f'Total records: {sum(counts.values())}')
        assert sum(counts.values()) >= 500, 'The demonstration database requires at least 500 records.'
        for query_path in sorted((ROOT / 'database/queries').glob('*.sql')):
            args = (1, None) if query_path.name.startswith('04') else ()
            rows = await conn.fetch(query_path.read_text(encoding='utf-8'), *args)
            print(f'{query_path.name}: {len(rows)} rows')
        for kind, query in [
            ('Foreign keys', "SELECT COUNT(*) FROM pg_constraint WHERE contype='f' AND connamespace='public'::regnamespace"),
            ('Check constraints', "SELECT COUNT(*) FROM pg_constraint WHERE contype='c' AND connamespace='public'::regnamespace"),
            ('User triggers', "SELECT COUNT(*) FROM pg_trigger t JOIN pg_class c ON t.tgrelid=c.oid WHERE NOT t.tgisinternal AND c.relnamespace='public'::regnamespace"),
        ]:
            print(f'{kind}: {await conn.fetchval(query)}')
    finally:
        await conn.close()


if __name__ == '__main__':
    asyncio.run(main())
