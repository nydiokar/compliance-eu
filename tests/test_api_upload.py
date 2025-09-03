from pathlib import Path

from fastapi.testclient import TestClient

from src.app import app
from src.db import init_database, get_session, DatasetCRUD
from src.models import DatasetCreate


def test_upload_analyze_and_process():
    init_database()
    client = TestClient(app)

    # Ensure at least one dataset exists for process
    with get_session() as db:
        ds = DatasetCRUD.get_by_name(db, "api_org", "api_dataset")
        if not ds:
            ds = DatasetCRUD.create(
                db,
                DatasetCreate(
                    org_id="api_org",
                    name="api_dataset",
                    profile="budget_execution_v1",
                    publish_target="none",
                ),
            )

    fixture = Path("tests/data_fixtures/budget_sample_en.csv")
    assert fixture.exists()

    # Analyze endpoint
    with open(fixture, "rb") as f:
        resp = client.post("/api/upload/analyze", files={"file": (fixture.name, f, "text/csv")})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_rows"] > 0
    assert isinstance(data["detected_headers"], list)

    # Process endpoint
    with open(fixture, "rb") as f:
        resp = client.post(
            "/api/upload/process",
            data={"dataset_id": ds.id, "column_mapping": "{}"},
            files={"file": (fixture.name, f, "text/csv")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["message"].startswith("Processing completed")
    assert "run_id" in data

