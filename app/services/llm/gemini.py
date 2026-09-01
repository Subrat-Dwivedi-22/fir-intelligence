import json
import os

from google import genai

from app.services.llm.base import LLMService
from app.services.llm.models import (
    IncidentAnalysis,
)


class GeminiLLMService(LLMService):

    def __init__(
        self,
        model: str | None = None,
    ):
        self.model_id = model or os.getenv(
            "GEMINI_MODEL",
            "gemini-2.5-flash-lite",
        )

        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not configured"
            )

        self.client = genai.Client(
            api_key=api_key,
        )

    def analyze_incident(
        self,
        narrative: str,
        known_persons: list[str],
    ) -> IncidentAnalysis:

        persons = ", ".join(known_persons)

        prompt = f"""
Analyze the following police FIR narrative.

IMPORTANT:
This is reported/alleged information.
Do not treat allegations as proven facts.

Known persons:
{persons}

FIR narrative:
{narrative}

Return JSON with exactly these fields:

{{
  "summary": "string",
  "key_points": ["string"],
  "modus_operandi": ["string"],
  "relationships": [
    {{
        "subject": "string",
        "subject_type": "PERSON|UNKNOWN|INCIDENT|WEAPON|VEHICLE|LOCATION|ORGANIZATION|PROPERTY|PHONE|ACCOUNT|OTHER",
        "predicate": "string",
        "object": "string",
        "object_type": "PERSON|UNKNOWN|INCIDENT|WEAPON|VEHICLE|LOCATION|ORGANIZATION|PROPERTY|PHONE|ACCOUNT|OTHER",
        "evidence": "string"
    }}
  ]
}}

Rules:

- Use only information present in the FIR.
- Do not invent people, events, motives or relationships.
- Preserve uncertainty.
- Do not create person IDs.
- Use known names exactly when possible.
- Keep the summary concise.
- Key points must describe reported events.
- Modus operandi must describe reported actions.
- Relationships may connect people, objects, vehicles, locations,
  organizations, events, or other explicitly mentioned entities.
- Only create a relationship when it is directly supported by the narrative.
- Do not infer associations merely because two people are listed
  in the FIR.
- Do not infer ownership, friendship, gang membership, or conspiracy
  unless explicitly supported.
- Use concise predicates such as USED, THREATENED, INJURED,
  STOLE, OCCURRED_AT, TRAVELLED_IN, TARGETED.

- INCIDENT is a first-class graph type.
- Use INCIDENT when the subject or object refers to the incident/event itself,
  such as "the incident", "this incident", or "the reported incident".
- Do NOT classify an incident as OTHER.
- Do NOT create an ENTITY merely to represent the incident.
- PERSON, UNKNOWN, INCIDENT, and generic entity types must be distinguished
  according to what the relationship endpoint actually represents.

- Use INCIDENT when the subject or object refers to the incident itself,
  such as "incident", "the incident", or "this incident".
- Do not represent the incident itself as a generic OTHER entity.

Example of an incident relationship:

{{
  "subject": "incident",
  "subject_type": "INCIDENT",
  "predicate": "OCCURRED_AT",
  "object": "Vaibhav Restaurant",
  "object_type": "LOCATION",
  "evidence": "The incident occurred near Vaibhav Restaurant."
}}
"""

        response = self.client.models.generate_content(
            model=self.model_id,
            contents=prompt,
            config={
                "temperature": 0,
                "response_mime_type": "application/json",
            },
        )

        if not response.text:
            raise RuntimeError(
                "Gemini returned an empty response"
            )

        result = json.loads(response.text)

        return IncidentAnalysis.model_validate(
            result
        )