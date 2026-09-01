from fastapi import APIRouter, HTTPException

from app.db.mongodb import db
from app.api.serialization import serialize_mongo
from app.schemas.graph import CaseGraphResponse


router = APIRouter(
    prefix="/cases",
    tags=["Case Graph"],
)

@router.get(
    "/{case_id}/graph",
    response_model=CaseGraphResponse,
)
def get_case_graph(case_id: str):

    # ==========================================
    # CASE
    # ==========================================

    case = db.cases.find_one(
        {"case_id": case_id},
        {"_id": 0},
    )

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found.",
        )

    # ==========================================
    # PERSONS
    # ==========================================

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
                    "person_id": "$person.person_id",
                    "name": "$person.identity.name",
                    "aliases": "$person.identity.aliases",
                    "roles": 1,
                    "confidence": 1,
                }
            },
        ])
    )

    # ==========================================
    # UNKNOWN IDENTITIES
    # ==========================================

    unknowns = list(
        db.unknown_identities.find(
            {"case_id": case_id},
            {
                "_id": 0,
                "unknown_id": 1,
                "label": 1,
                "roles": 1,
                "status": 1,
            },
        )
    )

    # ==========================================
    # INCIDENTS
    # ==========================================

    incidents = list(
        db.incidents.find(
            {"case_id": case_id},
            {
                "_id": 0,
                "incident_id": 1,
                "title": 1,
                "description": 1,
                "time": 1,
                "location": 1,
            },
        )
    )

    # ==========================================
    # ENTITIES
    # ==========================================

    entities = list(
        db.entities.find(
            {"case_ids": case_id},
            {
                "_id": 0,
                "entity_id": 1,
                "type": 1,
                "value": 1,
            },
        )
    )

    # ==========================================
    # RELATIONSHIPS
    # ==========================================

    relationships = list(
        db.relationships.find(
            {"context.case_id": case_id},
            {
                "_id": 0,
                "relationship_id": 1,
                "from": 1,
                "to": 1,
                "type": 1,
                "evidence": 1,
                "confidence": 1,
            },
        )
    )

    # ==========================================
    # GRAPH RESPONSE
    # ==========================================

    nodes = []

    for person in persons:
        nodes.append({
            "id": person["person_id"],
            "type": "PERSON",
            "label": person.get("name"),
            "roles": person.get("roles", []),
        })

    for unknown in unknowns:
        nodes.append({
            "id": unknown["unknown_id"],
            "type": "UNKNOWN",
            "label": unknown.get("label"),
            "roles": unknown.get("roles", []),
        })

    for incident in incidents:
        nodes.append({
            "id": incident["incident_id"],
            "type": "INCIDENT",
            "label": incident.get("title"),
        })

    for entity in entities:
        nodes.append({
            "id": entity["entity_id"],
            "type": "ENTITY",
            "entity_type": entity.get("type"),
            "label": entity.get("value"),
        })

    edges = []

    for relationship in relationships:
        edges.append({
            "id": relationship["relationship_id"],
            "from": relationship["from"],
            "to": relationship["to"],
            "type": relationship["type"],
            "evidence": relationship.get("evidence"),
            "confidence": relationship.get("confidence"),
        })

    return serialize_mongo({
        "case_id": case_id,
        "nodes": nodes,
        "edges": edges,
    })