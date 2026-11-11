"""Populate an empty MedConnect database with repeatable, synthetic clinic data."""
import asyncio
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

import asyncpg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app import config
from backend.app.auth import hash_password

TABLES = ('Departments', 'Doctors', 'Doctor_Schedules', 'Patients', 'Appointments',
          'Medical_Records', 'Prescriptions', 'Medicines', 'Prescription_Items', 'Invoices')


async def populate(conn):
    if await conn.fetchval('SELECT COUNT(*) FROM Patients'):
        raise RuntimeError('Sample data already exists. Reset the disposable demo database before seeding again.')
    today = await conn.fetchval('SELECT CURRENT_DATE')
    departments = ['General Medicine', 'Cardiology', 'Dermatology', 'Orthopedics', 'Pediatrics', 'Neurology']
    for name in departments:
        await conn.execute('INSERT INTO Departments (dept_name,location,description) VALUES ($1,$2,$3)',
                           name, f'Wing {chr(65 + departments.index(name))}', f'{name} outpatient services')
    doctor_names = [('Ananya', 'Rao'), ('Arjun', 'Reddy'), ('Meera', 'Shah'), ('Vikram', 'Nair'),
                    ('Kavya', 'Iyer'), ('Rohan', 'Mehta'), ('Priya', 'Menon'), ('Aditya', 'Rao'),
                    ('Sneha', 'Das'), ('Rahul', 'Verma'), ('Nisha', 'Patel'), ('Kiran', 'Kumar'),
                    ('Sana', 'Ali'), ('Dev', 'Kapoor'), ('Ishita', 'Sen')]
    password_hash = hash_password('Doctor@2026')
    for index, (first, last) in enumerate(doctor_names):
        doctor_id = await conn.fetchval('''
            INSERT INTO Doctors (dept_id,first_name,last_name,email,phone,specialization,qualification,
                                 consultation_fee,password_hash)
            VALUES ($1,$2,$3,$4,$5,$6,'MBBS, MD',$7,$8) RETURNING doctor_id
        ''', index % 6 + 1, first, last, f'doctor{index + 1}@medconnect.local', f'800000{index:04d}',
                                       departments[index % 6], 400 + index * 50, password_hash)
        for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
            await conn.execute('''
                INSERT INTO Doctor_Schedules (doctor_id,day_of_week,start_time,end_time,slot_duration_minutes)
                VALUES ($1,$2,'09:00','17:00',30)
            ''', doctor_id, day)
    first_names = ['Aarav', 'Diya', 'Ishaan', 'Anika', 'Rishi', 'Sara', 'Neel', 'Tara', 'Vihaan', 'Mira']
    last_names = ['Sharma', 'Reddy', 'Patel', 'Singh', 'Nair', 'Rao', 'Iyer', 'Das', 'Khan', 'Mehta']
    for index in range(180):
        await conn.execute('''
            INSERT INTO Patients (first_name,last_name,date_of_birth,gender,blood_group,phone,email,address)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        ''', first_names[index % 10], last_names[(index // 10) % 10],
                           date(1960 + index % 50, index % 12 + 1, index % 27 + 1),
                           ['Male', 'Female', 'Other'][index % 3], ['O+', 'A+', 'B+', 'AB+', 'O-'][index % 5],
                           f'900000{index:04d}', f'patient{index + 1}@example.test',
                           f'{index + 1}, Demonstration Avenue, Hyderabad')
    names = ['Paracetamol 500mg', 'Amoxicillin 250mg', 'Cetirizine 10mg', 'Ibuprofen 200mg',
             'Amlodipine 5mg', 'Metformin 500mg', 'Vitamin C 500mg', 'Calcium 500mg',
             'Loratadine 10mg', 'Atorvastatin 10mg', 'Losartan 25mg', 'Vitamin D3',
             'Iron supplement', 'Folic acid', 'Oral rehydration salts', 'Zinc supplement',
             'Aspirin 75mg', 'Lisinopril 5mg', 'Glucose tablets', 'Multivitamin',
             'Saline nasal spray', 'Antacid tablets', 'B-complex', 'Magnesium supplement',
             'Cough lozenges', 'Electrolyte powder', 'Throat spray', 'Bandage pack',
             'Antiseptic solution', 'Demonstration expired stock']
    for index, name in enumerate(names):
        await conn.execute('''
            INSERT INTO Medicines (name,category,manufacturer,unit_price,stock_quantity,reorder_level,expiry_date)
            VALUES ($1,$2,'MedConnect Demo Supplies',$3,$4,25,$5)
        ''', name, ['Antipyretic', 'Antibiotic', 'Antihistamine', 'Analgesic', 'Cardiovascular',
                    'Antidiabetic', 'Supplements', 'Other'][index % 8],
                           5 + index * 2, 12 if index >= 27 else 1000,
                           today + timedelta(days=-1 if index == 29 else 500))
    for day_offset in range(-14, 6):
        day = today + timedelta(days=day_offset)
        for doctor_id in range(1, 16):
            index = (day_offset + 14) * 15 + doctor_id
            patient_id = (index - 1) % 180 + 1
            appointment_id = await conn.fetchval('''
                INSERT INTO Appointments (patient_id,doctor_id,appointment_date,appointment_time,reason_for_visit)
                VALUES ($1,$2,$3,$4,$5) RETURNING appointment_id
            ''', patient_id, doctor_id, day, time(9 + doctor_id % 4, 30 if doctor_id % 2 else 0),
                                                  ['Routine follow-up', 'General consultation', 'Review visit'][index % 3])
            if index % 10 == 0:
                await conn.execute("UPDATE Appointments SET status='Cancelled' WHERE appointment_id=$1", appointment_id)
            elif day_offset < 0 and index % 9 == 0:
                await conn.execute("UPDATE Appointments SET status='No_Show' WHERE appointment_id=$1", appointment_id)
            elif day_offset < 0:
                await conn.execute("UPDATE Appointments SET status='In_Consultation' WHERE appointment_id=$1", appointment_id)
                recorded_at = datetime.combine(day, time(10))
                await conn.execute('''
                    INSERT INTO Medical_Records (appointment_id,patient_id,doctor_id,symptoms,diagnosis,clinical_notes,recorded_at)
                    VALUES ($1,$2,$3,'Demonstration symptoms','Synthetic follow-up record',
                            'Fictional training data; not a real patient encounter.',$4)
                ''', appointment_id, patient_id, doctor_id, recorded_at)
                prescription_id = await conn.fetchval('''
                    INSERT INTO Prescriptions (appointment_id,patient_id,doctor_id,instructions,issued_at)
                    VALUES ($1,$2,$3,'Demonstration prescription only.',$4) RETURNING prescription_id
                ''', appointment_id, patient_id, doctor_id, recorded_at)
                await conn.execute('''
                    INSERT INTO Prescription_Items (prescription_id,medicine_id,dosage,duration_days,quantity)
                    VALUES ($1,$2,'Demo dosage',3,$3)
                ''', prescription_id, index % 27 + 1, index % 4 + 3)
                await conn.execute("UPDATE Appointments SET status='Completed' WHERE appointment_id=$1", appointment_id)
                await conn.execute('CALL sp_generate_invoice($1::int)', appointment_id)
                if index % 4:
                    await conn.execute('''
                        UPDATE Invoices SET payment_status='Paid',payment_method=$1,paid_at=CURRENT_TIMESTAMP
                        WHERE appointment_id=$2
                    ''', ['UPI', 'Card', 'Cash'][index % 3], appointment_id)
    counts = {table: await conn.fetchval(f'SELECT COUNT(*) FROM {table}') for table in TABLES}
    return counts


async def main():
    conn = await asyncpg.connect(config.DATABASE_URL, server_settings={'timezone': 'Asia/Kolkata'})
    try:
        async with conn.transaction():
            counts = await populate(conn)
        for table, count in counts.items():
            print(f'{table}: {count}')
        print(f'Total: {sum(counts.values())} records. All patient and clinical data is synthetic.')
    finally:
        await conn.close()


if __name__ == '__main__':
    asyncio.run(main())
