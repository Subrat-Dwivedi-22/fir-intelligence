import uuid
from datetime import datetime, timezone


def create_relationship(
    from_type: str,
    from_id: str,
    to_type: str,
    to_id: str,
    relationship_type: str,
    case_id: str | None = None,
    incident_id: str | None = None,
    document_id: str | None = None,
    pages: list[int] | None = None,
    confidence: float | None = None,
    evidence: str | None = None,
):
    return {
        "relationship_id": str(
            uuid.uuid4()
        ),

        "from": {
            "type": from_type,
            "id": from_id,
        },

        "to": {
            "type": to_type,
            "id": to_id,
        },

        "type": relationship_type,

        "context": {
            "case_id": case_id,
            "incident_id": incident_id,
        },

        "source": {
            "document_id": document_id,
            "pages": pages or [],
        },

        "confidence": confidence,

        "evidence": evidence,

        "created_at": datetime.now(
            timezone.utc
        ),
    }
