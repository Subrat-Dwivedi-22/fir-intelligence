import uuid
from datetime import datetime, timezone


def create_unknown_identity_document(
    case_id: str,
    label: str,
    document_id: str | None = None,
    role: str | None = None,
    description: str | None = None,
):
    now = datetime.now(timezone.utc)

    return {
        "unknown_id": str(uuid.uuid4()),

        "case_id": case_id,

        "label": label,

        "roles": (
            [role]
            if role
            else []
        ),

        "status": "UNIDENTIFIED",

        "description": description,

        "source": {
            "document_id": document_id,
            "pages": [],
        },

        "linked_person_id": None,

        "identification": {
            "confidence": None,
            "method": None,
            "identified_at": None,
        },

        "created_at": now,
        "updated_at": now,
    }