from datetime import datetime, timezone


def create_person_document(
    person_id: str,
    name: str | None = None,
    extraction_confidence: float | None = None,
):
    now = datetime.now(timezone.utc)

    normalized_name = (
        name.lower().strip()
        if name
        else None
    )

    return {
        "person_id": person_id,

        "identity": {
            "name": name,
            "normalized_name": normalized_name,
            "aliases": [],
            "father_name": None,
            "date_of_birth": None,
            "approximate_age": None,
            "gender": None,
        },

        "contact": {
            "phones": [],
            "emails": [],
        },

        "addresses": [],

        "extraction_confidence": extraction_confidence,

        "identifiers": [],

        "case_ids": [],

        "identity_resolution": {
            "status": "PROVISIONAL",
            "method": None,
            "confidence": None,
        },

        "created_at": now,
        "updated_at": now,
    }