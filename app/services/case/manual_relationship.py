from app.db.mongodb import db

from app.repositories.relationship_repository import (
    RelationshipRepository,
)


class ManualRelationshipService:

    def __init__(self):
        self.relationship_repository = RelationshipRepository()

    def _resolve_entity(
        self,
        case_id: str,
        name: str,
    ) -> tuple[str, str] | None:

        normalized_name = name.strip().lower()

        # ------------------------------------------
        # Known person
        # ------------------------------------------

        person = db.persons.find_one(
            {
                "case_ids": case_id,
                "identity.normalized_name": normalized_name,
            },
            {
                "_id": 0,
                "person_id": 1,
            },
        )

        if person:
            return "PERSON", person["person_id"]

        # ------------------------------------------
        # Unknown identity
        # ------------------------------------------

        unknown = db.unknown_identities.find_one(
            {
                "case_id": case_id,
                "label": {
                    "$regex": f"^{name.strip()}$",
                    "$options": "i",
                },
            },
            {
                "_id": 0,
                "unknown_id": 1,
            },
        )

        if unknown:
            return "UNKNOWN", unknown["unknown_id"]

        # ------------------------------------------
        # Other entities
        # ------------------------------------------

        entity = db.entities.find_one(
            {
                "case_ids": case_id,
                "value": {
                    "$regex": f"^{name.strip()}$",
                    "$options": "i",
                },
            },
            {
                "_id": 0,
                "entity_id": 1,
                "type": 1,
            },
        )

        if entity:
            return (
                entity.get("type") or "ENTITY",
                entity["entity_id"],
            )

        return None

    def create(
        self,
        case_id: str,
        source: str,
        target: str,
        relationship_type: str,
        evidence: str,
    ) -> dict:

        source_entity = self._resolve_entity(
            case_id,
            source,
        )

        if source_entity is None:
            raise ValueError(
                f"Source entity not found in case: {source}"
            )

        target_entity = self._resolve_entity(
            case_id,
            target,
        )

        if target_entity is None:
            raise ValueError(
                f"Target entity not found in case: {target}"
            )

        from_type, from_id = source_entity
        to_type, to_id = target_entity

        return self.relationship_repository.create_manual(
            case_id=case_id,
            from_type=from_type,
            from_id=from_id,
            to_type=to_type,
            to_id=to_id,
            relationship_type=relationship_type.strip().upper(),
            evidence=evidence.strip(),
        )
