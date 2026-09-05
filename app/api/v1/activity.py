from fastapi import APIRouter, HTTPException

from app.db.mongodb import db
from app.models.activity import create_activity_document
from app.repositories.activity_repository import (
    ActivityRepository,
)
from app.schemas.activity import (
    CreateActivityRequest,
    ActivityResponse,
)

router = APIRouter(
    prefix="/cases",
    tags=["Activity"],
)

repository = ActivityRepository()


@router.post(
    "/{case_id}/activity",
    response_model=ActivityResponse,
)
def create_case_activity(
    case_id: str,
    request: CreateActivityRequest,
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

    activity = create_activity_document(
        case_id=case_id,
        action=request.action,
        actor=request.actor,
    )

    activity = repository.create(activity)

    return ActivityResponse(
        activity_id=activity["activity_id"],
        case_id=activity["case_id"],
        action=activity["action"],
        actor=activity["actor"],
        timestamp=activity["timestamp"],
    )
