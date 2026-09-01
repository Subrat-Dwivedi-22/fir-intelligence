from app.db.mongodb import db
from app.repositories.relationship_repository import (
    RelationshipRepository,
)


repository = RelationshipRepository()

CASE_ID = "test-relationship-repository-case"
INCIDENT_ID = "test-relationship-repository-incident"
DOCUMENT_ID = "test-relationship-repository-document"


print("=" * 60)
print("RELATIONSHIP REPOSITORY TEST")
print("=" * 60)


# Clean previous test data
db.relationships.delete_many(
    {
        "context.case_id": CASE_ID,
    }
)


# ==================================================
# 1. CREATE
# ==================================================

first = repository.create(
    from_type="PERSON",
    from_id="per_rakesh",
    to_type="PERSON",
    to_id="per_rohit",
    relationship_type="THREATENED",
    case_id=CASE_ID,
    incident_id=INCIDENT_ID,
    document_id=DOCUMENT_ID,
    evidence="Rakesh threatened Rohit.",
)

print("\n1. CREATE")
print(first)

assert first["relationship_id"]
assert first["from"]["id"] == "per_rakesh"


# ==================================================
# 2. REPEAT SAME RELATIONSHIP
# ==================================================

second = repository.create(
    from_type="PERSON",
    from_id="per_rakesh",
    to_type="PERSON",
    to_id="per_rohit",
    relationship_type="THREATENED",
    case_id=CASE_ID,
    incident_id=INCIDENT_ID,
    document_id=DOCUMENT_ID,
    evidence="Rakesh threatened Rohit.",
)

print("\n2. REPEAT")
print(second)

assert (
    second["relationship_id"]
    == first["relationship_id"]
)


count = db.relationships.count_documents(
    {
        "context.case_id": CASE_ID,
    }
)

assert count == 1


# ==================================================
# 3. DIFFERENT RELATIONSHIP
# ==================================================

third = repository.create(
    from_type="PERSON",
    from_id="per_rakesh",
    to_type="PERSON",
    to_id="per_rohit",
    relationship_type="TARGETED",
    case_id=CASE_ID,
    incident_id=INCIDENT_ID,
    document_id=DOCUMENT_ID,
    evidence="Rakesh targeted Rohit.",
)

print("\n3. DIFFERENT RELATIONSHIP")
print(third)

assert (
    third["relationship_id"]
    != first["relationship_id"]
)


count = db.relationships.count_documents(
    {
        "context.case_id": CASE_ID,
    }
)

assert count == 2


# ==================================================
# CLEANUP
# ==================================================

db.relationships.delete_many(
    {
        "context.case_id": CASE_ID,
    }
)


print("\n" + "=" * 60)
print("✓ RELATIONSHIP REPOSITORY TEST PASSED")
print("=" * 60)
