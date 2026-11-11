-- Enforce national 10-digit patient contacts without changing existing values.
-- Repeated execution is safe after a fresh schema install or an earlier upgrade.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'Patients'::regclass AND conname = 'chk_patient_phone_digits'
    ) THEN
        ALTER TABLE Patients ADD CONSTRAINT chk_patient_phone_digits
            CHECK (phone ~ '^[0-9]{10}$');
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'Patients'::regclass AND conname = 'chk_patient_emergency_phone_digits'
    ) THEN
        ALTER TABLE Patients ADD CONSTRAINT chk_patient_emergency_phone_digits
            CHECK (emergency_contact_phone IS NULL OR emergency_contact_phone ~ '^[0-9]{10}$');
    END IF;
END;
$$;
