import re

from app.repositories.entity_repository import (
    EntityRepository,
)


ENTITY_TYPES = {
    "WEAPON",
    "VEHICLE",
    "LOCATION",
    "ORGANIZATION",
    "PROPERTY",
    "PHONE",
    "ACCOUNT",
    "OTHER",
}


class EntityResolver:

    def __init__(self):
        self.repository = EntityRepository()

    def normalize(
        self,
        value: str,
    ) -> str:

        value = value.strip().lower()

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value

    def resolve(
        self,
        entity_type: str,
        value: str,
        case_id: str | None = None,
        document_id: str | None = None,
        pages: list[int] | None = None,
    ) -> dict:

        if not value or not value.strip():
            raise ValueError(
                "Entity value cannot be empty"
            )

        entity_type = (
            entity_type.strip().upper()
        )

        if entity_type not in ENTITY_TYPES:
            raise ValueError(
                f"Unsupported entity type: "
                f"{entity_type}"
            )

        normalized_value = self.normalize(
            value
        )

        return self.repository.create_or_get(
            entity_type=entity_type,
            value=value.strip(),
            normalized_value=normalized_value,
            case_id=case_id,
            document_id=document_id,
            pages=pages,
        )
