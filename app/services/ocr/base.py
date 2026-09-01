from abc import ABC, abstractmethod

from app.services.ocr.models import OCRDocument


class OCRService(ABC):

    @abstractmethod
    def process(self, pdf_path: str) -> OCRDocument:
        """Process a PDF and return structured OCR results."""
        raise NotImplementedError