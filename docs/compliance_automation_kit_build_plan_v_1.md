# Compliance Automation Kit — Build Plan v1.0 (Annotated)

This is an annotated copy of the build plan with current implementation status.

Legend: [Done] implemented • [Partial] some work exists • [Open] not implemented yet

## TL;DR
- Schema‑on‑read pipeline: [Done]
- Week 1 MVP (Open Data export + logs): [Done]
- Week 2 (Validators + CKAN + Scheduler): [Done] All components implemented and tested

## 0) Objectives and Non‑Goals
- Objectives: [Done] reflected in code structure (modular pipeline, Windows‑friendly, SQLite, CLI/UI)
- Non‑Goals: [Done] adhered to (no BI/deep ML; OCR optional)

## 1) Target Users and Use‑Cases
 - Open Data Auto‑Publisher (MVP): [Done] export + metadata + artifacts; publishing via CKAN is [Done]
- e‑Invoice Helper: [Open]
- ESG‑Lite Reporter: [Open]
- NIS2 Lite Logbook: [Open]

## 2) System Architecture
- Language: Python 3.11+ [Done]
- Web/API: FastAPI (UI via Jinja2/HTMX) [Done — minimal screens]
- Jobs/Scheduler: [Done] Custom cron‑based scheduler implemented (APScheduler not used)
- Storage: SQLite + FS [Done]
- Config: .env + pydantic‑settings [Done]
- Logging: structlog JSON logs [Done]

## 3) Repository Layout
- Core modules (intake/mapping/normalize/outputs/publish/audit):
  - intake: [Done] CSV/XLSX
  - mapping: [Done] DSL + fuzzy matcher; profile exists
  - normalize: [Done]
  - validate: [Done] robust rules + error CSV integrated
  - outputs: open_data [Done]; eInvoice [Partial]; esg_lite/nis2 [Open]
  - publish: ckan [Done] / ftp [Open]
  - audit: integrated into logging and artifacts [Partial]
- UI templates: dashboard/datasets/upload [Done]; dataset_detail/mapping/runs [Done minimal]
- CLI: click [Done]
- Tests: added pipeline/API/parser/validator basics [Done]

## 4) Data Model and Mapping DSL
- SQLite tables (datasets, mappings, runs, artifacts): [Done] + Alembic migration
- Mapping DSL (YAML): [Done] + budget_execution_v1 profile present
- Header inference (Cyrillic/Latin + Levenshtein): [Done]

## 5) Validators (per profile)
- Types/ranges/enums/unique: [Done] comprehensive implementation with numeric ranges, enums, unique constraints, date ranges, string patterns, email/URL/phone validation
- Row‑level errors as CSV: [Done] with severity levels (error/warning/info) and detailed error reasons
- Business rule validation: [Done] budget execution specific rules (execution vs planned amounts, calculation consistency)

## 6) Output Modules
- 6.1 Open Data CSV/JSON + metadata + ZIP: [Done] (ZIP optional via flag)
- CKAN upsert flow: [Done] complete client with package/resource upsert, retry logic, record ID tracking
- 6.2 e‑Invoice (UBL XML): [Partial] (minimal UBL builder; CSV→payload/UI pending)
- 6.3 ESG‑Lite: [Open]
- 6.4 NIS2 Lite Logbook: [Open]

## 7) Scheduler and Audit
- Scheduler per dataset: [Done] custom implementation with cron parsing, job management, background execution
- Audit trail (runs/artifacts, SHA‑256, structured logs): [Done]
- Retry/backoff: [Done] implemented in CKAN client with exponential backoff

## 8) Security and Privacy
- Redaction, ACLs, .env secrets: [Partial]
- At‑rest encryption guidance: [Open]

## 9) Windows‑First Dev/Deploy
- Dev setup: venv + `pip install -e .` [Done]
- Service via NSSM: [Open]
- Optional Docker: [Open]

## 10) Minimal Admin UI (HTMX/Jinja2)
- /datasets list/create/edit: [Done minimal] (form backed by /ui endpoint)
- /mappings/{id} mapping screen with drag‑drop: [Partial] minimal read-only; interactive save UI [Open]
- /runs/{dataset} history with artifacts links: [Done minimal]
- /scheduler status and job management: [Done] UI at /scheduler with job status, schedules, execution history
- /publish/test: [Open]

## 11) Test Strategy
- Fixtures (messy XLSX/CSV variants): [Partial]
- Golden files: [Open]
- Property tests: [Open]
- CKAN mock: [Open]
- CI (Windows + Linux): [Open]

## 12) One‑Month Build Plan (LLM‑Executable)

Week 1 — Core skeleton + Profile: Budget Execution
- Task 1.1: Initialize repo, settings, logging, SQLite models, Alembic. [Done]
- Task 1.2: Intake parsers (CSV/XLSX), encoding normalization, header inference. [Done]
- Task 1.3: Mapping DSL + UI skeleton for mapping save/load. [Partial] (DSL done; minimal UI; no full save workflow)
- Task 1.4: Normalization transforms; profile `budget_execution_v1`. [Done]
- Deliverable: CLI converts sample XLSX → canonical CSV/JSON + metadata; audit record created. [Done]

Week 2 — Validator + Open Data module + Scheduler
- Task 2.1: Validator rules (types, enums, unique/date range) + error CSV. [Done] (comprehensive rules with severity levels, business validation)
- Task 2.2: Open Data module: metadata JSON; ZIP pack. [Done]
- Task 2.3: CKAN client with upsert; retries; record IDs. [Done] (full client with retry logic, error handling, record tracking)
- Task 2.4: APScheduler wiring; per‑dataset cron; run history UI. [Done] (custom scheduler with cron support, UI at /scheduler)
- Deliverable: Dataset auto‑publishes to CKAN on schedule with logs. [Done]

Week 3 — e‑Invoice Helper (MVP)
- Task 3.1: e‑invoice profile + mapping fields. [Partial] (profile stub `einvoice_v1` added)
- Task 3.2: UBL XML generator; XSD validation. [Partial] (minimal UBL builder with optional XSD validation scaffold)
- Task 3.3: Minimal registry CSV + checksum; UI to upload invoice batch. [Open]
- Deliverable: CSV → valid UBL XML set; registry produced. [Open]

Week 4 — Hardening + NIS2 Lite Logbook
- Task 4.1: Error handling, retries, structured logs, telemetry counters. [Partial]
- Task 4.2: NIS2 checklist generator (PDF). [Open]
- Task 4.3: Documentation, install scripts, `.msi`/zip bundle; demo dataset pack. [Partial]
- Deliverable: v1 release with three modules, docs, and demo. [Open]

## Additional B2G Readiness Tasks (Post Week 4)

Week 5 — Authentication & Multi-User (2-3 days)
- Task 5.1: Simple login system with session management. [Open]
- Task 5.2: Role-based access (admin, finance user, compliance officer). [Open] 
- Task 5.3: User activity logging and audit trail integration. [Open]
- Deliverable: Multi-user access with proper authentication and role management.

Week 6 — Professional Installation Package (1 week)
- Task 6.1: Windows .msi installer with database initialization. [Open]
- Task 6.2: Windows service configuration and auto-startup. [Open]
- Task 6.3: Backup/restore utilities and configuration management. [Open]
- Task 6.4: Update mechanism for new versions. [Open]
- Deliverable: Professional installation package ready for municipal IT deployment.

Week 7 — Support Infrastructure (3-5 days)  
- Task 7.1: Health check endpoints and system monitoring. [Open]
- Task 7.2: Log export functionality and diagnostic tools. [Open]
- Task 7.3: Configuration management UI for system settings. [Open]
- Task 7.4: Installation and troubleshooting documentation. [Open]
- Deliverable: Complete support infrastructure for B2G deployment and maintenance.

## 13) LLM Work Orders (Prompts + Acceptance)
- WO‑1: SQLite models + Alembic + CRUD in CLI. [Done]
- WO‑2: Intake parsers + `load_frame`, `detect_headers`. [Done]
- WO‑3: Mapping UI (drag‑drop; save YAML). [Partial]
- WO‑4: Validator + Normalizer; error CSV; idempotent cleaning. [Done] (comprehensive validation with business rules, severity levels)
- WO‑5: Open Data + CKAN client; record IDs. [Done] (full CKAN integration with upsert, retries, record tracking)
- WO‑6: Scheduler + Audit (hashes/artifacts). [Done] (custom scheduler with cron support, complete audit trail)
- WO‑7: e‑Invoice UBL generator + checks. [Partial]
- WO‑8: NIS2 Logbook PDF + checksum. [Open]
- WO‑9: Packaging (PowerShell, service). [Open]
- WO‑10: Authentication system with roles and session management. [Open]
- WO‑11: Professional .msi installer with service configuration. [Open]
- WO‑12: Support infrastructure (health checks, logs, diagnostics). [Open]

## 14) Documentation Skeleton
- README Quickstart: [Done]
- Docs for Profiles/Mapping/CKAN/NIS2/ESG: [Partial] (stubs for Mapping, CKAN, e‑Invoice)

## 15) Risks/Mitigations
- Messy input → robust parser + error CSV: [Done]
- Support drag → logs + deterministic outputs: [Partial]
- Standards drift → version profiles: [Partial]

## 16–18) Demo/Commercial/Next Steps
- Demo scenario: [Partial] (Open Data fixture and outputs exist)
- Commercial frame: [Open]
- Immediate Next Work
  - e‑Invoice UI: upload page → calls `/api/einvoice/process`; show registry results
  - e‑Invoice CSV mapping: improve normalization (locale-aware numbers/dates), currency detection
  - CKAN: `/publish/test` endpoint + UI button for credential checks
  - Mapping UI: save/update workflow (read-only → basic edit)
  - NIS2 Lite: checklist PDF generator and minimal UI
  - Docs/Packaging: add ESG/NIS2 docs, installer/service guides

---

For open items, see POTENTIAL_ISSUES.md.
