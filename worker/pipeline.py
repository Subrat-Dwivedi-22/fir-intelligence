from datetime import datetime, timezone

from pydantic import BaseModel

from app.db.mongodb import db

from app.repositories.document_repository import (
    DocumentRepository,
)

from app.repositories.section_repository import (
    SectionRepository,
)

from app.services.extraction.sections import (
    segment_fir,
)

from app.services.extraction.adapter import (
    DocumentExtractionAdapter,
)

from app.services.ocr.factory import (
    get_ocr_service,
)

from app.services.llm.factory import (
    get_llm_service,
)

from app.services.identity.resolver import (
    PersonResolver,
)

from app.services.identity.case_linker import (
    CasePersonLinker,
)

from app.services.identity.unknown import (
    UnknownIdentityService,
)

from app.services.identity.case_unknown_linker import (
    CaseUnknownIdentityLinker,
)

from app.storage.s3 import s3_storage

from app.repositories.incident_repository import (
    IncidentRepository,
)

from app.services.entity.resolver import (
    EntityResolver,
)

from app.services.relationship.resolver import (
    RelationshipResolver,
)

from app.repositories.relationship_repository import (
    RelationshipRepository,
)


class FIRPipeline:
    """
    Main FIR/document ingestion pipeline.

    Pipeline:

        S3
         ↓
        OCR
         ↓
        Segmentation
         ↓
        Gemini semantic document extraction
         ↓
        Extraction adapter
         ↓
        Entity resolution
         ↓
        Case/person/unknown persistence
         ↓
        Incident persistence
         ↓
        Generic entity resolution
         ↓
        Relationship resolution
         ↓
        Relationship persistence
         ↓
        Completed job

    Architectural boundaries:

    - OCR is responsible for document text.
    - Segmentation is retained for document structure/provenance,
      but is NOT authoritative for extraction.
    - Gemini is responsible for semantic document understanding.
    - DocumentExtractionAdapter translates Gemini output into
      existing application domain contracts.
    - PersonResolver is responsible for canonical person resolution.
    - UnknownIdentityService handles explicitly unidentified people.
    - Case linkers connect resolved entities to the case.
    - EntityResolver manages generic canonical entities.
    - RelationshipResolver converts semantic relationship candidates
      into canonical graph endpoints.
    - Repositories handle MongoDB persistence.
    - MongoDB serialization happens at the persistence boundary.

    Important:

    The worker deliberately re-raises processing exceptions so that
    the SQS consumer can preserve retry semantics.
    """

    def __init__(self):

        # ==========================================
        # Repositories
        # ==========================================

        self.document_repository = (
            DocumentRepository()
        )

        self.section_repository = (
            SectionRepository()
        )

        # ==========================================
        # Processing services
        # ==========================================

        self.ocr_service = (
            get_ocr_service()
        )

        self.llm_service = (
            get_llm_service()
        )

        self.extraction_adapter = (
            DocumentExtractionAdapter()
        )

        # ==========================================
        # Identity services
        # ==========================================

        self.person_resolver = (
            PersonResolver()
        )

        self.case_person_linker = (
            CasePersonLinker()
        )

        self.unknown_identity_service = (
            UnknownIdentityService()
        )

        self.case_unknown_linker = (
            CaseUnknownIdentityLinker()
        )

        # ==========================================
        # Incident / relationship services
        # ==========================================

        self.incident_repository = (
            IncidentRepository()
        )

        self.entity_resolver = (
            EntityResolver()
        )

        self.relationship_resolver = (
            RelationshipResolver()
        )

        self.relationship_repository = (
            RelationshipRepository()
        )

    # ==================================================
    # MAIN PIPELINE
    # ==================================================

    def process(
        self,
        job_id: str,
        case_id: str,
        document_id: str,
        s3_key: str,
    ):
        """
        Process one document.

        The worker calls this method once for an SQS job.

        Exceptions are deliberately re-raised so the worker can
        preserve SQS retry semantics.
        """

        print(
            f"Starting FIR pipeline: {job_id}"
        )

        self._update_job(
            job_id,
            status="PROCESSING",
        )

        try:

            # ==========================================
            # 1. OCR
            # ==========================================

            self._update_step(
                job_id,
                "ocr",
                "PROCESSING",
            )

            pdf_path = self._download_pdf(
                s3_key
            )

            ocr_document = (
                self.ocr_service.process(
                    pdf_path
                )
            )

            self._store_ocr(
                document_id=document_id,
                ocr_document=ocr_document,
            )

            self._update_step(
                job_id,
                "ocr",
                "COMPLETED",
            )

            print(
                f"✓ OCR completed: "
                f"{len(ocr_document.pages)} pages"
            )

            # ==========================================
            # 2. SEGMENTATION
            # ==========================================

            self._update_step(
                job_id,
                "segmentation",
                "PROCESSING",
            )

            ocr_text = (
                ocr_document.full_text
            )

            if not ocr_text or not ocr_text.strip():
                raise ValueError(
                    "OCR produced no usable text"
                )

            sections = segment_fir(
                ocr_text
            )

            self.section_repository.replace_sections(
                document_id=document_id,
                sections=sections,
            )

            self._update_step(
                job_id,
                "segmentation",
                "COMPLETED",
            )

            print(
                f"✓ Segmented into "
                f"{len(sections)} sections"
            )

            # ==========================================
            # 3. GEMINI DOCUMENT EXTRACTION
            # ==========================================

            self._update_step(
                job_id,
                "extraction",
                "PROCESSING",
            )

            # IMPORTANT:
            #
            # Gemini receives the complete OCR text.
            #
            # We deliberately do not feed only the
            # segmented sections because arbitrary
            # documents may not follow FIR structure.
            document_extraction = (
                self.llm_service.extract_document(
                    text=ocr_text
                )
            )

            # Convert Gemini's universal extraction model
            # into the existing domain models consumed by
            # identity and incident services.
            extracted = (
                self.extraction_adapter.adapt(
                    document_extraction
                )
            )

            # Preserve the compatibility extraction record.
            self._store_extraction(
                job_id=job_id,
                case_id=case_id,
                document_id=document_id,
                extracted=extracted,
            )

            # Store the complete semantic extraction.
            self._store_document_extraction(
                job_id=job_id,
                case_id=case_id,
                document_id=document_id,
                extraction=document_extraction,
            )

            self._update_step(
                job_id,
                "extraction",
                "COMPLETED",
            )

            print(
                "✓ Gemini document extraction completed"
            )

            print(
                f"  Document type: "
                f"{document_extraction.document_type}"
            )

            print(
                f"  Persons: "
                f"{len(document_extraction.persons)}"
            )

            print(
                f"  Organizations: "
                f"{len(document_extraction.organizations)}"
            )

            print(
                f"  Locations: "
                f"{len(document_extraction.locations)}"
            )

            print(
                f"  Vehicles: "
                f"{len(document_extraction.vehicles)}"
            )

            print(
                f"  Evidence items: "
                f"{len(document_extraction.evidence_items)}"
            )

            print(
                f"  Relationships: "
                f"{len(document_extraction.relationships)}"
            )

            # ==========================================
            # 4. ENTITY RESOLUTION
            # ==========================================

            self._update_step(
                job_id,
                "entity_resolution",
                "PROCESSING",
            )

            resolved_people = []
            resolved_unknowns = []

            # ==========================================
            # 4A. PEOPLE
            # ==========================================

            for person in (
                document_extraction.persons
            ):

                if (
                    not person.name
                    or not person.name.strip()
                ):
                    continue

                role = (
                    self._primary_person_role(
                        person.roles
                    )
                )

                compatibility_person = (
                    self.extraction_adapter
                    .person_to_domain(
                        person=person,
                        role=role,
                    )
                )

                # --------------------------------------
                # Unknown / unidentified person
                # --------------------------------------

                if (
                    self._is_unknown_extraction_person(
                        person
                    )
                ):

                    unknown = (
                        self.unknown_identity_service.create(
                            case_id=case_id,
                            label=person.name,
                            document_id=document_id,
                            role=role,
                            description=person.evidence,
                            source_section=(
                                "semantic_extraction"
                            ),
                        )
                    )

                    resolved_unknowns.append(
                        {
                            "unknown": unknown,
                            "role": role,
                        }
                    )

                    print(
                        f"✓ Unknown identity created: "
                        f"{person.name} → "
                        f"{unknown['unknown_id']}"
                    )

                    continue

                # --------------------------------------
                # Known / provisional person
                # --------------------------------------

                person_result = (
                    self.person_resolver.resolve(
                        compatibility_person
                    )
                )

                resolved_people.append(
                    {
                        "person": (
                            compatibility_person
                        ),
                        "role": role,
                        "result": person_result,
                    }
                )

                print(
                    f"✓ Person resolved: "
                    f"{person.name} → "
                    f"{person_result['match_type']} "
                    f"as {role}"
                )

            # ==========================================
            # 4B. GENERIC ENTITIES
            # ==========================================

            generic_entities = []

            # ------------------------------------------
            # Organizations
            # ------------------------------------------

            for organization in (
                document_extraction.organizations
            ):

                if (
                    not organization.name
                    or not organization.name.strip()
                ):
                    continue

                entity = (
                    self.entity_resolver.resolve(
                        entity_type="ORGANIZATION",
                        value=organization.name,
                        case_id=case_id,
                        document_id=document_id,
                    )
                )

                generic_entities.append(
                    entity
                )

                print(
                    f"✓ Organization resolved: "
                    f"{organization.name} → "
                    f"{entity['entity_id']}"
                )

            # ------------------------------------------
            # Locations
            # ------------------------------------------

            for location in (
                document_extraction.locations
            ):

                if (
                    not location.name
                    or not location.name.strip()
                ):
                    continue

                entity = (
                    self.entity_resolver.resolve(
                        entity_type="LOCATION",
                        value=location.name,
                        case_id=case_id,
                        document_id=document_id,
                    )
                )

                generic_entities.append(
                    entity
                )

                print(
                    f"✓ Location resolved: "
                    f"{location.name} → "
                    f"{entity['entity_id']}"
                )

            # ------------------------------------------
            # Vehicles
            # ------------------------------------------

            for vehicle in (
                document_extraction.vehicles
            ):

                value = (
                    vehicle.registration_number
                    or vehicle.description
                    or vehicle.vehicle_type
                )

                if (
                    not value
                    or not value.strip()
                ):
                    continue

                entity = (
                    self.entity_resolver.resolve(
                        entity_type="VEHICLE",
                        value=value,
                        case_id=case_id,
                        document_id=document_id,
                    )
                )

                generic_entities.append(
                    entity
                )

                print(
                    f"✓ Vehicle resolved: "
                    f"{value} → "
                    f"{entity['entity_id']}"
                )

            # ------------------------------------------
            # Phone numbers
            # ------------------------------------------

            phone_values = set(
                document_extraction.phone_numbers
            )

            for person in (
                document_extraction.persons
            ):
                phone_values.update(
                    person.phone_numbers
                )

            for phone in phone_values:

                if (
                    not phone
                    or not phone.strip()
                ):
                    continue

                entity = (
                    self.entity_resolver.resolve(
                        entity_type="PHONE",
                        value=phone,
                        case_id=case_id,
                        document_id=document_id,
                    )
                )

                generic_entities.append(
                    entity
                )

            self._update_step(
                job_id,
                "entity_resolution",
                "COMPLETED",
            )

            print(
                f"✓ Entity resolution completed: "
                f"{len(resolved_people)} persons, "
                f"{len(resolved_unknowns)} "
                f"unknown identities, "
                f"{len(generic_entities)} "
                f"generic entities"
            )

            # ==========================================
            # 5. DATABASE UPDATE
            # ==========================================

            self._update_step(
                job_id,
                "persistence",
                "PROCESSING",
            )

            # ==========================================
            # 5A. CASE ↔ PERSON
            # ==========================================

            for item in resolved_people:

                result = item["result"]

                match_type = (
                    result["match_type"]
                )

                # --------------------------------------
                # MATCHED
                # --------------------------------------

                if match_type == "MATCHED":

                    self.case_person_linker.link(
                        case_id=case_id,
                        person_id=(
                            result["person_id"]
                        ),
                        role=item["role"],
                        document_id=document_id,
                        confidence=(
                            result["confidence"]
                        ),
                    )

                    print(
                        f"✓ Case linked to matched "
                        f"person: "
                        f"{item['person'].name} "
                        f"as {item['role']}"
                    )

                # --------------------------------------
                # NEW
                # --------------------------------------

                elif match_type == "NEW":

                    self.case_person_linker.link(
                        case_id=case_id,
                        person_id=(
                            result["person_id"]
                        ),
                        role=item["role"],
                        document_id=document_id,
                        confidence=(
                            result["confidence"]
                        ),
                    )

                    print(
                        f"✓ Case linked to new "
                        f"person: "
                        f"{item['person'].name} "
                        f"as {item['role']}"
                    )

                # --------------------------------------
                # CANDIDATE
                # --------------------------------------

                elif match_type == "CANDIDATE":

                    print(
                        f"⚠ Identity candidate "
                        f"requires review: "
                        f"{item['person'].name}"
                    )

                    self._store_identity_candidate(
                        case_id=case_id,
                        document_id=document_id,
                        extracted_person=(
                            item["person"]
                        ),
                        result=result,
                    )

            # ==========================================
            # 5B. CASE ↔ UNKNOWN IDENTITY
            # ==========================================

            for item in resolved_unknowns:

                unknown = item["unknown"]

                self.case_unknown_linker.link(
                    case_id=case_id,
                    unknown_id=(
                        unknown["unknown_id"]
                    ),
                    role=item["role"],
                    document_id=document_id,
                    confidence=1.0,
                )

                print(
                    f"✓ Case linked to unknown "
                    f"identity: "
                    f"{unknown['label']}"
                )

            # ==========================================
            # 5C. INCIDENT
            # ==========================================

            incident = (
                self.incident_repository
                .create_from_extracted(
                    case_id=case_id,
                    document_id=document_id,
                    extracted_incident=(
                        extracted.incident
                    ),
                )
            )

            incident_id = (
                incident["incident_id"]
            )

            print(
                f"✓ Incident persisted: "
                f"{incident_id}"
            )

            # ==========================================
            # 5D. RELATIONSHIPS
            # ==========================================

            relationships_created = 0
            relationships_unresolved = 0

            for candidate in (
                document_extraction.relationships
            ):

                resolved_relationship = (
                    self.relationship_resolver
                    .resolve_candidate(
                        candidate=candidate,
                        resolved_people=(
                            resolved_people
                        ),
                        resolved_unknowns=(
                            resolved_unknowns
                        ),
                        case_id=case_id,
                        document_id=document_id,
                        incident_id=incident_id,
                    )
                )

                # --------------------------------------
                # Unresolved relationship
                # --------------------------------------

                if (
                    resolved_relationship["status"]
                    != "RESOLVED"
                ):

                    relationships_unresolved += 1

                    print(
                        f"⚠ Relationship unresolved: "
                        f"{candidate.subject} "
                        f"→ "
                        f"{candidate.predicate} "
                        f"→ "
                        f"{candidate.object}"
                    )

                    continue

                # --------------------------------------
                # Persist relationship
                # --------------------------------------

                relationship = (
                    self.relationship_repository
                    .create(
                        from_type=(
                            resolved_relationship[
                                "from"
                            ]["type"]
                        ),
                        from_id=(
                            resolved_relationship[
                                "from"
                            ]["id"]
                        ),
                        to_type=(
                            resolved_relationship[
                                "to"
                            ]["type"]
                        ),
                        to_id=(
                            resolved_relationship[
                                "to"
                            ]["id"]
                        ),
                        relationship_type=(
                            resolved_relationship[
                                "type"
                            ]
                        ),
                        case_id=case_id,
                        incident_id=incident_id,
                        document_id=document_id,
                        confidence=resolved_relationship["confidence"],
                        evidence=(
                            resolved_relationship[
                                "evidence"
                            ]
                        ),
                    )
                )

                relationships_created += 1

                print(
                    f"✓ Relationship persisted: "
                    f"{relationship['from']['type']}/"
                    f"{relationship['from']['id']} "
                    f"{relationship['type']} → "
                    f"{relationship['to']['type']}/"
                    f"{relationship['to']['id']}"
                )

            print(
                f"✓ Relationship processing completed: "
                f"{relationships_created} created, "
                f"{relationships_unresolved} unresolved"
            )

            # ==========================================
            # PERSISTENCE COMPLETE
            # ==========================================

            self._update_step(
                job_id,
                "persistence",
                "COMPLETED",
            )

            print(
                "✓ persistence completed"
            )

            # ==========================================
            # 6. JOB COMPLETED
            # ==========================================

            self._update_job(
                job_id,
                status="COMPLETED",
            )

            print(
                f"✓ FIR pipeline completed: "
                f"{job_id}"
            )

        except Exception as exc:

            print(
                f"✗ FIR pipeline failed: {exc}"
            )

            self._update_job(
                job_id,
                status="FAILED",
                error={
                    "code": "PROCESSING_ERROR",
                    "message": str(exc),
                },
            )

            # Very important:
            # let the worker receive the exception so
            # SQS retry semantics remain intact.

            raise

    # ==================================================
    # PERSON ROLE
    # ==================================================

    @staticmethod
    def _primary_person_role(
        roles: list[str] | None,
    ) -> str:
        """
        Convert Gemini's semantic roles into the
        primary role used by the existing case/person
        linking layer.
        """

        if not roles:
            return "OTHER"

        normalized = {
            role.strip().upper()
            for role in roles
            if role and role.strip()
        }

        # Keep this ordering deterministic.
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

            if role not in normalized:
                continue

            if role == "INFORMANT":
                return "COMPLAINANT"

            if role == "UNKNOWN_ACCOMPLICE":
                return "UNKNOWN"

            return role

        return sorted(normalized)[0]

    # ==================================================
    # SEMANTIC UNKNOWN DETECTION
    # ==================================================

    @staticmethod
    def _is_unknown_extraction_person(
        person,
    ) -> bool:
        """
        Detect people that Gemini explicitly identifies
        as unknown, unidentified, anonymous, or provisional.

        Examples:

            Agent Blue
            Unidentified Foreign Node
            Unknown Accomplice

        Unknown identities must NOT be sent to PersonResolver.
        """

        roles = {
            role.strip().upper()
            for role in (person.roles or [])
            if role and role.strip()
        }

        unknown_roles = {
            "UNKNOWN",
            "UNKNOWN_PERSON",
            "UNKNOWN_ACCOMPLICE",
            "UNIDENTIFIED",
            "ANONYMOUS",
        }

        if roles & unknown_roles:
            return True

        name = (
            person.name.strip().lower()
            if person.name
            else ""
        )

        unknown_markers = (
            "unknown",
            "unidentified",
            "anonymous",
        )

        return any(
            marker in name
            for marker in unknown_markers
        )

    # ==================================================
    # LEGACY UNKNOWN PERSON DETECTION
    # ==================================================

    @staticmethod
    def _is_unknown_person(
        name: str | None,
    ) -> bool:
        """
        Backward-compatible detection for legacy
        deterministic UNKNOWN_PERSON_N labels.
        """

        if not name:
            return True

        return name.startswith(
            "UNKNOWN_PERSON_"
        )

    # ==================================================
    # S3 / PDF
    # ==================================================

    def _download_pdf(
        self,
        s3_key: str,
    ) -> str:

        import tempfile

        with tempfile.NamedTemporaryFile(
            suffix=".pdf",
            delete=False,
        ) as temp:

            path = temp.name

        s3_storage.download_file(
            key=s3_key,
            file_path=path,
        )

        print(
            "✓ PDF downloaded from S3"
        )

        return path

    # ==================================================
    # OCR PERSISTENCE
    # ==================================================

    def _store_ocr(
        self,
        document_id,
        ocr_document,
    ):

        for page in ocr_document.pages:

            confidence = 0.0

            if page.words:

                confidence = (
                    sum(
                        word.confidence
                        for word in page.words
                    )
                    / len(page.words)
                )

            self.document_repository.store_ocr_page(
                document_id=document_id,
                page_number=page.page_number,
                text=page.text,
                provider="paddleocr",
                confidence=confidence,
                blocks=[
                    {
                        "text": word.text,
                        "confidence": (
                            word.confidence
                        ),
                        "bounding_box": (
                            word.bounding_box
                        ),
                    }
                    for word in page.words
                ],
            )

    # ==================================================
    # LEGACY EXTRACTION PERSISTENCE
    # ==================================================

    def _store_extraction(
        self,
        job_id,
        case_id,
        document_id,
        extracted,
    ):

        db.extractions.update_one(
            {
                "job_id": job_id,
            },
            {
                "$set": {
                    "job_id": job_id,
                    "case_id": case_id,
                    "document_id": document_id,

                    "fir_number": (
                        extracted.fir_number
                    ),

                    "police_station": (
                        extracted.police_station
                    ),

                    "district": (
                        extracted.district
                    ),

                    "registration_date": (
                        extracted.registration_date
                    ),

                    "registration_time": (
                        extracted.registration_time
                    ),

                    "occurrence_date": (
                        extracted.occurrence_date
                    ),

                    "occurrence_time": (
                        extracted.occurrence_time
                    ),

                    "gd_entry_number": (
                        extracted.gd_entry_number
                    ),

                    "legal_sections": (
                        extracted.legal_sections
                    ),

                    "complainant": (
                        self._person_to_dict(
                            extracted.complainant
                        )
                        if extracted.complainant
                        else None
                    ),

                    "accused": [
                        self._person_to_dict(
                            person
                        )
                        for person
                        in extracted.accused
                    ],

                    "properties": [
                        self._property_to_dict(
                            prop
                        )
                        for prop
                        in extracted.properties
                    ],

                    "incident": (
                        self._incident_to_dict(
                            extracted.incident
                        )
                    ),

                    "extraction_method": (
                        "GEMINI_DOCUMENT_EXTRACTION"
                    ),

                    "updated_at": (
                        self._utc_now()
                    ),
                },

                "$setOnInsert": {
                    "created_at": (
                        self._utc_now()
                    ),
                },
            },
            upsert=True,
        )

    # ==================================================
    # SEMANTIC EXTRACTION PERSISTENCE
    # ==================================================

    def _store_document_extraction(
        self,
        job_id,
        case_id,
        document_id,
        extraction,
    ):
        """
        Store Gemini's complete universal extraction.

        This is deliberately separate from the compatibility
        `extractions` collection.

        The semantic extraction preserves information that the
        legacy ExtractedFIR compatibility model cannot represent,
        including:

            organizations
            locations
            vehicles
            evidence
            relationships
            aliases
            provenance/evidence text
            document type
            summary
        """

        serialized = (
            self._serialize_for_mongo(
                extraction
            )
        )

        db.document_extractions.update_one(
            {
                "job_id": job_id,
            },
            {
                "$set": {
                    "job_id": job_id,
                    "case_id": case_id,
                    "document_id": document_id,
                    "document_type": (
                        extraction.document_type
                    ),
                    "extraction": serialized,
                    "model": self._llm_model_name(),
                    "method": (
                        "GEMINI_DOCUMENT_EXTRACTION"
                    ),
                    "updated_at": (
                        self._utc_now()
                    ),
                },

                "$setOnInsert": {
                    "created_at": (
                        self._utc_now()
                    ),
                },
            },
            upsert=True,
        )

    # ==================================================
    # LLM MODEL NAME
    # ==================================================

    @staticmethod
    def _llm_model_name() -> str:
        """
        Return the configured Gemini model name.

        The worker currently uses GEMINI_MODEL when supplied
        and otherwise the application's Gemini default.
        """

        import os

        return os.getenv(
            "GEMINI_MODEL",
            "gemini-3.5-flash-lite",
        )

    # ==================================================
    # IDENTITY CANDIDATES
    # ==================================================

    def _store_identity_candidate(
        self,
        case_id,
        document_id,
        extracted_person,
        result,
    ):
        """
        Store unresolved identity candidates for later
        investigator/manual review.

        A CANDIDATE is deliberately NOT linked to an
        existing canonical person.
        """

        db.identity_candidates.update_one(
            {
                "case_id": case_id,
                "document_id": document_id,
                "extracted_name": (
                    extracted_person.name
                ),
            },
            {
                "$set": {
                    "case_id": case_id,
                    "document_id": document_id,

                    "extracted_name": (
                        extracted_person.name
                    ),

                    "role": (
                        extracted_person.role
                    ),

                    "confidence": (
                        result["confidence"]
                    ),

                    "candidates": (
                        result.get(
                            "candidates",
                            [],
                        )
                    ),

                    "status": "PENDING_REVIEW",

                    "updated_at": (
                        self._utc_now()
                    ),
                },

                "$setOnInsert": {
                    "created_at": (
                        self._utc_now()
                    ),
                },
            },
            upsert=True,
        )

    # ==================================================
    # SERIALIZATION HELPERS
    # ==================================================

    @staticmethod
    def _person_to_dict(
        person,
    ):

        return {
            "name": person.name,

            "role": person.role,

            "father_name": (
                person.father_name
            ),

            "aliases": (
                person.aliases
            ),

            "date_of_birth": (
                person.date_of_birth
            ),

            "approximate_age": (
                person.approximate_age
            ),

            "phone_numbers": (
                person.phone_numbers
            ),

            "addresses": (
                person.addresses
            ),

            "occupation": (
                person.occupation
            ),

            "source_section": (
                person.source_section
            ),
        }

    @staticmethod
    def _property_to_dict(
        prop,
    ):

        return {
            "category": (
                prop.category
            ),

            "description": (
                prop.description
            ),

            "registration_number": (
                prop.registration_number
            ),

            "estimated_value": (
                prop.estimated_value
            ),

            "source_section": (
                prop.source_section
            ),
        }

    @staticmethod
    def _incident_to_dict(
        incident,
    ):

        return {
            "occurred_at": (
                incident.occurred_at
            ),

            "location": (
                incident.location
            ),

            "summary": (
                incident.summary
            ),

            "key_points": (
                incident.key_points
            ),

            "modus_operandi": (
                incident.modus_operandi
            ),

            "source_section": (
                incident.source_section
            ),
        }

    # ==================================================
    # JOB STATUS
    # ==================================================

    def _update_job(
        self,
        job_id: str,
        status: str,
        error=None,
    ):

        update = {
            "status": status,
            "updated_at": (
                self._utc_now()
            ),
        }

        if error is not None:
            update["error"] = error

        if status == "COMPLETED":

            update["completed_at"] = (
                self._utc_now()
            )

            update["error"] = None

        if status == "PROCESSING":

            update["error"] = None

        db.ingestion_jobs.update_one(
            {
                "job_id": job_id,
            },
            {
                "$set": update
            },
        )

    # ==================================================
    # STEP STATUS
    # ==================================================

    def _update_step(
        self,
        job_id: str,
        step: str,
        status: str,
    ):

        db.ingestion_jobs.update_one(
            {
                "job_id": job_id,
            },
            {
                "$set": {
                    f"steps.{step}": status,
                    "updated_at": (
                        self._utc_now()
                    ),
                }
            },
        )

    # ==================================================
    # MONGO SERIALIZATION
    # ==================================================

    @staticmethod
    def _serialize_for_mongo(
        value,
    ):
        """
        Convert application objects into MongoDB-safe
        Python structures.

        Handles:

            Pydantic BaseModel
            dict
            list
            tuple
        """

        if isinstance(
            value,
            BaseModel,
        ):

            return (
                FIRPipeline._serialize_for_mongo(
                    value.model_dump()
                )
            )

        if isinstance(
            value,
            dict,
        ):

            return {
                key: (
                    FIRPipeline._serialize_for_mongo(
                        item
                    )
                )
                for key, item in value.items()
            }

        if isinstance(
            value,
            list,
        ):

            return [
                FIRPipeline._serialize_for_mongo(
                    item
                )
                for item in value
            ]

        if isinstance(
            value,
            tuple,
        ):

            return [
                FIRPipeline._serialize_for_mongo(
                    item
                )
                for item in value
            ]

        return value

    # ==================================================
    # TIME
    # ==================================================

    @staticmethod
    def _utc_now():

        return datetime.now(
            timezone.utc
        )
