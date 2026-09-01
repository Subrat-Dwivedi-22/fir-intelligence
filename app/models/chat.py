import uuid
from datetime import datetime, timezone


def create_chat_message(
    case_id: str,
    role: str,
    content: str,
) -> dict:
    now = datetime.now(timezone.utc)

    return {
        "message_id": str(uuid.uuid4()),
        "case_id": case_id,
        "role": role,
        "content": content,
        "created_at": now,
    }
