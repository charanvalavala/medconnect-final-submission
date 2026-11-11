"""Verify sample-data completeness and refusal to duplicate an existing seed."""
import asyncio

import asyncpg

from scripts.seed import populate
from tests.support import PostgreSQLCase, ROOT


class TestSampleData(PostgreSQLCase):
    def test_fresh_seed_has_1308_records_and_all_workflow_states(self):
        self.conn.execute((ROOT / 'schema.sql').read_text(encoding='utf-8'))
        async def seed():
            conn = await asyncpg.connect(self.dsn, server_settings={'search_path': self.schema, 'timezone': 'Asia/Kolkata'})
            try:
                async with conn.transaction():
                    counts = await populate(conn)
                with self.assertRaises(RuntimeError):
                    await populate(conn)
                return counts
            finally:
                await conn.close()
        counts = asyncio.run(seed())
        self.assertEqual(sum(counts.values()), 1308)
        self.assertEqual(counts['Appointments'], 300)
        self.assertEqual(counts['Medical_Records'], 168)
        self.assertEqual(set(r[0] for r in self.conn.execute('SELECT DISTINCT status FROM Appointments')),
                         {'Scheduled', 'Completed', 'Cancelled', 'No_Show'})
        self.assertEqual(set(r[0] for r in self.conn.execute('SELECT DISTINCT payment_status FROM Invoices')), {'Pending', 'Paid'})
