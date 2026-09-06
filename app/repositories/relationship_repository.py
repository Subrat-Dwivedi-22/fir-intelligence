from datetime import datetime, timezone

from app.db.mongodb import db
from app.models.relationship import (
    create_relationship,
)
from app.services.relationship.weight import relationship_weight


class RelationshipRepository:

    def create(
        self,
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
    ) -> dict:

        now = datetime.now(timezone.utc)

        # ------------------------------------------
        # Relationship identity
        #
        # One logical relationship per:
        #
        # case + incident + source document +
        # from + to + relationship type
        #
        # Evidence is deliberately NOT part of the
        # identity because repeated processing of the
        # same FIR must not create duplicate graph edges.
        # ------------------------------------------

        query = {
            "context.case_id": case_id,
            "context.incident_id": incident_id,
            "source.document_id": document_id,
            "from.type": from_type,
            "from.id": from_id,
            "to.type": to_type,
            "to.id": to_id,
            "type": relationship_type,
        }

        existing = db.relationships.find_one(
            query,
            {
                "_id": 0,
            },
        )

        if existing:

            update = {
                "updated_at": now,
                "weight": relationship_weight(relationship_type),
            }

            if evidence:
                update["evidence"] = evidence

            if confidence is not None:
                update["confidence"] = confidence

            if pages:
                update["source.pages"] = pages

            db.relationships.update_one(
                query,
                {
                    "$set": update,
                },
            )

            existing.update(update)

            return existing


        # ------------------------------------------
        # Create new relationship
        # ------------------------------------------

        relationship = create_relationship(
            from_type=from_type,
            from_id=from_id,
            to_type=to_type,
            to_id=to_id,
            relationship_type=relationship_type,
            case_id=case_id,
            incident_id=incident_id,
            document_id=document_id,
            pages=pages,
            confidence=confidence,
            evidence=evidence,
            weight=relationship_weight(relationship_type),
        )

        db.relationships.insert_one(
            relationship
        )

        relationship.pop(
            "_id",
            None,
        )

        return relationship

    # ==================================================
    # QUERIES
    # ==================================================

    def get_by_case(
        self,
        case_id: str,
    ):

        return list(
            db.relationships.find(
                {
                    "context.case_id": case_id,
                },
                {
                    "_id": 0,
                },
            )
        )

    def get_by_incident(
        self,
        incident_id: str,
    ):

        return list(
            db.relationships.find(
                {
                    "context.incident_id": incident_id,
                },
                {
                    "_id": 0,
                },
            )
        )

    def get_from_entity(
        self,
        entity_type: str,
        entity_id: str,
    ):

        return list(
            db.relationships.find(
                {
                    "from.type": entity_type,
                    "from.id": entity_id,
                },
                {
                    "_id": 0,
                },
            )
        )

    def get_to_entity(
        self,
        entity_type: str,
        entity_id: str,
    ):

        return list(
            db.relationships.find(
                {
                    "to.type": entity_type,
                    "to.id": entity_id,
                },
                {
                    "_id": 0,
                },
            )
        )

    def create_manual(
        self,
        case_id: str,
        from_type: str,
        from_id: str,
        to_type: str,
        to_id: str,
        relationship_type: str,
        evidence: str,
    ) -> dict:
        return self.create(
            from_type=from_type,
            from_id=from_id,
            to_type=to_type,
            to_id=to_id,
            relationship_type=relationship_type,
            case_id=case_id,
            incident_id=None,
            document_id=None,
            evidence=evidence,
        )    
