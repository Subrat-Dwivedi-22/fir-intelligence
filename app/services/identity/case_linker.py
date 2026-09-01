from datetime import datetime, timezone

from app.db.mongodb import db


class CasePersonLinker:
    """
    Maintains the relationship between a case and a canonical person.

    Authoritative relationship:
        case_persons

    Denormalized reverse lookup:
        persons.case_ids

    The operation is idempotent:
        - repeated linking does not duplicate roles
        - repeated linking does not duplicate case_ids
        - the same case/person relationship is reused
    """

    def link(
        self,
        case_id: str,
        person_id: str,
        role: str,
        document_id: str,
        confidence: float = 1.0,
    ):
        now = datetime.now(timezone.utc)

        # ==========================================
        # 1. CASE ↔ PERSON RELATIONSHIP
        # ==========================================

        db.case_persons.update_one(
            {
                "case_id": case_id,
                "person_id": person_id,
            },
            {
                "$addToSet": {
                    "roles": role,
                },
                "$set": {
                    "updated_at": now,
                    "confidence": confidence,
                },
                "$setOnInsert": {
                    "case_id": case_id,
                    "person_id": person_id,
                    "source": {
                        "document_id": document_id,
                    },
                    "created_at": now,
                },
            },
            upsert=True,
        )

        db.cases.update_one(
            {
                "case_id": case_id,
            },
            {
                "$addToSet": {
                    "person_ids": person_id,
                }
            },
        )

        # ==========================================
        # 2. PERSON → CASE REVERSE LOOKUP
        # ==========================================

        db.persons.update_one(
            {
                "person_id": person_id,
            },
            {
                "$addToSet": {
                    "case_ids": case_id,
                },
                "$set": {
                    "updated_at": now,
                },
            },
        )

        # ==========================================
        # 3. RETURN CURRENT RELATIONSHIP
        # ==========================================

        return db.case_persons.find_one(
            {
                "case_id": case_id,
                "person_id": person_id,
            },
            {
                "_id": 0,
            },
        )