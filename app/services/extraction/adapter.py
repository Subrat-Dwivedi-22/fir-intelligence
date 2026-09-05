from app.services.extraction.models import (
    ExtractedFIR,
    ExtractedIncident,
    ExtractedPerson,
    ExtractedProperty,
)

from app.services.llm.models import DocumentExtraction


class DocumentExtractionAdapter:
    """
    Converts Gemini's universal DocumentExtraction model into
    the existing extraction domain models used by identity,
    relationship, and persistence services.

    Gemini is responsible for understanding document semantics.

    This adapter is responsible only for translating Gemini's
    result into the existing application contracts.
    """

    def adapt(
        self,
        extraction: DocumentExtraction,
    ) -> ExtractedFIR:
        """
        Convert a complete Gemini document extraction into
        the existing ExtractedFIR compatibility model.
        """

        fir = ExtractedFIR()

        self._adapt_identifiers(
            extraction,
            fir,
        )

        self._adapt_people(
            extraction,
            fir,
        )

        self._adapt_incident(
            extraction,
            fir,
        )

        self._adapt_properties(
            extraction,
            fir,
        )

        return fir

    # ============================================================
    # IDENTIFIERS
    # ============================================================

    def _adapt_identifiers(
        self,
        extraction: DocumentExtraction,
        fir: ExtractedFIR,
    ) -> None:
        """
        Map Gemini identifiers into the existing FIR fields.
        """

        for identifier in extraction.identifiers:

            if not identifier.type:
                continue

            if not identifier.value:
                continue

            identifier_type = (
                identifier.type
                .strip()
                .lower()
            )

            value = (
                identifier.value
                .strip()
            )

            if not value:
                continue

            if identifier_type in {
                "fir number",
                "fir_number",
                "fir no",
                "fir no.",
                "fir",
            }:

                fir.fir_number = value

            elif identifier_type in {
                "gd entry number",
                "gd_entry_number",
                "gd entry",
                "gd entry no",
                "gd entry no.",
            }:

                fir.gd_entry_number = value

            elif identifier_type in {
                "police station",
                "police_station",
                "station",
            }:

                fir.police_station = value

            elif identifier_type in {
                "district",
            }:

                fir.district = value

    # ============================================================
    # PEOPLE
    # ============================================================

    def _adapt_people(
        self,
        extraction: DocumentExtraction,
        fir: ExtractedFIR,
    ) -> None:
        """
        Convert Gemini people into the compatibility model.

        Important:

        We preserve semantic roles where possible.

        We do NOT assume that every person is accused.
        """

        for person in extraction.persons:

            if not person.name:
                continue

            name = person.name.strip()

            if not name:
                continue

            roles = {
                role.strip().upper()
                for role in (person.roles or [])
                if role and role.strip()
            }

            role = self._primary_role(
                roles
            )

            extracted_person = (
                self.person_to_domain(
                    person=person,
                    role=role,
                )
            )

            # ------------------------------------------
            # Complainant / informant
            # ------------------------------------------

            if role == "COMPLAINANT":

                if fir.complainant is None:

                    fir.complainant = (
                        extracted_person
                    )

                else:
                    fir.accused.append(
                        extracted_person
                    )

                continue

            # ------------------------------------------
            # Everyone else is preserved in the
            # compatibility list.
            #
            # The actual semantic role is retained on
            # ExtractedPerson.role and the new pipeline
            # uses that role when linking to the case.
            # ------------------------------------------

            fir.accused.append(
                extracted_person
            )

    # ============================================================
    # PERSON CONVERSION
    # ============================================================

    def person_to_domain(
        self,
        person,
        role: str,
    ) -> ExtractedPerson:
        """
        Convert one Gemini semantic person into the existing
        ExtractedPerson domain object.

        This method intentionally does not perform identity
        resolution. That remains PersonResolver's responsibility.
        """

        return ExtractedPerson(
            name=person.name.strip(),
            role=role,
            aliases=list(
                person.aliases or []
            ),
            father_name=(
                person.father_or_husband_name
            ),
            approximate_age=(
                person.age
            ),
            phone_numbers=list(
                person.phone_numbers or []
            ),
            addresses=list(
                person.addresses or []
            ),
            source_section=(
                "semantic_extraction"
            ),
        )

    # ============================================================
    # ROLE MAPPING
    # ============================================================

    @staticmethod
    def _primary_role(
        roles: set[str],
    ) -> str:
        """
        Select the primary application role from Gemini's
        semantic roles.

        This is only a compatibility mapping.

        The original Gemini roles remain available in the
        raw document extraction stored separately.
        """

        priority = [
            "COMPLAINANT",
            "INFORMANT",
            "ACCUSED",
            "VICTIM",
            "WITNESS",
            "KEY_OPERATOR",
            "UNKNOWN_ACCOMPLICE",
            "OFFICER",
        ]

        for role in priority:

            if role not in roles:
                continue

            if role == "INFORMANT":
                return "COMPLAINANT"

            if role == "UNKNOWN_ACCOMPLICE":
                return "UNKNOWN"

            return role

        return (
            sorted(roles)[0]
            if roles
            else "OTHER"
        )

    # ============================================================
    # INCIDENT
    # ============================================================

    def _adapt_incident(
        self,
        extraction: DocumentExtraction,
        fir: ExtractedFIR,
    ) -> None:
        """
        Convert the primary Gemini incident into the existing
        ExtractedIncident compatibility model.
        """

        if not extraction.incidents:
            return

        incident = extraction.incidents[0]

        occurred_at = None

        if incident.dates:

            occurred_at = (
                incident.dates[0]
            )

            if incident.times:

                occurred_at = (
                    f"{occurred_at} "
                    f"{incident.times[0]}"
                )

        location = None

        if incident.locations:
            location = (
                incident.locations[0]
            )

        summary = (
            incident.description
            or incident.title
            or extraction.summary
        )

        fir.incident = ExtractedIncident(
            occurred_at=occurred_at,
            location=location,
            summary=summary,
            key_points=list(
                incident.key_points or []
            ),
            modus_operandi=list(
                incident.modus_operandi or []
            ),
            source_section=(
                "semantic_extraction"
            ),
        )

    # ============================================================
    # PROPERTY / EVIDENCE
    # ============================================================

    def _adapt_properties(
        self,
        extraction: DocumentExtraction,
        fir: ExtractedFIR,
    ) -> None:
        """
        Convert vehicles and evidence into the existing
        compatibility property model.

        The complete richer representation remains available
        in document_extractions.
        """

        # ------------------------------------------
        # Vehicles
        # ------------------------------------------

        for vehicle in extraction.vehicles:

            description = (
                vehicle.description
                or vehicle.vehicle_type
                or "Vehicle"
            )

            fir.properties.append(
                ExtractedProperty(
                    category="VEHICLE",
                    description=description,
                    registration_number=(
                        vehicle.registration_number
                    ),
                    source_section=(
                        "semantic_extraction"
                    ),
                )
            )

        # ------------------------------------------
        # Evidence
        # ------------------------------------------

        for evidence in (
            extraction.evidence_items
        ):

            if not evidence.evidence_type:
                continue

            description = (
                evidence.description
                or evidence.evidence_type
            )

            if evidence.value:

                description = (
                    f"{description} "
                    f"({evidence.value})"
                )

            fir.properties.append(
                ExtractedProperty(
                    category=(
                        evidence.evidence_type
                        .strip()
                        .upper()
                    ),
                    description=description,
                    estimated_value=None,
                    source_section=(
                        "semantic_extraction"
                    ),
                )
            )
