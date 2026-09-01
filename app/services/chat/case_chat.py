import os

from google import genai

from app.core.config import settings


class CaseChatService:

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

    def answer(
        self,
        question: str,
        case_context: dict,
        chat_history: list[dict],
    ) -> str:
        
        history_text = "\n".join(
            f"{message['role'].upper()}: {message['content']}"
            for message in chat_history[-10:]
        )

        prompt = f"""
You are an investigative intelligence assistant.

You are answering questions about ONE police case.

IMPORTANT:
- Use only the supplied case data.
- Do not invent facts, people, evidence,
  relationships, motives, or events.
- Treat allegations in the FIR as allegations,
  not proven facts.
- Clearly distinguish facts from inference.
- If the case data does not contain enough information,
  say so.
- Recommendations must be clearly labeled as recommendations.
- Do not claim that a recommendation is established evidence.
- Conversation history is context for understanding follow-up questions.
- Case data remains the authoritative source of facts.
- Do not treat previous AI answers as evidence.

CASE DATA:
{case_context}

CONVERSATION HISTORY:
{history_text}

USER QUESTION:
{question}

Answer concisely and clearly.

When appropriate use:

FACTS:
...

INFERENCE:
...

RECOMMENDATION:
...
"""

        response = self.client.models.generate_content(
            model=self.model_id,
            contents=prompt,
            config={
                "temperature": 0,
            },
        )

        if not response.text:
            raise RuntimeError(
                "Gemini returned an empty response"
            )

        return response.text
