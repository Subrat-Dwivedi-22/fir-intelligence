from abc import ABC, abstractmethod

from app.services.llm.models import (
    DocumentExtraction,
    IncidentAnalysis,
)


class LLMService(ABC):

    @abstractmethod
    def extract_document(
        self,
        text: str,
    ) -> DocumentExtraction:
        """
        Extract structured facts from an arbitrary
        law-enforcement-related document.

        The document format is not assumed.
        """
        pass

    @abstractmethod
    def analyze_incident(
        self,
        narrative: str,
        known_persons: list[str],
    ) -> IncidentAnalysis:
        """
        Analyze an incident narrative.

        Kept for compatibility with existing
        investigation/analysis functionality.
        """
        pass
