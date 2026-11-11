"""Verify patient contact rules through HTTP, PostgreSQL, and existing-data upgrades."""
import psycopg

from tests.test_api import ApplicationCase
from tests.support import PostgreSQLCase, ROOT


class TestPatientPhoneAPI(ApplicationCase):
    def body(self, **changes):
        return {'first_name': 'Contact', 'last_name': 'Test', 'date_of_birth': '2000-01-01',
                'gender': 'Other', 'phone': '0123456789', 'address': 'Test Street', **changes}

    def test_registration_rejects_invalid_national_numbers(self):
        for field in ['phone', 'emergency_contact_phone']:
            for value in ['1234567', '123456789', '12345678901', 'abcdefghij', '12345abc90',
                          '+919876543210', '12345 6789', '12345-6789', '１２３４５６７８９０']:
                with self.subTest(field=field, value=value):
                    response = self.client.post('/api/patients', headers=self.admin, json=self.body(**{field: value}))
                    self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM Patients'), 10)

    def test_edit_rejects_invalid_contacts_without_changing_patient(self):
        before = self.conn.execute('SELECT phone,emergency_contact_phone FROM Patients WHERE patient_id=1').fetchone()
        for changes in [{'phone': 'letters123'}, {'emergency_contact_phone': '123'}]:
            with self.subTest(changes=changes):
                response = self.client.put('/api/patients/1', headers=self.admin, json=self.body(**changes))
                self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.conn.execute('SELECT phone,emergency_contact_phone FROM Patients WHERE patient_id=1').fetchone(), before)

    def test_valid_contacts_remain_strings_and_blank_emergency_is_optional(self):
        response = self.client.post('/api/patients', headers=self.admin,
                                    json=self.body(phone=' 0123456789 ', emergency_contact_phone=' 0012345678 '))
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()['phone'], '0123456789')
        self.assertEqual(response.json()['emergency_contact_phone'], '0012345678')
        for blank in [None, '', '   ']:
            response = self.client.put('/api/patients/' + str(response.json()['patient_id']), headers=self.admin,
                                       json=self.body(emergency_contact_phone=blank))
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIsNone(response.json()['emergency_contact_phone'])


class TestPatientPhoneDatabase(PostgreSQLCase):
    def test_direct_sql_rejects_invalid_contacts(self):
        for field in ['phone', 'emergency_contact_phone']:
            for value in ['1234567', '12345678901', 'letters123', '12345 6789', '１２３４５６７８９０', '1234567890\n']:
                with self.subTest(field=field, value=value), self.assertRaises(psycopg.errors.CheckViolation):
                    self.conn.execute(f'UPDATE Patients SET {field}=%s WHERE patient_id=1', (value,))

    def test_direct_sql_preserves_leading_zeroes_and_allows_null_emergency(self):
        self.conn.execute("UPDATE Patients SET phone='0123456789',emergency_contact_phone=NULL WHERE patient_id=1")
        self.assertEqual(self.conn.execute('SELECT phone,emergency_contact_phone FROM Patients WHERE patient_id=1').fetchone(),
                         ('0123456789', None))

    def remove_phone_constraints(self):
        self.conn.execute('ALTER TABLE Patients DROP CONSTRAINT chk_patient_phone_digits, DROP CONSTRAINT chk_patient_emergency_phone_digits')

    def test_upgrade_is_repeatable_and_retains_existing_rows(self):
        before = self.conn.execute('SELECT * FROM Patients ORDER BY patient_id').fetchall()
        self.remove_phone_constraints()
        migration = (ROOT / 'database/migrations/001_patient_phone_numbers.sql').read_text()
        for _ in range(2):
            self.conn.execute(migration)
        self.assertEqual(self.conn.execute('SELECT * FROM Patients ORDER BY patient_id').fetchall(), before)
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.conn.execute("UPDATE Patients SET phone='bad-number' WHERE patient_id=1")

    def test_upgrade_rejects_invalid_legacy_data_without_partial_changes(self):
        self.remove_phone_constraints()
        self.conn.execute("UPDATE Patients SET emergency_contact_phone='legacy-invalid' WHERE patient_id=1")
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.conn.execute((ROOT / 'database/migrations/001_patient_phone_numbers.sql').read_text())
        self.assertEqual(self.scalar('SELECT emergency_contact_phone FROM Patients WHERE patient_id=1'), 'legacy-invalid')
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM pg_constraint WHERE conrelid='Patients'::regclass AND conname IN ('chk_patient_phone_digits','chk_patient_emergency_phone_digits')"), 0)
