import uuid
from datetime import datetime, timezone


def create_document(
    case_id: str,
    filename: str,
    s3_bucket: str,
    s3_key: str,
    sha256: str,
):
    now = datetime.now(timezone.utc)

    return {
        "document_id": str(uuid.uuid4()),

        "case_id": case_id,

        "type": "FIR",

        "source": {
            "filename": filename,
            "mime_type": "application/pdf",
            "sha256": sha256,
        },

        "storage": {
            "provider": "s3",
            "bucket": s3_bucket,
            "key": s3_key,
        },

        "ocr": {
            "provider": None,
            "status": "pending",
            "job_id": None,
            "pages": 0,
        },

        "created_at": now,
        "updated_at": now,
    }