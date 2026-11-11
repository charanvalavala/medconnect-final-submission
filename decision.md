# MedConnect: Architectural & Design Decision Log

## 1. Final Scope & Continuity

The final application retains the ten-table mid-sem design and the proposed PostgreSQL/FastAPI/React architecture. The submitted mid-sem PDF and original diagrams remain historical artifacts. This log records the decisions implemented for the final demonstration; the executable schema and tests provide the corresponding evidence.

## 2. Database & Application Decisions

### Decision 1: PostgreSQL 16 & Raw Parameterized SQL

PostgreSQL provides the partial index, transactional row locking, PL/pgSQL routines, and reporting constructs used by the three workflows. FastAPI uses `asyncpg` parameter binding rather than string-building user values. SQL remains directly inspectable during the viva. Static report filenames come from a fixed allowlist.

### Decision 2: Ten Relations & Staff-Only Access

The final scope has Admin/Receptionist and Doctor logins. Patients are registered records. Doctor password hashes reside in `Doctors`; the single administration identity is configured through environment variables. A separate user/supertype table is unnecessary for this demonstration. The hypothetical 11-table user hierarchy from the earlier specification is not implemented.

### Decision 3: Booking Locks, Overlap Checks & Partial Uniqueness

The original partial unique index prevents identical non-cancelled slot keys. On its own it does not prove arbitrary time ranges do not overlap. The final booking trigger also validates an active provider, matches a recurring weekday shift, checks alignment, captures the shift duration, and checks overlap against existing visits. All booking writes for one provider lock the same doctor row. Active shifts cannot overlap. Schedule changes are rejected while the provider has upcoming Scheduled/In_Consultation bookings.

The API rejects past booking/rescheduling times in clinic time. Availability is a read, not a reservation: another writer can win before a user confirms. The write is checked again and a conflict offers refreshed times. Cancelled rows are retained and excluded from slot occupancy. Completed and No_Show rows keep their historical slots. Only Scheduled appointments may be rescheduled; patient and doctor identities are not reassigned.

### Decision 4: One Transaction for Clinical Completion

The treating doctor starts a Scheduled consultation. The completion endpoint locks that appointment and writes its record, optional prescription/items, status, and invoice in one transaction. Inventory deduction happens inside that same transaction through the trigger. Insufficient stock on the second item therefore rolls back the first deduction and all clinical inserts. Medicine-ID ordering reduces opposing lock-order deadlocks. The database returns an error and rollback if a remaining conflict occurs.

### Decision 5: Historical Dispensing Prices & Issued Invoices

`Prescription_Items.unit_price` is captured from the locked medicine row at dispense time. Invoice medication totals use that stored value; changing the catalog later does not alter the charge. The consultation fee is captured at invoice creation. The procedure locks the appointment so concurrent calls converge on one invoice. An insertion trigger checks identity, Completed status, and expected amounts. Issued charge fields cannot be updated or deleted. Supported payment behavior is Pending to Paid, with time/method recorded; the API safely returns an existing same-method payment retry.

### Decision 6: Retained Clinical History

The schema retains the original FK actions, including record-to-appointment SET NULL and item-to-prescription CASCADE. Final retention triggers deliberately block deletes of appointments, schedules, clinical records, prescriptions, dispenses, and invoices. These cascades therefore are not a supported clinical-deletion mechanism. Unlinked patient entries can be deleted; linked entries are protected by foreign keys. Nullable appointment links remain useful for legacy record imports, but the frontend does not provide an import/editor for those records.

### Decision 7: Normalization Claims Follow Actual Dependencies

Departments, catalog data, providers, patients, schedules, and prescription lines are separated. Department facts are not repeated in doctor rows, and the prescription/medicine bridge removes repeating medication groups. Nullable unique columns are described conditionally rather than treated as unconditional candidate keys.

The stored invoice total is deliberate derived redundancy: `(consultation_fee, medicine_total) -> total_amount` has a non-superkey determinant. Clinical/invoice header identities also repeat appointment information for provenance and indexed retrieval, with matching identities enforced at insertion. A universal claim that every stored relation is in BCNF is therefore inappropriate. Snapshot prices are historical facts, not copies of a permanently determined current catalog price.

### Decision 8: Temporal Rules & PostgreSQL CHECK Semantics

The earlier explanation that PostgreSQL universally rejects stable/volatile functions in CHECK constraints was incorrect. PostgreSQL assumes a CHECK condition is immutable for unchanged row values; it does not continuously recheck it as time or another table changes. Static domains and invoice arithmetic remain CHECKs. Future birth dates and past booking times are validated by the API, while expiry-at-dispense and cross-row workflow rules use triggers. See PostgreSQL 16 [constraints](https://www.postgresql.org/docs/16/ddl-constraints.html), [locking](https://www.postgresql.org/docs/16/explicit-locking.html), and [partial indexes](https://www.postgresql.org/docs/16/indexes-partial.html).

### Decision 9: Reports Distinguish Billing from Collections

The view reports Paid invoices only. The monthly department report separately shows billed, collected, and pending totals. Attendance/no-show ratios use completed plus no-show visits as their denominator, excluding cancelled or unfinished visits. Missing dispensing velocity produces a null estimate rather than an arbitrary stock-days value. The patient-history query aggregates medication lines in a correlated subquery to avoid multiplying encounters.

### Decision 10: Reproducible Local Demonstration

Bootstrap creates schema and sample data together on an empty database and retains an existing database on restart. Reset is explicit and restricted by instructions to disposable demonstration data. The seed uses relative dates, stable fictional identities, all workflow states, and 1,308 rows. Runtime and test dependency versions are pinned. Tests use independent PostgreSQL schemas and real stored routines, replacing the original SQLite translation as the primary check.

### Decision 11: Frontend & Interaction Design

React 18, Vite, Tailwind, TanStack Query, and Lucide implement the proposed staff/doctor workspace. A navy/teal interface connects the registry, booking, consultation, pharmacy, billing, and report screens. Native dialog focus management, visible labels, conflict messages, empty/loading states, responsive layouts, and reduced-motion support cover the demonstration interactions. Data mutations invalidate query caches so subsequent screens read current backend state.

### Decision 12: Final Report & Team Responsibilities

The final design report is authored in LaTeX and compiled in a separate Overleaf project. It retains the blue headings and academic structure of the mid-sem report, with corrected participation, keys, normalization, and implementation details. The final report is capped at five pages; detailed reproducibility and viva material remain in repository Markdown. The five named members retain their original roles, with final module responsibilities listed in README and the checklist.

### Decision 13: Patient Contact Format

Registration and profile editing use ten-digit Indian national contact numbers. The form shows `+91` separately and requests a numeric keypad, while native pattern validation, the API, and database CHECK constraints reject other formats. The emergency contact is optional but follows the same rule when provided. Contact values remain strings so leading zeroes are preserved; the rule does not require a mobile-only first digit. Existing databases receive an additive, repeatable migration. Invalid legacy values cause the migration to fail atomically for correction, rather than being truncated or discarded.

## 3. Boundaries

No patient accounts, provider onboarding/password reset UI, clinical amendment workflow, refunds, payment gateway, split payments, batch-level pharmacy traceability, multi-clinic scheduling, or production deployment is included. Staff authentication is implemented for the local demonstration, without online abuse controls or credential recovery. List views return bounded results rather than general pagination. The database owner can bypass retention by changing schema/routines; this is not a tamper-proof audit system.
