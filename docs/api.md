# MedConnect: API Route Map

Base path: `/api`. Interactive request schemas are available at `http://localhost:8000/docs`. Except health and login, requests require `Authorization: Bearer <token>`. Monetary response values are JSON numbers; medication prices nested in JSON history retain exact snapshot values as returned by PostgreSQL.

## 1. Authentication & Reference Data

| Method | Route | Access | Purpose |
|---|---|---|---|
| GET | /health | Public | database readiness |
| POST | /auth/login | Public | email/password → token and staff identity |
| GET | /auth/me | Staff | current identity; active doctor rechecked |
| GET | /departments | Staff | specialties |
| GET | /doctors?dept_id=1 | Staff | providers without password hashes |
| GET | /schedules?doctor_id=1 | Staff | recurring shifts |
| POST | /schedules | Admin | create a non-overlapping shift |

Login token lifetime is four hours. Doctor IDs come from signed subjects, never from an untrusted role selector. Inactive doctor accounts fail subsequent requests.

## 2. Patient Registry & Booking

| Method | Route | Access | Purpose |
|---|---|---|---|
| GET | /patients?q=Rao&limit=100 | Staff | name/phone search; doctors see associated patients |
| POST | /patients | Admin | register patient |
| PUT | /patients/{id} | Admin | update demographics |
| DELETE | /patients/{id} | Admin | delete only if no linked history |
| GET | /slots?doctor_id=1&appointment_date=2026-11-16 | Staff | unoccupied future shift-aligned slots |
| GET | /appointments?appointment_date=2026-11-16&status=Scheduled&doctor_id=1 | Staff | latest matching visits; doctor scope forced to signed identity |
| POST | /appointments | Admin | patient_id, doctor_id, appointment_date/time, reason_for_visit |
| PATCH | /appointments/{id}/reschedule | Admin | future appointment_date/time for a Scheduled visit |
| PATCH | /appointments/{id}/status | By action | reception: Cancelled/No_Show; assigned doctor: In_Consultation |
| GET | /patients/{id}/history | Staff | clinical records with JSON medication list; doctor records scoped |

Dates use `YYYY-MM-DD`; slots use local `HH:MM` or `HH:MM:SS` in Asia/Kolkata. `/slots` supports `exclude_appointment_id` while rescheduling. An available time is advisory until booking commits. Patient lists are bounded by limit (1-250); appointment lists return at most 250 rows, with date/status filters.

## 3. Clinical Encounter, Pharmacy & Billing

| Method | Route | Access | Purpose |
|---|---|---|---|
| POST | /appointments/{id}/complete | Assigned doctor | atomic record, prescription, stock, completion, invoice |
| GET | /medicines?q=tablet | Staff | catalog, price, stock, reorder/expiry flags |
| POST | /medicines | Admin | add medicine with opening stock |
| POST | /medicines/{id}/restock | Admin | positive quantity received |
| PATCH | /medicines/{id}/price | Admin | nonnegative unit_price; previous dispenses unchanged |
| GET | /invoices?payment_status=Pending | Admin | latest 250 matching invoices |
| POST | /invoices/{id}/pay | Admin | record Cash/Card/UPI/Insurance/NetBanking payment |
| GET | /overview | Staff | role-scoped clinic metrics; financial totals only for Admin |
| GET | /reports | Admin | five report choices |
| GET | /reports/{report_id} | Admin | department-revenue, doctor-performance, pharmacy-reorder, peak-demand, patient-history |

`patient-history` report requires `?patient_id=1`. Patient/doctor filters use native bound parameters. Report filenames are allowlisted.

### Completion Request

```json
{
  "symptoms": "Demonstration symptoms",
  "diagnosis": "Demonstration assessment",
  "clinical_notes": "Synthetic demonstration only",
  "instructions": "Demonstration prescription instructions",
  "items": [
    { "medicine_id": 1, "dosage": "Demo dosage", "duration_days": 3, "quantity": 4 }
  ]
}
```

An empty items list is allowed. Duplicate medicine IDs, nonpositive quantities, malformed fields, and unsupported values produce 422. Failed stock/identity/lifecycle rules produce 409 and roll back the whole operation. Completed encounters reject further completion rather than dispensing again. Prescription item price is never supplied by the client.

## 4. Response & Error Semantics

- **200/201:** successful read/write; creation uses 201 for patient, appointment, medicine, schedule.
- **401:** missing, invalid, or expired token; inactive doctor; invalid login.
- **403:** role/assignment does not permit the operation.
- **404:** requested record/report does not exist.
- **409:** collision, protected history, lifecycle conflict, stock failure, or mismatched payment retry.
- **422:** invalid request data, missing required report parameter, future birth date, or past booking time.
- **500:** unexpected database failure; detailed error is logged on the server and not sent to the client.

Payment retry with the same method returns the previously recorded payment. The application does not transfer money or call a payment gateway. Other repeated creates are governed by unique/lifecycle constraints, rather than a general request-idempotency framework.
