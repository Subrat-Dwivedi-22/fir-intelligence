from datetime import datetime, timezone

from app.db.mongodb import db
from app.models.entity import create_entity_document


class EntityRepository:

    def find_by_normalized_value(
        self,
        entity_type: str,
        normalized_value: str,
    ) -> dict | None:

        return db.entities.find_one(
            {
                "type": entity_type,
                "normalized_value": normalized_value,
            },
            {
                "_id": 0,
            },
        )

    def get_by_id(
        self,
        entity_id: str,
    ) -> dict | None:

        return db.entities.find_one(
            {
                "entity_id": entity_id,
            },
            {
                "_id": 0,
            },
        )

    def create_or_get(
        self,
        entity_type: str,
        value: str,
        normalized_value: str,
        case_id: str | None = None,
        document_id: str | None = None,
        pages: list[int] | None = None,
        confidence: float | None = None,
        metadata: dict | None = None,
    ) -> dict:

        existing = self.find_by_normalized_value(
            entity_type=entity_type,
            normalized_value=normalized_value,
        )

        if existing:

            if case_id:

                update_fields = {
                    "updated_at": datetime.now(
                        timezone.utc
                    ),
                }

                if confidence is not None:
                    update_fields["confidence"] = confidence

                # Merge metadata without overwriting existing keys
                if metadata:
                    for mk, mv in metadata.items():
                        if mv is not None:
                            update_fields[f"metadata.{mk}"] = mv

                db.entities.update_one(
                    {
                        "entity_id": existing[
                            "entity_id"
                        ],
                    },
                    {
                        "$addToSet": {
                            "case_ids": case_id,
                        },
                        "$set": update_fields,
                    },
                )

                if confidence is not None:
                    existing["confidence"] = confidence

                existing["case_ids"] = list(
                    set(
                        existing.get(
                            "case_ids",
                            [],
                        )
                        + [case_id]
                    )
                )

                if metadata:
                    existing_meta = existing.get("metadata", {})
                    existing_meta.update(metadata)
                    existing["metadata"] = existing_meta

            return existing

        document = create_entity_document(
            entity_type=entity_type,
            value=value,
            normalized_value=normalized_value,
            case_id=case_id,
            document_id=document_id,
            pages=pages,
            confidence=confidence,
            metadata=metadata,
        )

        db.entities.insert_one(
            document
        )

        return document

    def get_by_case(
        self,
        case_id: str,
    ):

        return list(
            db.entities.find(
                {
                    "case_ids": case_id,
                },
                {
                    "_id": 0,
                },
            )
        )
