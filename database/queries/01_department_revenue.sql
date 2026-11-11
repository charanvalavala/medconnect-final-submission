-- Query 1: Departmental Revenue & Contribution Ranking (current calendar month)
-- Multi-table joins, grouped CTE, filtered aggregates, and window functions.
WITH DeptRevenueSummary AS (
    SELECT d.dept_id, d.dept_name,
           COUNT(i.invoice_id) AS invoices_issued,
           COUNT(i.invoice_id) FILTER (WHERE i.payment_status = 'Paid') AS paid_invoices,
           COALESCE(SUM(i.total_amount), 0.00) AS billed_amount,
           COALESCE(SUM(i.total_amount) FILTER (WHERE i.payment_status = 'Paid'), 0.00) AS collected_amount,
           COALESCE(SUM(i.total_amount) FILTER (WHERE i.payment_status = 'Pending'), 0.00) AS outstanding_amount
    FROM Departments d
    LEFT JOIN Doctors doc ON d.dept_id = doc.dept_id
    LEFT JOIN Appointments a ON doc.doctor_id = a.doctor_id
    LEFT JOIN Invoices i ON a.appointment_id = i.appointment_id
        AND i.issued_at >= DATE_TRUNC('month', CURRENT_DATE)
        AND i.issued_at < DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month'
    GROUP BY d.dept_id, d.dept_name
)
SELECT *, ROUND(collected_amount * 100.0 / NULLIF(SUM(collected_amount) OVER (), 0), 2) AS revenue_share_pct,
       DENSE_RANK() OVER (ORDER BY collected_amount DESC) AS department_rank
FROM DeptRevenueSummary
ORDER BY department_rank, dept_name;
