import uuid
from datetime import datetime, timezone


def create_case_person(
    case_id: str,
    person_id: str,
    role: str,
    document_id: str | None = None,
    pages: list[int] | None = None,
    confidence: float | None = None,
):
    return {
        "relationship_id": str(uuid.uuid4()),

        "case_id": case_id,
        "person_id": person_id,

        "roles": [role],

        "source": {
            "document_id": document_id,
            "pages": pages or [],
        },

        "confidence": confidence,

        "created_at": datetime.now(timezone.utc),
    }