"""PostgreSQL fixtures isolated in a fresh schema for every test."""
import os
import unittest
import uuid
from pathlib import Path

import psycopg
from psycopg import sql

from backend.app.auth import hash_password

ROOT = Path(__file__).resolve().parents[1]
PASSWORD_HASH = hash_password('Doctor@2026')


class PostgreSQLCase(unittest.TestCase):
    def setUp(self):
        self.dsn = os.getenv('TEST_DATABASE_URL')
        if not self.dsn:
            self.fail('Set TEST_DATABASE_URL to a PostgreSQL test database. Tests do not use SQLite.')
        self.schema = 'test_medconnect_' + uuid.uuid4().hex
        self.conn = psycopg.connect(self.dsn, autocommit=True)
        self.addCleanup(self.cleanup_database)
        self.conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
        self.conn.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(self.schema)))
        self.conn.execute("SET timezone TO 'Asia/Kolkata'")
        self.conn.execute((ROOT / 'schema.sql').read_text(encoding='utf-8'))
        self.conn.execute("INSERT INTO Departments (dept_name,location) VALUES ('General Medicine','Wing A')")
        for index in (1, 2):
            self.conn.execute('''
                INSERT INTO Doctors (dept_id,first_name,last_name,email,phone,specialization,
                                     qualification,consultation_fee,password_hash)
                VALUES (1,'Doctor',%s,%s,%s,'General Medicine','MD',200,%s)
            ''', (str(index), f'doctor{index}@medconnect.local', f'800000000{index}', PASSWORD_HASH))
            for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
                self.conn.execute('''
                    INSERT INTO Doctor_Schedules (doctor_id,day_of_week,start_time,end_time)
                    VALUES (%s,%s,'09:00','17:00')
                ''', (index, day))
        for index in range(1, 11):
            self.conn.execute('''
                INSERT INTO Patients (first_name,last_name,date_of_birth,gender,phone,address)
                VALUES ('Patient',%s,'1990-01-01','Other',%s,'Demonstration Street')
            ''', (str(index), f'900000000{index:02d}'))
        for name, price in [('Medicine A', '12.50'), ('Medicine B', '7.25')]:
            self.conn.execute('''
                INSERT INTO Medicines (name,category,manufacturer,unit_price,stock_quantity,expiry_date)
                VALUES (%s,'Other','Demo Supplies',%s,100,CURRENT_DATE+365)
            ''', (name, price))
        self.day = self.conn.execute('SELECT CURRENT_DATE + 1').fetchone()[0]

    def cleanup_database(self):
        if not self.conn.closed:
            self.conn.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(sql.Identifier(self.schema)))
            self.conn.close()

    def connection(self):
        conn = psycopg.connect(self.dsn, autocommit=True)
        conn.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(self.schema)))
        conn.execute("SET timezone TO 'Asia/Kolkata'")
        conn.execute("SET statement_timeout TO '15000ms'")
        return conn

    def scalar(self, query, params=()):
        return self.conn.execute(query, params).fetchone()[0]

    def book(self, slot='09:00', patient=1, doctor=1, day=None):
        return self.scalar('''
            INSERT INTO Appointments (patient_id,doctor_id,appointment_date,appointment_time,reason_for_visit)
            VALUES (%s,%s,%s,%s,'Test consultation') RETURNING appointment_id
        ''', (patient, doctor, day or self.day, slot))

    def start(self, appointment_id):
        self.conn.execute("UPDATE Appointments SET status='In_Consultation' WHERE appointment_id=%s", (appointment_id,))

    def record(self, appointment_id, patient=1, doctor=1):
        self.conn.execute('''
            INSERT INTO Medical_Records (appointment_id,patient_id,doctor_id,symptoms,diagnosis)
            VALUES (%s,%s,%s,'Test symptoms','Test diagnosis')
        ''', (appointment_id, patient, doctor))

    def prescription(self, appointment_id, patient=1, doctor=1):
        return self.scalar('''
            INSERT INTO Prescriptions (appointment_id,patient_id,doctor_id)
            VALUES (%s,%s,%s) RETURNING prescription_id
        ''', (appointment_id, patient, doctor))

    def dispense(self, prescription_id, medicine=1, quantity=4, conn=None):
        (conn or self.conn).execute('''
            INSERT INTO Prescription_Items (prescription_id,medicine_id,dosage,duration_days,quantity)
            VALUES (%s,%s,'Test dosage',3,%s)
        ''', (prescription_id, medicine, quantity))

    def completed(self, slot='09:00', patient=1, doctor=1):
        appointment_id = self.book(slot, patient, doctor)
        self.start(appointment_id)
        self.record(appointment_id, patient, doctor)
        self.conn.execute("UPDATE Appointments SET status='Completed' WHERE appointment_id=%s", (appointment_id,))
        return appointment_id
