from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from src.core.einvoice import generate_invoices_from_csv
from src.settings import settings
from src.logging_conf import get_logger

logger = get_logger("api.einvoice")
router = APIRouter()


@router.post("/process")
async def process_einvoice_csv(
    file: UploadFile = File(...),
    org_id: str = Form(...),
):
    """Process an uploaded CSV into UBL XML invoices and a registry CSV.

    Returns registry path and list of generated files.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # Save to temp
    temp_dir = settings.upload_dir / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / file.filename
    try:
        contents = await file.read()
        temp_path.write_bytes(contents)
        logger.info("einvoice_csv_uploaded", file=file.filename, size=len(contents))

        result = generate_invoices_from_csv(temp_path, output_dir=None, org_id=org_id)
        return {
            "registry": str(result["registry"]),
            "invoices": [str(p) for p in result["invoices"]],
        }
    except Exception as e:
        logger.error("einvoice_process_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass

