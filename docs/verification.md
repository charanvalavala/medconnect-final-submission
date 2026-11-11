# MedConnect: Final Verification Record

**Validation date: 11 November 2026 | PostgreSQL 16.11 | Windows native execution**

## 1. Requirements & Evidence Matrix

| Final requirement | Status | Evidence |
|---|---|---|
| Approximately 8-12 meaningful relations | Verified | Ten base tables in `schema.sql`; catalog assertions in `tests/test_schema_empirical.py` |
| At least 500 records | Verified | Fresh seed: 1,308 records; `tests/test_seed.py`; `scripts/verify_db.py` |
| Three integrated workflows | Verified | Browser registration/booking/cancellation/rebooking; doctor encounter/stock/invoice; reception payment/report |
| Five substantial SQL queries | Verified | All five files in `database/queries` execute on PostgreSQL, through tests and the API |
| Three additional DBMS features | Verified | Transactions/row locks, triggers, invoice procedure, revenue view, partial/supporting indexes |
| Full frontend/backend/configuration | Verified locally | React production build, running FastAPI/PostgreSQL, environment generator, dependency locks, native instructions |
| Final design PDF at most five pages | Verified | `output/pdf/MedConnect_Final_Submission.pdf`: exactly five pages, compiled in Overleaf and visually inspected |
| Names, IDs, responsibilities, setup, workflows | Present | README, checklist, report, and demo guide |
| Reproduction from schema and sample data | Verified natively | Fresh database bootstrap; restart retains data; explicit reset and seed recreate 1,308 rows |
| Separate final repository | Verified published | `https://github.com/charanvalavala/medconnect-final-submission`; original mid-sem history retained |

## 2. PostgreSQL & HTTP Tests

```text
TEST_DATABASE_URL=postgresql://medconnect:medconnect@127.0.0.1:55432/medconnect_phone_tests
.venv/Scripts/python -m pytest -q

51 passed, 1 warning, 53 subtests passed
```

The local validation instance uses a dedicated loopback PostgreSQL 16.11 server on port 55432. This is a real PostgreSQL process, not a SQLite translation. README defaults to the normal PostgreSQL port 5432 for fresh installations. Each test creates and removes an isolated random schema; test statements do not reset the demonstrated public schema.

| Test area | Checked behavior |
|---|---|
| Schema and domains | ten relations, repeatable rebuild, duplicate PK, missing FK, allowed values, nonnegative stock/fees, appropriate patient deletion |
| Schedule and booking | overlapping shifts, misaligned/out-of-shift slots, inactive doctor, retained cancellation/reuse, reschedule collision, blocked schedule changes with upcoming bookings |
| Concurrency | ten independent connections compete for one slot: one booking and nine conflicts; two prescriptions compete for five units: one four-unit dispense, one rejection, one unit remains; five concurrent invoice calls create one invoice |
| Clinical provenance | mismatched patient/doctor rejected; multiple legacy null links permitted; required medical record before completion |
| Stock and prices | automatic deduction, duplicate-line rollback, expired/insufficient stock, negative quantity rejection, multi-item transaction rollback, dispensed unit-price snapshots |
| Billing and reports | actual PL/pgSQL procedure, independent amount expectations, invoice preconditions/retry, immutable issued amounts, invalid direct invoice insert, Paid-only view, guarded stock projection, no history row multiplication, all five queries execute |
| HTTP workflows | login/expiry, patient CRUD/search, booking collision/cancellation/rebooking, full encounter/payment/report, duplicate completion, same/different-method payment retries, role/assignment boundaries, scoped history, malformed inputs and injection-shaped search |
| Sample data | 1,308 records, 300 appointments, 168 completed encounter artifacts, seeded visit/payment states, refusal to duplicate the seed |

The warning comes from the installed Starlette test client announcing a future HTTP client migration. It does not represent a failing assertion. Tests use fixture-derived expected stock, money, row counts, and authorization outcomes; the invoice procedure is executed rather than reimplemented as a test substitute.

## 3. Fresh Database Reproduction

A separate, newly created PostgreSQL database was used for the following sequence:

```text
python scripts/bootstrap.py
  Initialized MedConnect with 1308 synthetic records.
python scripts/bootstrap.py
  Existing clinic database retained.
python scripts/verify_db.py
  Total records: 1308
python scripts/init_db.py --reset
  Created ten MedConnect relations and their database routines.
python scripts/seed.py
  Total: 1308 records.
python scripts/verify_db.py
  Total records: 1308
```

Fresh relation counts:

| Departments | Doctors | Schedules | Patients | Appointments | Medical records | Prescriptions | Medicines | Items | Invoices |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 6 | 15 | 105 | 180 | 300 | 168 | 168 | 30 | 168 | 168 |

The catalog reports **14 foreign keys, 28 CHECK constraints, and 11 user triggers**. The five report result counts for the fresh seed were **6, 15, 3, 2, and 28**, respectively. Browser demonstration writes add records beyond these fresh-seed totals.

## 4. Browser & Frontend Verification

The live browser used the running PostgreSQL-backed API. Observed operations:

1. Admin sign-in; patient registration and name search.
2. Booking a new visit, cancelling it, and successfully rebooking its released slot while the cancelled row remains.
3. Doctor sign-in and assigned appointment view; start and complete an encounter for the rebooked patient.
4. Four units of the ₹5.00 catalog medicine with Doctor 1's ₹400.00 consultation produce a **₹420.00 invoice**.
5. Reception records UPI payment; invoice becomes Paid. Collected-today changes from **₹116,407.00 to ₹116,827.00** and outstanding balance falls from **₹31,568.00 to ₹31,148.00**.
6. Department revenue reflects the additional ₹420 collection. Mobile dashboard layout was checked at **390 × 844**, with navigation into the appointments view and no document-level horizontal overflow. The viewport override was then reset.

Representative captures:

- [Clinical encounter](screenshots/clinical-encounter.jpg)
- [Recording the payment](screenshots/billing-payment.jpg)
- [SQL reports](screenshots/reports.jpg)
- [Mobile overview](screenshots/mobile-dashboard.jpg)

The frontend uses labelled controls, native dialog focus handling, loading/empty/error states, cache refresh after writes, and reduced-motion CSS. The browser checks are selected workflow observations, not an exhaustive automated browser suite. API and database tests cover failed multi-item stock transactions and permission boundaries independently.

The clean frontend install and production build passed with `npm ci` followed by `npm run build`: 1,622 transformed modules, approximately 42.6 kB CSS and 249.4 kB JavaScript before gzip. The native preview was stopped during the clean install to release Windows executable file locks, then restarted for the final captures.

## 5. Design Report & Source Consistency

The final source is `docs/overleaf/main.tex`, compiled in the [separate final Overleaf project](https://www.overleaf.com/project/6af4478a23cb8e68c83a8fed). The final PDF has five A4 pages and identifies the final public repository. All pages were rendered for inspection; the final schema formatting and diagram labels were checked after adjustment.

Overleaf reports **0 errors and 0 warnings**. Two informational underfull-box entries remain in narrow table paragraphs; the rendered tables are readable, within the margins, and contain no overlapping text. The full relational SVG is generated from the DDL; the report's conceptual model and relational attribute catalog describe the final schema.

Normalization wording was corrected to distinguish nullable unique links and the deliberate stored invoice-total dependency. The earlier claim that PostgreSQL universally rejects time-dependent CHECK expressions was replaced with the actual constraint immutability assumption and the implemented validation boundary.

## 6. Verification Limits & Remaining Team Steps

- Native PostgreSQL and API execution were verified. Docker/Compose files are supplied, but a Docker engine was not available on the validation host, so container execution was not verified here.
- The local runtime is Python 3.14; the documented Python 3.12 route also passed in the published GitHub workflow. Frontend dependencies are locked with npm and the production build is checked locally.
- Hosted CI passed for the implementation revision; the publication record below links the observed run.
- This is selected correctness/concurrency coverage, not a production load, penetration, or exhaustive state-space assessment. Authentication recovery, request throttling, a separate database least-privilege role, amendments/refunds, and immutable audit-event storage are outside scope.
- The team must review its assigned responsibilities, rehearse individual explanations, submit the repository URL through the course channel, and demonstrate the same published version. Those actions are not represented by a passing local test run.

## 7. Publication Record

The separate public repository is [charanvalavala/medconnect-final-submission](https://github.com/charanvalavala/medconnect-final-submission). Implementation commit 62c2af5e40df6788975af0d7116f68e3ace1bfc3 passed [GitHub CI](https://github.com/charanvalavala/medconnect-final-submission/actions/runs/43011264085): PostgreSQL 16 / Python 3.12 database-and-API verification, fresh bootstrap/restart/report execution, and the Node 22 frontend clean install/build.

The original team repository was read again after publication: its main remains at mid-sem commit 3e10a8ea6de8b7073798a89d7d5e22abdeb404f1. The final copy retains that history without changing the original remote.

## 8. Patient Contact Validation Update

Patient registration and profile editing now require ten ASCII digits, with `+91` displayed separately. The emergency number is optional; provided values follow the same rule. Values remain strings and preserve leading zeroes. The form uses numeric input hints and native validation; the API and PostgreSQL enforce the format independently.

The complete suite passes **51 tests and 53 subtests**, including invalid lengths, letters, separators, country-code input, Unicode digit substitutes, creation/editing, surrounding-whitespace handling, optional emergency contacts, leading zeroes, and direct SQL validation. A UTF-8 test database ensures Unicode cases reach the database constraints rather than being blocked by the older Windows demo database encoding.

The additive migration was applied twice to the existing demonstration database: **181 patient records and 169 invoices were retained unchanged**. Tests also verify repeatable upgrades and atomic failure on invalid legacy contacts, without partial constraints or silent rewriting. Existing Compose installations receive the migration through bootstrap; native installations can run `scripts/migrate_db.py` without resetting their data.

The updated form was checked in Edge: both controls show a separate `+91` prefix, invalid letters and short numbers fail native validation, a ten-digit string with a leading zero remains valid, and an empty emergency contact remains valid. See [registration preview](screenshots/patient-phone-validation.jpg). The production frontend build also passes.
