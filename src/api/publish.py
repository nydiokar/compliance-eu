from fastapi import APIRouter, HTTPException

from src.core.publish.ckan import create_ckan_client_from_settings, CKANError
from src.logging_conf import get_logger

logger = get_logger("api.publish")
router = APIRouter()


@router.get("/publish/test")
async def publish_test():
    """Test CKAN connectivity with current settings."""
    try:
        client = create_ckan_client_from_settings()
    except Exception as e:
        logger.error("ckan_client_init_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"CKAN client init failed: {e}")

    try:
        ok = client.test_connection()
        if ok:
            return {"ok": True, "message": "CKAN reachable"}
        raise HTTPException(status_code=502, detail="CKAN not reachable")
    except CKANError as e:
        logger.error("ckan_connection_failed", error=str(e))
        raise HTTPException(status_code=502, detail=f"CKAN test failed: {e}")

