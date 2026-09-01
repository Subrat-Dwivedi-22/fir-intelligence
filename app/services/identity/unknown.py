from datetime import datetime, timezone

from app.db.mongodb import db
from app.models.unknown_identity import (
    create_unknown_identity_document,
)


class UnknownIdentityService:
    """
    Manages case-specific unidentified persons.

    An UnknownIdentity is deliberately NOT a Person.

    Example:

        UNKNOWN_PERSON_1
            ↓
        unk_<uuid>
            ↓
        UNIDENTIFIED

    If investigators later identify the person,
    the unknown identity is linked to a canonical
    Person without deleting the historical record.
    """

    def create(
        self,
        case_id: str,
        label: str,
        document_id: str | None = None,
        role: str | None = None,
        description: str | None = None,
        source_section: str | None = None,
    ) -> dict:

        existing = db.unknown_identities.find_one(
            {
                "case_id": case_id,
                "label": label,
                "source.document_id": document_id,
            }
        )

        if existing:
            return existing

        document = (
            create_unknown_identity_document(
                case_id=case_id,
                label=label,
                document_id=document_id,
                role=role,
                description=description,
            )
        )

        document["source"][
            "section"
        ] = source_section

        db.unknown_identities.insert_one(
            document
        )

        return document

    def get(
        self,
        unknown_id: str,
    ) -> dict | None:

        return db.unknown_identities.find_one(
            {
                "unknown_id": unknown_id
            },
            {
                "_id": 0
            },
        )

    def identify(
        self,
        unknown_id: str,
        person_id: str,
        confidence: float,
        method: str,
    ) -> dict | None:
        """
        Link an unknown identity to a canonical Person.

        The UnknownIdentity record is retained.
        """

        now = datetime.now(
            timezone.utc
        )

        result = (
            db.unknown_identities.find_one_and_update(
                {
                    "unknown_id": unknown_id,
                    "status": "UNIDENTIFIED",
                },
                {
                    "$set": {
                        "status": "IDENTIFIED",
                        "linked_person_id": person_id,
                        "identification": {
                            "confidence": confidence,
                            "method": method,
                            "identified_at": now,
                        },
                        "updated_at": now,
                    }
                },
                return_document=True,
            )
        )

        if result is None:
            return None

        result.pop("_id", None)

        return result