from datetime import datetime, timezone

from app.db.mongodb import db
from app.models.incident import create_incident


class IncidentRepository:

    def create_from_extracted(
        self,
        case_id: str,
        document_id: str,
        extracted_incident,
        llm_analysis=None,
    ) -> dict:
        """
        Create and persist an incident.

        Deterministic extraction is authoritative for structured
        FIR facts such as occurrence time and location.

        LLM analysis provides semantic enrichment such as:
        summary, key points, and modus operandi.
        """

        incident = create_incident(
            case_id=case_id,
            title=extracted_incident.summary,
        )

        # ==================================================
        # DETERMINISTIC EXTRACTION
        # ==================================================

        incident["description"] = (
            extracted_incident.summary
        )

        incident["key_points"] = list(
            extracted_incident.key_points
        )

        incident["time"]["start"] = (
            extracted_incident.occurred_at
        )

        incident["location"]["text"] = (
            extracted_incident.location
        )

        incident["source"] = {
            "document_id": document_id,
            "pages": [],
        }

        incident["extraction"] = {
            "method": "DETERMINISTIC_EXTRACTION",
            "model": None,
            "confidence": None,
        }

        # ==================================================
        # LLM ENRICHMENT
        # ==================================================

        if llm_analysis is not None:

            # LLM summary is useful when deterministic
            # extraction did not produce one.
            if (
                not incident["description"]
                and llm_analysis.summary
            ):
                incident["description"] = (
                    llm_analysis.summary
                )

            # Same principle for title.
            if (
                not incident["title"]
                and llm_analysis.summary
            ):
                incident["title"] = (
                    llm_analysis.summary
                )

            # Preserve deterministic key points when
            # available. Otherwise use LLM enrichment.
            if (
                not incident["key_points"]
                and llm_analysis.key_points
            ):
                incident["key_points"] = list(
                    llm_analysis.key_points
                )

            # Modus operandi is semantic information
            # that does not currently exist in the
            # deterministic incident model.
            incident["modus_operandi"] = list(
                llm_analysis.modus_operandi
            )

            incident["llm_analysis"] = {
                "summary": llm_analysis.summary,
                "key_points": list(
                    llm_analysis.key_points
                ),
                "modus_operandi": list(
                    llm_analysis.modus_operandi
                ),
            }

        else:

            incident["modus_operandi"] = []

        # ==================================================
        # Persist incident
        # ==================================================

        now = datetime.now(timezone.utc)

        incident["updated_at"] = now

        db.incidents.insert_one(
            incident
        )

        # ==================================================
        # Link incident to case
        # ==================================================

        db.cases.update_one(
            {
                "case_id": case_id,
            },
            {
                "$addToSet": {
                    "incident_ids": incident[
                        "incident_id"
                    ],
                },
                "$set": {
                    "updated_at": now,
                },
            },
        )

        incident.pop("_id", None)

        return incident

    # ==================================================
    # GET
    # ==================================================

    def get_by_id(
        self,
        incident_id: str,
    ):
        return db.incidents.find_one(
            {
                "incident_id": incident_id,
            },
            {
                "_id": 0,
            },
        )

    def get_by_case(
        self,
        case_id: str,
    ):
        return list(
            db.incidents.find(
                {
                    "case_id": case_id,
                },
                {
                    "_id": 0,
                },
            ).sort(
                "created_at",
                1,
            )
        )
