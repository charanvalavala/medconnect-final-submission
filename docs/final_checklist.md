# MedConnect: Final Submission Checklist

**Group-11 | P2 Section | Submission: 15 November 2026 | Demo: 17-19 November 2026**

## 1. Requirements & Baseline Review

- [x] Clone the original repository and retain its mid-sem history.
- [x] Read the submitted design PDF and the project guidelines, including Sections 3-8.
- [x] Inspect the schema, diagrams, design specification, decision log, project plan, and existing tests.
- [x] Identify final requirements: 8-12 meaningful tables, 500+ records, 3+ workflows, 5+ substantial queries, 3+ additional DBMS features, complete source/configuration, reproducible setup, team details, and a design PDF of at most five pages.
- [x] Retain PostgreSQL 16, ten canonical relations, FastAPI, raw parameterized SQL, and React.
- [x] Confirm the five members and retain their mid-sem areas of responsibility.
- [x] Replace mid-sem roadmap claims with verified final behavior.

## 2. Database Implementation

- [x] Execute schema creation on a clean PostgreSQL database and repeat the reset successfully.
- [x] Preserve ten relations and document every added column/constraint.
- [x] Validate schedule availability, slot alignment, provider status, and booking collisions.
- [x] Preserve cancelled bookings and permit slot reuse.
- [x] Validate linked patient/doctor identities in clinical records, prescriptions, and invoices.
- [x] Make prescription creation and stock deduction atomic, including multi-item rollback.
- [x] Snapshot dispensed prices and protect finalized clinical/billing data.
- [x] Serialize invoice creation and require completed appointments.
- [x] Verify paid-only revenue reporting and invoice arithmetic.
- [x] Supply repeatable sample-data population with at least 500 records and all workflow states.
- [x] Provide five executable SQL reports with joins, aggregation, CTEs, subqueries, and window functions.
- [x] Document keys, nullability, referential actions, indexes, and normalization exceptions accurately.

## 3. Backend & Access Control

- [x] Configure database connections and environment variables with no committed secrets.
- [x] Implement staff login, password hashing, token expiry, and doctor/admin authorization.
- [x] Implement patient insertion, editing, searching, and deletion where no history exists.
- [x] Implement doctor, department, schedule, and medicine retrieval/administration.
- [x] Implement available slots, booking, rescheduling, cancellation, and no-show handling.
- [x] Implement doctor consultation, medical history, prescriptions, and atomic completion.
- [x] Implement invoice retrieval, payment, and analytics.
- [x] Return useful validation, conflict, missing-record, and authorization responses.
- [x] Verify that doctor access is limited to their own appointments and relevant patient records.

## 4. Frontend Integration

- [x] Build React/Vite/Tailwind application with consistent MedConnect styling.
- [x] Provide login, overview, patient registry, booking, consultation, pharmacy, billing, and reports.
- [x] Connect every displayed workflow to the real backend and PostgreSQL data.
- [x] Provide loading, empty, validation, conflict, and success states.
- [x] Verify keyboard labels, small-screen layout, and clean production build.
- [x] Complete three browser workflows: booking/cancellation; consultation/stock; payment/revenue.
- [x] Capture representative application screens for the demonstration guide.

## 5. Verification & Reproducibility

- [x] Replace SQLite simulation as the primary check with tests against PostgreSQL.
- [x] Check primary/foreign keys, domains, uniqueness, and appropriate deletion behavior.
- [x] Race independent database connections for a single appointment slot.
- [x] Race prescriptions against limited stock; prove no overselling.
- [x] Check failed multi-item prescriptions leave no partial clinical or inventory changes.
- [x] Check price changes, repeated completion/invoice/payment, unauthorized requests, and malformed input.
- [x] Execute all five reports and verify representative results against independent expectations.
- [x] Provide Docker Compose and native setup, dependency locks, environment example, and health checks.
- [x] Reproduce setup, seed, tests, and production build from the documented commands.
- [x] Add CI for PostgreSQL-backed tests and frontend build.
- [x] Record actual commands/results and remaining limits in the verification document.

## 6. Final Documentation & PDF

- [x] Update README with the actual stack, setup, credentials, workflows, team IDs, and responsibilities.
- [x] Update design and decision documents to match executable behavior.
- [x] Create corrected final conceptual and relational diagrams with legible keys/cardinalities.
- [x] Write a five-page final design report in LaTeX using Overleaf.
- [x] Include ER model, relational schema, keys, constraints, assumptions, normalization, and decisions.
- [x] Compile in Overleaf, export the PDF and source, and inspect all five rendered pages.
- [x] Prepare a short live-demo route and individual viva questions tied to the code.
- [x] Package the final source, database scripts, report, and reproducibility instructions.
- [x] Check for stale placeholders, incorrect links, generated caches, and unsupported claims.

## 7. Team Responsibilities

| Member | BITS ID | Continued responsibility | Final implementation responsibility |
|---|---|---|---|
| K S Rajeev Kasyap | 2023A3PS0368H | Database Architect | Final ER/relational diagrams, schema maintenance, keys, indexes, and schedule/booking design |
| Rithwik Sai Madadi | 2023A3PS0304H | Schema & Keys Lead | FastAPI database integration, patient registry, booking APIs, staff access, and reproducible setup |
| Peketi Sai Manoj | 2023A3PS0325H | Constraints & Normalization | Clinical integrity, pharmacy trigger, invoice procedure, concurrency checks, and normalization justification |
| Y Sameeksha | 2023A3PS0367H | App Design & Architecture | React staff/doctor interface, workflow integration, validation states, and application demonstration |
| Charan Teja Valavala | 2022A7PS0059H | Documentation & Coordination | SQL reports, sample-data/verification coordination, final report, README, and viva preparation |

The table assigns module responsibilities. Each member must run and understand the integrated system before the individual viva.

## 8. Submission & Demonstration

- [ ] Confirm the team has reviewed its responsibility table and can explain all ten relations.
- [ ] Publish the reviewed final version to the team repository and verify its remote contents.
- [ ] Submit the GitHub repository link through the course submission channel before 15 November.
- [ ] Use the same final version and sample data for the in-lab demonstration.

The remaining items require team review, repository publication, course submission, or the live demonstration; local verification alone does not complete them.
