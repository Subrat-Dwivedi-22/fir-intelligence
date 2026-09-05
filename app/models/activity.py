import uuid
from datetime import datetime, timezone


def create_activity_document(
    case_id: str,
    action: str,
    actor: str,
):
    now = datetime.now(timezone.utc)

    return {
        "activity_id": str(uuid.uuid4()),
        "case_id": case_id,
        "action": action,
        "actor": actor,
        "timestamp": now,
    }
