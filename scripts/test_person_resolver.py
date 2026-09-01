import uuid

from app.db.mongodb import db
from app.services.extraction.models import ExtractedPerson
from app.services.identity.resolver import PersonResolver
from app.services.person_identity import generate_person_id
from app.models.person import create_person_document


resolver = PersonResolver()

TEST_PREFIX = f"resolver-test-{uuid.uuid4()}"


def create_test_person(
    name: str,
    father_name: str,
    date_of_birth: str,
    phone: str | None = None,
    address: str | None = None,
):
    """
    Create a controlled canonical person for resolver testing.

    This avoids depending on real FIR data.
    """

    person_id = generate_person_id()

    document = create_person_document(
        person_id=person_id,
        name=name,
    )

    document["identity"]["normalized_name"] = (
        name.lower()
    )

    document["identity"]["father_name"] = (
        father_name
    )

    document["identity"]["date_of_birth"] = (
        date_of_birth
    )

    document["identity_resolution"] = {
        "status": "PROVISIONAL",
        "method": "TEST",
        "confidence": 0.0,
    }

    if phone:
        document["contact"]["phones"] = [
            phone
        ]

    if address:
        document["addresses"] = [
            {
                "text": address,
                "normalized": address.lower(),
            }
        ]

    db.persons.insert_one(document)

    return document


def assert_result(
    result: dict,
    expected_type: str,
):
    actual = result["match_type"]

    assert actual == expected_type, (
        f"Expected {expected_type}, "
        f"got {actual}: {result}"
    )


try:

    # ==========================================================
    # TEST DATA
    # ==========================================================

    test_person = create_test_person(
        name="Test Rakesh",
        father_name="Test Suresh",
        date_of_birth="01/01/1998",
        phone="9999999999",
        address="Test Address, Pune",
    )

    person_id = test_person["person_id"]

    print("\n" + "=" * 60)
    print("PERSON RESOLUTION TEST")
    print("=" * 60)

    print(
        f"Test canonical person: {person_id}"
    )

    # ==========================================================
    # 1. PHONE MATCH
    # ==========================================================

    person = ExtractedPerson(
        name="Completely Different Name",
        role="ACCUSED",
        phone_numbers=["9999999999"],
    )

    result = resolver.resolve(person)

    print("\n1. PHONE MATCH")
    print(result)

    assert_result(
        result,
        "MATCHED",
    )

    assert (
        result["person_id"]
        == person_id
    )

    assert (
        result["match_method"]
        == "PHONE"
    )

    # ==========================================================
    # 2. NAME + FATHER + DOB
    # ==========================================================

    person = ExtractedPerson(
        name="Test Rakesh",
        role="ACCUSED",
        father_name="Test Suresh",
        date_of_birth="01/01/1998",
    )

    result = resolver.resolve(person)

    print("\n2. DEMOGRAPHIC MATCH")
    print(result)

    assert_result(
        result,
        "MATCHED",
    )

    assert (
        result["person_id"]
        == person_id
    )

    assert (
        result["match_method"]
        == "DEMOGRAPHIC"
    )

    # ==========================================================
    # 3. NAME + FATHER + ADDRESS, NO DOB
    # ==========================================================

    person = ExtractedPerson(
        name="Test Rakesh",
        role="ACCUSED",
        father_name="Test Suresh",
        addresses=[
            "Test Address, Pune"
        ],
    )

    result = resolver.resolve(person)

    print("\n3. CANDIDATE — NO DOB")
    print(result)

    assert_result(
        result,
        "CANDIDATE",
    )

    # ==========================================================
    # 4. SAME NAME + FATHER + WRONG DOB
    # ==========================================================

    person = ExtractedPerson(
        name="Test Rakesh",
        role="ACCUSED",
        father_name="Test Suresh",
        date_of_birth="10/10/2000",
        addresses=[
            "Test Address, Pune"
        ],
    )

    result = resolver.resolve(person)

    print("\n4. WRONG DOB")
    print(result)

    # It must NOT automatically match.
    assert result["match_type"] != "MATCHED"

    # ==========================================================
    # 5. NAME ONLY
    # ==========================================================

    person = ExtractedPerson(
        name="Test Rakesh",
        role="ACCUSED",
    )

    result = resolver.resolve(person)

    print("\n5. NAME ONLY")
    print(result)

    assert_result(
        result,
        "CANDIDATE",
    )

    # ==========================================================
    # 6. COMPLETELY NEW PERSON
    # ==========================================================

    person = ExtractedPerson(
        name=TEST_PREFIX,
        role="ACCUSED",
        father_name="Nobody",
    )

    result = resolver.resolve(person)

    print("\n6. NEW PERSON")
    print(result)

    assert_result(
        result,
        "NEW",
    )

    assert result["created"] is True

    new_person_id = result["person_id"]

    # ==========================================================
    # 7. UNKNOWN PERSON MUST NOT GO THROUGH RESOLVER
    # ==========================================================

    person = ExtractedPerson(
        name="UNKNOWN_PERSON_99",
        role="ACCUSED",
    )

    try:
        resolver.resolve(person)

        raise AssertionError(
            "UNKNOWN_PERSON should have "
            "been rejected by PersonResolver"
        )

    except ValueError:
        print(
            "\n7. UNKNOWN PERSON"
        )
        print(
            "✓ Correctly rejected by "
            "PersonResolver"
        )

    # ==========================================================
    # SUCCESS
    # ==========================================================

    print("\n" + "=" * 60)
    print("✓ ALL PERSON RESOLUTION TESTS PASSED")
    print("=" * 60)


finally:

    # ==========================================================
    # CLEANUP
    # ==========================================================

    db.persons.delete_many(
        {
            "identity_resolution.method": "TEST"
        }
    )

    # Remove the NEW test person as well.
    if "new_person_id" in locals():

        db.persons.delete_one(
            {
                "person_id": new_person_id
            }
        )

    print(
        "\n✓ Resolver test data cleaned up"
    )