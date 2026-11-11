# MedConnect: Live Demonstration & Individual Viva Guide

## 1. Before the Lab

1. Use the final reviewed repository revision, the final five-page PDF, and the matching Overleaf source.
2. Start the application using the README's native or Compose route. Confirm `/api/health` returns `ok` and run `scripts/verify_db.py`.
3. Sign in as `admin@medconnect.local` / `Clinic@2026`. Keep the doctor account `doctor1@medconnect.local` / `Doctor@2026` ready.
4. Use synthetic demonstration records. Do not reset while the application is being demonstrated.
5. Open `schema.sql`, the five query files, `backend/app/main.py`, and the test results so each database concept can be located directly.

## 2. Workflow 1: Register, Book, Cancel & Rebook

**Reception account; approximately 3 minutes.**

1. Open Patient registry and register a new fictional patient with a unique phone/email. Edit one profile field, then find the patient with the name/phone search.
2. Open Appointments → New appointment. Select that patient, **Dr. Ananya Rao**, and tomorrow's date. Choose an available time (for example 09:00), give a reason, and confirm.
3. Show the confirmed booking in Tomorrow. Explain that the availability list is advisory; the INSERT is rechecked under a doctor row lock.
4. Cancel the booking. Show the retained Cancelled row, then book the same time again. Both rows remain, with only the Scheduled row occupying the slot.
5. If time permits, reschedule the new visit to another available time. An occupied time cannot be selected from the refreshed list; direct competing writes are rejected by the database.

**Locate in the implementation:** `fn_validate_schedule`, `fn_validate_appointment`, and `uq_doctor_slot_active` in `schema.sql`; `/api/slots`, booking, reschedule, and status routes in `backend/app/main.py`.

**Explain:** partial index predicate; why a normal UNIQUE key would block cancellation reuse; why exact-slot uniqueness alone does not cover arbitrary overlaps; READ COMMITTED plus row locks; HTTP 409 conflict recovery.

## 3. Workflow 2: Doctor Encounter, Stock Failure & Completion

**Doctor account; approximately 4 minutes.**

1. Sign out and sign in as Doctor 1. Open Consultations → Tomorrow. The patient booked with Ananya Rao is visible; another doctor's appointments are not returned by the API.
2. Start visit → Open encounter. Enter fictional symptoms/assessment and clinical notes. Add two distinct medicines.
3. For a failure demonstration, make the second line exceed available stock, within the request limit of 10,000 units. Submit. The server returns a stock conflict and the form retains the input. No medical record, prescription, invoice, or stock change is committed.
4. Correct the quantities and complete. For an easy calculation, select **Paracetamol 500mg**, four units, at the seed price of **₹5.00**. With Doctor 1's **₹400.00** consultation fee, a single-line visit should issue **₹420.00**.
5. Show Completed status, the clinical history, and the medicine's four-unit stock reduction. Explain that a completed record cannot be reopened/edited or dispensed again.

The quantity/price example assumes the catalog has not been repriced during the demo. Read the actual displayed price and calculate the expected amount before submitting.

**Locate:** the completion transaction in `backend/app/main.py`; stock trigger/function, clinical identity triggers, retention triggers, and `sp_generate_invoice` in `schema.sql`. The tests include both database-level and HTTP-level multi-item rollback checks.

**Explain:** one transaction spans record/header/lines/stock/status/invoice; BEFORE INSERT trigger effects roll back with the statement/transaction; stock rows serialize competing dispensers; sorting medicine IDs reduces deadlocks; captured prices protect past charges.

## 4. Workflow 3: Payment, Revenue & Five SQL Reports

**Reception account; approximately 3 minutes.**

1. Sign in as Admin and open Billing → Pending. Find the new invoice and verify consultation, pharmacy, and total amounts.
2. Record the payment using UPI. This records a payment received at reception; it is not an online transfer.
3. Show the Paid row and the change in Overview collections/outstanding balance. Open Reports & insights → Department revenue and explain billed, collected, and outstanding columns.
4. Show Doctor performance, Pharmacy reorder, Patient history, and Peak demand. Use the new patient's ID for history. Export one report as CSV.
5. Open the corresponding files in `database/queries` and point out the joins, CTEs, grouping, filtered aggregates, subquery/JSON aggregation, and window functions.

**Locate:** payment route; `v_daily_department_revenue`; `01_department_revenue.sql` through `05_peak_demand.sql`.

**Explain:** Pending bills do not enter the paid-only view; monthly billed/collected columns are different; the view groups by issue date while collected-today uses payment date; safe same-method payment retries do not change paid time or totals.

## 5. Short SQL Inspection Route

Run with the database account from the README, using the selected IDs from the actual demonstration:

```sql
SELECT status, COUNT(*) FROM Appointments GROUP BY status ORDER BY status;
SELECT name, unit_price, stock_quantity, reorder_level FROM Medicines ORDER BY medicine_id;
SELECT appointment_id, payment_status, consultation_fee, medicine_total, total_amount
FROM Invoices ORDER BY invoice_id DESC LIMIT 5;
SELECT * FROM v_daily_department_revenue ORDER BY revenue_date DESC, dept_name;
SELECT indexdef FROM pg_indexes
WHERE tablename = 'appointments' AND indexname = 'uq_doctor_slot_active';
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM Appointments WHERE doctor_id = 1 AND appointment_date = CURRENT_DATE;
```

A sequential scan on a small seed table is not itself an index defect. Explain planner cost and the query/index columns rather than promising an index scan for every request.

## 6. Ten Individual Viva Questions

| Question | Points a complete answer should cover |
|---|---|
| Why ten relations? | Entity separation, prescription/medicine M:N bridge, one-to-one encounter artifacts; no unnecessary user hierarchy. |
| Which entities are weak? | Surrogate-key dependent entities are not automatically weak by identifying-key semantics; distinguish existence dependency from partial keys. |
| Is every table in BCNF? | Explain key-based dependencies and the deliberate invoice-total FD; nullable UNIQUE is conditional. Avoid the earlier universal claim. |
| Why partial uniqueness and a lock? | Cancelled-slot reuse; exact-key collisions; schedule alignment and range overlap; serialized provider writes. |
| What if two prescriptions consume the last five units? | Medicine row lock, one winner, insufficient stock for the second, no negative stock; refer to the independent-connection test. |
| What if the second medicine fails? | Entire encounter transaction rolls back: first deduction, record, header/lines, status, invoice. |
| What happens when prices change? | Existing item unit price and invoice values stay fixed; new dispenses use new catalog price; consultation fee captured at issue. |
| What can be deleted or corrected? | Unlinked patient can be deleted; history retained; no clinical amendment/refund workflow implemented. |
| How are reports protected and correct? | Admin authorization, bound query parameters, allowlisted report names, grouping boundaries, no join multiplication, independent numeric expectations. |
| What is not proven by passing tests? | Not exhaustive state coverage, production security/load, irreversible audit tamper prevention, or third-party deployment verification. |

## 7. Team Review & Handoff

Each member should explain their assigned module and trace all three workflows across frontend, backend, and database. Review the responsibility table together, confirm the same revision is published, and submit the GitHub repository link through the course channel. The checklist distinguishes local implementation from these final team/publication steps.
