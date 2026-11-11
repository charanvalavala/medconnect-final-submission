-- Query 3: Pharmacy Stock Depletion & Reorder Priorities
-- Two CTEs, multi-table aggregation, outer join, and conditional stock projection.
WITH RecentDispenses AS (
    SELECT pi.medicine_id, SUM(pi.quantity) AS units_dispensed_30_days
    FROM Prescription_Items pi
    JOIN Prescriptions p ON pi.prescription_id = p.prescription_id
    WHERE p.issued_at >= CURRENT_DATE - INTERVAL '29 days'
    GROUP BY pi.medicine_id
), DrugDispenseVelocity AS (
    SELECT m.*, COALESCE(rd.units_dispensed_30_days, 0) AS units_dispensed_30_days,
           COALESCE(rd.units_dispensed_30_days, 0) / 30.0 AS daily_burn_rate
    FROM Medicines m LEFT JOIN RecentDispenses rd ON m.medicine_id = rd.medicine_id
)
SELECT medicine_id, name AS medicine_name, category, stock_quantity, reorder_level,
       units_dispensed_30_days, ROUND(daily_burn_rate, 2) AS daily_burn_rate,
       ROUND(stock_quantity / NULLIF(daily_burn_rate, 0), 1) AS estimated_days_remaining,
       CASE WHEN expiry_date < CURRENT_DATE THEN 'EXPIRED'
            WHEN stock_quantity <= reorder_level THEN 'CRITICAL_REORDER'
            ELSE 'WARNING_LOW' END AS stock_health
FROM DrugDispenseVelocity
WHERE stock_quantity <= reorder_level * 1.5 OR expiry_date < CURRENT_DATE
ORDER BY estimated_days_remaining NULLS LAST, stock_quantity, medicine_id;
