"""Verify schema, clinical integrity, billing, and SQL reports on PostgreSQL."""
from decimal import Decimal

import psycopg

from tests.support import PostgreSQLCase, ROOT


class TestDDLAndIntegrityConstraints(PostgreSQLCase):
    def test_exactly_ten_canonical_relations(self):
        self.assertEqual(self.scalar('''
            SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s AND table_type='BASE TABLE'
        ''', (self.schema,)), 10)

    def test_schema_rebuilds_on_existing_database(self):
        self.conn.execute((ROOT / 'schema.sql').read_text(encoding='utf-8'))
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM Patients'), 0)

    def test_duplicate_primary_key_rejected(self):
        with self.assertRaises(psycopg.errors.UniqueViolation):
            self.conn.execute("INSERT INTO Departments (dept_id,dept_name,location) VALUES (1,'Duplicate','Wing B')")

    def test_missing_foreign_key_rejected(self):
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            self.conn.execute('UPDATE Doctors SET dept_id=999 WHERE doctor_id=1')

    def test_linked_patient_cannot_be_deleted(self):
        self.book()
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            self.conn.execute('DELETE FROM Patients WHERE patient_id=1')

    def test_unlinked_patient_can_be_deleted(self):
        self.conn.execute('DELETE FROM Patients WHERE patient_id=10')
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM Patients'), 9)

    def test_domains_and_nonnegative_amounts(self):
        for query in ["UPDATE Doctors SET consultation_fee=-1 WHERE doctor_id=1",
                      "UPDATE Patients SET gender='Invalid' WHERE patient_id=1",
                      "UPDATE Medicines SET stock_quantity=-1 WHERE medicine_id=1",
                      "UPDATE Patients SET email='invalid' WHERE patient_id=1"]:
            with self.subTest(query=query), self.assertRaises(psycopg.errors.CheckViolation):
                self.conn.execute(query)

    def test_overlapping_shifts_rejected(self):
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.conn.execute("INSERT INTO Doctor_Schedules (doctor_id,day_of_week,start_time,end_time) VALUES (1,'Monday','10:00','18:00')")

    def test_booking_off_schedule_and_misaligned_slots_rejected(self):
        for slot in ['08:00', '09:10', '16:45', '17:00']:
            with self.subTest(slot=slot), self.assertRaises(psycopg.errors.CheckViolation):
                self.book(slot)

    def test_booking_inactive_doctor_rejected(self):
        self.conn.execute("UPDATE Doctors SET status='On_Leave' WHERE doctor_id=1")
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.book()

    def test_cancellation_releases_slot_and_retains_history(self):
        first = self.book()
        self.conn.execute("UPDATE Appointments SET status='Cancelled' WHERE appointment_id=%s", (first,))
        second = self.book(patient=2)
        self.assertNotEqual(first, second)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM Appointments'), 2)
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.conn.execute("UPDATE Appointments SET status='Scheduled' WHERE appointment_id=%s", (first,))

    def test_rescheduling_collision_rolls_back_original_slot(self):
        first = self.book()
        self.book('09:30', patient=2)
        with self.assertRaises(psycopg.errors.UniqueViolation):
            self.conn.execute("UPDATE Appointments SET appointment_time='09:30' WHERE appointment_id=%s", (first,))
        self.assertEqual(str(self.scalar('SELECT appointment_time FROM Appointments WHERE appointment_id=%s', (first,))), '09:00:00')

    def test_completed_status_requires_clinical_record(self):
        appointment = self.book()
        self.start(appointment)
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.conn.execute("UPDATE Appointments SET status='Completed' WHERE appointment_id=%s", (appointment,))

    def test_schedule_change_with_upcoming_booking_is_rejected(self):
        self.book()
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.conn.execute("UPDATE Doctor_Schedules SET end_time='12:00' WHERE doctor_id=1")

    def test_provenance_mismatch_rejected(self):
        appointment = self.book()
        self.start(appointment)
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.record(appointment, patient=2)
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.prescription(appointment, doctor=2)

    def test_multiple_legacy_records_allow_null_appointment(self):
        for _ in range(2):
            self.record(None)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM Medical_Records WHERE appointment_id IS NULL'), 2)


class TestClinicalInventoryAndBilling(PostgreSQLCase):
    def test_trigger_deducts_stock_and_snapshots_price(self):
        appointment = self.book()
        self.start(appointment)
        prescription = self.prescription(appointment)
        self.dispense(prescription)
        self.assertEqual(self.scalar('SELECT stock_quantity FROM Medicines WHERE medicine_id=1'), 96)
        self.assertEqual(self.scalar('SELECT unit_price FROM Prescription_Items'), Decimal('12.50'))

    def test_duplicate_item_does_not_deduct_extra_stock(self):
        appointment = self.book()
        self.start(appointment)
        prescription = self.prescription(appointment)
        self.dispense(prescription)
        with self.assertRaises(psycopg.errors.UniqueViolation):
            self.dispense(prescription)
        self.assertEqual(self.scalar('SELECT stock_quantity FROM Medicines WHERE medicine_id=1'), 96)

    def test_insufficient_or_expired_stock_is_rejected(self):
        appointment = self.book()
        self.start(appointment)
        prescription = self.prescription(appointment)
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.dispense(prescription, quantity=101)
        self.conn.execute('UPDATE Medicines SET expiry_date=CURRENT_DATE-1 WHERE medicine_id=1')
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.dispense(prescription)
        self.assertEqual(self.scalar('SELECT stock_quantity FROM Medicines WHERE medicine_id=1'), 100)

    def test_negative_dispense_does_not_increase_inventory(self):
        appointment = self.book()
        self.start(appointment)
        prescription = self.prescription(appointment)
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.dispense(prescription, quantity=-4)
        self.assertEqual(self.scalar('SELECT stock_quantity FROM Medicines WHERE medicine_id=1'), 100)

    def test_multi_item_failure_rolls_back_all_clinical_and_stock_changes(self):
        appointment = self.book()
        self.start(appointment)
        with self.assertRaises(psycopg.errors.CheckViolation):
            with self.conn.transaction():
                self.record(appointment)
                prescription = self.prescription(appointment)
                self.dispense(prescription, medicine=1, quantity=4)
                self.dispense(prescription, medicine=2, quantity=101)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM Medical_Records'), 0)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM Prescriptions'), 0)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM Prescription_Items'), 0)
        self.assertEqual(self.scalar('SELECT SUM(stock_quantity) FROM Medicines'), 200)

    def test_actual_procedure_calculation_uses_dispensed_prices(self):
        appointment = self.book()
        self.start(appointment)
        self.record(appointment)
        prescription = self.prescription(appointment)
        self.dispense(prescription, 1, 4)
        self.dispense(prescription, 2, 2)
        self.conn.execute('UPDATE Medicines SET unit_price=999 WHERE medicine_id=1')
        self.conn.execute("UPDATE Appointments SET status='Completed' WHERE appointment_id=%s", (appointment,))
        self.conn.execute('CALL sp_generate_invoice(%s)', (appointment,))
        self.assertEqual(self.conn.execute('SELECT consultation_fee,medicine_total,total_amount FROM Invoices').fetchone(),
                         (Decimal('200.00'), Decimal('64.50'), Decimal('264.50')))

    def test_invoice_precondition_and_repeated_call(self):
        appointment = self.book()
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.conn.execute('CALL sp_generate_invoice(%s)', (appointment,))
        self.start(appointment)
        self.record(appointment)
        self.conn.execute("UPDATE Appointments SET status='Completed' WHERE appointment_id=%s", (appointment,))
        for _ in range(2):
            self.conn.execute('CALL sp_generate_invoice(%s)', (appointment,))
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM Invoices'), 1)

    def test_issued_invoice_amounts_cannot_change(self):
        appointment = self.completed()
        self.conn.execute('CALL sp_generate_invoice(%s)', (appointment,))
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.conn.execute('UPDATE Invoices SET consultation_fee=0,total_amount=0')

    def test_direct_invoice_insert_rejects_wrong_patient_and_amount(self):
        appointment = self.completed()
        for patient, fee in [(2, 200), (1, 1)]:
            with self.subTest(patient=patient, fee=fee), self.assertRaises(psycopg.errors.CheckViolation):
                self.conn.execute('''
                    INSERT INTO Invoices (appointment_id,patient_id,consultation_fee,medicine_total,total_amount)
                    VALUES (%s,%s,%s,0,%s)
                ''', (appointment, patient, fee, fee))

    def test_reorder_projection_uses_independent_stock_and_quantity_expectations(self):
        appointment = self.book()
        self.start(appointment)
        prescription = self.prescription(appointment)
        self.dispense(prescription, quantity=4)
        self.conn.execute('UPDATE Medicines SET reorder_level=100 WHERE medicine_id=1')
        row = self.conn.execute((ROOT / 'database/queries/03_pharmacy_reorder.sql').read_text()).fetchone()
        self.assertEqual(row[0], 1)
        self.assertEqual(row[3], 96)
        self.assertEqual(row[5], 4)
        self.assertEqual(row[7], Decimal('720.0'))

    def test_history_aggregates_items_without_multiplying_records(self):
        appointment = self.book()
        self.start(appointment)
        self.record(appointment)
        prescription = self.prescription(appointment)
        self.dispense(prescription, 1, 4)
        self.dispense(prescription, 2, 2)
        query = (ROOT / 'database/queries/04_patient_history.sql').read_text().replace('$1', '%(p)s').replace('$2', '%(d)s')
        rows = self.conn.execute(query, {'p': 1, 'd': None}).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0][-1]), 2)
        self.assertEqual([line['quantity'] for line in rows[0][-1]], [4, 2])

    def test_finalized_records_and_dispenses_are_retained(self):
        appointment = self.book()
        self.start(appointment)
        self.record(appointment)
        prescription = self.prescription(appointment)
        self.dispense(prescription)
        self.conn.execute("UPDATE Appointments SET status='Completed' WHERE appointment_id=%s", (appointment,))
        for query in ['DELETE FROM Appointments', 'DELETE FROM Medical_Records', "UPDATE Medical_Records SET diagnosis='Changed'",
                      'DELETE FROM Prescriptions', 'DELETE FROM Prescription_Items', 'UPDATE Prescription_Items SET quantity=1']:
            with self.subTest(query=query), self.assertRaises(psycopg.errors.CheckViolation):
                self.conn.execute(query)
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.dispense(prescription, medicine=2)

    def test_paid_only_view_and_department_report_match_independent_amount(self):
        for slot in ['09:00', '09:30']:
            appointment = self.completed(slot)
            self.conn.execute('CALL sp_generate_invoice(%s)', (appointment,))
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM v_daily_department_revenue'), 0)
        self.conn.execute("UPDATE Invoices SET payment_status='Paid',paid_at=CURRENT_TIMESTAMP,payment_method='UPI' WHERE invoice_id=1")
        self.assertEqual(self.scalar('SELECT settled_revenue FROM v_daily_department_revenue'), Decimal('200.00'))
        row = self.conn.execute((ROOT / 'database/queries/01_department_revenue.sql').read_text()).fetchone()
        self.assertEqual(row[4:7], (Decimal('400.00'), Decimal('200.00'), Decimal('200.00')))

    def test_five_sql_reports_execute_on_postgresql(self):
        appointment = self.completed()
        self.conn.execute('CALL sp_generate_invoice(%s)', (appointment,))
        for path in sorted((ROOT / 'database/queries').glob('*.sql')):
            query = path.read_text(encoding='utf-8')
            with self.subTest(report=path.name):
                if path.name.startswith('04'):
                    query = query.replace('$1', '%(patient)s').replace('$2', '%(doctor)s')
                    rows = self.conn.execute(query, {'patient': 1, 'doctor': None}).fetchall()
                    self.assertEqual(rows[0][8], 'Test diagnosis')
                else:
                    self.conn.execute(query).fetchall()
