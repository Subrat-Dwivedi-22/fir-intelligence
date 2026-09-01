import uuid
from datetime import datetime, timezone


def create_entity_document(
    entity_type: str,
    value: str,
    normalized_value: str,
    case_id: str | None = None,
    document_id: str | None = None,
    pages: list[int] | None = None,
):
    now = datetime.now(timezone.utc)

    return {
        "entity_id": f"ent_{uuid.uuid4()}",

        "type": entity_type,

        "value": value,

        "normalized_value": normalized_value,

        "case_ids": (
            [case_id]
            if case_id
            else []
        ),

        "source": {
            "document_id": document_id,
            "pages": pages or [],
        },

        "created_at": now,
        "updated_at": now,
    }
