from app.db.mongodb import db

from app.services.extraction.models import (
    ExtractedPerson,
)
from app.services.relationship.resolver import (
    RelationshipResolver,
)
from app.services.llm.models import (
    RelationshipCandidate,
)


resolver = RelationshipResolver()

CASE_ID = "test-relationship-case"
DOCUMENT_ID = "test-relationship-document"


rakesh = ExtractedPerson(
    name="Rakesh",
    role="ACCUSED",
    aliases=["Raka"],
    father_name="Suresh Jadhav",
    addresses=[
        "Rasta Peth, Pune"
    ],
    source_section="accused",
)

rohit = ExtractedPerson(
    name="Rohit Anil Deshmukh",
    role="COMPLAINANT",
    father_name="Anil Deshmukh",
    phone_numbers=[
        "9876543210"
    ],
    source_section="complainant",
)


rakesh_id = "per_test_rakesh"
rohit_id = "per_test_rohit"

resolved_people = [
    {
        "person": rakesh,
        "role": "ACCUSED",
        "result": {
            "person_id": rakesh_id,
            "match_type": "NEW",
        },
    },
    {
        "person": rohit,
        "role": "COMPLAINANT",
        "result": {
            "person_id": rohit_id,
            "match_type": "NEW",
        },
    },
]


resolved_unknowns = [
    {
        "unknown": {
            "unknown_id": "unk_test_001",
            "label": "UNKNOWN_PERSON_1",
        },
        "role": "ACCUSED",
    }
]


print("=" * 60)
print("RELATIONSHIP RESOLUTION TEST")
print("=" * 60)


# ==================================================
# 1. PERSON → PERSON
# ==================================================

candidate = RelationshipCandidate(
    subject="Rakesh",
    subject_type="PERSON",
    predicate="THREATENED",
    object="complainant",
    object_type="PERSON",
    evidence=(
        "Rakesh threatened the complainant "
        "with a knife."
    ),
)

result = resolver.resolve_candidate(
    candidate=candidate,
    resolved_people=resolved_people,
    resolved_unknowns=resolved_unknowns,
    case_id=CASE_ID,
    document_id=DOCUMENT_ID,
)

print("\n1. PERSON → PERSON")
print(result)

assert result["status"] == "RESOLVED"
assert result["from"] == {
    "type": "PERSON",
    "id": rakesh_id,
}
assert result["to"] == {
    "type": "PERSON",
    "id": rohit_id,
}


# ==================================================
# 2. PERSON → GENERIC ENTITY
# ==================================================

candidate = RelationshipCandidate(
    subject="Rakesh",
    subject_type="PERSON",
    predicate="USED",
    object="knife",
    object_type="WEAPON",
    evidence=(
        "Rakesh used a knife."
    ),
)

result = resolver.resolve_candidate(
    candidate=candidate,
    resolved_people=resolved_people,
    resolved_unknowns=resolved_unknowns,
    case_id=CASE_ID,
    document_id=DOCUMENT_ID,
)

print("\n2. PERSON → ENTITY")
print(result)

assert result["status"] == "RESOLVED"
assert result["from"]["id"] == rakesh_id
assert result["to"]["type"] == "ENTITY"

weapon_id = result["to"]["id"]


# ==================================================
# 3. UNKNOWN → PERSON
# ==================================================

candidate = RelationshipCandidate(
    subject="UNKNOWN_PERSON_1",
    subject_type="UNKNOWN",
    predicate="TARGETED",
    object="Rakesh",
    object_type="PERSON",
    evidence=(
        "An unidentified person targeted Rakesh."
    ),
)

result = resolver.resolve_candidate(
    candidate=candidate,
    resolved_people=resolved_people,
    resolved_unknowns=resolved_unknowns,
    case_id=CASE_ID,
    document_id=DOCUMENT_ID,
)

print("\n3. UNKNOWN → PERSON")
print(result)

assert result["status"] == "RESOLVED"

assert result["from"] == {
    "type": "UNKNOWN",
    "id": "unk_test_001",
}

assert result["to"]["id"] == rakesh_id


# ==================================================
# 4. ALIAS
# ==================================================

candidate = RelationshipCandidate(
    subject="Raka",
    subject_type="PERSON",
    predicate="USED",
    object="knife",
    object_type="WEAPON",
    evidence="Raka used a knife.",
)

result = resolver.resolve_candidate(
    candidate=candidate,
    resolved_people=resolved_people,
    resolved_unknowns=resolved_unknowns,
    case_id=CASE_ID,
    document_id=DOCUMENT_ID,
)

print("\n4. ALIAS")
print(result)

assert result["status"] == "RESOLVED"
assert result["from"]["id"] == rakesh_id


# ==================================================
# 5. CANDIDATE PERSON MUST NOT RESOLVE
# ==================================================

candidate_person = ExtractedPerson(
    name="Mangesh",
    role="ACCUSED",
)

candidate_people = [
    {
        "person": candidate_person,
        "role": "ACCUSED",
        "result": {
            "person_id": "per_candidate",
            "match_type": "CANDIDATE",
        },
    }
]

candidate = RelationshipCandidate(
    subject="Mangesh",
    subject_type="PERSON",
    predicate="KNOWS",
    object="Rakesh",
    object_type="PERSON",
    evidence="Mangesh knows Rakesh.",
)

result = resolver.resolve_candidate(
    candidate=candidate,
    resolved_people=candidate_people + resolved_people,
    resolved_unknowns=resolved_unknowns,
    case_id=CASE_ID,
    document_id=DOCUMENT_ID,
)

print("\n5. CANDIDATE MUST NOT RESOLVE")
print(result)

assert result["status"] == "UNRESOLVED"

# ==================================================
# 6. INCIDENT → LOCATION
# ==================================================

INCIDENT_ID = "incident_test_001"

candidate = RelationshipCandidate(
    subject="incident",
    subject_type="INCIDENT",
    predicate="OCCURRED_AT",
    object="Vaibhav Restaurant",
    object_type="LOCATION",
    evidence=(
        "The incident occurred near Vaibhav Restaurant."
    ),
)

result = resolver.resolve_candidate(
    candidate=candidate,
    resolved_people=resolved_people,
    resolved_unknowns=resolved_unknowns,
    case_id=CASE_ID,
    document_id=DOCUMENT_ID,
    incident_id=INCIDENT_ID,
)

print("\n6. INCIDENT → LOCATION")
print(result)

assert result["status"] == "RESOLVED"

assert result["from"] == {
    "type": "INCIDENT",
    "id": INCIDENT_ID,
}

assert result["to"]["type"] == "ENTITY"

assert result["to"]["id"]


# ==================================================
# CLEANUP
# ==================================================

db.entities.delete_many(
    {
        "case_ids": CASE_ID
    }
)


print("\n" + "=" * 60)
print("✓ ALL RELATIONSHIP RESOLUTION TESTS PASSED")
print("=" * 60)
