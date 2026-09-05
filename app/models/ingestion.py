import uuid
from datetime import datetime, timezone


def create_ingestion_job(
    case_id: str,
    document_id: str,
):
    now = datetime.now(timezone.utc)

    return {
        "job_id": str(uuid.uuid4()),

        "case_id": case_id,
        "document_id": document_id,

        "status": "QUEUED",

        "steps": {
            "upload": "PENDING",
            "ocr": "PENDING",
            "segmentation": "PENDING",
            "extraction": "PENDING",
            "entity_resolution": "PENDING",
            "persistence": "PENDING",
        },

        "error": None,

        "retry_count": 0,

        "created_at": now,
        "updated_at": now,

        "completed_at": None,
    }
