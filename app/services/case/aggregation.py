from app.db.mongodb import db

from app.repositories.incident_repository import (
    IncidentRepository,
)

from app.repositories.relationship_repository import (
    RelationshipRepository,
)


class CaseAggregationService:

    def __init__(self):

        self.incident_repository = (
            IncidentRepository()
        )

        self.relationship_repository = (
            RelationshipRepository()
        )

    def get_case(
        self,
        case_id: str,
    ) -> dict | None:

        case = db.cases.find_one(
            {
                "case_id": case_id,
            },
            {
                "_id": 0,
            },
        )

        if case is None:
            return None

        persons = list(
            db.case_persons.find(
                {
                    "case_id": case_id,
                },
                {
                    "_id": 0,
                },
            )
        )

        person_ids = [
            item["person_id"]
            for item in persons
        ]

        canonical_persons = list(
            db.persons.find(
                {
                    "person_id": {
                        "$in": person_ids
                    }
                },
                {
                    "_id": 0,
                },
            )
        )

        unknowns = list(
            db.unknown_identities.find(
                {
                    "case_id": case_id,
                },
                {
                    "_id": 0,
                },
            )
        )

        incidents = (
            self.incident_repository.get_by_case(
                case_id
            )
        )

        entities = list(
            db.entities.find(
                {
                    "case_ids": case_id,
                },
                {
                    "_id": 0,
                },
            )
        )

        relationships = (
            self.relationship_repository.get_by_case(
                case_id
            )
        )

        documents = list(
            db.documents.find(
                {
                    "case_id": case_id,
                },
                {
                    "_id": 0,
                },
            )
        )

        return {
            "case": case,
            "persons": canonical_persons,
            "case_persons": persons,
            "unknown_identities": unknowns,
            "incidents": incidents,
            "entities": entities,
            "relationships": relationships,
            "documents": documents,
        }
