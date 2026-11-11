-- Query 5: Peak Hour Demand & Patient No-Show Analysis (last 90 days)
-- Grouped CTE, date extraction, filtered counts, ratios, and ranked demand.
WITH HourlyBookingMetrics AS (
    SELECT EXTRACT(ISODOW FROM appointment_date)::int AS day_index,
           TRIM(TO_CHAR(appointment_date, 'Day')) AS day_of_week,
           EXTRACT(HOUR FROM appointment_time)::int AS booking_hour,
           COUNT(*) AS booked_visits,
           COUNT(*) FILTER (WHERE status = 'Completed') AS completed_visits,
           COUNT(*) FILTER (WHERE status = 'No_Show') AS no_show_visits,
           COUNT(*) FILTER (WHERE status = 'Cancelled') AS cancelled_visits
    FROM Appointments
    WHERE appointment_date BETWEEN CURRENT_DATE - 89 AND CURRENT_DATE
    GROUP BY 1, 2, 3
)
SELECT *, ROUND(no_show_visits * 100.0 / NULLIF(completed_visits + no_show_visits, 0), 2) AS no_show_rate_pct,
       RANK() OVER (ORDER BY booked_visits DESC) AS demand_rank
FROM HourlyBookingMetrics
ORDER BY day_index, booking_hour;
