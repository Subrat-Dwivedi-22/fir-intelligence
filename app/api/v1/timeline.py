from fastapi import APIRouter, HTTPException

from app.db.mongodb import db
from app.schemas.timeline import TimelineEvent
from app.services.case.timeline import TimelineService

router = APIRouter(
    prefix="/cases",
    tags=["Timeline"],
)

service = TimelineService()


@router.get(
    "/{case_id}/timeline",
    response_model=list[TimelineEvent],
)
def get_case_timeline(
    case_id: str,
):
    case = db.cases.find_one(
        {"case_id": case_id},
        {"_id": 1},
    )

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found.",
        )

    return service.get_by_case(case_id)
