from fastapi import APIRouter, HTTPException

from app.db.mongodb import db
from app.schemas.relationship import (
    CreateRelationshipRequest,
    RelationshipResponse,
)
from app.services.case.manual_relationship import (
    ManualRelationshipService,
)

router = APIRouter(
    prefix="/cases",
    tags=["Relationships"],
)


@router.post(
    "/{case_id}/relationships",
    response_model=RelationshipResponse,
)
def create_case_relationship(
    case_id: str,
    request: CreateRelationshipRequest,
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

    service = ManualRelationshipService()

    try:
        relationship = service.create(
            case_id=case_id,
            source=request.source,
            target=request.target,
            relationship_type=request.type,
            evidence=request.evidence,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    return RelationshipResponse(
        relationship_id=relationship["relationship_id"],
        case_id=case_id,
        source=request.source,
        target=request.target,
        type=relationship["type"],
        evidence=relationship.get("evidence"),
    )
