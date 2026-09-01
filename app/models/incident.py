import uuid
from datetime import datetime, timezone


def create_incident(
    case_id: str,
    title: str | None = None,
):
    now = datetime.now(timezone.utc)

    return {
        "incident_id": str(uuid.uuid4()),

        "case_id": case_id,

        "title": title,

        "description": None,

        "key_points": [],

        "time": {
            "start": None,
            "end": None,
            "confidence": None,
        },

        "location": {
            "text": None,
            "normalized": None,
            "coordinates": None,
            "confidence": None,
        },

        "crime_types": [],

        "source": {
            "document_id": None,
            "pages": [],
        },

        "extraction": {
            "method": None,
            "model": None,
            "confidence": None,
        },

        "created_at": now,
        "updated_at": now,
    }