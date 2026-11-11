"""Exercise the HTTP workflows and permissions against an isolated PostgreSQL schema."""
from datetime import timedelta
from decimal import Decimal

import jwt
from fastapi.testclient import TestClient

from backend.app import config
from backend.app.main import app
from tests.support import PASSWORD_HASH, PostgreSQLCase


class TestApplicationWorkflows(PostgreSQLCase):
    def setUp(self):
        super().setUp()
        config.DATABASE_URL = self.dsn
        config.DATABASE_SCHEMA = self.schema
        config.JWT_SECRET = 'medconnect-test-signing-key-with-sufficient-length'
        config.ADMIN_EMAIL = 'admin@medconnect.local'
        config.ADMIN_PASSWORD_HASH = PASSWORD_HASH
        self.client = TestClient(app)
        self.client.__enter__()
        self.addCleanup(lambda: self.client.__exit__(None, None, None))
        self.admin = self.login('admin@medconnect.local')
        self.doctor = self.login('doctor1@medconnect.local')
        self.other_doctor = self.login('doctor2@medconnect.local')

    def login(self, email):
        response = self.client.post('/api/auth/login', json={'email': email, 'password': 'Doctor@2026'})
        self.assertEqual(response.status_code, 200, response.text)
        return {'Authorization': f'Bearer {response.json()["access_token"]}'}

    def api_book(self, slot='10:00'):
        response = self.client.post('/api/appointments', headers=self.admin, json={
            'patient_id': 1, 'doctor_id': 1, 'appointment_date': str(self.day),
            'appointment_time': slot, 'reason_for_visit': 'Application workflow test'})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()['appointment_id']

    def api_start(self, appointment):
        response = self.client.patch(f'/api/appointments/{appointment}/status', headers=self.doctor,
                                     json={'status': 'In_Consultation'})
        self.assertEqual(response.status_code, 200, response.text)

    def encounter_body(self, items=None):
        return {'symptoms': 'Test symptoms', 'diagnosis': 'Test diagnosis', 'clinical_notes': 'Follow-up',
                'instructions': 'Demonstration', 'items': items if items is not None else [
                    {'medicine_id': 1, 'dosage': 'Test dosage', 'duration_days': 3, 'quantity': 4}]}

    def test_health_and_authentication_boundaries(self):
        self.assertEqual(self.client.get('/api/health').json()['status'], 'ok')
        self.assertEqual(self.client.get('/api/patients').status_code, 401)
        self.assertEqual(self.client.post('/api/auth/login', json={'email': 'doctor1@medconnect.local', 'password': 'wrong'}).status_code, 401)
        expired = jwt.encode({'sub': '1', 'role': 'Doctor', 'name': 'Doctor', 'iat': 1, 'exp': 2}, config.JWT_SECRET, algorithm='HS256')
        self.assertEqual(self.client.get('/api/auth/me', headers={'Authorization': f'Bearer {expired}'}).status_code, 401)

    def test_patient_crud_search_and_validation(self):
        body = {'first_name': 'Demo', 'last_name': 'New', 'date_of_birth': '2000-01-01', 'gender': 'Other',
                'phone': '9999999999', 'address': 'Test Street'}
        response = self.client.post('/api/patients', headers=self.admin, json=body)
        self.assertEqual(response.status_code, 201, response.text)
        patient_id = response.json()['patient_id']
        body['last_name'] = 'Updated'
        self.assertEqual(self.client.put(f'/api/patients/{patient_id}', headers=self.admin, json=body).status_code, 200)
        rows = self.client.get('/api/patients?q=Demo%20Updated', headers=self.admin).json()
        self.assertEqual([r['patient_id'] for r in rows], [patient_id])
        self.assertEqual(self.client.delete(f'/api/patients/{patient_id}', headers=self.admin).status_code, 200)
        body['date_of_birth'] = str(self.day + timedelta(days=100))
        self.assertEqual(self.client.post('/api/patients', headers=self.admin, json=body).status_code, 422)

    def test_booking_cancellation_rebooking_and_collision(self):
        first = self.api_book()
        response = self.client.get(f'/api/slots?doctor_id=1&appointment_date={self.day}', headers=self.admin)
        self.assertNotIn('10:00', [r['time'] for r in response.json()])
        collision = self.client.post('/api/appointments', headers=self.admin, json={
            'patient_id': 2, 'doctor_id': 1, 'appointment_date': str(self.day), 'appointment_time': '10:00', 'reason_for_visit': 'Collision'})
        self.assertEqual(collision.status_code, 409, collision.text)
        self.assertEqual(self.client.patch(f'/api/appointments/{first}/status', headers=self.admin, json={'status': 'Cancelled'}).status_code, 200)
        second = self.api_book()
        self.assertNotEqual(first, second)

    def test_full_encounter_payment_and_reports(self):
        appointment = self.api_book()
        self.api_start(appointment)
        before = self.scalar('SELECT stock_quantity FROM Medicines WHERE medicine_id=1')
        response = self.client.post(f'/api/appointments/{appointment}/complete', headers=self.doctor, json=self.encounter_body())
        self.assertEqual(response.status_code, 200, response.text)
        invoice = response.json()
        self.assertEqual(Decimal(str(invoice['total_amount'])), Decimal('250.00'))
        self.assertEqual(self.scalar('SELECT stock_quantity FROM Medicines WHERE medicine_id=1'), before - 4)
        self.assertEqual(self.client.get('/api/overview', headers=self.admin).json()['outstanding'], 250)
        payment = self.client.post(f'/api/invoices/{invoice["invoice_id"]}/pay', headers=self.admin, json={'payment_method': 'UPI'})
        self.assertEqual(payment.status_code, 200, payment.text)
        self.assertEqual(self.scalar('SELECT settled_revenue FROM v_daily_department_revenue'), Decimal('250.00'))
        report = self.client.get('/api/reports/department-revenue', headers=self.admin)
        self.assertEqual(report.status_code, 200, report.text)
        self.assertEqual(Decimal(str(report.json()[0]['collected_amount'])), Decimal('250.00'))
        for report_id in ['doctor-performance', 'pharmacy-reorder', 'peak-demand', 'patient-history?patient_id=1']:
            response = self.client.get('/api/reports/' + report_id, headers=self.admin)
            self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.get('/api/invoices', headers=self.admin).status_code, 200)
        history = self.client.get('/api/patients/1/history', headers=self.doctor)
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual(history.json()[0]['prescribed_medications'][0]['quantity'], 4)

    def test_http_multi_item_failure_rolls_back_every_change(self):
        appointment = self.api_book()
        self.api_start(appointment)
        items = [{'medicine_id': 1, 'dosage': 'Test', 'duration_days': 2, 'quantity': 4},
                 {'medicine_id': 2, 'dosage': 'Test', 'duration_days': 2, 'quantity': 101}]
        response = self.client.post(f'/api/appointments/{appointment}/complete', headers=self.doctor, json=self.encounter_body(items))
        self.assertEqual(response.status_code, 409, response.text)
        for table in ['Medical_Records', 'Prescriptions', 'Prescription_Items', 'Invoices']:
            self.assertEqual(self.scalar(f'SELECT COUNT(*) FROM {table}'), 0)
        self.assertEqual(self.scalar('SELECT SUM(stock_quantity) FROM Medicines'), 200)
        self.assertEqual(self.scalar('SELECT status FROM Appointments WHERE appointment_id=%s', (appointment,)), 'In_Consultation')

    def test_duplicate_completion_does_not_dispense_again(self):
        appointment = self.api_book()
        self.api_start(appointment)
        self.assertEqual(self.client.post(f'/api/appointments/{appointment}/complete', headers=self.doctor, json=self.encounter_body()).status_code, 200)
        self.assertEqual(self.client.post(f'/api/appointments/{appointment}/complete', headers=self.doctor, json=self.encounter_body()).status_code, 409)
        self.assertEqual(self.scalar('SELECT stock_quantity FROM Medicines WHERE medicine_id=1'), 96)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM Invoices'), 1)

    def test_doctor_cannot_access_other_encounter_or_admin_operations(self):
        appointment = self.api_book()
        self.assertEqual(self.client.patch(f'/api/appointments/{appointment}/status', headers=self.other_doctor, json={'status': 'In_Consultation'}).status_code, 403)
        self.assertEqual(self.client.get('/api/patients/1/history', headers=self.other_doctor).status_code, 403)
        for path in ['/api/invoices', '/api/reports', '/api/reports/department-revenue']:
            self.assertEqual(self.client.get(path, headers=self.doctor).status_code, 403)
        self.assertEqual(self.client.post('/api/medicines/1/restock', headers=self.doctor, json={'quantity': 10}).status_code, 403)
        rows = self.client.get('/api/appointments?doctor_id=1', headers=self.other_doctor).json()
        self.assertEqual(rows, [])

    def test_same_method_payment_retry_is_safe_and_different_method_rejected(self):
        appointment = self.api_book()
        self.api_start(appointment)
        invoice = self.client.post(f'/api/appointments/{appointment}/complete', headers=self.doctor, json=self.encounter_body([])).json()
        path = f'/api/invoices/{invoice["invoice_id"]}/pay'
        first = self.client.post(path, headers=self.admin, json={'payment_method': 'Cash'})
        again = self.client.post(path, headers=self.admin, json={'payment_method': 'Cash'})
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json(), again.json())
        self.assertEqual(self.client.post(path, headers=self.admin, json={'payment_method': 'UPI'}).status_code, 409)

    def test_patient_history_is_scoped_to_treating_doctor(self):
        self.completed(doctor=1)
        self.completed(doctor=2)
        doctor_rows = self.client.get('/api/patients/1/history', headers=self.doctor).json()
        admin_rows = self.client.get('/api/patients/1/history', headers=self.admin).json()
        self.assertEqual(len(doctor_rows), 1)
        self.assertEqual(len(admin_rows), 2)
        self.assertEqual(doctor_rows[0]['doctor_name'], 'Doctor 1')

    def test_invalid_input_and_sql_injection_are_not_executed(self):
        response = self.client.get('/api/patients', headers=self.admin, params={'q': "'; DROP TABLE Patients; --"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM Patients'), 10)
        self.assertEqual(self.client.post('/api/medicines/1/restock', headers=self.admin, json={'quantity': -3}).status_code, 422)
        appointment = self.api_book()
        self.api_start(appointment)
        duplicate = self.encounter_body()
        duplicate['items'] *= 2
        self.assertEqual(self.client.post(f'/api/appointments/{appointment}/complete', headers=self.doctor, json=duplicate).status_code, 422)
