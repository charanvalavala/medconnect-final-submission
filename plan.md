# DBMS Project Plan: MedConnect

## 1. Submission Milestones

The mid-sem repository contains the original schema, diagrams, submitted PDF, and tests. The final milestone adds the integrated PostgreSQL-backed application, sample data, SQL reports, reproducibility configuration, verification, and a five-page design report.

- **Final repository submission:** 15 November 2026.
- **In-lab demonstration and individual viva:** 17-19 November 2026.
- **Working checklist:** [docs/final_checklist.md](docs/final_checklist.md).

## 2. Implementation Sequence

1. Review the mid-sem design and final guidelines; identify gaps and preserve the original history.
2. Finalize the ten-table schema, schedule/identity constraints, dispensing snapshots, invoice behavior, and stock transaction boundaries.
3. Add deterministic synthetic sample data and five executable reports.
4. Implement FastAPI authentication, registry, booking, clinical, inventory, payment, and report routes.
5. Connect the React staff/doctor workspace, including responsive layouts and validation states.
6. Verify real PostgreSQL routines, independent-connection races, rollback, API permissions, and production frontend compilation.
7. Compile and inspect the five-page Overleaf report; align README, decisions, design, and viva route with the final implementation.
8. Review with the team, publish the final version, and submit its GitHub link through the course channel.

## 3. Team Allocation

The five-person allocation in [README](README.md) continues the submitted mid-sem roles. Each member owns a defined final module and must also understand the complete ER model, all ten relations, the three transaction/report workflows, and the reproducibility steps.

## 4. Demonstration Acceptance

The final demonstration should start from the documented setup and show reception booking, a doctor completing an encounter with stock deduction, and reception recording payment followed by a revenue report. Show one rejected booking or stock operation and explain how the database preserves consistency. Use the same published revision and seed data for the class demonstration.
