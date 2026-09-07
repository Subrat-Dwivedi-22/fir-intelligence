from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class Relationship(BaseModel):
    relationship_id: str

    from_: dict[str, str] = Field(alias="from")
    to: dict[str, str]

    type: str

    context: dict[str, Any] = Field(default_factory=dict)
    source: dict[str, Any] = Field(default_factory=dict)

    evidence: str | None = None
    confidence: float | None = None
    weight: float = 0.50

    # How this edge was established.
    # DIRECT = explicitly extracted semantic relationship
    # STRUCTURED_FACT = built from an extracted structured fact
    # EVENT_DERIVED = deterministically derived from an extracted event
    derivation: str = "DIRECT"

    # Flexible relationship-specific metadata.
    # Examples:
    # {"call_count": 14, "date": "2026-01-12"}
    # {"amount": 4200000, "currency": "INR"}
    metadata: dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    model_config = {
        "populate_by_name": True,
    }


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
    weight: float = 0.50,
    derivation: str = "DIRECT",
    metadata: dict[str, Any] | None = None,
) -> dict:
    now = datetime.now(timezone.utc)

    return {
        "relationship_id": f"{from_type}:{from_id}:{relationship_type}:{to_type}:{to_id}",
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

        "evidence": evidence,
        "confidence": confidence,
        "weight": weight,
        "derivation": derivation,
        "metadata": metadata or {},

        "created_at": now,
        "updated_at": now,
    }