import uuid
from datetime import datetime, timezone


def create_case_document(
    case_number: str,
    title: str,
    case_type: str,
    priority: str,
    synopsis: str | None = None,
    district: str | None = None,
    police_station: str | None = None,
):
    now = datetime.now(timezone.utc)

    case_id = str(uuid.uuid4())

    return {
        "case_id": case_id,

        "case_number": case_number,

        "title": title,

        "case_type": case_type,

        "priority": priority,

        "synopsis": synopsis,

        "jurisdiction": {
            "state": None,
            "district": district,
            "police_station": police_station,
        },

        "registration": {
            "registered_at": now,
        },

        "legal_sections": [],

        "status": "OPEN",

        "closed_at": None,

        "incident_ids": [],
        "person_ids": [],
        "document_ids": [],

        "created_at": now,
        "updated_at": now,
    }
