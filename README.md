# Compliance Automation Kit

A modular schema-on-read pipeline that ingests messy municipal/SME files (Excel/CSV/PDF), maps them via saved profiles, validates, and emits strict compliant outputs for EU regulations.

## Features

- **Open Data Auto-Publisher**: Convert budget/procurement spreadsheets to standardized CSV/JSON + metadata → CKAN upload
- **e-Invoice Helper**: Parse invoice data and generate EN 16931 compliant UBL XML
- **ESG-Lite Reporter**: Extract sustainability metrics and generate reports
- **NIS2 Lite Logbook**: Capture cybersecurity evidence and generate compliance checklists

## Quick Start

### Windows Setup

```powershell
# Clone and setup
git clone https://github.com/compliance-kit/compliance-automation-kit
cd compliance-automation-kit
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -U pip
pip install -e .

# Configure
copy .env.example .env
# Edit .env with your settings

# Initialize database
alembic upgrade head

# Start server
uvicorn src.app:app --reload --port 8000
```

### Linux Setup

```bash
# Clone and setup
git clone https://github.com/compliance-kit/compliance-automation-kit
cd compliance-automation-kit
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .

# Configure
cp .env.example .env
# Edit .env with your settings

# Initialize database
alembic upgrade head

# Start server
uvicorn src.app:app --reload --port 8000
```

## Usage

1. **Web Interface**: Visit http://localhost:8000 for the admin UI
2. **CLI**: Use `compliance-kit --help` for command-line operations
3. **API**: REST API available at http://localhost:8000/api/docs (if `DEBUG=true`)

### Example Workflow (Open Data)

1. Upload messy Excel file with budget data
2. Map columns using the visual interface
3. Save mapping profile for reuse
4. Set up automated publishing schedule
5. Monitor runs and download compliant outputs

### e‑Invoice (MVP)

- Generate UBL invoices from a CSV via CLI:

```bash
compliance-kit einvoice generate \
  --input path/to/invoices.csv \
  --org-id my_org \
  --out outputs/my_org/einvoice \
  --xsd path/to/UBL-Invoice-2.1.xsd   # optional
```

- Process a CSV via API (returns registry + list of XML files):

```
POST /api/einvoice/process
Content-Type: multipart/form-data
  file=@invoices.csv
  org_id=my_org
```

## Architecture

```
Input Layer → Mapper/Profiler → Validator/Normalizer → Output Modules → Publisher
(CSV/XLSX/PDF)  (schema-on-read)   (types/dates)      (OD/eInv/ESG/NIS2)  (CKAN/FTP)
```

## Documentation

- Mapping DSL: `docs/mapping_dsl.md`
- CKAN Publishing: `docs/ckan_publishing.md`
- e‑Invoice MVP: `docs/e_invoice_mvp.md`
- Build Plan: `docs/compliance_automation_kit_build_plan_v_1.md`

## What’s New

- e‑Invoice batch generation (CSV → UBL XML + registry) via CLI and API
- Custom cron-based scheduler with UI at `/scheduler`
- CKAN client + publisher with retries and id tracking
- Robust validators with business rules and error CSVs

## Next Work

- e‑Invoice UI upload page; stronger CSV mapping/normalization; optional bundled XSD
- Mapping UI: add save/update workflow (drag/drop optional later)
- CKAN: `/publish/test` endpoint + UI button to verify credentials
- NIS2 Lite: checklist PDF generator and basic UI
- Docs: add ESG/NIS2 docs and packaging instructions (.msi / service)

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/ tests/
isort src/ tests/

# Type checking
mypy src/

# Pre-commit hooks
pre-commit install
pre-commit run --all-files
```

## License

MIT License - see [LICENSE](LICENSE) file.

## Support

- [GitHub Issues](https://github.com/compliance-kit/compliance-automation-kit/issues)
- [Documentation](https://compliance-kit.readthedocs.io/)
