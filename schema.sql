-- ============================================================================
-- MedConnect: Clinic Appointment Management System
-- Database Schema Definition (PostgreSQL 15 / 16 DDL)
-- Document: schema.sql
-- Milestone: Final Project Submission
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 0. CLEAN TEARDOWN (Run only in a disposable/demo database)
-- ----------------------------------------------------------------------------
DROP VIEW IF EXISTS v_daily_department_revenue CASCADE;
DROP PROCEDURE IF EXISTS sp_generate_invoice(INT) CASCADE;
DROP FUNCTION IF EXISTS fn_trg_deduct_medicine_stock() CASCADE;
DROP FUNCTION IF EXISTS fn_validate_appointment() CASCADE;
DROP FUNCTION IF EXISTS fn_validate_schedule() CASCADE;
DROP FUNCTION IF EXISTS fn_validate_clinical_link() CASCADE;
DROP FUNCTION IF EXISTS fn_protect_invoice() CASCADE;
DROP FUNCTION IF EXISTS fn_reject_change() CASCADE;

DROP TABLE IF EXISTS Invoices CASCADE;
DROP TABLE IF EXISTS Prescription_Items CASCADE;
DROP TABLE IF EXISTS Prescriptions CASCADE;
DROP TABLE IF EXISTS Medical_Records CASCADE;
DROP TABLE IF EXISTS Appointments CASCADE;
DROP TABLE IF EXISTS Doctor_Schedules CASCADE;
DROP TABLE IF EXISTS Doctors CASCADE;
DROP TABLE IF EXISTS Departments CASCADE;
DROP TABLE IF EXISTS Patients CASCADE;
DROP TABLE IF EXISTS Medicines CASCADE;

-- ----------------------------------------------------------------------------
-- 1. MASTER DEPARTMENTS TABLE
-- ----------------------------------------------------------------------------
CREATE TABLE Departments (
    dept_id          SERIAL PRIMARY KEY,
    dept_name        VARCHAR(100) NOT NULL UNIQUE,
    description      TEXT,
    location         VARCHAR(100) NOT NULL,
    contact_number   VARCHAR(20),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_dept_name_len 
        CHECK (char_length(dept_name) >= 2)
);

-- ----------------------------------------------------------------------------
-- 2. CLINICAL DOCTORS (PROVIDERS) TABLE
-- ----------------------------------------------------------------------------
CREATE TABLE Doctors (
    doctor_id        SERIAL PRIMARY KEY,
    dept_id          INT NOT NULL,
    first_name       VARCHAR(50) NOT NULL,
    last_name        VARCHAR(50) NOT NULL,
    email            VARCHAR(100) NOT NULL UNIQUE,
    phone            VARCHAR(20) NOT NULL UNIQUE,
    specialization   VARCHAR(100) NOT NULL,
    qualification    VARCHAR(100) NOT NULL,
    consultation_fee NUMERIC(10, 2) NOT NULL,
    status           VARCHAR(20) NOT NULL DEFAULT 'Active',
    password_hash    TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_doctor_department 
        FOREIGN KEY (dept_id) 
        REFERENCES Departments(dept_id) 
        ON DELETE RESTRICT 
        ON UPDATE CASCADE,

    CONSTRAINT chk_doctor_fee_positive 
        CHECK (consultation_fee >= 0.00),

    CONSTRAINT chk_doctor_status_valid 
        CHECK (status IN ('Active', 'On_Leave', 'Resigned', 'Suspended')),

    CONSTRAINT chk_doctor_email_format 
        CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

-- ----------------------------------------------------------------------------
-- 3. DOCTOR RECURRING SCHEDULES TABLE
-- ----------------------------------------------------------------------------
CREATE TABLE Doctor_Schedules (
    schedule_id           SERIAL PRIMARY KEY,
    doctor_id             INT NOT NULL,
    day_of_week           VARCHAR(10) NOT NULL,
    start_time            TIME NOT NULL,
    end_time              TIME NOT NULL,
    slot_duration_minutes INT NOT NULL DEFAULT 30,
    is_active             BOOLEAN NOT NULL DEFAULT TRUE,

    CONSTRAINT fk_schedule_doctor 
        FOREIGN KEY (doctor_id) 
        REFERENCES Doctors(doctor_id) 
        ON DELETE CASCADE 
        ON UPDATE CASCADE,

    CONSTRAINT chk_schedule_day_of_week 
        CHECK (day_of_week IN ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')),

    CONSTRAINT chk_schedule_time_order 
        CHECK (start_time < end_time),

    CONSTRAINT chk_schedule_slot_duration 
        CHECK (slot_duration_minutes IN (15, 20, 30, 45, 60)),

    CONSTRAINT uq_doctor_shift_start 
        UNIQUE (doctor_id, day_of_week, start_time)
);

-- ----------------------------------------------------------------------------
-- 4. REGISTERED PATIENTS TABLE
-- ----------------------------------------------------------------------------
CREATE TABLE Patients (
    patient_id              SERIAL PRIMARY KEY,
    first_name              VARCHAR(50) NOT NULL,
    last_name               VARCHAR(50) NOT NULL,
    date_of_birth           DATE NOT NULL,
    gender                  VARCHAR(10) NOT NULL,
    blood_group             VARCHAR(5),
    phone                   VARCHAR(20) NOT NULL UNIQUE,
    email                   VARCHAR(100) UNIQUE,
    address                 TEXT NOT NULL,
    emergency_contact_phone VARCHAR(20),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_patient_phone_digits
        CHECK (phone ~ '^[0-9]{10}$'),

    CONSTRAINT chk_patient_emergency_phone_digits
        CHECK (emergency_contact_phone IS NULL OR emergency_contact_phone ~ '^[0-9]{10}$'),

    CONSTRAINT chk_patient_dob_valid 
        CHECK (date_of_birth >= '1900-01-01'),

    CONSTRAINT chk_patient_gender_valid 
        CHECK (gender IN ('Male', 'Female', 'Other')),

    CONSTRAINT chk_patient_blood_group 
        CHECK (blood_group IS NULL OR blood_group IN ('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-')),

    CONSTRAINT chk_patient_email_format 
        CHECK (email IS NULL OR email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

-- ----------------------------------------------------------------------------
-- 5. APPOINTMENTS (CONSULTATION BOOKINGS) TABLE
-- ----------------------------------------------------------------------------
CREATE TABLE Appointments (
    appointment_id   SERIAL PRIMARY KEY,
    patient_id       INT NOT NULL,
    doctor_id        INT NOT NULL,
    appointment_date DATE NOT NULL,
    appointment_time TIME NOT NULL,
    duration_minutes INT NOT NULL DEFAULT 30 CHECK (duration_minutes IN (15, 20, 30, 45, 60)),
    status           VARCHAR(20) NOT NULL DEFAULT 'Scheduled',
    reason_for_visit VARCHAR(255),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_appointment_patient 
        FOREIGN KEY (patient_id) 
        REFERENCES Patients(patient_id) 
        ON DELETE RESTRICT 
        ON UPDATE CASCADE,

    CONSTRAINT fk_appointment_doctor 
        FOREIGN KEY (doctor_id) 
        REFERENCES Doctors(doctor_id) 
        ON DELETE RESTRICT 
        ON UPDATE CASCADE,

    CONSTRAINT chk_appointment_status 
        CHECK (status IN ('Scheduled', 'In_Consultation', 'Completed', 'Cancelled', 'No_Show')),

    CONSTRAINT chk_appointment_date_valid 
        CHECK (appointment_date >= '2020-01-01')
);

-- CRITICAL CONCURRENCY CONTROL: Partial Unique Index
-- Guarantees zero double-booking for active slots while permitting rebooking of cancelled slots
CREATE UNIQUE INDEX uq_doctor_slot_active 
ON Appointments (doctor_id, appointment_date, appointment_time) 
WHERE status NOT IN ('Cancelled');

-- ----------------------------------------------------------------------------
-- 6. MEDICAL RECORDS (CLINICAL EHR) TABLE
-- ----------------------------------------------------------------------------
CREATE TABLE Medical_Records (
    record_id        SERIAL PRIMARY KEY,
    appointment_id   INT UNIQUE,
    patient_id       INT NOT NULL,
    doctor_id        INT NOT NULL,
    symptoms         TEXT NOT NULL,
    diagnosis        TEXT NOT NULL,
    clinical_notes   TEXT,
    recorded_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_record_appointment 
        FOREIGN KEY (appointment_id) 
        REFERENCES Appointments(appointment_id) 
        ON DELETE SET NULL 
        ON UPDATE CASCADE,

    CONSTRAINT fk_record_patient 
        FOREIGN KEY (patient_id) 
        REFERENCES Patients(patient_id) 
        ON DELETE RESTRICT 
        ON UPDATE CASCADE,

    CONSTRAINT fk_record_doctor 
        FOREIGN KEY (doctor_id) 
        REFERENCES Doctors(doctor_id) 
        ON DELETE RESTRICT 
        ON UPDATE CASCADE
);

-- ----------------------------------------------------------------------------
-- 7. PRESCRIPTIONS (MEDICAL ORDERS) TABLE
-- ----------------------------------------------------------------------------
CREATE TABLE Prescriptions (
    prescription_id  SERIAL PRIMARY KEY,
    appointment_id   INT NOT NULL UNIQUE,
    patient_id       INT NOT NULL,
    doctor_id        INT NOT NULL,
    instructions     TEXT,
    issued_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_prescription_appointment 
        FOREIGN KEY (appointment_id) 
        REFERENCES Appointments(appointment_id) 
        ON DELETE RESTRICT 
        ON UPDATE CASCADE,

    CONSTRAINT fk_prescription_patient 
        FOREIGN KEY (patient_id) 
        REFERENCES Patients(patient_id) 
        ON DELETE RESTRICT 
        ON UPDATE CASCADE,

    CONSTRAINT fk_prescription_doctor 
        FOREIGN KEY (doctor_id) 
        REFERENCES Doctors(doctor_id) 
        ON DELETE RESTRICT 
        ON UPDATE CASCADE
);

-- ----------------------------------------------------------------------------
-- 8. PHARMACY MEDICINES CATALOG & INVENTORY TABLE
-- ----------------------------------------------------------------------------
CREATE TABLE Medicines (
    medicine_id      SERIAL PRIMARY KEY,
    name             VARCHAR(100) NOT NULL UNIQUE,
    category         VARCHAR(50) NOT NULL,
    manufacturer     VARCHAR(100) NOT NULL,
    unit_price       NUMERIC(10, 2) NOT NULL,
    stock_quantity   INT NOT NULL DEFAULT 0,
    reorder_level    INT NOT NULL DEFAULT 20,
    expiry_date      DATE NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_med_unit_price 
        CHECK (unit_price >= 0.00),

    CONSTRAINT chk_med_stock_quantity 
        CHECK (stock_quantity >= 0),

    CONSTRAINT chk_med_reorder_level 
        CHECK (reorder_level >= 0),

    CONSTRAINT chk_med_category_valid 
        CHECK (category IN ('Antibiotic', 'Analgesic', 'Antihistamine', 'Antipyretic', 'Cardiovascular', 'Antidiabetic', 'Supplements', 'Other'))
);

-- ----------------------------------------------------------------------------
-- 9. PRESCRIPTION ITEMS (ASSOCIATIVE BRIDGE) TABLE
-- ----------------------------------------------------------------------------
CREATE TABLE Prescription_Items (
    item_id          SERIAL PRIMARY KEY,
    prescription_id  INT NOT NULL,
    medicine_id      INT NOT NULL,
    dosage           VARCHAR(50) NOT NULL,
    duration_days    INT NOT NULL,
    quantity         INT NOT NULL,
    unit_price       NUMERIC(10, 2) NOT NULL CHECK (unit_price >= 0.00),

    CONSTRAINT fk_item_prescription 
        FOREIGN KEY (prescription_id) 
        REFERENCES Prescriptions(prescription_id) 
        ON DELETE CASCADE 
        ON UPDATE CASCADE,

    CONSTRAINT fk_item_medicine 
        FOREIGN KEY (medicine_id) 
        REFERENCES Medicines(medicine_id) 
        ON DELETE RESTRICT 
        ON UPDATE CASCADE,

    CONSTRAINT chk_item_duration_days 
        CHECK (duration_days > 0),

    CONSTRAINT chk_item_quantity_positive 
        CHECK (quantity > 0),

    CONSTRAINT uq_prescription_medicine 
        UNIQUE (prescription_id, medicine_id)
);

-- ----------------------------------------------------------------------------
-- 10. FINANCIAL INVOICES TABLE
-- ----------------------------------------------------------------------------
CREATE TABLE Invoices (
    invoice_id       SERIAL PRIMARY KEY,
    appointment_id   INT NOT NULL UNIQUE,
    patient_id       INT NOT NULL,
    consultation_fee NUMERIC(10, 2) NOT NULL,
    medicine_total   NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    total_amount     NUMERIC(10, 2) NOT NULL,
    payment_status   VARCHAR(20) NOT NULL DEFAULT 'Pending',
    payment_method   VARCHAR(20),
    issued_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    paid_at          TIMESTAMPTZ,

    CONSTRAINT fk_invoice_appointment 
        FOREIGN KEY (appointment_id) 
        REFERENCES Appointments(appointment_id) 
        ON DELETE RESTRICT 
        ON UPDATE CASCADE,

    CONSTRAINT fk_invoice_patient 
        FOREIGN KEY (patient_id) 
        REFERENCES Patients(patient_id) 
        ON DELETE RESTRICT 
        ON UPDATE CASCADE,

    CONSTRAINT chk_invoice_fees_positive 
        CHECK (consultation_fee >= 0.00 AND medicine_total >= 0.00),

    CONSTRAINT chk_invoice_total_balance 
        CHECK (total_amount = (consultation_fee + medicine_total)),

    CONSTRAINT chk_invoice_payment_status 
        CHECK (payment_status IN ('Pending', 'Paid', 'Refunded', 'Cancelled')),

    CONSTRAINT chk_invoice_payment_method 
        CHECK (payment_method IS NULL OR payment_method IN ('Cash', 'Card', 'UPI', 'Insurance', 'NetBanking')),

    CONSTRAINT chk_invoice_paid_state 
        CHECK (
            (payment_status = 'Paid' AND paid_at IS NOT NULL AND payment_method IS NOT NULL) OR 
            (payment_status != 'Paid')
        )
);

-- ----------------------------------------------------------------------------
-- 11. PERFORMANCE & QUERY TUNING INDEXES
-- ----------------------------------------------------------------------------
-- Indexes supporting the booking, history, inventory, and reporting queries.
CREATE INDEX idx_doctors_dept_id ON Doctors(dept_id);
CREATE INDEX idx_doctors_status ON Doctors(status);
CREATE INDEX idx_schedules_doctor_day ON Doctor_Schedules(doctor_id, day_of_week) WHERE is_active = TRUE;

CREATE INDEX idx_patients_last_name ON Patients(last_name, first_name);

CREATE INDEX idx_appt_patient_id ON Appointments(patient_id);
CREATE INDEX idx_appt_doctor_date ON Appointments(doctor_id, appointment_date, status);

CREATE INDEX idx_medrec_patient_id ON Medical_Records(patient_id, recorded_at DESC);
CREATE INDEX idx_presc_patient_id ON Prescriptions(patient_id);

CREATE INDEX idx_items_medicine_id ON Prescription_Items(medicine_id);

CREATE INDEX idx_med_stock_reorder ON Medicines(stock_quantity, reorder_level);
CREATE INDEX idx_med_category ON Medicines(category);

CREATE INDEX idx_invoices_patient ON Invoices(patient_id, payment_status);
CREATE INDEX idx_invoices_status_date ON Invoices(payment_status, issued_at);

-- ----------------------------------------------------------------------------
-- 12. ADVANCED DBMS FEATURE 1: PL/pgSQL INVENTORY DEDUCTION TRIGGER
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_trg_deduct_medicine_stock()
RETURNS TRIGGER AS $$
DECLARE
    v_current_stock INT;
    v_med_name VARCHAR(100);
    v_unit_price NUMERIC(10, 2);
    v_expiry_date DATE;
    v_status VARCHAR(20);
BEGIN
    -- Serialize dispensing with encounter completion on the parent appointment.
    SELECT a.status INTO v_status
    FROM Appointments a JOIN Prescriptions p USING (appointment_id)
    WHERE p.prescription_id = NEW.prescription_id
    FOR UPDATE OF a;
    IF NOT FOUND OR v_status != 'In_Consultation' THEN
        RAISE EXCEPTION 'Medicines can only be dispensed during an open consultation.' USING ERRCODE = '23514';
    END IF;

    -- Acquire exclusive row-level lock on the medicine to serialize concurrent updates
    SELECT stock_quantity, name, unit_price, expiry_date
    INTO v_current_stock, v_med_name, v_unit_price, v_expiry_date
    FROM Medicines
    WHERE medicine_id = NEW.medicine_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Medicine ID % does not exist in pharmacy inventory.', NEW.medicine_id USING ERRCODE = '23503';
    END IF;

    -- Validate inventory sufficiency
    IF v_current_stock < NEW.quantity THEN
        RAISE EXCEPTION 'Insufficient inventory for "%" (ID %): requested %, but only % available in stock.', 
            v_med_name, NEW.medicine_id, NEW.quantity, v_current_stock USING ERRCODE = '23514';
    END IF;

    IF v_expiry_date < CURRENT_DATE THEN
        RAISE EXCEPTION 'Expired medicine cannot be dispensed: %', v_med_name USING ERRCODE = '23514';
    END IF;
    NEW.unit_price := v_unit_price;

    -- Atomically decrement stock
    UPDATE Medicines
    SET stock_quantity = stock_quantity - NEW.quantity
    WHERE medicine_id = NEW.medicine_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_deduct_medicine_stock
BEFORE INSERT ON Prescription_Items
FOR EACH ROW
EXECUTE FUNCTION fn_trg_deduct_medicine_stock();

-- ----------------------------------------------------------------------------
-- 13. ADVANCED DBMS FEATURE 2: AUTOMATED INVOICING STORED PROCEDURE
-- ----------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE sp_generate_invoice(p_appointment_id INT)
LANGUAGE plpgsql
AS $$
DECLARE
    v_patient_id INT;
    v_doctor_id INT;
    v_appt_status VARCHAR(20);
    v_consultation_fee NUMERIC(10, 2);
    v_medicine_total NUMERIC(10, 2) := 0.00;
    v_prescription_id INT;
    v_existing_invoice INT;
BEGIN
    -- A single appointment lock makes concurrent calls return the same invoice.
    PERFORM 1 FROM Appointments WHERE appointment_id = p_appointment_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Appointment ID % not found.', p_appointment_id USING ERRCODE = '23503';
    END IF;
    -- Verify if invoice already exists for this appointment
    SELECT COUNT(*) INTO v_existing_invoice 
    FROM Invoices 
    WHERE appointment_id = p_appointment_id;

    IF v_existing_invoice > 0 THEN
        RAISE NOTICE 'Invoice already exists for appointment ID %', p_appointment_id;
        RETURN;
    END IF;

    -- Retrieve appointment details and doctor consultation fee
    SELECT a.patient_id, a.doctor_id, a.status, d.consultation_fee
    INTO v_patient_id, v_doctor_id, v_appt_status, v_consultation_fee
    FROM Appointments a
    JOIN Doctors d ON a.doctor_id = d.doctor_id
    WHERE a.appointment_id = p_appointment_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Appointment ID % not found.', p_appointment_id;
    END IF;

    -- Ensure appointment is completed prior to billing
    IF v_appt_status != 'Completed' THEN
        RAISE EXCEPTION 'Cannot generate invoice for appointment % with status %', p_appointment_id, v_appt_status USING ERRCODE = '23514';
    END IF;

    -- Calculate total charges for dispensed prescription medications
    SELECT prescription_id INTO v_prescription_id
    FROM Prescriptions
    WHERE appointment_id = p_appointment_id;

    IF v_prescription_id IS NOT NULL THEN
        SELECT COALESCE(SUM(pi.quantity * pi.unit_price), 0.00)
        INTO v_medicine_total
        FROM Prescription_Items pi
        WHERE pi.prescription_id = v_prescription_id;
    END IF;

    -- Insert consolidated encounter invoice
    INSERT INTO Invoices (
        appointment_id, 
        patient_id, 
        consultation_fee, 
        medicine_total, 
        total_amount, 
        payment_status
    ) VALUES (
        p_appointment_id, 
        v_patient_id, 
        v_consultation_fee, 
        v_medicine_total, 
        (v_consultation_fee + v_medicine_total), 
        'Pending'
    );
END;
$$;

-- ----------------------------------------------------------------------------
-- 14. ADVANCED DBMS FEATURE 3: DEPARTMENT DAILY REVENUE ANALYTICS VIEW
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_daily_department_revenue AS
SELECT 
    d.dept_id,
    d.dept_name,
    DATE(i.issued_at) AS revenue_date,
    COUNT(i.invoice_id) AS total_invoices,
    SUM(i.consultation_fee) AS total_consultation_revenue,
    SUM(i.medicine_total) AS total_pharmacy_revenue,
    SUM(i.total_amount) AS gross_revenue,
    SUM(i.total_amount) AS settled_revenue
FROM Invoices i
JOIN Appointments a ON i.appointment_id = a.appointment_id
JOIN Doctors doc ON a.doctor_id = doc.doctor_id
JOIN Departments d ON doc.dept_id = d.dept_id
WHERE i.payment_status = 'Paid'
GROUP BY d.dept_id, d.dept_name, DATE(i.issued_at);

-- ============================================================================
-- 15. SCHEDULE, ENCOUNTER, AND FINANCIAL INTEGRITY
-- ============================================================================

CREATE OR REPLACE FUNCTION fn_validate_schedule()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM 1 FROM Doctors WHERE doctor_id = NEW.doctor_id FOR UPDATE;
    IF NEW.is_active AND EXISTS (
        SELECT 1 FROM Doctor_Schedules s
        WHERE s.doctor_id = NEW.doctor_id AND s.day_of_week = NEW.day_of_week
          AND s.is_active AND s.schedule_id != NEW.schedule_id
          AND NEW.start_time < s.end_time AND NEW.end_time > s.start_time
    ) THEN
        RAISE EXCEPTION 'Active doctor shifts must not overlap.' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'UPDATE' AND NEW IS DISTINCT FROM OLD AND EXISTS (
        SELECT 1 FROM Appointments WHERE doctor_id = OLD.doctor_id
          AND appointment_date >= CURRENT_DATE AND status IN ('Scheduled', 'In_Consultation')
    ) THEN
        RAISE EXCEPTION 'Resolve upcoming bookings before changing a schedule.' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validate_schedule BEFORE INSERT OR UPDATE ON Doctor_Schedules
FOR EACH ROW EXECUTE FUNCTION fn_validate_schedule();

CREATE OR REPLACE FUNCTION fn_validate_appointment()
RETURNS TRIGGER AS $$
DECLARE
    v_duration INT;
    v_doctor_status VARCHAR(20);
BEGIN
    -- All bookings for a provider serialize on the same row, including raw SQL.
    SELECT status INTO v_doctor_status FROM Doctors WHERE doctor_id = NEW.doctor_id FOR UPDATE;
    IF TG_OP = 'UPDATE' THEN
        IF (NEW.patient_id, NEW.doctor_id) IS DISTINCT FROM (OLD.patient_id, OLD.doctor_id) THEN
            RAISE EXCEPTION 'Appointment patient and doctor cannot be reassigned.' USING ERRCODE = '23514';
        END IF;
        IF NEW.status != OLD.status AND NOT (
            (OLD.status = 'Scheduled' AND NEW.status IN ('In_Consultation', 'Cancelled', 'No_Show')) OR
            (OLD.status = 'In_Consultation' AND NEW.status = 'Completed')
        ) THEN
            RAISE EXCEPTION 'Invalid appointment status transition.' USING ERRCODE = '23514';
        END IF;
        IF OLD.status != 'Scheduled' AND
           (NEW.appointment_date, NEW.appointment_time, NEW.duration_minutes, NEW.reason_for_visit)
           IS DISTINCT FROM (OLD.appointment_date, OLD.appointment_time, OLD.duration_minutes, OLD.reason_for_visit) THEN
            RAISE EXCEPTION 'Only scheduled appointments may be rescheduled or edited.' USING ERRCODE = '23514';
        END IF;
        IF (NEW.appointment_date, NEW.appointment_time) IS NOT DISTINCT FROM
           (OLD.appointment_date, OLD.appointment_time) THEN
            IF NEW.duration_minutes != OLD.duration_minutes THEN
                RAISE EXCEPTION 'Booked duration cannot be changed.' USING ERRCODE = '23514';
            END IF;
            IF NEW.status = 'Completed' AND NOT EXISTS (
                SELECT 1 FROM Medical_Records WHERE appointment_id = NEW.appointment_id
            ) THEN
                RAISE EXCEPTION 'A clinical record is required before completion.' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END IF;
    ELSIF NEW.status != 'Scheduled' THEN
        RAISE EXCEPTION 'New appointments must start as Scheduled.' USING ERRCODE = '23514';
    END IF;

    IF v_doctor_status IS DISTINCT FROM 'Active' THEN
        RAISE EXCEPTION 'Select an active doctor.' USING ERRCODE = '23514';
    END IF;
    SELECT slot_duration_minutes INTO v_duration FROM Doctor_Schedules
    WHERE doctor_id = NEW.doctor_id AND is_active
      AND day_of_week = trim(to_char(NEW.appointment_date, 'Day'))
      AND NEW.appointment_time >= start_time
      AND NEW.appointment_time + slot_duration_minutes * INTERVAL '1 minute' <= end_time
      AND mod(EXTRACT(EPOCH FROM (NEW.appointment_time - start_time))::NUMERIC,
              slot_duration_minutes * 60) = 0;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Appointment must align with an available doctor shift.' USING ERRCODE = '23514';
    END IF;
    NEW.duration_minutes := v_duration;
    IF EXISTS (
        SELECT 1 FROM Appointments a
        WHERE a.doctor_id = NEW.doctor_id AND a.appointment_date = NEW.appointment_date
          AND a.status != 'Cancelled' AND a.appointment_id != NEW.appointment_id
          AND NEW.appointment_time < a.appointment_time + a.duration_minutes * INTERVAL '1 minute'
          AND NEW.appointment_time + NEW.duration_minutes * INTERVAL '1 minute' > a.appointment_time
    ) THEN
        RAISE EXCEPTION 'The selected doctor slot is already booked.' USING ERRCODE = '23505';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validate_appointment BEFORE INSERT OR UPDATE ON Appointments
FOR EACH ROW EXECUTE FUNCTION fn_validate_appointment();

CREATE OR REPLACE FUNCTION fn_validate_clinical_link()
RETURNS TRIGGER AS $$
DECLARE
    v_appointment Appointments%ROWTYPE;
BEGIN
    IF NEW.appointment_id IS NULL THEN RETURN NEW; END IF;
    SELECT * INTO v_appointment FROM Appointments
    WHERE appointment_id = NEW.appointment_id FOR UPDATE;
    IF NOT FOUND OR (NEW.patient_id, NEW.doctor_id) IS DISTINCT FROM
       (v_appointment.patient_id, v_appointment.doctor_id) THEN
        RAISE EXCEPTION 'Clinical identities must match the appointment.' USING ERRCODE = '23514';
    END IF;
    IF v_appointment.status != 'In_Consultation' THEN
        RAISE EXCEPTION 'Clinical entries require an open consultation.' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_record_identity BEFORE INSERT ON Medical_Records
FOR EACH ROW EXECUTE FUNCTION fn_validate_clinical_link();
CREATE TRIGGER trg_prescription_identity BEFORE INSERT ON Prescriptions
FOR EACH ROW EXECUTE FUNCTION fn_validate_clinical_link();

CREATE OR REPLACE FUNCTION fn_reject_change()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Clinical and booking history must be retained; this change is not supported.' USING ERRCODE = '23514';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_keep_appointments BEFORE DELETE ON Appointments
FOR EACH ROW EXECUTE FUNCTION fn_reject_change();
CREATE TRIGGER trg_keep_records BEFORE UPDATE OR DELETE ON Medical_Records
FOR EACH ROW EXECUTE FUNCTION fn_reject_change();
CREATE TRIGGER trg_keep_prescriptions BEFORE UPDATE OR DELETE ON Prescriptions
FOR EACH ROW EXECUTE FUNCTION fn_reject_change();
CREATE TRIGGER trg_keep_dispenses BEFORE UPDATE OR DELETE ON Prescription_Items
FOR EACH ROW EXECUTE FUNCTION fn_reject_change();
CREATE TRIGGER trg_keep_schedules BEFORE DELETE ON Doctor_Schedules
FOR EACH ROW EXECUTE FUNCTION fn_reject_change();

CREATE OR REPLACE FUNCTION fn_protect_invoice()
RETURNS TRIGGER AS $$
DECLARE
    v_patient_id INT;
    v_status VARCHAR(20);
    v_expected_fee NUMERIC(10, 2);
    v_expected_medicine_total NUMERIC(10, 2);
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Invoices must be retained.' USING ERRCODE = '23514';
    END IF;
    SELECT patient_id, status INTO v_patient_id, v_status FROM Appointments
    WHERE appointment_id = NEW.appointment_id FOR UPDATE;
    IF v_status IS DISTINCT FROM 'Completed' OR NEW.patient_id IS DISTINCT FROM v_patient_id THEN
        RAISE EXCEPTION 'Invoice requires a completed appointment and matching patient.' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        IF (NEW.appointment_id, NEW.patient_id, NEW.consultation_fee, NEW.medicine_total, NEW.total_amount, NEW.issued_at)
           IS DISTINCT FROM
           (OLD.appointment_id, OLD.patient_id, OLD.consultation_fee, OLD.medicine_total, OLD.total_amount, OLD.issued_at) THEN
            RAISE EXCEPTION 'Issued invoice amounts and identity are immutable.' USING ERRCODE = '23514';
        END IF;
        IF OLD.payment_status != 'Pending' OR NEW.payment_status != 'Paid' THEN
            RAISE EXCEPTION 'Only Pending to Paid payment transitions are supported.' USING ERRCODE = '23514';
        END IF;
    ELSE
        IF NEW.payment_status != 'Pending' THEN
            RAISE EXCEPTION 'Invoices must be issued as Pending.' USING ERRCODE = '23514';
        END IF;
        SELECT d.consultation_fee INTO v_expected_fee FROM Doctors d
        JOIN Appointments a USING (doctor_id) WHERE a.appointment_id = NEW.appointment_id;
        SELECT COALESCE(SUM(pi.quantity * pi.unit_price), 0.00) INTO v_expected_medicine_total
        FROM Prescriptions p JOIN Prescription_Items pi USING (prescription_id)
        WHERE p.appointment_id = NEW.appointment_id;
        IF NEW.consultation_fee != v_expected_fee OR NEW.medicine_total != v_expected_medicine_total THEN
            RAISE EXCEPTION 'Invoice amounts must match the consultation and dispensed price snapshots.' USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_protect_invoice BEFORE INSERT OR UPDATE OR DELETE ON Invoices
FOR EACH ROW EXECUTE FUNCTION fn_protect_invoice();

-- End of schema.sql
-- ============================================================================
