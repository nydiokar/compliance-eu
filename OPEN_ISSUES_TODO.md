Open Issues TODO (High → Low)

1) CKAN Not Found handling in client helpers [High]
- File: `src/core/publish/ckan.py`
- Fix: Catch `CKANError` in `get_package/get_resource`, return `None` for not-found.

2) Upload path mismatch vs scheduler [High]
- File: `src/api/upload.py`
- Fix: Save uploads under `uploads/<org_id>/<dataset_id>` to match scheduler.

3) Duplicate `except` in dataset create (UI) [High]
- File: `src/app.py`
- Fix: Remove duplicate `except` branch.

4) Dashboard run status counts use Enum incorrectly [Medium]
- File: `src/ui/templates/dashboard.html`
- Fix: Compare `status.value` to strings in counters.

5) UBL root default namespace missing [Medium]
- File: `src/core/einvoice/ubl.py`
- Fix: Set default `Invoice-2` namespace on root; add `xsi`.

6) Database StaticPool used unconditionally [Low]
- File: `src/db.py`
- Fix: Use `StaticPool` only for SQLite URLs.

7) Allowed extensions include unsupported formats [Low]
- File: `src/settings.py` / intake
- Fix: Narrow defaults or improve error message for unsupported but allowed types.

