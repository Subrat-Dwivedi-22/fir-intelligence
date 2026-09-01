from app.db.mongodb import db


def get_case_context(
    case_id: str,
) -> dict | None:

    case = db.cases.find_one(
        {"case_id": case_id},
        {"_id": 0},
    )

    if case is None:
        return None

    persons = list(
        db.case_persons.aggregate([
            {
                "$match": {
                    "case_id": case_id,
                }
            },
            {
                "$lookup": {
                    "from": "persons",
                    "localField": "person_id",
                    "foreignField": "person_id",
                    "as": "person",
                }
            },
            {
                "$unwind": "$person",
            },
            {
                "$project": {
                    "_id": 0,
                    "person": "$person",
                    "roles": 1,
                    "confidence": 1,
                }
            },
        ])
    )

    unknowns = list(
        db.unknown_identities.find(
            {"case_id": case_id},
            {"_id": 0},
        )
    )

    incidents = list(
        db.incidents.find(
            {"case_id": case_id},
            {"_id": 0},
        )
    )

    entities = list(
        db.entities.find(
            {"case_ids": case_id},
            {"_id": 0},
        )
    )

    relationships = list(
        db.relationships.find(
            {"context.case_id": case_id},
            {"_id": 0},
        )
    )

    return {
        "case": case,
        "persons": persons,
        "unknown_identities": unknowns,
        "incidents": incidents,
        "entities": entities,
        "relationships": relationships,
    }
