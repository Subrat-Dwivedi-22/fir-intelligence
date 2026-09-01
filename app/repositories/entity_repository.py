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
    ) -> dict:

        existing = self.find_by_normalized_value(
            entity_type=entity_type,
            normalized_value=normalized_value,
        )

        if existing:

            if case_id:

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
                        "$set": {
                            "updated_at": datetime.now(
                                timezone.utc
                            ),
                        },
                    },
                )

                existing["case_ids"] = list(
                    set(
                        existing.get(
                            "case_ids",
                            [],
                        )
                        + [case_id]
                    )
                )

            return existing

        document = create_entity_document(
            entity_type=entity_type,
            value=value,
            normalized_value=normalized_value,
            case_id=case_id,
            document_id=document_id,
            pages=pages,
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
