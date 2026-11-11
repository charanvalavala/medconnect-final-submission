# MedConnect: Clinic Appointment Management System

![DBMS Course Project](https://img.shields.io/badge/Course-DBMS_Project-blue.svg)
![Database](https://img.shields.io/badge/Database-PostgreSQL_16-336791.svg)
![Backend](https://img.shields.io/badge/Backend-FastAPI-009688.svg)
![Frontend](https://img.shields.io/badge/Frontend-React_18-61DAFB.svg)

## 1. Project Overview & Clinical Domain

**MedConnect** connects reception, doctors, pharmacy, and billing for a multi-specialty outpatient clinic. The application uses ten PostgreSQL relations, raw parameterized SQL, and three integrated workflows: booking with collision prevention; clinical encounter with inventory deduction; and invoicing, payment, and reporting.

**Group-11 | P2 Section | Final submission: 15 November 2026**

**Final repository:** https://github.com/charanvalavala/medconnect-final-submission

This separate final-submission copy continues the team's [mid-sem repository](https://github.com/Rajeev-Kasyap/dbms-clinic-project), preserving its original Git history.

| Member | BITS ID | Continued role & final module responsibilities |
|---|---|---|
| K S Rajeev Kasyap | 2023A3PS0368H | Database Architect: ER/relational diagrams, schema, keys, indexes, schedule and booking design |
| Rithwik Sai Madadi | 2023A3PS0304H | Schema & Keys Lead: backend/database integration, patient and booking APIs, staff access, setup |
| Peketi Sai Manoj | 2023A3PS0325H | Constraints & Normalization: clinical integrity, pharmacy trigger, invoice procedure, concurrency, normalization |
| Y Sameeksha | 2023A3PS0367H | App Design & Architecture: React staff/doctor interface, validation, responsive layout, workflow demonstration |
| Charan Teja Valavala | 2022A7PS0059H | Documentation & Coordination: SQL reports, sample-data/verification coordination, final report, README, viva preparation |

These module responsibilities continue the submitted mid-sem roles. Each member should review and run the integrated system before the individual viva.

## 2. System Architecture & Technology Stack

```text
React 18 + Vite + Tailwind CSS + TanStack Query + Lucide
                  | REST / JSON, bearer token
FastAPI + Pydantic + asyncpg connection pool
                  | raw bound SQL, explicit transactions
PostgreSQL 16: 10 tables, constraints, indexes, triggers,
              invoice procedure, paid-only revenue view
```

The clinic uses **Asia/Kolkata time** and **INR**. Admin/Receptionist and Doctor are the application roles; patients do not have login accounts. All bundled patient and clinical entries are synthetic demonstration data.

## 3. Quick Start: Docker Compose

Prerequisites: Python 3.11+ (3.12 recommended), Docker Engine/Desktop with Compose, and Git. Node is only needed for the native frontend route. Run commands from the repository root.

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements.txt -c backend/requirements-lock.txt
.venv/Scripts/python scripts/setup_env.py
docker compose up --build -d
```

On macOS/Linux, replace `.venv/Scripts/python` with `.venv/bin/python`.

- Application: **http://localhost:8080**
- API health: **http://localhost:8000/api/health**
- Interactive API documentation: **http://localhost:8000/docs**

The setup service creates the schema and seeds **1,308 records** on a fresh database. A restart retains existing records. Configuration is generated in the ignored `.env`; the example file documents the supported settings. The Compose database credentials are for the local demonstration, with published ports bound to localhost.

```powershell
docker compose logs setup backend
docker compose stop
docker compose start
```

For an intentional reset of the **disposable demonstration database**, stop the application services, recreate the schema, and seed again:

```powershell
docker compose stop frontend backend
docker compose run --rm setup python scripts/init_db.py --reset
docker compose run --rm setup python scripts/seed.py
docker compose up -d backend frontend
```

`--reset` deletes the configured MedConnect tables and their data. Do not use it for a database whose contents should be retained. `schema.sql` is a complete rebuild script, not an incremental migration.

## 4. Native Setup & Run Instructions

Install PostgreSQL 16, Python 3.11+, and Node 22 LTS. Create a database and login using a PostgreSQL administration account:

```sql
CREATE USER medconnect WITH PASSWORD 'medconnect';
CREATE DATABASE medconnect OWNER medconnect;
```

Then run:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements-dev.txt -c backend/requirements-lock.txt
.venv/Scripts/python scripts/setup_env.py
# Adjust DATABASE_URL in .env if the database uses another host, port, or login.
.venv/Scripts/python scripts/bootstrap.py
.venv/Scripts/python scripts/verify_db.py
.venv/Scripts/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open **http://localhost:5173**. Vite proxies `/api` to the local backend. For a release build, run `npm run build`; Compose serves that build through Nginx. `vite preview` alone does not provide the backend proxy.

### Demonstration Accounts

| Role | Email | Password |
|---|---|---|
| Admin/Receptionist | `admin@medconnect.local` | `Clinic@2026` |
| Doctor 1: Ananya Rao | `doctor1@medconnect.local` | `Doctor@2026` |
| Doctor 2: Arjun Reddy | `doctor2@medconnect.local` | `Doctor@2026` |

All 15 seeded doctors use `doctor1` through `doctor15` at `medconnect.local`. The administration hash is generated by `setup_env.py`; doctor hashes are inserted by the seed script. The token signing secret is randomly generated. Tokens expire after four hours, and inactive doctors are rejected on each authenticated request. Demo passwords should be replaced if the project is adapted for wider use.

## 5. Core Application Workflows & DBMS Features

### Workflow 1: Appointment Booking & Concurrency

Reception registers/selects a patient, chooses an active doctor, and retrieves available shift-aligned times. PostgreSQL locks the doctor row, validates the weekday/slot, snapshots duration, checks overlap, and enforces the partial unique index `uq_doctor_slot_active`. A competing booking returns HTTP 409. Scheduled visits can be rescheduled or cancelled. Cancellation retains the row and frees its slot; No_Show and Completed continue to occupy their historical slots.

### Workflow 2: Clinical Encounter & Pharmacy

The assigned doctor starts the consultation, records symptoms/diagnosis, and optionally adds distinct medicine lines. The `trg_deduct_medicine_stock` trigger locks inventory, rejects expired or insufficient stock, snapshots the unit price, and deducts quantity. Completion saves records, prescription, stock changes, appointment status, and invoice in one transaction. A failure leaves the consultation open with no partial clinical or inventory changes.

### Workflow 3: Billing, Payment & Analytics

`sp_generate_invoice` requires a completed visit and sums dispensed price snapshots plus the consultation fee at invoice issue time. Concurrent/repeated calls issue one invoice. Reception records a Pending-to-Paid transition. Repeating the same payment method returns the existing payment; a different method conflicts. The revenue view includes paid invoices only. Reports distinguish billed, paid, and outstanding amounts.

### Additional Operations

Patient creation, editing, name/phone search, and deletion of unlinked entries; medicine creation, stock receipt, and catalog repricing; patient clinical history; schedule creation through the documented API; five reports with CSV export. Doctor access is limited to assigned appointments and that doctor's clinical records. The UI bounds patient, appointment, and invoice lists to 250 results; patient search and date/status filters narrow the selection.

## 6. Database Schema Overview

| # | Relation | Main keys / purpose |
|---|---|---|
| 1 | `Departments` | `dept_id`; unique department name |
| 2 | `Doctors` | `doctor_id`; department FK; email/phone unique within doctors |
| 3 | `Doctor_Schedules` | `schedule_id`; doctor FK; weekly shifts and slot length |
| 4 | `Patients` | `patient_id`; phone and non-null email unique within patients |
| 5 | `Appointments` | `appointment_id`; patient/doctor FKs; duration and lifecycle |
| 6 | `Medical_Records` | `record_id`; nullable unique appointment; patient/doctor provenance |
| 7 | `Prescriptions` | `prescription_id`; unique appointment; patient/doctor provenance |
| 8 | `Medicines` | `medicine_id`; unique name; catalog price, expiry, and stock |
| 9 | `Prescription_Items` | `item_id`; unique prescription/medicine pair; dispensed price snapshot |
| 10 | `Invoices` | `invoice_id`; unique appointment; frozen charges and payment state |

See [database design](docs/database_design.md), [decision log](decision.md), and the [final design report](output/pdf/MedConnect_Final_Submission.pdf). The final report is authored and compiled in [Overleaf](https://www.overleaf.com/project/6af4478a23cb8e68c83a8fed); its editable source is in [docs/overleaf](docs/overleaf/main.tex). The earlier PDF and diagrams remain mid-sem artifacts; use the final design for the demonstration.

### Five Non-Trivial SQL Queries

| Report | SQL concepts | Executable file |
|---|---|---|
| Department revenue | joins, grouped CTE, filtered aggregation, DENSE_RANK, SUM OVER | [01](database/queries/01_department_revenue.sql) |
| Doctor performance | outer joins, conditional counts, grouping, guarded ratios | [02](database/queries/02_doctor_performance.sql) |
| Pharmacy reorder | two CTEs, joins, CASE, stock velocity | [03](database/queries/03_pharmacy_reorder.sql) |
| Patient clinical history | correlated subquery, JSON aggregation, scoped parameters | [04](database/queries/04_patient_history.sql) |
| Peak demand and no-shows | grouped CTE, date extraction, filtered counts, RANK | [05](database/queries/05_peak_demand.sql) |

## 7. Verification & Viva Preparation

Tests run against **PostgreSQL**, using fresh, randomly named schemas that are removed after each test. Set `TEST_DATABASE_URL` explicitly; no SQLite fallback is used. The database login needs permission to create schemas in the test database.

```powershell
$env:TEST_DATABASE_URL='postgresql://medconnect:medconnect@localhost:5432/medconnect'
.venv/Scripts/python -m pytest -q
.venv/Scripts/python scripts/verify_db.py
cd frontend
npm ci
npm run build
```

On macOS/Linux, use `export TEST_DATABASE_URL=...` and `.venv/bin/python`. [CI](.github/workflows/ci.yml) runs PostgreSQL 16 tests, fresh seeding/restart checks, report execution, and the frontend build. A workflow file is included; hosted results depend on publishing this version to GitHub.

- [Detailed checklist](docs/final_checklist.md)
- [Verification results and limits](docs/verification.md)
- [Live demonstration and viva guide](docs/demo_guide.md)
- [API route map](docs/api.md)
- [Final Overleaf source archive](output/pdf/MedConnect_Final_Overleaf.zip)

## 8. Project Layout & Scope

```text
schema.sql                 Complete PostgreSQL rebuild script
database/queries/          Five executable reports
backend/app/               FastAPI routes, authentication, validation, configuration
frontend/src/              React workspace and styling
scripts/                   Environment generation, bootstrap, reset, seeding, verification
tests/                     PostgreSQL integrity, concurrency, and HTTP tests
docs/                      Design, API, checklist, verification, and demo guide
docs/overleaf/             Editable final LaTeX report
output/pdf/                Final report and Overleaf source archive
compose.yaml               Local database, setup, API, and frontend services
```

This is a local course demonstration. It does not implement patient self-service, amendments/refunds, partial payments, batch/lot-level inventory, audit-event storage, password recovery, production monitoring, or multi-clinic scheduling. Application permissions do not prevent the database owner from changing routines or disabling triggers. These boundaries are described in the design and viva guide.
