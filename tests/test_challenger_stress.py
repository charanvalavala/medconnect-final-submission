"""Race independent PostgreSQL connections against the booking and stock rules."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import psycopg

from tests.support import PostgreSQLCase


class TestConcurrencyAndSlotRaceConditions(PostgreSQLCase):
    def test_ten_connections_race_for_one_slot(self):
        barrier = Barrier(10)
        def attempt(patient_id):
            with self.connection() as conn:
                barrier.wait(timeout=10)
                try:
                    conn.execute('''
                        INSERT INTO Appointments (patient_id,doctor_id,appointment_date,appointment_time)
                        VALUES (%s,1,%s,'09:00')
                    ''', (patient_id, self.day))
                    return 'booked'
                except psycopg.errors.UniqueViolation:
                    return 'collision'
        with ThreadPoolExecutor(max_workers=10) as pool:
            outcomes = list(pool.map(attempt, range(1, 11)))
        self.assertEqual(outcomes.count('booked'), 1)
        self.assertEqual(outcomes.count('collision'), 9)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM Appointments'), 1)

    def test_two_prescriptions_cannot_oversell_limited_stock(self):
        self.conn.execute('UPDATE Medicines SET stock_quantity=5 WHERE medicine_id=1')
        first = self.book(doctor=1)
        second = self.book(doctor=2, patient=2)
        self.start(first)
        self.start(second)
        prescriptions = [self.prescription(first), self.prescription(second, patient=2, doctor=2)]
        barrier = Barrier(2)
        def attempt(prescription):
            with self.connection() as conn:
                barrier.wait(timeout=10)
                try:
                    self.dispense(prescription, quantity=4, conn=conn)
                    return 'dispensed'
                except psycopg.errors.CheckViolation:
                    return 'insufficient'
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(attempt, prescriptions))
        self.assertEqual(sorted(outcomes), ['dispensed', 'insufficient'])
        self.assertEqual(self.scalar('SELECT stock_quantity FROM Medicines WHERE medicine_id=1'), 1)
        self.assertEqual(self.scalar('SELECT SUM(quantity) FROM Prescription_Items'), 4)

    def test_concurrent_invoice_calls_issue_one_invoice(self):
        appointment = self.completed()
        barrier = Barrier(5)
        def issue(_):
            with self.connection() as conn:
                barrier.wait(timeout=10)
                conn.execute('CALL sp_generate_invoice(%s)', (appointment,))
        with ThreadPoolExecutor(max_workers=5) as pool:
            list(pool.map(issue, range(5)))
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM Invoices'), 1)
