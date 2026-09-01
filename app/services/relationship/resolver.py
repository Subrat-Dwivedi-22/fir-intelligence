from app.services.entity.resolver import (
    ENTITY_TYPES,
    EntityResolver,
)
from app.services.extraction.models import (
    ExtractedPerson,
)
from app.services.identity.normalizer import (
    normalize_name,
)


PERSON = "PERSON"
UNKNOWN = "UNKNOWN"
INCIDENT = "INCIDENT"


SUPPORTED_TYPES = {
    PERSON,
    UNKNOWN,
    INCIDENT,
    *ENTITY_TYPES,
}


class RelationshipResolver:

    """
    Resolve an LLM relationship candidate into canonical
    graph endpoints.

    The LLM supplies semantic entity references.

    This service is responsible for converting those
    references into canonical IDs.

    It never invents identities.
    """

    def __init__(self):
        self.entity_resolver = EntityResolver()

    def resolve_candidate(
        self,
        candidate,
        resolved_people: list[dict],
        resolved_unknowns: list[dict],
        case_id: str,
        document_id: str,
        incident_id: str | None = None,
    ) -> dict:

        subject = self._resolve_endpoint(
            value=candidate.subject,
            entity_type=candidate.subject_type,
            resolved_people=resolved_people,
            resolved_unknowns=resolved_unknowns,
            case_id=case_id,
            document_id=document_id,
            incident_id=incident_id,
        )

        if subject is None:
            return {
                "status": "UNRESOLVED",
                "reason": "SUBJECT_NOT_RESOLVED",
                "candidate": candidate,
            }

        object_endpoint = self._resolve_endpoint(
            value=candidate.object,
            entity_type=candidate.object_type,
            resolved_people=resolved_people,
            resolved_unknowns=resolved_unknowns,
            case_id=case_id,
            document_id=document_id,
            incident_id=incident_id,
        )

        if object_endpoint is None:
            return {
                "status": "UNRESOLVED",
                "reason": "OBJECT_NOT_RESOLVED",
                "candidate": candidate,
            }

        return {
            "status": "RESOLVED",

            "from": subject,

            "to": object_endpoint,

            "type": candidate.predicate.strip().upper(),

            "evidence": candidate.evidence,
        }

    # ==================================================
    # ENDPOINT
    # ==================================================

    def _resolve_endpoint(
        self,
        value: str,
        entity_type: str,
        resolved_people: list[dict],
        resolved_unknowns: list[dict],
        case_id: str,
        document_id: str,
        incident_id: str | None = None,
    ) -> dict | None:

        if not value:
            return None

        entity_type = (
            entity_type.strip().upper()
        )

        if entity_type not in SUPPORTED_TYPES:
            return None

        # ==============================================
        # PERSON
        # ==============================================

        if entity_type == PERSON:

            return self._resolve_person(
                value=value,
                resolved_people=resolved_people,
            )

        # ==============================================
        # UNKNOWN
        # ==============================================

        if entity_type == UNKNOWN:

            return self._resolve_unknown(
                value=value,
                resolved_unknowns=resolved_unknowns,
            )

        # ==============================================
        # INCIDENT
        # ==============================================

        if entity_type == INCIDENT:

            if not incident_id:
                return None

            normalized = normalize_name(
                value
            )

            if normalized in {
                "incident",
                "the incident",
                "this incident",
            }:
                return {
                    "type": "INCIDENT",
                    "id": incident_id,
                }

            return None

        # ==============================================
        # GENERIC ENTITY
        # ==============================================

        entity = self.entity_resolver.resolve(
            entity_type=entity_type,
            value=value,
            case_id=case_id,
            document_id=document_id,
        )

        return {
            "type": "ENTITY",
            "id": entity["entity_id"],
        }

    # ==================================================
    # PERSON
    # ==================================================

    @staticmethod
    def _resolve_person(
        value: str,
        resolved_people: list[dict],
    ) -> dict | None:

        normalized = normalize_name(
            value
        )

        if not normalized:
            return None

        # ==============================================
        # ROLE REFERENCE
        # ==============================================

        role_map = {
            "complainant": "COMPLAINANT",
            "informant": "COMPLAINANT",
            "victim": "VICTIM",
            "accused": "ACCUSED",
        }

        role = role_map.get(
            normalized
        )

        if role:

            matches = []

            for item in resolved_people:

                if item["role"] != role:
                    continue

                result = item["result"]

                if result["match_type"] in {
                    "MATCHED",
                    "NEW",
                }:
                    matches.append(
                        result["person_id"]
                    )

            # A role reference must resolve
            # unambiguously.

            if len(matches) == 1:

                return {
                    "type": "PERSON",
                    "id": matches[0],
                }

            return None

        # ==============================================
        # NAME / ALIAS
        # ==============================================

        for item in resolved_people:

            person: ExtractedPerson = (
                item["person"]
            )

            result = item["result"]

            if result["match_type"] not in {
                "MATCHED",
                "NEW",
            }:
                continue

            # ------------------------------------------
            # Full name
            # ------------------------------------------

            if normalize_name(
                person.name
            ) == normalized:

                return {
                    "type": "PERSON",
                    "id": result["person_id"],
                }

            # ------------------------------------------
            # Aliases
            # ------------------------------------------

            for alias in person.aliases:

                if normalize_name(
                    alias
                ) == normalized:

                    return {
                        "type": "PERSON",
                        "id": result["person_id"],
                    }

        return None

    # ==================================================
    # UNKNOWN
    # ==================================================

    @staticmethod
    def _resolve_unknown(
        value: str,
        resolved_unknowns: list[dict],
    ) -> dict | None:

        normalized = normalize_name(
            value
        )

        if not normalized:
            return None

        for item in resolved_unknowns:

            unknown = item["unknown"]

            label = unknown.get(
                "label"
            )

            if normalize_name(
                label
            ) != normalized:
                continue

            return {
                "type": "UNKNOWN",
                "id": unknown[
                    "unknown_id"
                ],
            }

        return None
