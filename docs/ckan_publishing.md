CKAN Publishing

Components:
- `src/core/publish/ckan.py` — `CKANClient` with retries and `CKANPublisher` for package/resource upsert and file uploads
- Pipeline integration: optional publish step when `publish_to_ckan=True`, records external IDs on `Run`

Configuration (`.env` or environment):
- `CKAN_URL`, `CKAN_API_KEY`, `CKAN_ORGANIZATION`
- Optional: `CKAN_TIMEOUT`, `CKAN_MAX_RETRIES`, `CKAN_BACKOFF_FACTOR`

Usage:
- Programmatic: create client via `create_ckan_client_from_settings()` then `CKANPublisher.publish_dataset(...)`
- CLI/UI: Future endpoints can call the same publisher; ensure credentials are set.

Notes:
- `test_connection()` calls `/api/3/action/site_read` to verify reachability
- Idempotency is achieved by checking/creating packages and updating resources by name

