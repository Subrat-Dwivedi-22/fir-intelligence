import json
import os
from app.db.mongodb import db
from google import genai

from app.core.config import settings
from app.schemas.analysis import (
    InvestigationAnalysisResponse,
)


class InvestigationAnalysisService:

    def __init__(self):
        api_key = settings.gemini_api_key

        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not configured"
            )

        self.model_id = os.getenv(
            "GEMINI_MODEL",
            "gemini-3.5-flash-lite",
        )

        self.client = genai.Client(
            api_key=api_key,
        )

    def analyze(
        self,
        case_id: str,
        case_context: dict,
    ) -> InvestigationAnalysisResponse:

        prompt = f"""
You are an investigative intelligence assistant.

Analyze the supplied police case data.

IMPORTANT:
- Use ONLY the supplied case data.
- FIR allegations are allegations, not proven facts.
- Do not invent people, evidence, motives, relationships,
  events, or investigative findings.
- Clearly distinguish what is explicitly supported by the
  case from analytical recommendations.
- Recommendations are suggestions for investigators,
  not established facts.
- Do not accuse or identify a person beyond what the
  case data explicitly supports.
- If information is unavailable, say so rather than guessing.

CASE ID:
{case_id}

CASE DATA:
{case_context}

Return ONLY valid JSON matching this structure:

{{
  "summary": "concise case summary",
  "key_findings": [
    "finding supported by the case"
  ],
  "unresolved_identities": [
    "unresolved person or identity"
  ],
  "relationship_findings": [
    "important relationship supported by the case"
  ],
  "evidence_gaps": [
    "important missing evidence or information"
  ],
  "investigation_recommendations": [
    {{
      "priority": "HIGH|MEDIUM|LOW",
      "recommendation": "specific investigative action",
      "reason": "why this action is relevant",
      "evidence_basis": [
        "case fact supporting the recommendation"
      ]
    }}
  ]
}}

Focus on useful investigative intelligence.

Do not create recommendations merely to fill the list.
If there are no meaningful recommendations, return an empty list.
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

        try:
            result = json.loads(
                response.text
            )
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Gemini returned invalid JSON"
            ) from exc

        result["case_id"] = case_id

        analysis = InvestigationAnalysisResponse.model_validate(
            result
        )

        db.case_analyses.update_one(
            {
                "case_id": case_id,
            },
            {
                "$set": {
                    **analysis.model_dump(),
                }
            },
            upsert=True,
        )

        return analysis
