from abc import ABC, abstractmethod

from app.services.llm.models import IncidentAnalysis


class LLMService(ABC):

    @abstractmethod
    def analyze_incident(
        self,
        narrative: str,
        known_persons: list[str],
    ) -> IncidentAnalysis:
        pass