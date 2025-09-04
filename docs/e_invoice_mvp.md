e‑Invoice Helper (MVP)

Scope: Minimal UBL 2.1 invoice XML generation with optional XSD validation, plus CSV→UBL batch generation and registry CSV.

- Entry points:
  - `src/core/einvoice/ubl.py`
    - `UBLInvoiceBuilder`: builds and writes UBL Invoice XML from a structured object
    - `generate_ubl_invoice(payload, output_path, xsd_path=None)`: convenience wrapper
  - `src/core/einvoice/batch.py`
    - `generate_invoices_from_csv(input_csv, output_dir=None, org_id=None, xsd_path=None)`: parse CSV, group by invoice, generate UBL files, and write `registry.csv`

- Profile mapping for header resolution:
  - `data/profiles/einvoice_v1.yaml` (targets: invoice_id, issue_date, supplier_name, customer_name, line_description, quantity, unit_price, tax_percent)

- Input payload keys (for direct builder usage):
  - `id`, `issue_date` (YYYY‑MM‑DD), `currency`
  - `supplier` and `customer`: `{name, tax_id?, country?, city?, postal_code?, street?}`
  - `lines`: list of `{id, description, quantity, unit_price, line_extension_amount, tax_percent?}`
  - `totals`: `{line_extension_amount, tax_exclusive_amount, tax_inclusive_amount, payable_amount}`

- Validation: If an XSD path is provided (local file), the output is validated; failures are logged without aborting (MVP behavior).

Usage
-----

CLI:

```bash
compliance-kit einvoice generate \
  --input path/to/invoices.csv \
  --org-id my_org \
  --out outputs/my_org/einvoice \
  --xsd path/to/UBL-Invoice-2.1.xsd   # optional
```

API:

```
POST /api/einvoice/process
Content-Type: multipart/form-data
  file=@invoices.csv
  org_id=my_org
```

Outputs
-------
- One XML per invoice under the output directory
- `registry.csv` with: invoice_id, file_path, currency, payable_amount, checksum, status, error

Next Work
---------
- [ ] UI upload page for e‑Invoice (form posting to `/api/einvoice/process`) with results view
- [ ] Stronger CSV mapping/normalization (locale-aware decimals/dates, currency detection)
- [ ] Optional bundled UBL XSD for offline validation
- [ ] More unit tests: multi-invoice CSVs, error rows, XSD validation
