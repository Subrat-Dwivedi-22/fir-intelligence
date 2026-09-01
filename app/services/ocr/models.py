from dataclasses import dataclass, field


@dataclass
class OCRWord:
    text: str
    confidence: float
    bounding_box: list[list[float]]


@dataclass
class OCRPage:
    page_number: int
    text: str
    words: list[OCRWord] = field(default_factory=list)


@dataclass
class OCRDocument:
    pages: list[OCRPage] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n\n".join(
            page.text
            for page in self.pages
        )