from app.db.mongodb import db

from app.services.case.aggregation import (
    CaseAggregationService,
)


CASE_ID = "68a92354-e965-4ac0-b840-f7dd76a88ed0"


service = CaseAggregationService()

print("=" * 60)
print("CASE AGGREGATION TEST")
print("=" * 60)

result = service.get_case(
    CASE_ID
)

assert result is not None

print("\nCASE")
print(result["case"]["case_id"])

print("\nPERSONS")
for person in result["persons"]:
    print(
        person.get("person_id"),
        person.get("identity", {}).get("name"),
    )

print("\nUNKNOWN IDENTITIES")
for unknown in result["unknown_identities"]:
    print(
        unknown["unknown_id"],
        unknown["label"],
    )

print("\nINCIDENTS")
for incident in result["incidents"]:
    print(
        incident["incident_id"],
        incident.get("title"),
    )

print("\nENTITIES")
for entity in result["entities"]:
    print(
        entity["entity_id"],
        entity["type"],
        entity["value"],
    )

print("\nRELATIONSHIPS")
for relationship in result["relationships"]:
    print(
        relationship["from"],
        relationship["type"],
        relationship["to"],
    )

print("\nDOCUMENTS")
for document in result["documents"]:
    print(
        document["document_id"]
    )

print("\n" + "=" * 60)
print("✓ CASE AGGREGATION TEST PASSED")
print("=" * 60)
