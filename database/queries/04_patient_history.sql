-- Query 4: Longitudinal Patient EHR & Dispensed Medication Snapshots
-- $1 = patient ID; $2 = treating doctor ID, or NULL for administration.
-- Correlated JSON aggregation prevents prescription lines multiplying record rows.
SELECT r.record_id, r.appointment_id, r.recorded_at, a.appointment_date,
       p.first_name || ' ' || p.last_name AS patient_name,
       doc.first_name || ' ' || doc.last_name AS doctor_name, dept.dept_name,
       r.symptoms, r.diagnosis, r.clinical_notes,
       pr.instructions,
       COALESCE((
           SELECT json_agg(json_build_object(
               'medicine_name', m.name, 'dosage', pi.dosage,
               'duration_days', pi.duration_days, 'quantity', pi.quantity, 'unit_price', pi.unit_price
           ) ORDER BY pi.item_id)
           FROM Prescription_Items pi JOIN Medicines m ON pi.medicine_id = m.medicine_id
           WHERE pi.prescription_id = pr.prescription_id
       ), '[]'::json) AS prescribed_medications
FROM Medical_Records r
JOIN Patients p ON r.patient_id = p.patient_id
JOIN Doctors doc ON r.doctor_id = doc.doctor_id
JOIN Departments dept ON doc.dept_id = dept.dept_id
LEFT JOIN Appointments a ON r.appointment_id = a.appointment_id
LEFT JOIN Prescriptions pr ON a.appointment_id = pr.appointment_id
WHERE r.patient_id = $1 AND ($2::int IS NULL OR r.doctor_id = $2)
ORDER BY r.recorded_at DESC, r.record_id DESC;
