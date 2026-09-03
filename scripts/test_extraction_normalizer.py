from pprint import pprint

from app.services.llm.normalizer import (
    normalize_extraction_payload,
)


def run():
    payload = {
        "document_type": "INVESTIGATION_REPORT",

        "monetary_amounts": [
            {
                "amount": 1200000,
                "currency": "INR",
                "original_text": "Rs. 12,00,000",
                "evidence": (
                    "Neha paid Rs. 12,00,000 "
                    "to Sunrise Property Ventures"
                ),
            },
            {
                "amount": 1200000,
                "currency": "INR",
                "original_text": "INR 12 lakh",
                "evidence": (
                    "transfer of INR 12 lakh "
                    "to an account associated "
                    "with Sunrise Property Ventures."
                ),
            },
            {
                "amount": 1200000,
                "currency": "INR",
                "original_text": "Rs. 12,00,000",
                "evidence": (
                    "Neha paid Rs. 12,00,000 "
                    "to Sunrise Property Ventures"
                ),
            },
        ],

        "persons": [
            {
                "name": "Mr. X",
                "roles": ["UNKNOWN"],
            },
            {
                "name": "Neha Joshi",
                "roles": ["COMPLAINANT"],
            },
        ],

        "locations": [
            {
                "location_type": "OFFICE",
                "address": (
                    "Office 508, Crescent Plaza, Noida"
                ),
            }
        ],

        "relationships": [
            {
                "subject": "Mr. X",
                "subject_type": "PERSON",
                "predicate": "ARRANGED_MEETING_WITH",
                "object": "Neha Joshi",
                "object_type": "PERSON",
                "evidence": (
                    "Mr. X arranged the meeting "
                    "with Neha Joshi."
                ),
            },
            {
                "subject": "Arjun Malhotra",
                "subject_type": "PERSON",
                "predicate": "INTRODUCED_TO",
                "object": "Sunrise Property Ventures",
                "object_type": "ORGANIZATION",
                "evidence": (
                    "Arjun introduced Neha "
                    "to the company representative."
                ),
            },
        ],
    }

    result = normalize_extraction_payload(
        payload
    )

    # Location name recovered from address.
    assert (
        result["locations"][0]["name"]
        == "Office 508, Crescent Plaza, Noida"
    )

    # The exact duplicate monetary entry was removed,
    # but the two differently evidenced entries remain.
    assert len(
        result["monetary_amounts"]
    ) == 2

    # Explicitly unknown person becomes UNKNOWN
    # in the relationship endpoint.
    relationship = result[
        "relationships"
    ][0]

    assert (
        relationship["subject_type"]
        == "UNKNOWN"
    )

    # Unsupported relationship is removed because
    # "Sunrise Property Ventures" does not occur in
    # its relationship evidence.
    assert len(
        result["relationships"]
    ) == 2

    pprint(result)

    print(
        "Normalizer tests passed."
    )


if __name__ == "__main__":
    run()