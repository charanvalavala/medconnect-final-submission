import json
import re
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import asyncpg
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import config, models
from .auth import admin_user, create_token, current_user, verify_password

CLINIC_ZONE = ZoneInfo('Asia/Kolkata')
REPORTS = {
    'department-revenue': ('Department revenue', '01_department_revenue.sql'),
    'doctor-performance': ('Doctor performance', '02_doctor_performance.sql'),
    'pharmacy-reorder': ('Pharmacy reorder', '03_pharmacy_reorder.sql'),
    'patient-history': ('Patient clinical history', '04_patient_history.sql'),
    'peak-demand': ('Peak demand and no-shows', '05_peak_demand.sql'),
}


@asynccontextmanager
async def lifespan(app):
    if len(config.JWT_SECRET) < 32 or not config.ADMIN_PASSWORD_HASH:
        raise RuntimeError('Set JWT_SECRET (at least 32 characters) and ADMIN_PASSWORD_HASH in .env.')
    if not re.fullmatch(r'[a-z_][a-z0-9_]*', config.DATABASE_SCHEMA):
        raise RuntimeError('Invalid database schema name.')
    async def initialize(conn):
        await conn.set_type_codec('json', encoder=json.dumps, decoder=json.loads, schema='pg_catalog')
        await conn.set_type_codec('jsonb', encoder=json.dumps, decoder=json.loads, schema='pg_catalog')
    app.state.pool = await asyncpg.create_pool(
        config.DATABASE_URL, min_size=2, max_size=10, command_timeout=20,
        server_settings={'search_path': config.DATABASE_SCHEMA, 'timezone': 'Asia/Kolkata'}, init=initialize)
    yield
    await app.state.pool.close()


app = FastAPI(title='MedConnect Clinic API', version='1.0.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS,
                   allow_credentials=False, allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
                   allow_headers=['Authorization', 'Content-Type'])


@app.exception_handler(asyncpg.PostgresError)
async def database_error(request, exc):
    if isinstance(exc, asyncpg.UniqueViolationError):
        message = 'This slot or unique entry already exists. Refresh and choose another.'
        status = 409
    elif isinstance(exc, asyncpg.ForeignKeyViolationError):
        message = 'This record is linked to clinical history, or a referenced record does not exist.'
        status = 409
    elif isinstance(exc, asyncpg.CheckViolationError):
        message = str(exc).split('\n')[0]
        if 'violates check constraint' in message:
            message = 'The supplied value does not satisfy the database rules.'
        status = 409
    elif isinstance(exc, (asyncpg.DeadlockDetectedError, asyncpg.SerializationError)):
        message, status = 'Another operation changed this data. Refresh and try again.', 409
    else:
        import logging
        logging.getLogger('medconnect').exception('Database operation failed', exc_info=exc)
        message, status = 'The database operation could not be completed.', 500
    return JSONResponse(status_code=status, content={'detail': message})


def result(row):
    return dict(row) if row else None


def future_slot(day, slot):
    if datetime.combine(day, slot, CLINIC_ZONE) <= datetime.now(CLINIC_ZONE):
        raise HTTPException(422, 'Choose a future appointment time.')


async def appointment_for(conn, appointment_id, user, lock=False):
    row = await conn.fetchrow('SELECT * FROM Appointments WHERE appointment_id = $1' +
                              (' FOR UPDATE' if lock else ''), appointment_id)
    if row is None:
        raise HTTPException(404, 'Appointment not found.')
    if user['role'] == 'Doctor' and row['doctor_id'] != user['id']:
        raise HTTPException(403, 'This appointment belongs to another doctor.')
    return row


@app.get('/api/health')
async def health(request: Request):
    await request.app.state.pool.fetchval('SELECT 1')
    return {'status': 'ok', 'database': 'PostgreSQL'}


@app.post('/api/auth/login')
async def login(body: models.Login, request: Request):
    if body.email.lower() == config.ADMIN_EMAIL.lower():
        valid = verify_password(body.password, config.ADMIN_PASSWORD_HASH)
        user = {'id': 0, 'name': 'Clinic Administration', 'role': 'Admin'}
    else:
        row = await request.app.state.pool.fetchrow(
            "SELECT doctor_id, first_name || ' ' || last_name AS name, password_hash FROM Doctors "
            "WHERE lower(email) = lower($1) AND status = 'Active'", body.email)
        valid = verify_password(body.password, row['password_hash'] if row else config.ADMIN_PASSWORD_HASH)
        valid = valid and row is not None
        user = {'id': row['doctor_id'], 'name': row['name'], 'role': 'Doctor'} if row else {}
    if not valid:
        raise HTTPException(401, 'Email or password is incorrect.')
    return {'access_token': create_token(user), 'token_type': 'bearer', 'user': user}


@app.get('/api/auth/me')
async def me(user=Depends(current_user)):
    return user


@app.get('/api/departments')
async def departments(request: Request, user=Depends(current_user)):
    return [dict(r) for r in await request.app.state.pool.fetch('SELECT * FROM Departments ORDER BY dept_name')]


@app.get('/api/doctors')
async def doctors(request: Request, dept_id: int | None = None, user=Depends(current_user)):
    return [dict(r) for r in await request.app.state.pool.fetch('''
        SELECT d.doctor_id, d.dept_id, d.first_name, d.last_name, d.email, d.specialization,
               d.qualification, d.consultation_fee, d.status, dept.dept_name
        FROM Doctors d JOIN Departments dept USING (dept_id)
        WHERE ($1::int IS NULL OR d.dept_id = $1) ORDER BY d.first_name, d.last_name
    ''', dept_id)]


@app.get('/api/schedules')
async def schedules(request: Request, doctor_id: int | None = None, user=Depends(current_user)):
    return [dict(r) for r in await request.app.state.pool.fetch('''
        SELECT * FROM Doctor_Schedules WHERE ($1::int IS NULL OR doctor_id = $1)
        ORDER BY doctor_id, schedule_id
    ''', doctor_id)]


@app.post('/api/schedules', status_code=201)
async def add_schedule(body: models.Schedule, request: Request, user=Depends(admin_user)):
    row = await request.app.state.pool.fetchrow('''
        INSERT INTO Doctor_Schedules (doctor_id, day_of_week, start_time, end_time, slot_duration_minutes)
        VALUES ($1, $2, $3, $4, $5) RETURNING *
    ''', *body.model_dump().values())
    return dict(row)


@app.get('/api/patients')
async def patients(request: Request, q: str = Query('', max_length=100),
                   limit: int = Query(100, ge=1, le=250), user=Depends(current_user)):
    doctor_id = user['id'] if user['role'] == 'Doctor' else None
    rows = await request.app.state.pool.fetch('''
        SELECT p.* FROM Patients p
        WHERE (p.first_name || ' ' || p.last_name ILIKE $1 OR p.phone ILIKE $1)
          AND ($2::int IS NULL OR EXISTS (
              SELECT 1 FROM Appointments a WHERE a.patient_id = p.patient_id AND a.doctor_id = $2))
        ORDER BY p.patient_id DESC LIMIT $3
    ''', f'%{q}%', doctor_id, limit)
    return [dict(r) for r in rows]


@app.post('/api/patients', status_code=201)
async def add_patient(body: models.Patient, request: Request, user=Depends(admin_user)):
    return dict(await request.app.state.pool.fetchrow('''
        INSERT INTO Patients (first_name, last_name, date_of_birth, gender, blood_group,
                              phone, email, address, emergency_contact_phone)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING *
    ''', *body.model_dump().values()))


@app.put('/api/patients/{patient_id}')
async def edit_patient(patient_id: int, body: models.Patient, request: Request, user=Depends(admin_user)):
    row = await request.app.state.pool.fetchrow('''
        UPDATE Patients SET first_name=$1,last_name=$2,date_of_birth=$3,gender=$4,blood_group=$5,
                            phone=$6,email=$7,address=$8,emergency_contact_phone=$9
        WHERE patient_id=$10 RETURNING *
    ''', *body.model_dump().values(), patient_id)
    if row is None:
        raise HTTPException(404, 'Patient not found.')
    return dict(row)


@app.delete('/api/patients/{patient_id}')
async def delete_patient(patient_id: int, request: Request, user=Depends(admin_user)):
    deleted = await request.app.state.pool.fetchval('DELETE FROM Patients WHERE patient_id=$1 RETURNING patient_id', patient_id)
    if deleted is None:
        raise HTTPException(404, 'Patient not found.')
    return {'deleted': deleted}


@app.get('/api/slots')
async def slots(request: Request, doctor_id: int, appointment_date: date,
                exclude_appointment_id: int | None = None, user=Depends(current_user)):
    async with request.app.state.pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT s.* FROM Doctor_Schedules s JOIN Doctors d USING (doctor_id)
            WHERE s.doctor_id=$1 AND s.day_of_week=$2 AND s.is_active AND d.status='Active'
            ORDER BY s.start_time
        ''', doctor_id, appointment_date.strftime('%A'))
        booked = await conn.fetch('''
            SELECT appointment_time, duration_minutes FROM Appointments
            WHERE doctor_id=$1 AND appointment_date=$2 AND status != 'Cancelled'
              AND ($3::int IS NULL OR appointment_id != $3)
        ''', doctor_id, appointment_date, exclude_appointment_id)
    available = []
    for shift in rows:
        cursor = datetime.combine(appointment_date, shift['start_time'], CLINIC_ZONE)
        end = datetime.combine(appointment_date, shift['end_time'], CLINIC_ZONE)
        duration = timedelta(minutes=shift['slot_duration_minutes'])
        while cursor + duration <= end:
            occupied = any(cursor < datetime.combine(appointment_date, a['appointment_time'], CLINIC_ZONE) +
                           timedelta(minutes=a['duration_minutes']) and cursor + duration >
                           datetime.combine(appointment_date, a['appointment_time'], CLINIC_ZONE) for a in booked)
            if not occupied and cursor > datetime.now(CLINIC_ZONE):
                available.append({'time': cursor.strftime('%H:%M'), 'duration_minutes': shift['slot_duration_minutes']})
            cursor += duration
    return available


@app.get('/api/appointments')
async def appointments(request: Request, appointment_date: date | None = None,
                       status: str | None = None, doctor_id: int | None = None,
                       user=Depends(current_user)):
    if user['role'] == 'Doctor':
        doctor_id = user['id']
    rows = await request.app.state.pool.fetch('''
        SELECT a.*, p.first_name || ' ' || p.last_name AS patient_name, p.phone,
               d.first_name || ' ' || d.last_name AS doctor_name, dept.dept_name
        FROM Appointments a JOIN Patients p USING (patient_id)
        JOIN Doctors d USING (doctor_id) JOIN Departments dept ON d.dept_id=dept.dept_id
        WHERE ($1::date IS NULL OR a.appointment_date=$1)
          AND ($2::text IS NULL OR a.status=$2) AND ($3::int IS NULL OR a.doctor_id=$3)
        ORDER BY a.appointment_date DESC, a.appointment_time LIMIT 250
    ''', appointment_date, status, doctor_id)
    return [dict(r) for r in rows]


@app.post('/api/appointments', status_code=201)
async def book(body: models.Booking, request: Request, user=Depends(admin_user)):
    future_slot(body.appointment_date, body.appointment_time)
    async with request.app.state.pool.acquire() as conn, conn.transaction():
        return dict(await conn.fetchrow('''
            INSERT INTO Appointments (patient_id,doctor_id,appointment_date,appointment_time,reason_for_visit)
            VALUES ($1,$2,$3,$4,$5) RETURNING *
        ''', *body.model_dump().values()))


@app.patch('/api/appointments/{appointment_id}/reschedule')
async def reschedule(appointment_id: int, body: models.Reschedule, request: Request, user=Depends(admin_user)):
    future_slot(body.appointment_date, body.appointment_time)
    async with request.app.state.pool.acquire() as conn, conn.transaction():
        row = await appointment_for(conn, appointment_id, user, lock=True)
        if row['status'] != 'Scheduled':
            raise HTTPException(409, 'Only scheduled appointments can be rescheduled.')
        return dict(await conn.fetchrow('''
            UPDATE Appointments SET appointment_date=$1, appointment_time=$2
            WHERE appointment_id=$3 RETURNING *
        ''', body.appointment_date, body.appointment_time, appointment_id))


@app.patch('/api/appointments/{appointment_id}/status')
async def appointment_status(appointment_id: int, body: models.AppointmentStatus, request: Request,
                             user=Depends(current_user)):
    if user['role'] == 'Doctor' and body.status != 'In_Consultation':
        raise HTTPException(403, 'Only reception may cancel or mark a no-show.')
    if user['role'] == 'Admin' and body.status == 'In_Consultation':
        raise HTTPException(403, 'The treating doctor must start the consultation.')
    async with request.app.state.pool.acquire() as conn, conn.transaction():
        row = await appointment_for(conn, appointment_id, user, lock=True)
        if body.status == 'No_Show' and datetime.combine(row['appointment_date'], row['appointment_time'], CLINIC_ZONE) > datetime.now(CLINIC_ZONE):
            raise HTTPException(409, 'A future appointment cannot be marked as a no-show.')
        return dict(await conn.fetchrow('UPDATE Appointments SET status=$1 WHERE appointment_id=$2 RETURNING *',
                                        body.status, appointment_id))


@app.post('/api/appointments/{appointment_id}/complete')
async def complete(appointment_id: int, body: models.Encounter, request: Request, user=Depends(current_user)):
    if user['role'] != 'Doctor':
        raise HTTPException(403, 'The treating doctor must complete the consultation.')
    async with request.app.state.pool.acquire() as conn, conn.transaction():
        row = await appointment_for(conn, appointment_id, user, lock=True)
        if row['status'] != 'In_Consultation':
            raise HTTPException(409, 'Start the consultation first. Completed encounters cannot be changed.')
        await conn.execute('''
            INSERT INTO Medical_Records (appointment_id,patient_id,doctor_id,symptoms,diagnosis,clinical_notes)
            VALUES ($1,$2,$3,$4,$5,$6)
        ''', appointment_id, row['patient_id'], row['doctor_id'], body.symptoms, body.diagnosis, body.clinical_notes)
        if body.items:
            prescription_id = await conn.fetchval('''
                INSERT INTO Prescriptions (appointment_id,patient_id,doctor_id,instructions)
                VALUES ($1,$2,$3,$4) RETURNING prescription_id
            ''', appointment_id, row['patient_id'], row['doctor_id'], body.instructions)
            # Lock medicines in a stable order to avoid opposite-order dispensing deadlocks.
            for item in sorted(body.items, key=lambda item: item.medicine_id):
                await conn.execute('''
                    INSERT INTO Prescription_Items (prescription_id,medicine_id,dosage,duration_days,quantity)
                    VALUES ($1,$2,$3,$4,$5)
                ''', prescription_id, item.medicine_id, item.dosage, item.duration_days, item.quantity)
        await conn.execute("UPDATE Appointments SET status='Completed' WHERE appointment_id=$1", appointment_id)
        await conn.execute('CALL sp_generate_invoice($1::int)', appointment_id)
        return dict(await conn.fetchrow('SELECT * FROM Invoices WHERE appointment_id=$1', appointment_id))


@app.get('/api/patients/{patient_id}/history')
async def patient_history(patient_id: int, request: Request, user=Depends(current_user)):
    doctor_id = user['id'] if user['role'] == 'Doctor' else None
    async with request.app.state.pool.acquire() as conn:
        if doctor_id and not await conn.fetchval('''
            SELECT EXISTS(SELECT 1 FROM Appointments WHERE patient_id=$1 AND doctor_id=$2)
        ''', patient_id, doctor_id):
            raise HTTPException(403, 'No appointment connects this patient to your account.')
        if not await conn.fetchval('SELECT EXISTS(SELECT 1 FROM Patients WHERE patient_id=$1)', patient_id):
            raise HTTPException(404, 'Patient not found.')
        query = (config.ROOT / 'database/queries/04_patient_history.sql').read_text(encoding='utf-8')
        rows = await conn.fetch(query, patient_id, doctor_id)
    return [dict(r) for r in rows]


@app.get('/api/medicines')
async def medicines(request: Request, q: str = Query('', max_length=100), user=Depends(current_user)):
    return [dict(r) for r in await request.app.state.pool.fetch('''
        SELECT *, stock_quantity <= reorder_level AS needs_reorder, expiry_date < CURRENT_DATE AS expired
        FROM Medicines WHERE name ILIKE $1 OR category ILIKE $1 ORDER BY name
    ''', f'%{q}%')]


@app.post('/api/medicines', status_code=201)
async def add_medicine(body: models.Medicine, request: Request, user=Depends(admin_user)):
    return dict(await request.app.state.pool.fetchrow('''
        INSERT INTO Medicines (name,category,manufacturer,unit_price,stock_quantity,reorder_level,expiry_date)
        VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING *
    ''', *body.model_dump().values()))


@app.post('/api/medicines/{medicine_id}/restock')
async def restock(medicine_id: int, body: models.StockReceipt, request: Request, user=Depends(admin_user)):
    row = await request.app.state.pool.fetchrow('''
        UPDATE Medicines SET stock_quantity=stock_quantity+$1 WHERE medicine_id=$2 RETURNING *
    ''', body.quantity, medicine_id)
    if row is None:
        raise HTTPException(404, 'Medicine not found.')
    return dict(row)


@app.patch('/api/medicines/{medicine_id}/price')
async def medicine_price(medicine_id: int, body: models.MedicinePrice, request: Request, user=Depends(admin_user)):
    row = await request.app.state.pool.fetchrow('UPDATE Medicines SET unit_price=$1 WHERE medicine_id=$2 RETURNING *',
                                              body.unit_price, medicine_id)
    if row is None:
        raise HTTPException(404, 'Medicine not found.')
    return dict(row)


@app.get('/api/invoices')
async def invoices(request: Request, payment_status: str | None = None, user=Depends(admin_user)):
    return [dict(r) for r in await request.app.state.pool.fetch('''
        SELECT i.*, p.first_name || ' ' || p.last_name AS patient_name, a.appointment_date,
               d.first_name || ' ' || d.last_name AS doctor_name, dept.dept_name
        FROM Invoices i JOIN Patients p USING (patient_id) JOIN Appointments a USING (appointment_id)
        JOIN Doctors d ON a.doctor_id=d.doctor_id JOIN Departments dept USING (dept_id)
        WHERE ($1::text IS NULL OR i.payment_status=$1) ORDER BY i.invoice_id DESC LIMIT 250
    ''', payment_status)]


@app.post('/api/invoices/{invoice_id}/pay')
async def pay(invoice_id: int, body: models.Payment, request: Request, user=Depends(admin_user)):
    async with request.app.state.pool.acquire() as conn, conn.transaction():
        row = await conn.fetchrow('SELECT * FROM Invoices WHERE invoice_id=$1 FOR UPDATE', invoice_id)
        if row is None:
            raise HTTPException(404, 'Invoice not found.')
        if row['payment_status'] == 'Paid':
            if row['payment_method'] != body.payment_method:
                raise HTTPException(409, 'This invoice was already paid using another method.')
            return dict(row)
        if row['payment_status'] != 'Pending':
            raise HTTPException(409, 'Only pending invoices may be paid.')
        return dict(await conn.fetchrow('''
            UPDATE Invoices SET payment_status='Paid',payment_method=$1,paid_at=CURRENT_TIMESTAMP
            WHERE invoice_id=$2 RETURNING *
        ''', body.payment_method, invoice_id))


@app.get('/api/reports')
async def report_list(user=Depends(admin_user)):
    return [{'id': key, 'name': title} for key, (title, _) in REPORTS.items()]


@app.get('/api/reports/{report_id}')
async def report(report_id: str, request: Request, patient_id: int | None = None, user=Depends(admin_user)):
    if report_id not in REPORTS:
        raise HTTPException(404, 'Report not found.')
    query = (config.ROOT / 'database/queries' / REPORTS[report_id][1]).read_text(encoding='utf-8')
    params = ()
    if report_id == 'patient-history':
        if patient_id is None:
            raise HTTPException(422, 'Select a patient for the history report.')
        params = (patient_id, None)
    return [dict(r) for r in await request.app.state.pool.fetch(query, *params)]


@app.get('/api/overview')
async def overview(request: Request, user=Depends(current_user)):
    doctor_id = user['id'] if user['role'] == 'Doctor' else None
    async with request.app.state.pool.acquire() as conn:
        counts = dict(await conn.fetchrow('''
            SELECT COUNT(*) FILTER (WHERE appointment_date=CURRENT_DATE) AS appointments_today,
                   COUNT(*) FILTER (WHERE status='Scheduled' AND appointment_date=CURRENT_DATE) AS waiting_today,
                   COUNT(*) FILTER (WHERE status='Completed' AND appointment_date=CURRENT_DATE) AS completed_today,
                   COUNT(DISTINCT patient_id) AS patients
            FROM Appointments WHERE ($1::int IS NULL OR doctor_id=$1)
        ''', doctor_id))
        counts['active_doctors'] = await conn.fetchval("SELECT COUNT(*) FROM Doctors WHERE status='Active'")
        counts['low_stock'] = await conn.fetchval('SELECT COUNT(*) FROM Medicines WHERE stock_quantity <= reorder_level')
        counts['clinic_date'] = str(await conn.fetchval('SELECT CURRENT_DATE'))
        if user['role'] == 'Admin':
            counts['patients'] = await conn.fetchval('SELECT COUNT(*) FROM Patients')
            counts.update(dict(await conn.fetchrow('''
                SELECT COALESCE(SUM(total_amount) FILTER (WHERE payment_status='Paid' AND paid_at::date=CURRENT_DATE),0) AS collected_today,
                       COALESCE(SUM(total_amount) FILTER (WHERE payment_status='Pending'),0) AS outstanding
                FROM Invoices
            ''')))
            counts['revenue'] = [dict(r) for r in await conn.fetch('''
                SELECT d.dept_name, COALESCE(SUM(v.settled_revenue),0) AS revenue
                FROM Departments d LEFT JOIN v_daily_department_revenue v USING (dept_id)
                GROUP BY d.dept_id, d.dept_name ORDER BY revenue DESC
            ''')]
    return counts
