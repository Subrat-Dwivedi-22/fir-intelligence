import hashlib
import uuid

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    UploadFile,
    status,
)

from app.core.config import settings
from app.db.mongodb import db
from app.models.document import create_document
from app.models.ingestion import create_ingestion_job
from app.schemas.fir import FIRUploadResponse
from app.storage.s3 import s3_storage
from app.queue.sqs import sqs_queue


router = APIRouter(
    prefix="/cases",
    tags=["Case Documents"],
)


ALLOWED_CONTENT_TYPES = {
    "application/pdf",
}


@router.post(
    "/{case_id}/documents",
    response_model=FIRUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_case_document(
    case_id: str,
    file: UploadFile = File(...),
):

    # ==========================================
    # 1. VERIFY CASE
    # ==========================================

    case = db.cases.find_one(
        {
            "case_id": case_id,
        }
    )

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found.",
        )

    # ==========================================
    # 2. VALIDATE FILE TYPE
    # ==========================================

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported.",
        )

    # ==========================================
    # 3. READ FILE
    # ==========================================

    data = await file.read()

    max_size = (
        settings.max_fir_size_mb
        * 1024
        * 1024
    )

    if len(data) > max_size:
        raise HTTPException(
            status_code=413,
            detail=(
                f"FIR exceeds maximum size of "
                f"{settings.max_fir_size_mb} MB."
            ),
        )

    if len(data) == 0:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty.",
        )

    # ==========================================
    # 4. VERIFY PDF SIGNATURE
    # ==========================================

    if not data.startswith(b"%PDF"):
        raise HTTPException(
            status_code=400,
            detail=(
                "File does not appear to be "
                "a valid PDF."
            ),
        )

    # ==========================================
    # 5. GENERATE CHECKSUM
    # ==========================================

    sha256 = hashlib.sha256(
        data
    ).hexdigest()

    # ==========================================
    # 6. CHECK DUPLICATE DOCUMENT
    # ==========================================

    existing_document = db.documents.find_one(
        {
            "source.sha256": sha256,
        }
    )

    if existing_document:
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    "This document has already "
                    "been uploaded."
                ),
                "document_id": existing_document[
                    "document_id"
                ],
                "case_id": existing_document[
                    "case_id"
                ],
            },
        )

    # ==========================================
    # 7. CREATE DOCUMENT ID
    # ==========================================

    document_id = str(
        uuid.uuid4()
    )

    s3_key = (
        f"cases/{case_id}/"
        f"documents/{document_id}/"
        f"original.pdf"
    )

    # ==========================================
    # 8. UPLOAD TO S3
    # ==========================================

    try:

        s3_storage.upload_bytes(
            data=data,
            key=s3_key,
            content_type="application/pdf",
        )

    except Exception as exc:
        print(
            f"S3 upload failed: "
            f"{type(exc).__name__}: {exc}"
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to upload document to S3.",
        ) from exc

    # ==========================================
    # 9. CREATE DOCUMENT RECORD
    # ==========================================

    document = create_document(
        case_id=case_id,
        filename=file.filename or "document.pdf",
        s3_bucket=settings.s3_bucket,
        s3_key=s3_key,
        sha256=sha256,
    )

    document["document_id"] = document_id

    # ==========================================
    # 10. CREATE INGESTION JOB
    # ==========================================

    job = create_ingestion_job(
        case_id=case_id,
        document_id=document_id,
    )

    job["steps"]["upload"] = "COMPLETED"

    # ==========================================
    # 11. PERSIST DOCUMENT + JOB
    # ==========================================

    db.documents.insert_one(
        document
    )

    db.ingestion_jobs.insert_one(
        job
    )

    # ==========================================
    # 12. LINK DOCUMENT TO CASE
    # ==========================================

    db.cases.update_one(
        {
            "case_id": case_id,
        },
        {
            "$addToSet": {
                "document_ids": document_id,
            },
            "$set": {
                "updated_at": job[
                    "created_at"
                ],
            },
        },
    )

    # ==========================================
    # 13. QUEUE PROCESSING
    # ==========================================

    try:

        sqs_queue.send_message(
            {
                "job_id": job["job_id"],
                "case_id": case_id,
                "document_id": document_id,
                "s3": {
                    "bucket": settings.s3_bucket,
                    "key": s3_key,
                },
            }
        )

    except Exception as exc:

        db.ingestion_jobs.update_one(
            {
                "job_id": job["job_id"],
            },
            {
                "$set": {
                    "status": "FAILED",
                    "error": {
                        "code": "QUEUE_ERROR",
                        "message": str(exc),
                    },
                },
            },
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Document uploaded but could "
                "not be queued for processing."
            ),
        ) from exc

    # ==========================================
    # 14. RESPONSE
    # ==========================================

    return FIRUploadResponse(
        case_id=case_id,
        document_id=document_id,
        job_id=job["job_id"],
        status="QUEUED",
        message=(
            "Document uploaded successfully "
            "and queued for processing."
        ),
    )