import hashlib
import hmac

from app.core.config import settings


def normalize_identifier(value: str) -> str:
    """
    Normalize an identity identifier before hashing.

    Removes whitespace and hyphens.
    """
    return (
        value
        .strip()
        .replace(" ", "")
        .replace("-", "")
    )


def generate_person_id_from_aadhaar(
    aadhaar: str,
) -> str:
    normalized = normalize_identifier(aadhaar)

    digest = hmac.new(
        settings.person_id_hmac_secret.encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return f"per_{digest}"


def generate_person_id() -> str:
    """
    Generate a provisional person ID when
    no strong identity identifier is available.
    """
    import uuid

    return f"per_{uuid.uuid4()}"