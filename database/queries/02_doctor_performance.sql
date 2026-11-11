-- Query 2: Provider Workload & Clinical Reliability (last 30 days, through today)
-- Outer joins, conditional aggregation, and guarded completion ratios.
SELECT doc.doctor_id, doc.first_name || ' ' || doc.last_name AS doctor_name, d.dept_name,
       COUNT(a.appointment_id) AS booked_visits,
       COUNT(a.appointment_id) FILTER (WHERE a.status = 'Completed') AS completed_visits,
       COUNT(a.appointment_id) FILTER (WHERE a.status = 'Cancelled') AS cancelled_visits,
       COUNT(a.appointment_id) FILTER (WHERE a.status = 'No_Show') AS no_show_visits,
       ROUND(COUNT(a.appointment_id) FILTER (WHERE a.status = 'Completed') * 100.0 /
             NULLIF(COUNT(a.appointment_id) FILTER (WHERE a.status IN ('Completed', 'No_Show')), 0), 2) AS attendance_pct,
       COALESCE(SUM(i.total_amount) FILTER (WHERE i.payment_status = 'Paid'), 0.00) AS collected_amount
FROM Doctors doc
JOIN Departments d ON doc.dept_id = d.dept_id
LEFT JOIN Appointments a ON doc.doctor_id = a.doctor_id
    AND a.appointment_date BETWEEN CURRENT_DATE - 29 AND CURRENT_DATE
LEFT JOIN Invoices i ON a.appointment_id = i.appointment_id
WHERE doc.status = 'Active'
GROUP BY doc.doctor_id, d.dept_name
ORDER BY completed_visits DESC, doctor_name;
