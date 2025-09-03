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
3. **API**: REST API available at http://localhost:8000/docs

### Example Workflow

1. Upload messy Excel file with budget data
2. Map columns using the visual interface
3. Save mapping profile for reuse
4. Set up automated publishing schedule
5. Monitor runs and download compliant outputs

## Architecture

```
Input Layer → Mapper/Profiler → Validator/Normalizer → Output Modules → Publisher
(CSV/XLSX/PDF)  (schema-on-read)   (types/dates)      (OD/eInv/ESG/NIS2)  (CKAN/FTP)
```

## Documentation

- [Mapping Profiles](docs/Profiles.md)
- [CKAN Integration](docs/CKAN.md)
- [e-Invoice Setup](docs/eInvoice.md)
- [NIS2 Compliance](docs/NIS2.md)

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