from datetime import datetime, timezone

from app.db.mongodb import db
from app.models.person import create_person_document
from app.services.extraction.models import ExtractedPerson
from app.services.person_identity import generate_person_id

from .normalizer import normalize_name, normalize_phone


class PersonResolver:
    """
    Resolves an ExtractedPerson into the canonical
    person representation used by the intelligence system.

    Resolution policy:

        Exact phone
            -> automatic MATCHED

        Name + father name + DOB
            -> automatic MATCHED

        Name + father name + address
            -> CANDIDATE

        Name only
            -> CANDIDATE

        No existing candidate
            -> NEW provisional person

    Unknown persons such as UNKNOWN_PERSON_1 are NOT
    handled here. They belong to UnknownIdentity.
    """

    # ==================================================
    # PUBLIC API
    # ==================================================

    def resolve(
        self,
        person: ExtractedPerson,
    ) -> dict:
        """
        Resolve an extracted person.

        Returns:

            MATCHED
            {
                "person_id": "...",
                "match_type": "MATCHED",
                "match_method": "...",
                "confidence": 0.95,
                "created": False,
            }

            CANDIDATE
            {
                "match_type": "CANDIDATE",
                "confidence": 0.85,
                "candidates": [...],
                "created": False,
            }

            NEW
            {
                "person_id": "...",
                "match_type": "NEW",
                "confidence": 0.0,
                "created": True,
            }
        """

        # --------------------------------------------------
        # Unknown identities are handled by
        # UnknownIdentityService, not PersonResolver.
        # --------------------------------------------------

        if self._is_unknown_person(person):
            raise ValueError(
                "Unknown identities must be handled "
                "by UnknownIdentityService"
            )

        # ==================================================
        # 1. EXACT PHONE MATCH
        # ==================================================

        for phone in person.phone_numbers:

            normalized_phone = normalize_phone(
                phone
            )

            if not normalized_phone:
                continue

            existing = self._find_by_phone(
                normalized_phone
            )

            if existing:

                return {
                    "person_id": existing[
                        "person_id"
                    ],
                    "match_type": "MATCHED",
                    "match_method": "PHONE",
                    "confidence": 0.95,
                    "created": False,
                }

        # ==================================================
        # 2. NAME CANDIDATES
        # ==================================================

        normalized_name = normalize_name(
            person.name
        )

        if normalized_name:

            candidates = self._find_by_name(
                normalized_name
            )

            if candidates:

                scored_candidates = (
                    self._score_candidates(
                        person,
                        candidates,
                    )
                )

                if scored_candidates:

                    best = scored_candidates[0]

                    # --------------------------------------
                    # Strong demographic match
                    #
                    # Name + father + DOB
                    # --------------------------------------

                    if (
                        best["has_father_match"]
                        and best["has_dob_match"]
                        and best["confidence"] >= 0.90
                    ):

                        return {
                            "person_id": best[
                                "person_id"
                            ],
                            "match_type": "MATCHED",
                            "match_method": (
                                "DEMOGRAPHIC"
                            ),
                            "confidence": best[
                                "confidence"
                            ],
                            "created": False,
                        }

                    # --------------------------------------
                    # Possible match
                    #
                    # Do NOT automatically merge.
                    # --------------------------------------

                    return {
                        "match_type": "CANDIDATE",
                        "confidence": best[
                            "confidence"
                        ],
                        "candidates": (
                            scored_candidates
                        ),
                        "created": False,
                    }

        # ==================================================
        # 3. NO MATCH
        # ==================================================

        new_person = self._create_person(
            person
        )

        return {
            "person_id": new_person[
                "person_id"
            ],
            "match_type": "NEW",
            "match_method": None,
            "confidence": 0.0,
            "created": True,
        }

    # ==================================================
    # UNKNOWN DETECTION
    # ==================================================

    @staticmethod
    def _is_unknown_person(
        person: ExtractedPerson,
    ) -> bool:

        if not person.name:
            return True

        return person.name.startswith(
            "UNKNOWN_PERSON_"
        )

    # ==================================================
    # PHONE LOOKUP
    # ==================================================

    def _find_by_phone(
        self,
        phone: str,
    ):

        return db.persons.find_one(
            {
                "contact.phones": phone
            }
        )

    # ==================================================
    # NAME LOOKUP
    # ==================================================

    def _find_by_name(
        self,
        normalized_name: str,
    ) -> list[dict]:

        return list(
            db.persons.find(
                {
                    "identity.normalized_name":
                        normalized_name
                },
                {
                    "_id": 0,
                    "person_id": 1,
                    "identity": 1,
                    "contact": 1,
                    "addresses": 1,
                },
            ).limit(20)
        )

    # ==================================================
    # CANDIDATE SCORING
    # ==================================================

    def _score_candidates(
        self,
        extracted: ExtractedPerson,
        candidates: list[dict],
    ) -> list[dict]:
        """
        Score possible existing persons.

        Base score:

            Name       = 0.50
            Father     = 0.25
            DOB        = 0.15
            Address    = 0.10

        Important:

        Even a score of 1.00 is not sufficient by itself
        unless the strong identity rule is satisfied.

        Automatic demographic resolution requires:

            father name match
            AND
            DOB match
            AND
            score >= 0.90
        """

        results = []

        extracted_father = normalize_name(
            extracted.father_name
        )

        extracted_dob = (
            extracted.date_of_birth
        )

        extracted_addresses = {
            self._normalize_address(address)
            for address in extracted.addresses
            if address
        }

        for candidate in candidates:

            identity = candidate.get(
                "identity",
                {}
            )

            # ==================================================
            # Base name match
            # ==================================================

            score = 0.50

            # ==================================================
            # Father name
            # ==================================================

            candidate_father = normalize_name(
                identity.get("father_name")
            )

            has_father_match = (
                bool(extracted_father)
                and bool(candidate_father)
                and extracted_father
                == candidate_father
            )

            if has_father_match:
                score += 0.25

            # ==================================================
            # DOB
            # ==================================================

            candidate_dob = identity.get(
                "date_of_birth"
            )

            has_dob_match = (
                bool(extracted_dob)
                and bool(candidate_dob)
                and extracted_dob
                == candidate_dob
            )

            if has_dob_match:
                score += 0.15

            # ==================================================
            # Address
            # ==================================================

            candidate_addresses = set()

            for address in candidate.get(
                "addresses",
                [],
            ):

                if isinstance(
                    address,
                    dict,
                ):

                    text = address.get(
                        "text",
                        ""
                    )

                else:

                    text = str(address)

                normalized_address = (
                    self._normalize_address(
                        text
                    )
                )

                if normalized_address:
                    candidate_addresses.add(
                        normalized_address
                    )

            has_address_match = (
                bool(extracted_addresses)
                and bool(candidate_addresses)
                and bool(
                    extracted_addresses
                    & candidate_addresses
                )
            )

            if has_address_match:
                score += 0.10

            # ==================================================
            # Result
            # ==================================================

            candidate_name = identity.get(
                "name"
            )

            results.append(
                {
                    "person_id": candidate[
                        "person_id"
                    ],

                    "name": candidate_name,

                    "confidence": round(
                        score,
                        2,
                    ),

                    "has_father_match": (
                        has_father_match
                    ),

                    "has_dob_match": (
                        has_dob_match
                    ),

                    "has_address_match": (
                        has_address_match
                    ),
                }
            )

        return sorted(
            results,
            key=lambda item: item[
                "confidence"
            ],
            reverse=True,
        )

    # ==================================================
    # CREATE PERSON
    # ==================================================

    def _create_person(
        self,
        extracted: ExtractedPerson,
    ) -> dict:
        """
        Create a canonical provisional person using
        the existing Person domain model.
        """

        person_id = generate_person_id()

        document = create_person_document(
            person_id=person_id,
            name=extracted.name,
        )

        # ==================================================
        # Identity
        # ==================================================

        document["identity"][
            "normalized_name"
        ] = normalize_name(
            extracted.name
        )

        document["identity"][
            "aliases"
        ] = list(
            extracted.aliases
        )

        document["identity"][
            "father_name"
        ] = extracted.father_name

        document["identity"][
            "date_of_birth"
        ] = extracted.date_of_birth

        document["identity"][
            "approximate_age"
        ] = extracted.approximate_age

        # ==================================================
        # Contact
        # ==================================================

        normalized_phones = []

        for phone in extracted.phone_numbers:

            normalized_phone = normalize_phone(
                phone
            )

            if (
                normalized_phone
                and normalized_phone
                not in normalized_phones
            ):
                normalized_phones.append(
                    normalized_phone
                )

        document["contact"][
            "phones"
        ] = normalized_phones

        # ==================================================
        # Addresses
        # ==================================================

        document["addresses"] = []

        for address in extracted.addresses:

            if not address:
                continue

            document["addresses"].append(
                {
                    "text": address,
                    "normalized": (
                        self._normalize_address(
                            address
                        )
                    ),
                }
            )

        # ==================================================
        # Identity resolution metadata
        # ==================================================

        document[
            "identity_resolution"
        ] = {
            "status": "PROVISIONAL",
            "method": "INITIAL_EXTRACTION",
            "confidence": 0.0,
        }

        # ==================================================
        # Persist
        # ==================================================

        db.persons.insert_one(
            document
        )

        return document

    # ==================================================
    # ADDRESS NORMALIZATION
    # ==================================================

    @staticmethod
    def _normalize_address(
        address: str | None,
    ) -> str:

        if not address:
            return ""

        return " ".join(
            address.lower().split()
        )