"""
Deterministic post-processing for Gemini DocumentExtraction payloads.

Boundary:
- Gemini performs semantic understanding.
- This module performs deterministic normalization/safety checks.
- It must never invent facts or silently merge potentially distinct facts.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


TOP_LEVEL_LIST_FIELDS = (
    "identifiers",
    "dates",
    "times",
    "phone_numbers",
    "email_addresses",
    "monetary_amounts",
    "persons",
    "organizations",
    "locations",
    "vehicles",
    "evidence_items",
    "incidents",
    "relationships",
)

UNKNOWN_ROLE_MARKERS = {
    "UNKNOWN",
    "UNKNOWN_PERSON",
    "UNKNOWN_ACCOMPLICE",
    "UNIDENTIFIED",
    "UNIDENTIFIED_PERSON",
    "PERSON_UNKNOWN",
}

PERSON_ENDPOINT_TYPES = {
    "PERSON",
    "UNKNOWN",
    "PERSON_UNKNOWN",
}


def _clean_string(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, str):
        value = " ".join(value.split())
        return value or None

    return value


def _norm_text(value: Any) -> str:
    cleaned = _clean_string(value)

    if cleaned is None:
        return ""

    return str(cleaned).casefold().strip()


def _unique_strings(values: Any) -> list[str]:
    if values is None:
        return []

    if isinstance(values, str):
        values = [values]

    if not isinstance(values, list):
        values = [values]

    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        cleaned = _clean_string(value)

        if not isinstance(cleaned, str):
            continue

        key = cleaned.casefold()

        if not key or key in seen:
            continue

        seen.add(key)
        result.append(cleaned)

    return result


def _ensure_lists(payload: dict[str, Any]) -> None:
    for field in TOP_LEVEL_LIST_FIELDS:
        value = payload.get(field)

        if value is None:
            payload[field] = []

        elif not isinstance(value, list):
            payload[field] = [value]


def _normalize_identifier(item: Any) -> Any:
    if not isinstance(item, dict):
        return item

    item = dict(item)

    if not item.get("type"):
        item["type"] = (
            item.get("identifier_type")
            or item.get("id_type")
        )

    for key in (
        "type",
        "value",
        "evidence",
    ):
        if key in item:
            item[key] = _clean_string(item[key])

    return item


def _normalize_money(item: Any) -> Any:
    if not isinstance(item, dict):
        return item

    item = dict(item)

    for key in (
        "currency",
        "original_text",
        "context",
        "evidence",
    ):
        if key in item:
            item[key] = _clean_string(item[key])

    amount = item.get("amount")

    if isinstance(amount, str):
        cleaned = amount.strip().replace(",", "")

        try:
            item["amount"] = float(cleaned)

        except ValueError:
            pass

    return item


def _normalize_person(item: Any) -> Any:
    if not isinstance(item, dict):
        return item

    item = dict(item)

    for key in (
        "name",
        "father_or_husband_name",
        "age",
        "evidence",
    ):
        if key in item:
            item[key] = _clean_string(item[key])

    for key in (
        "roles",
        "aliases",
        "phone_numbers",
        "email_addresses",
        "addresses",
    ):
        item[key] = _unique_strings(item.get(key))

    return item


def _normalize_location(item: Any) -> Any:
    if not isinstance(item, dict):
        return item

    item = dict(item)

    # Gemini may return only `address` instead of `name`.
    # This does not create a new fact; it normalizes representation.
    if not _clean_string(item.get("name")):
        address = _clean_string(item.get("address"))

        if address:
            item["name"] = address

    for key in (
        "name",
        "location_type",
        "address",
        "evidence",
    ):
        if key in item:
            item[key] = _clean_string(item[key])

    return item


def _normalize_generic_object(item: Any) -> Any:
    if not isinstance(item, dict):
        return item

    item = dict(item)

    for key, value in list(item.items()):
        if isinstance(value, str):
            item[key] = _clean_string(value)

    return item


def _build_unknown_names(
    persons: list[Any],
) -> set[str]:
    unknown_names: set[str] = set()

    for person in persons:
        if not isinstance(person, dict):
            continue

        name = _norm_text(person.get("name"))

        roles = {
            _norm_text(role).upper()
            for role in (person.get("roles") or [])
            if role
        }

        if not name:
            continue

        if name.startswith("unknown_person_"):
            unknown_names.add(name)

        if roles & UNKNOWN_ROLE_MARKERS:
            unknown_names.add(name)

        if name in {
            "unknown",
            "unidentified",
            "unknown person",
            "unidentified person",
        }:
            unknown_names.add(name)

    return unknown_names


def _normalize_relationship(
    item: Any,
    unknown_names: set[str],
) -> dict[str, Any] | None:

    if not isinstance(item, dict):
        return None

    item = dict(item)

    for key in (
        "subject",
        "subject_type",
        "predicate",
        "object",
        "object_type",
        "evidence",
    ):
        if key in item:
            item[key] = _clean_string(item[key])

    if item.get("subject_type"):
        item["subject_type"] = str(
            item["subject_type"]
        ).upper()

    if item.get("object_type"):
        item["object_type"] = str(
            item["object_type"]
        ).upper()

    subject_name = _norm_text(
        item.get("subject")
    )

    object_name = _norm_text(
        item.get("object")
    )

    # If an endpoint was explicitly extracted as an unknown person,
    # force the relationship endpoint to UNKNOWN.
    if (
        subject_name in unknown_names
        and item.get("subject_type")
        in PERSON_ENDPOINT_TYPES
    ):
        item["subject_type"] = "UNKNOWN"

    if (
        object_name in unknown_names
        and item.get("object_type")
        in PERSON_ENDPOINT_TYPES
    ):
        item["object_type"] = "UNKNOWN"

    return item


def _dedupe_scalar_lists(
    payload: dict[str, Any],
) -> None:

    for field in (
        "dates",
        "times",
        "phone_numbers",
        "email_addresses",
    ):
        payload[field] = _unique_strings(
            payload.get(field)
        )


def _dedupe_relationships(
    payload: dict[str, Any],
) -> None:

    relationships = payload.get(
        "relationships"
    ) or []

    result: list[dict[str, Any]] = []
    seen: set[
        tuple[str, str, str, str, str]
    ] = set()

    for relationship in relationships:

        if not isinstance(
            relationship,
            dict,
        ):
            continue

        key = (
            _norm_text(
                relationship.get("subject")
            ),
            str(
                relationship.get("subject_type")
                or ""
            ).upper(),
            _norm_text(
                relationship.get("predicate")
            ),
            _norm_text(
                relationship.get("object")
            ),
            str(
                relationship.get("object_type")
                or ""
            ).upper(),
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(relationship)

    payload["relationships"] = result


def _dedupe_exact_money_duplicates(
    payload: dict[str, Any],
) -> None:

    amounts = payload.get(
        "monetary_amounts"
    ) or []

    result: list[Any] = []

    seen: set[
        tuple[Any, str, str, str]
    ] = set()

    for item in amounts:

        if not isinstance(item, dict):
            result.append(item)
            continue

        amount = item.get("amount")

        currency = _norm_text(
            item.get("currency")
        )

        original_text = _norm_text(
            item.get("original_text")
        )

        evidence = _norm_text(
            item.get("evidence")
        )

        try:
            amount_key = (
                float(amount)
                if amount is not None
                else None
            )

        except (
            TypeError,
            ValueError,
        ):
            amount_key = amount

        key = (
            amount_key,
            currency,
            original_text,
            evidence,
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(item)

    payload["monetary_amounts"] = result


def normalize_extraction_payload(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Normalize a raw Gemini extraction payload before
    DocumentExtraction.model_validate().

    This function must remain deterministic and conservative.
    """

    if not isinstance(payload, dict):
        raise TypeError(
            "Document extraction payload "
            "must be a JSON object"
        )

    normalized = deepcopy(payload)

    _ensure_lists(normalized)

    normalized["document_type"] = _clean_string(
        normalized.get("document_type")
    )

    normalized["identifiers"] = [
        _normalize_identifier(item)
        for item in normalized["identifiers"]
    ]

    normalized["persons"] = [
        _normalize_person(item)
        for item in normalized["persons"]
    ]

    normalized["locations"] = [
        _normalize_location(item)
        for item in normalized["locations"]
    ]

    normalized["monetary_amounts"] = [
        _normalize_money(item)
        for item in normalized["monetary_amounts"]
    ]

    normalized["organizations"] = [
        _normalize_generic_object(item)
        for item in normalized["organizations"]
    ]

    normalized["vehicles"] = [
        _normalize_generic_object(item)
        for item in normalized["vehicles"]
    ]

    normalized["evidence_items"] = [
        _normalize_generic_object(item)
        for item in normalized["evidence_items"]
    ]

    normalized["incidents"] = [
        _normalize_generic_object(item)
        for item in normalized["incidents"]
    ]

    _dedupe_scalar_lists(normalized)

    _dedupe_exact_money_duplicates(
        normalized
    )

    unknown_names = _build_unknown_names(
        normalized["persons"]
    )

    relationships: list[dict[str, Any]] = []

    for relationship in normalized[
        "relationships"
    ]:

        clean_relationship = (
            _normalize_relationship(
                relationship,
                unknown_names,
            )
        )

        if clean_relationship is not None:
            relationships.append(
                clean_relationship
            )

    normalized["relationships"] = relationships

    _dedupe_relationships(normalized)

    return normalized