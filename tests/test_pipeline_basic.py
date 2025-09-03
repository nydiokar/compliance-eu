import os
from pathlib import Path

from src.settings import settings
from src.logging_conf import setup_logging
from src.db import init_database, get_session, DatasetCRUD
from src.models import DatasetCreate
from src.core.pipeline import process_file_pipeline


def test_pipeline_end_to_end(tmp_path: Path):
    setup_logging()
    init_database()

    # Ensure dataset exists
    with get_session() as db:
        ds = DatasetCRUD.get_by_name(db, "test_org", "budget_execution_test")
        if not ds:
            ds = DatasetCRUD.create(
                db,
                DatasetCreate(
                    org_id="test_org",
                    name="budget_execution_test",
                    profile="budget_execution_v1",
                    description="pytest e2e",
                    publish_target="none",
                ),
            )

    # Use provided fixture CSV
    input_file = Path("tests/data_fixtures/budget_sample_en.csv")
    assert input_file.exists(), f"Missing fixture: {input_file}"

    # Run pipeline
    result = process_file_pipeline(
        file_path=input_file,
        dataset_id=ds.id,
        profile_name="budget_execution_v1",
        org_id="test_org",
        metadata={
            "title": "Budget Execution",
            "publisher": "test_org",
            "profile": "budget_execution_v1",
        },
    )

    # Validate outputs
    exports = result["exports"]
    for k in ("csv", "json", "metadata"):
        p = exports[k]
        assert Path(p).exists(), f"Export {k} not found: {p}"
        assert Path(p).stat().st_size > 0

    assert result["status"] == "completed"
    assert result["input_stats"]["rows"] > 0
    assert result["output_stats"]["rows"] > 0

