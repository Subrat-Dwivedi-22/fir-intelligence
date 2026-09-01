from app.services.identity.unknown import (
    UnknownIdentityService,
)
from app.services.identity.case_unknown_linker import (
    CaseUnknownIdentityLinker,
)


unknown_service = UnknownIdentityService()
linker = CaseUnknownIdentityLinker()


unknown = unknown_service.create(
    case_id="test-case-unknown-001",
    label="UNKNOWN_PERSON_1",
    document_id="test-document-001",
    role="ACCUSED",
    source_section="accused",
)


print(
    "\nUNKNOWN:",
    unknown["unknown_id"],
)


first = linker.link(
    case_id="test-case-unknown-001",
    unknown_id=unknown["unknown_id"],
    role="ACCUSED",
    document_id="test-document-001",
    confidence=1.0,
)


second = linker.link(
    case_id="test-case-unknown-001",
    unknown_id=unknown["unknown_id"],
    role="ACCUSED",
    document_id="test-document-001",
    confidence=1.0,
)


print("\nFIRST LINK")
print(first)

print("\nSECOND LINK")
print(second)