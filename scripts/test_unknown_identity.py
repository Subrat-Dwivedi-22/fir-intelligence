from app.services.identity.unknown import (
    UnknownIdentityService,
)


service = UnknownIdentityService()


result = service.create(
    case_id="test-case-001",
    label="UNKNOWN_PERSON_1",
    document_id="test-document-001",
    role="ACCUSED",
    description=(
        "Male person involved in the incident"
    ),
    source_section="accused",
)


print("\nUNKNOWN IDENTITY")
print("=" * 60)
print(
    "unknown_id:",
    result["unknown_id"],
)
print(
    "case_id:",
    result["case_id"],
)
print(
    "label:",
    result["label"],
)
print(
    "status:",
    result["status"],
)
print(
    "roles:",
    result["roles"],
)

identified = service.identify(
    unknown_id=result["unknown_id"],
    person_id="per_test_person_001",
    confidence=0.98,
    method="INVESTIGATOR_VERIFICATION",
)

print("\nIDENTIFIED")
print("=" * 60)

print(
    "unknown_id:",
    identified["unknown_id"],
)

print(
    "status:",
    identified["status"],
)

print(
    "linked_person_id:",
    identified["linked_person_id"],
)

print(
    "identification:",
    identified["identification"],
)