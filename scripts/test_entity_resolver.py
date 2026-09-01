from app.db.mongodb import db
from app.services.entity.resolver import (
    EntityResolver,
)


resolver = EntityResolver()

CASE_A = "test-entity-case-a"
CASE_B = "test-entity-case-b"

print("=" * 60)
print("GENERIC ENTITY RESOLUTION TEST")
print("=" * 60)


# ==================================================
# 1. CREATE
# ==================================================

knife = resolver.resolve(
    entity_type="WEAPON",
    value="Knife",
    case_id=CASE_A,
    document_id="test-document-a",
)

print("\n1. CREATE")
print(knife)

assert knife["entity_id"].startswith(
    "ent_"
)

assert knife["type"] == "WEAPON"

assert knife["normalized_value"] == "knife"

assert CASE_A in knife["case_ids"]


# ==================================================
# 2. SAME ENTITY
# ==================================================

same_knife = resolver.resolve(
    entity_type="WEAPON",
    value="  knife  ",
    case_id=CASE_A,
    document_id="test-document-a",
)

print("\n2. SAME ENTITY")
print(same_knife)

assert (
    same_knife["entity_id"]
    == knife["entity_id"]
)


# ==================================================
# 3. SAME ENTITY — SECOND CASE
# ==================================================

second_case_knife = resolver.resolve(
    entity_type="WEAPON",
    value="KNIFE",
    case_id=CASE_B,
    document_id="test-document-b",
)

print("\n3. SECOND CASE")
print(second_case_knife)

assert (
    second_case_knife["entity_id"]
    == knife["entity_id"]
)

assert CASE_B in second_case_knife[
    "case_ids"
]


# ==================================================
# 4. DIFFERENT TYPE
# ==================================================

knife_location = resolver.resolve(
    entity_type="LOCATION",
    value="Knife Market",
    case_id=CASE_A,
)

print("\n4. DIFFERENT TYPE")
print(knife_location)

assert (
    knife_location["entity_id"]
    != knife["entity_id"]
)

assert knife_location["type"] == "LOCATION"


# ==================================================
# CLEANUP
# ==================================================

db.entities.delete_many(
    {
        "case_ids": {
            "$in": [
                CASE_A,
                CASE_B,
            ]
        }
    }
)

print("\n" + "=" * 60)
print("✓ ENTITY RESOLUTION TEST PASSED")
print("=" * 60)
