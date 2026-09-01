from fastapi import APIRouter, HTTPException

from app.db.mongodb import db


router = APIRouter(
    prefix="/firs/jobs",
    tags=["FIR Jobs"],
)


@router.get("/{job_id}")
def get_fir_job_status(
    job_id: str,
):
    job = db.ingestion_jobs.find_one(
        {
            "job_id": job_id,
        },
        {
            "_id": 0,
        },
    )

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Ingestion job not found.",
        )

    return job