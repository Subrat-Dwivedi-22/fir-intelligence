from datetime import datetime, timezone

from app.db.mongodb import db
from app.repositories.incident_repository import IncidentRepository


class TimelineService:
    def __init__(self):
        self.incident_repository = IncidentRepository()

    def _parse_timestamp(self, value):
        if value is None:
            return None

        if isinstance(value, datetime):
            return value

        if not isinstance(value, str):
            return None

        value = value.strip()

        formats = [
            "%d %B %Y %H:%M hrs",
            "%d %B %Y %H:%M",
            "%d %B %Y %I:%M %p",
            "%d %B %Y",
            "%d-%m-%Y %H:%M",
            "%d-%m-%Y",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(value, fmt)
                return parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

        return None

    def _entity_labels_for_incident(self, incident_id: str) -> list[str]:
        relationships = db.relationships.find(
            {"context.incident_id": incident_id},
            {"_id": 0, "from": 1, "to": 1},
        )

        labels = []

        for relationship in relationships:
            for endpoint in (
                relationship.get("from"),
                relationship.get("to"),
            ):
                if not endpoint:
                    continue

                entity_type = endpoint.get("type")
                entity_id = endpoint.get("id")

                if not entity_id:
                    continue

                label = None

                if entity_type == "PERSON":
                    person = db.persons.find_one(
                        {"person_id": entity_id},
                        {"_id": 0, "identity.name": 1},
                    )

                    if person:
                        label = person.get("identity", {}).get("name")

                elif entity_type == "UNKNOWN":
                    unknown = db.unknown_identities.find_one(
                        {"unknown_id": entity_id},
                        {"_id": 0, "label": 1},
                    )

                    if unknown:
                        label = unknown.get("label")

                else:
                    entity = db.entities.find_one(
                        {"entity_id": entity_id},
                        {"_id": 0, "value": 1, "type": 1},
                    )

                    if entity:
                        label = entity.get("value") or entity.get("type")

                if label and label not in labels:
                    labels.append(label)

        return labels

    def get_by_case(self, case_id: str) -> list[dict]:
        incidents = self.incident_repository.get_by_case(case_id)

        events = []

        for incident in incidents:
            raw_timestamp = incident.get("time", {}).get("start")

            timestamp = self._parse_timestamp(raw_timestamp)

            if timestamp is None:
                timestamp = self._parse_timestamp(
                    incident.get("created_at")
                )

            events.append(
                {
                    "timestamp": timestamp,
                    "title": incident.get("title") or "Incident",
                    "description": incident.get("description") or "",
                    "key_points": incident.get("key_points") or [],
                    "entities_involved": self._entity_labels_for_incident(
                        incident["incident_id"]
                    ),
                }
            )

        events.sort(
            key=lambda event: (
                event["timestamp"] is None,
                event["timestamp"] or datetime.max.replace(
                    tzinfo=timezone.utc
                ),
            )
        )

        return events