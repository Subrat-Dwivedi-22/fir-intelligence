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
from app.services.extraction.parser import (
    parse_fir,
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
    Main FIR ingestion pipeline.

    Pipeline:

        S3
         ↓
        OCR
         ↓
        Segmentation
         ↓
        Deterministic extraction
         ↓
        Gemini analysis
         ↓
        Entity resolution
         ↓
        Case/person/unknown persistence
         ↓
        Incident persistence
         ↓
        Generic entity resolution
         ↓
        Relationship persistence
         ↓
        Completed job

    Important architectural boundaries:

    - OCR is responsible for document text.
    - deterministic extraction is responsible for structured FIR fields.
    - Gemini is responsible for semantic incident analysis.
    - PersonResolver is responsible for canonical person resolution.
    - UnknownIdentityService handles explicitly unidentified people.
    - Case linkers connect resolved entities to the case.
    - MongoDB serialization happens only at the persistence boundary.
    - EntityResolver manages generic canonical entities.
    - RelationshipResolver converts LLM relationship candidates
      into canonical graph endpoints.
    - RelationshipRepository persists graph relationships.
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

        self.incident_repository = (
            IncidentRepository()
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
        Process one FIR document.

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

            # Segmentation is part of the extraction
            # preparation stage. We do not create another
            # ingestion model just for this step.

            self._update_step(
            job_id,
                "segmentation",
                "PROCESSING",
            )

            ocr_text = (
                ocr_document.full_text
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
            # 3. DETERMINISTIC EXTRACTION
            # ==========================================

            self._update_step(
                job_id,
                "extraction",
                "PROCESSING",
            )

            section_map = {
                section.name: section.text
                for section in sections
            }

            extracted = parse_fir(
                section_map.get(
                    "header",
                    "",
                ),
                section_map,
            )

            self._store_extraction(
                job_id=job_id,
                case_id=case_id,
                document_id=document_id,
                extracted=extracted,
            )

            self._update_step(
                job_id,
                "extraction",
                "COMPLETED",
            )

            print(
                "✓ Deterministic extraction completed"
            )

            # ==========================================
            # 4. GEMINI ANALYSIS
            # ==========================================

            # Existing ingestion model calls this
            # LLM analysis
            # instead of inventing another step name.

            self._update_step(
                job_id,
                "llm_analysis",
                "PROCESSING",
            )

            narrative = (
                section_map.get(
                    "narrative",
                    "",
                )
            )

            known_persons = []

            # ------------------------------------------
            # Complainant
            # ------------------------------------------

            if extracted.complainant:

                known_persons.append(
                    extracted.complainant.name
                )

            # ------------------------------------------
            # Accused
            # ------------------------------------------

            known_persons.extend(
                person.name
                for person in extracted.accused
                if person.name
            )

            analysis = (
                self.llm_service.analyze_incident(
                    narrative=narrative,
                    known_persons=known_persons,
                )
            )

            self._store_llm_analysis(
                job_id=job_id,
                case_id=case_id,
                document_id=document_id,
                analysis=analysis,
            )

            self._update_step(
                job_id,
                "llm_analysis",
                "COMPLETED",
            )

            print(
                "✓ LLM analysis completed"
            )

            # ==========================================
            # 5. ENTITY RESOLUTION
            # ==========================================

            self._update_step(
                job_id,
                "entity_resolution",
                "PROCESSING",
            )

            resolved_people = []
            resolved_unknowns = []

            # ==========================================
            # 5A. COMPLAINANT
            # ==========================================

            if extracted.complainant:

                complainant_result = (
                    self.person_resolver.resolve(
                        extracted.complainant
                    )
                )

                resolved_people.append(
                    {
                        "person": (
                            extracted.complainant
                        ),
                        "role": "COMPLAINANT",
                        "result": (
                            complainant_result
                        ),
                    }
                )

                print(
                    f"✓ Complainant resolved: "
                    f"{extracted.complainant.name} "
                    f"→ "
                    f"{complainant_result['match_type']}"
                )

            # ==========================================
            # 5B. ACCUSED
            # ==========================================

            for accused in extracted.accused:

                # --------------------------------------
                # Explicitly unknown person
                # --------------------------------------

                if self._is_unknown_person(
                    accused.name
                ):

                    unknown = (
                        self.unknown_identity_service.create(
                            case_id=case_id,
                            label=accused.name,
                            document_id=document_id,
                            role="ACCUSED",
                            description=None,
                            source_section=(
                                accused.source_section
                            ),
                        )
                    )

                    resolved_unknowns.append(
                        {
                            "unknown": unknown,
                            "role": "ACCUSED",
                        }
                    )

                    print(
                        f"✓ Unknown identity created: "
                        f"{accused.name} "
                        f"→ "
                        f"{unknown['unknown_id']}"
                    )

                    continue

                # --------------------------------------
                # Known/provisional person
                # --------------------------------------

                accused_result = (
                    self.person_resolver.resolve(
                        accused
                    )
                )

                resolved_people.append(
                    {
                        "person": accused,
                        "role": "ACCUSED",
                        "result": accused_result,
                    }
                )

                print(
                    f"✓ Accused resolved: "
                    f"{accused.name} "
                    f"→ "
                    f"{accused_result['match_type']}"
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
                f"unknown identities"
            )

            # ==========================================
            # 6. DATABASE UPDATE
            # ==========================================

            self._update_step(
                job_id,
                "persistence",
                "PROCESSING",
            )

            # ==========================================
            # 6A. CASE ↔ PERSON
            # ==========================================

            for item in resolved_people:

                result = item["result"]

                match_type = (
                    result["match_type"]
                )

                # --------------------------------------
                # MATCHED
                #
                # Existing canonical person.
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
                        f"✓ Case linked to matched person: "
                        f"{item['person'].name} "
                        f"as {item['role']}"
                    )

                # --------------------------------------
                # NEW
                #
                # Resolver has already created the
                # provisional person.
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
                        f"✓ Case linked to new person: "
                        f"{item['person'].name} "
                        f"as {item['role']}"
                    )

                # --------------------------------------
                # CANDIDATE
                #
                # DO NOT automatically merge.
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
            # 6B. CASE ↔ UNKNOWN IDENTITY
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
                    f"✓ Case linked to unknown identity: "
                    f"{unknown['label']}"
                )

            # ==========================================
            # 6C. INCIDENT
            # ==========================================

            incident = (
                self.incident_repository
                .create_from_extracted(
                    case_id=case_id,
                    document_id=document_id,
                    extracted_incident=(
                        extracted.incident
                    ),
                    llm_analysis=analysis,
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
            # 6D. RELATIONSHIPS
            # ==========================================

            relationships_created = 0
            relationships_unresolved = 0

            for candidate in analysis.relationships:

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
                        confidence=None,
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
            # 7. JOB COMPLETED
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
    # UNKNOWN PERSON DETECTION
    # ==================================================

    @staticmethod
    def _is_unknown_person(
        name: str | None,
    ) -> bool:
        """
        Detect the deterministic labels generated by
        the extraction layer for unidentified people.

        Examples:

            UNKNOWN_PERSON_1
            UNKNOWN_PERSON_2
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
    # DETERMINISTIC EXTRACTION PERSISTENCE
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
    # LLM ANALYSIS PERSISTENCE
    # ==================================================

    def _store_llm_analysis(
        self,
        job_id,
        case_id,
        document_id,
        analysis,
    ):
        """
        Store Gemini's Pydantic result in MongoDB.

        Gemini currently returns:

            IncidentAnalysis
                ├── summary
                ├── key_points
                ├── modus_operandi
                └── relationships
                        └── RelationshipCandidate

        PyMongo cannot directly encode the nested
        Pydantic objects.

        Therefore serialization happens here, at the
        persistence boundary.
        """

        analysis = (
            self._serialize_for_mongo(
                analysis
            )
        )

        db.llm_analyses.update_one(
            {
                "job_id": job_id,
            },
            {
                "$set": {
                    "job_id": job_id,
                    "case_id": case_id,
                    "document_id": document_id,
                    "analysis": analysis,
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
    # MONGO SERIALIZATION
    # ==================================================

    @staticmethod
    def _serialize_for_mongo(
        value,
    ):
        """
        Convert application objects into MongoDB-safe
        Python structures.

        Currently handles:

            Pydantic BaseModel
            dict
            list
            tuple

        Pydantic model_dump() recursively converts nested
        Pydantic models such as RelationshipCandidate.

        We intentionally keep this logic at the persistence
        boundary instead of making LLM models MongoDB-aware.
        """

        # ----------------------------------------------
        # Pydantic model
        # ----------------------------------------------

        if isinstance(
            value,
            BaseModel,
        ):

            return (
                FIRPipeline._serialize_for_mongo(
                    value.model_dump()
                )
            )

        # ----------------------------------------------
        # Dictionary
        # ----------------------------------------------

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

        # ----------------------------------------------
        # List
        # ----------------------------------------------

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

        # ----------------------------------------------
        # Tuple
        # ----------------------------------------------

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

        # ----------------------------------------------
        # Primitive
        # ----------------------------------------------

        return value

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
    # TIME
    # ==================================================

    @staticmethod
    def _utc_now():

        return datetime.now(
            timezone.utc
        )