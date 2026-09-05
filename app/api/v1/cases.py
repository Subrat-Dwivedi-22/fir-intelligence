from fastapi import APIRouter, HTTPException

from app.db.mongodb import db
from app.models.case import create_case_document
from app.schemas.case import (
    CreateCaseRequest,
    CreateCaseResponse,
    CaseDetailResponse,
    CaseListItem,
    CaseSummaryResponse,
    CaseStatus,
)
from app.api.serialization import serialize_mongo
from datetime import datetime, timezone


router = APIRouter(
    prefix="/cases",
    tags=["Cases"],
)


# ==========================================
# CREATE CASE
# ==========================================

@router.post(
    "",
    response_model=CreateCaseResponse,
)
def create_case(
    request: CreateCaseRequest,
):
    existing_case = db.cases.find_one(
        {
            "case_number": request.case_number,
        }
    )

    if existing_case:
        raise HTTPException(
            status_code=409,
            detail="Case number already exists.",
        )

    case = create_case_document(
        case_number=request.case_number,
        title=request.title,
        case_type=request.case_type,
        priority=request.priority.value,
        synopsis=request.synopsis,
        police_station=request.police_station,
        district=request.district,
    )

    db.cases.insert_one(case)

    return CreateCaseResponse(
        case_id=case["case_id"],
        case_number=case["case_number"],
        title=case["title"],
        case_type=case["case_type"],
        priority=case["priority"],
        synopsis=case["synopsis"],
        status=case["status"],
    )


# ==========================================
# LIST CASES
# ==========================================

@router.get(
    "",
    response_model=list[CaseListItem],
)
def list_cases():

    cases = db.cases.find(
        {},
        {
            "_id": 0,
            "case_id": 1,
            "case_number": 1,
            "title": 1,
            "case_type": 1,
            "priority": 1,
            "synopsis": 1,
            "jurisdiction": 1,
            "status": 1,
            "created_at": 1,
        },
    ).sort(
        "created_at",
        -1,
    )

    result = []

    for case in cases:

        jurisdiction = case.get(
            "jurisdiction",
            {},
        )

        result.append(
            {
                "case_id": case.get(
                    "case_id"
                ),
                "case_number": case.get(
                    "case_number"
                ),
                "title": case.get(
                    "title"
                ),
                "police_station": jurisdiction.get(
                    "police_station"
                ),
                "status": case.get(
                    "status"
                ),
                "created_at": case.get(
                    "created_at"
                ),
                "case_type": case.get("case_type"),
                "priority": case.get("priority"),
                "synopsis": case.get("synopsis"),
            }
        )

    return serialize_mongo(result)


# ==========================================
# CASE SUMMARY
# ==========================================

@router.get(
    "/{case_id}/summary",
    response_model=CaseSummaryResponse,
)
def get_case_summary(
    case_id: str,
):

    case = db.cases.find_one(
        {
            "case_id": case_id,
        },
        {
            "_id": 0,
        },
    )

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found.",
        )

    document_count = db.documents.count_documents(
        {
            "case_id": case_id,
        }
    )

    person_count = db.case_persons.count_documents(
        {
            "case_id": case_id,
        }
    )

    unknown_identity_count = (
        db.unknown_identities.count_documents(
            {
                "case_id": case_id,
            }
        )
    )

    incident_count = db.incidents.count_documents(
        {
            "case_id": case_id,
        }
    )

    entity_count = db.entities.count_documents(
        {
            "case_ids": case_id,
        }
    )

    relationship_count = (
        db.relationships.count_documents(
            {
                "context.case_id": case_id,
            }
        )
    )

    analysis_available = (
        db.case_analyses.count_documents(
            {
                "case_id": case_id,
            }
        )
        > 0
    )

    jurisdiction = case.get(
        "jurisdiction",
        {},
    )

    return CaseSummaryResponse(
        case_id=case_id,
        case_number=case.get("case_number"),
        title=case.get("title"),
        case_type=case.get("case_type"),
        priority=case.get("priority"),
        synopsis=case.get("synopsis"),
        police_station=jurisdiction.get("police_station"),
        status=case.get("status"),
        document_count=document_count,
        person_count=person_count,
        unknown_identity_count=unknown_identity_count,
        incident_count=incident_count,
        entity_count=entity_count,
        relationship_count=relationship_count,
        analysis_available=analysis_available,
    )

# ==========================================
# CLOSE CASE
# ==========================================

@router.post(
    "/{case_id}/close",
    response_model=CaseDetailResponse,
)
def close_case(
    case_id: str,
):
    now = datetime.now(timezone.utc)

    case = db.cases.find_one(
        {
            "case_id": case_id,
        },
        {
            "_id": 0,
        },
    )

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found.",
        )

    if case.get("status") == CaseStatus.CLOSED.value:
        return get_case(case_id)

    db.cases.update_one(
        {
            "case_id": case_id,
        },
        {
            "$set": {
                "status": CaseStatus.CLOSED.value,
                "closed_at": now,
                "updated_at": now,
            }
        },
    )

    return get_case(case_id)


# ==========================================
# GET CASE DETAILS
# ==========================================

@router.get(
    "/{case_id}",
    response_model=CaseDetailResponse,
)
def get_case(
    case_id: str,
):

    case = db.cases.find_one(
        {
            "case_id": case_id,
        },
        {
            "_id": 0,
        },
    )

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found.",
        )

    # --------------------------------------
    # PERSONS
    # --------------------------------------

    persons = list(
        db.case_persons.aggregate(
            [
                {
                    "$match": {
                        "case_id": case_id,
                    }
                },
                {
                    "$lookup": {
                        "from": "persons",
                        "localField": "person_id",
                        "foreignField": "person_id",
                        "as": "person",
                    }
                },
                {
                    "$unwind": "$person",
                },
                {
                    "$project": {
                        "_id": 0,
                        "person": "$person",
                        "roles": 1,
                        "confidence": 1,
                        "document_id": 1,
                    }
                },
            ]
        )
    )

    for item in persons:
        item.get(
            "person",
            {},
        ).pop(
            "_id",
            None,
        )

    # --------------------------------------
    # UNKNOWN IDENTITIES
    # --------------------------------------

    unknown_identities = list(
        db.unknown_identities.find(
            {
                "case_id": case_id,
            },
            {
                "_id": 0,
            },
        )
    )

    # --------------------------------------
    # INCIDENTS
    # --------------------------------------

    incidents = list(
        db.incidents.find(
            {
                "case_id": case_id,
            },
            {
                "_id": 0,
            },
        )
    )

    # --------------------------------------
    # ENTITIES
    # --------------------------------------

    entities = list(
        db.entities.find(
            {
                "case_ids": case_id,
            },
            {
                "_id": 0,
            },
        )
    )

    # --------------------------------------
    # RELATIONSHIPS
    # --------------------------------------

    relationships = list(
        db.relationships.find(
            {
                "context.case_id": case_id,
            },
            {
                "_id": 0,
            },
        )
    )

    # --------------------------------------
    # DOCUMENTS
    # --------------------------------------

    documents = list(
        db.documents.find(
            {
                "case_id": case_id,
            },
            {
                "_id": 0,
            },
        )
    )

    # --------------------------------------
    # INGESTION JOBS
    # --------------------------------------

    ingestion_jobs = list(
        db.ingestion_jobs.find(
            {
                "case_id": case_id,
            },
            {
                "_id": 0,
            },
        ).sort(
            "created_at",
            -1,
        )
    )

    return CaseDetailResponse(
        case=serialize_mongo(case),
        persons=serialize_mongo(
            persons
        ),
        unknown_identities=serialize_mongo(
            unknown_identities
        ),
        incidents=serialize_mongo(
            incidents
        ),
        entities=serialize_mongo(
            entities
        ),
        relationships=serialize_mongo(
            relationships
        ),
        documents=serialize_mongo(
            documents
        ),
        ingestion_jobs=serialize_mongo(
            ingestion_jobs
        ),
    )