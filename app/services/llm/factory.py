import os

from dotenv import load_dotenv

from app.services.llm.gemini import GeminiLLMService


load_dotenv()


def get_llm_service():

    provider = os.getenv(
        "LLM_PROVIDER",
        "gemini",
    )

    print(f"LLM provider: {provider}")

    if provider == "gemini":
        return GeminiLLMService()

    raise ValueError(
        f"Unsupported LLM provider: {provider}"
    )