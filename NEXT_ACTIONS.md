NEXT ACTIONS — LLM Execution Guide (Engine-First)

Purpose
- Provide a single, LLM-friendly checklist to continue work without prior context.
- Each task includes acceptance criteria, file pointers, and verification steps.

Bootstrap (once per session)
- Environment
  - Python 3.11+ (Windows-friendly)
  - `pip install -e .` (from repo root)
  - Optional dev tools: `pip install -e ".[dev]"` (pytest, black, etc.)
  - Initialize DB: `alembic upgrade head`
- Run
  - Start server (dev): `python -m uvicorn src.app:app --host 127.0.0.1 --port 8000 --reload`
  - Health: GET `http://127.0.0.1:8000/health` → status ok, db ok, scheduler running
  - API docs (DEBUG=true): `http://127.0.0.1:8000/api/docs`
- Quick Sanity
  - e‑Invoice CLI: `compliance-kit einvoice generate --input tests/data_fixtures/budget_sample_en.csv --org-id test_org` (should output a registry and XMLs; file is a placeholder for flow testing)
  - CKAN connectivity (if env set): GET `http://127.0.0.1:8000/publish/test`

Conventions
- Keep changes minimal and targeted; follow existing module structure.
- Update or add unit tests near changed logic.
- For UI, create simple, functional screens; avoid styling flourishes.
- Prefer reusing existing helpers (normalize, logging) over duplicating logic.

Task 1 — e‑Invoice normalization + totals validation (engine)
- Goal: Robust CSV→UBL for locale and totals consistency.
- Files
  - Implement in: `src/core/einvoice/batch.py`
  - Optional reuse: `src/core/normalize/transforms.py` for date/decimal cleaning
  - Tests: `tests/test_einvoice_batch.py` (add more cases)
- Requirements
  - Parse decimals with EU formats: thousand separators (space/comma), decimal separators (comma/dot).
  - Parse dates in common formats: `YYYY-MM-DD`, `DD.MM.YYYY`, `DD/MM/YYYY`.
  - Currency detection: if a `currency` column is present and consistent per invoice group, set invoice currency from that; else default `EUR`.
  - Totals validation: recompute line net and VAT; if `payable_amount != sum(net)+sum(vat)` within 1-cent tolerance, mark registry status `warning` with `error='totals_mismatch'` and computed vs provided amounts.
  - Retain current success flow; do not fail invoice generation on warnings.
- Acceptance
  - Given a CSV with decimal commas and `DD.MM.YYYY` dates, XML generates with correct numeric values and ISO dates.
  - If a currency column is provided (per invoice), the output XML uses that currency.
  - Registry contains `status=warning` for invoices with mismatched totals and includes reason.
  - Unit tests cover: EU decimals, date formats, currency column, totals mismatch warning.
- Verification
  - Run: `pytest -q tests/test_einvoice_batch.py`

Task 2 — e‑Invoice minimal UI upload
- Goal: Functional UI to upload a CSV and list registry results.
- Files
  - New template: `src/ui/templates/einvoice.html`
  - App route (UI): add `@app.get("/einvoice")` in `src/app.py` to render template.
  - Use existing API: `POST /api/einvoice/process` (already implemented).
- Requirements
  - Form with file input and `org_id` text.
  - On submit (multipart), call `/api/einvoice/process` via HTMX/JS; display registry table and links to generated XML files.
  - Add a nav link (e.g., in `base.html` navbar) to `/einvoice`.
- Acceptance
  - Visiting `/einvoice` renders the form.
  - Uploading a sample CSV shows a registry (invoice_id, amount, checksum, status, error) and file links.
- Verification
  - Browser: `http://127.0.0.1:8000/einvoice`

Task 3 — Scheduler “Run Now” endpoint
- Goal: Trigger dataset pipeline ad hoc via API.
- Files
  - New router: `src/api/scheduler.py` with `POST /api/scheduler/run/{dataset_id}`
  - Use `process_file_pipeline` with the latest uploaded file (same logic as scheduled job helper)
  - Job helper reference: `src/core/scheduler/jobs.py` (`process_dataset_job`, `find_latest_input_file`)
- Requirements
  - Accept dataset id; resolve latest input from `uploads/<org>/<dataset_id>`.
  - Execute pipeline once (no schedule change) and return run id + basic stats.
  - Propagate errors with clear messages (404 if dataset or input missing).
- Acceptance
  - API returns `status=completed` and `run_id` for valid dataset.
  - Errors handled for missing input directory/files.
- Verification
  - `curl -X POST http://127.0.0.1:8000/api/scheduler/run/<dataset_id>`
  - Check `/runs/{dataset_id}` UI page for run record.

Task 4 — CKAN dry-run mode (no network changes)
- Goal: Validate CKAN metadata and credentials without modifying CKAN.
- Files
  - CLI: add `compliance-kit ckan dry-run --dataset-id ...` in `src/cli/ck.py`
  - API: optional `POST /api/publish/dry-run` (new router or extend publish API)
  - Publisher: in `src/core/publish/ckan.py`, add a method to prepare metadata and skip API mutations.
- Requirements
  - Validate presence of `CKAN_URL`, `CKAN_API_KEY`, `owner_org`.
  - Build package/resource payloads; output a report (JSON) of what would happen (create/update and which resources).
  - If `MOCK_CKAN=true` (settings), always report success without network.
- Acceptance
  - CLI/API returns a deterministic report; no network mutation occurs.
  - Errors clearly reported for missing/invalid settings.
- Verification
  - CLI: `compliance-kit ckan dry-run --dataset-id <id>`

Task 5 — LLM bootstrap & acceptance checks (docs)
- Goal: Make it trivial for a new LLM to continue tomorrow’s work.
- Files
  - This file (NEXT_ACTIONS.md) — update as tasks complete.
  - Link from README and build plan (optional if not asked).
- Requirements
  - Each completed task should add a brief “What changed / How to test” to this file.
  - Keep acceptance criteria precise.
- Acceptance
  - A new LLM can pick up the next item and know exactly what to do and how to verify it.

Appendix — References & Pointers
- e‑Invoice code: `src/core/einvoice/{ubl.py,batch.py}`
- Pipeline: `src/core/pipeline.py`
- Intake parsers: `src/core/intake/parsers.py`
- Normalization helpers: `src/core/normalize/transforms.py`
- Scheduler: `src/core/scheduler/{scheduler.py,jobs.py,cron.py}`
- CKAN: `src/core/publish/ckan.py`
- API routers: `src/api/*`
- UI templates: `src/ui/templates/*`
- Tests: `tests/*`
