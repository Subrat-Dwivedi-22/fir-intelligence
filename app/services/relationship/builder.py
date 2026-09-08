from typing import Any


class RelationshipBuilder:
    """
    Builds deterministic graph relationships from structured,
    already-extracted and already-resolved data.

    This service does NOT perform LLM inference.

    Relationships created here must be supported by explicit
    structured facts from the extraction pipeline.
    """

    # ----------------------------------------------------------
    # Generic helper
    # ----------------------------------------------------------

    @staticmethod
    def _node(
        node_type: str,
        node_id: str,
    ) -> dict[str, str]:
        return {
            "type": node_type.upper(),
            "id": node_id,
        }

    # ----------------------------------------------------------
    # Person -> Phone
    # ----------------------------------------------------------

    def build_person_phone_relationships(
        self,
        resolved_people: list[dict[str, Any]],
        phone_entities: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:

        relationships = []

        for item in resolved_people:

            result = item.get("result") or {}

            person_id = result.get("person_id")

            if not person_id:
                continue

            person = item.get("person")

            if person is None:
                continue

            for phone in person.phone_numbers or []:

                phone_value = str(phone).strip()

                if not phone_value:
                    continue

                phone_entity = phone_entities.get(
                    self._normalize(phone_value)
                )

                if not phone_entity:
                    continue

                relationships.append(
                    {
                        "from": self._node(
                            "PERSON",
                            person_id,
                        ),
                        "to": self._node(
                            "PHONE",
                            phone_entity["entity_id"],
                        ),
                        "type": "HAS_PHONE",
                        "confidence": 1.0,
                        "evidence": (
                            f"Phone number {phone_value} "
                            f"is associated with the extracted person."
                        ),
                        "derivation": "STRUCTURED_FACT",
                    }
                )

        return relationships

    # ----------------------------------------------------------
    # Person -> Generic entities
    # ----------------------------------------------------------

    def build_person_entity_relationships(
        self,
        resolved_people: list[dict[str, Any]],
        generic_entities: list[dict[str, Any]],
        extraction,
    ) -> list[dict[str, Any]]:

        relationships = []

        entity_lookup = {}

        for entity in generic_entities:

            normalized = entity.get(
                "normalized_value"
            )

            if normalized:
                entity_lookup[
                    (
                        entity.get("type"),
                        normalized,
                    )
                ] = entity

        for item in resolved_people:

            result = item.get("result") or {}

            person_id = result.get("person_id")

            if not person_id:
                continue

            person = item.get("person")

            if person is None:
                continue

            # ------------------------------------------
            # Organization relationships
            # ------------------------------------------

            for organization in (
                extraction.organizations or []
            ):

                if not organization.name:
                    continue

                entity = entity_lookup.get(
                    (
                        "ORGANIZATION",
                        self._normalize(
                            organization.name
                        ),
                    )
                )

                if not entity:
                    continue

                # IMPORTANT:
                # We do NOT create WORKS_FOR / OWNS from
                # mere co-occurrence.
                #
                # Those semantic relationships must come
                # from explicit Gemini relationship extraction.
                #
                # This section is intentionally empty unless
                # a source-backed structured field explicitly
                # tells us the relationship.
                #
                # Keeping this rule prevents hallucinated graph
                # connections.

        return relationships

    # ----------------------------------------------------------
    # Generic entity relationships
    # ----------------------------------------------------------

    def build_generic_relationships(
        self,
        generic_entities: list[dict[str, Any]],
        extraction,
        incident_id: str | None = None,
    ) -> list[dict[str, Any]]:

        relationships = []

        # Build normalized lookup
        entity_lookup = {}

        for entity in generic_entities:

            entity_type = entity.get("type")
            normalized_value = entity.get(
                "normalized_value"
            )

            if not entity_type or not normalized_value:
                continue

            entity_lookup[
                (
                    entity_type,
                    normalized_value,
                )
            ] = entity

        # ------------------------------------------------------
        # Incident -> Location
        #
        # The incident location is explicitly represented by
        # the extracted incident structure.
        # ------------------------------------------------------

        if incident_id and extraction.incidents:

            for incident in extraction.incidents:

                for location_name in (
                    incident.locations or []
                ):

                    location_name = str(
                        location_name
                    ).strip()

                    if not location_name:
                        continue

                    location_entity = entity_lookup.get(
                        (
                            "LOCATION",
                            self._normalize(
                                location_name
                            ),
                        )
                    )

                    if not location_entity:
                        continue

                    relationships.append(
                        {
                            "from": self._node(
                                "INCIDENT",
                                incident_id,
                            ),
                            "to": self._node(
                                "LOCATION",
                                location_entity[
                                    "entity_id"
                                ],
                            ),
                            "type": "OCCURRED_AT",
                            "confidence": 1.0,
                            "evidence": (
                                f"Incident location: "
                                f"{location_name}"
                            ),
                            "derivation": (
                                "STRUCTURED_FACT"
                            ),
                        }
                    )

        return relationships

    # ----------------------------------------------------------
    # Utility
    # ----------------------------------------------------------

    @staticmethod
    def _normalize(
        value: str,
    ) -> str:

        return (
            value.strip()
            .lower()
        )
