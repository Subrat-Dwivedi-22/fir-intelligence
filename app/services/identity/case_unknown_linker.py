from datetime import datetime, timezone

from app.db.mongodb import db
from app.models.case_unknown_identity import (
    create_case_unknown_identity,
)


class CaseUnknownIdentityLinker:
    """
    Links a case-specific UnknownIdentity to a Case.

    The operation is idempotent:
    repeated worker processing must not create duplicate links.
    """

    def link(
        self,
        case_id: str,
        unknown_id: str,
        role: str,
        document_id: str | None = None,
        pages: list[int] | None = None,
        confidence: float | None = None,
    ) -> dict:

        now = datetime.now(timezone.utc)

        existing = db.case_unknown_identities.find_one(
            {
                "case_id": case_id,
                "unknown_id": unknown_id,
            }
        )

        if existing:
            db.case_unknown_identities.update_one(
                {
                    "case_id": case_id,
                    "unknown_id": unknown_id,
                },
                {
                    "$addToSet": {
                        "roles": role,
                    },
                    "$set": {
                        "updated_at": now,
                    },
                },
            )

            existing["roles"] = list(
                set(existing.get("roles", []) + [role])
            )
            existing["updated_at"] = now

            return existing

        document = create_case_unknown_identity(
            case_id=case_id,
            unknown_id=unknown_id,
            role=role,
            document_id=document_id,
            pages=pages,
            confidence=confidence,
        )

        document["updated_at"] = now

        db.case_unknown_identities.insert_one(
            document
        )

        return document